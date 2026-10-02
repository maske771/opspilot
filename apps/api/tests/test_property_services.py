import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.models import Organization, Property, Service, TicketPriority, User, UserRole
from app.organization_routes import SlaPair
from app.property_service_routes import (
    PropertyServiceEntry,
    PropertyServicesUpdate,
    get_property_services,
    update_property_services,
)
from app.services import ensure_services
from app.tickets import TicketCreate, TicketUpdate, create_ticket, update_ticket


def setup(db_session, org_sla=None):
    org = Organization(name="Org", sla_overrides=org_sla)
    db_session.add(org)
    db_session.flush()
    owner = User(organization_id=org.id, email=f"owner-{uuid.uuid4().hex[:6]}@example.com", password_hash="h", role=UserRole.OWNER)
    prop = Property(organization_id=org.id, name="Sunset Tower")
    db_session.add_all([owner, prop])
    db_session.commit()
    ensure_services(db_session, org.id)
    services = {s.code: s for s in db_session.scalars(select(Service).where(Service.organization_id == org.id))}
    return org, owner, prop, services


def minutes(ticket):
    return (
        round((ticket.response_deadline - ticket.created_at).total_seconds() / 60),
        round((ticket.resolution_deadline - ticket.created_at).total_seconds() / 60),
    )


# ---- reading / configuring


def test_an_unconfigured_property_offers_every_service_with_inherited_sla(db_session):
    org, owner, prop, _ = setup(db_session, org_sla={"high": {"response_minutes": 20, "resolution_minutes": 200}})

    result = get_property_services(prop.id, user=owner, db=db_session)

    assert result.configured is False
    assert all(s.enabled for s in result.services)
    plumbing = next(s for s in result.services if s.code == "plumbing")
    by_priority = {row.priority: row for row in plumbing.sla}
    assert (by_priority[TicketPriority.HIGH].response_minutes, by_priority[TicketPriority.HIGH].source) == (20, "organization")
    assert (by_priority[TicketPriority.CRITICAL].response_minutes, by_priority[TicketPriority.CRITICAL].source) == (15, "default")


def test_configuring_a_subset_with_a_property_sla(db_session):
    org, owner, prop, services = setup(db_session)

    result = update_property_services(
        prop.id,
        PropertyServicesUpdate(
            services=[
                PropertyServiceEntry(service_id=services["plumbing"].id, sla={TicketPriority.HIGH: SlaPair(response_minutes=10, resolution_minutes=90)}),
                PropertyServiceEntry(service_id=services["other"].id),
            ]
        ),
        user=owner,
        db=db_session,
    )

    assert result.configured is True
    enabled = {s.code for s in result.services if s.enabled}
    assert enabled == {"plumbing", "other"}
    plumbing = next(s for s in result.services if s.code == "plumbing")
    high = next(r for r in plumbing.sla if r.priority == TicketPriority.HIGH)
    assert (high.response_minutes, high.resolution_minutes, high.source) == (10, 90, "property")
    assert plumbing.overrides[TicketPriority.HIGH].response_minutes == 10


def test_an_empty_list_resets_to_unconfigured(db_session):
    org, owner, prop, services = setup(db_session)
    update_property_services(prop.id, PropertyServicesUpdate(services=[PropertyServiceEntry(service_id=services["plumbing"].id)]), user=owner, db=db_session)

    result = update_property_services(prop.id, PropertyServicesUpdate(services=[]), user=owner, db=db_session)

    assert result.configured is False
    assert all(s.enabled for s in result.services)


def test_only_owner_and_admin_can_configure(db_session):
    org, owner, prop, _ = setup(db_session)
    manager = User(organization_id=org.id, email="m@example.com", password_hash="h", role=UserRole.MANAGER)
    db_session.add(manager)
    db_session.commit()

    with pytest.raises(HTTPException) as exc:
        get_property_services(prop.id, user=manager, db=db_session)
    assert exc.value.status_code == 403


def test_services_from_another_org_or_archived_are_rejected(db_session):
    org, owner, prop, services = setup(db_session)
    _, _, _, foreign = setup(db_session)
    services["access"].archived = True
    db_session.commit()

    for service_id in (foreign["plumbing"].id, services["access"].id):
        with pytest.raises(HTTPException) as exc:
            update_property_services(prop.id, PropertyServicesUpdate(services=[PropertyServiceEntry(service_id=service_id)]), user=owner, db=db_session)
        assert exc.value.status_code == 400


def test_a_property_from_another_org_is_not_found(db_session):
    _, owner, _, _ = setup(db_session)
    _, _, foreign_prop, _ = setup(db_session)

    with pytest.raises(HTTPException) as exc:
        get_property_services(foreign_prop.id, user=owner, db=db_session)
    assert exc.value.status_code == 404


# ---- tickets use the chain property+service → organization → default


def test_ticket_deadlines_follow_the_property_service_sla(db_session):
    org, owner, prop, services = setup(db_session, org_sla={"high": {"response_minutes": 20, "resolution_minutes": 200}})
    other_prop = Property(organization_id=org.id, name="Riverside")
    db_session.add(other_prop)
    db_session.commit()
    update_property_services(
        prop.id,
        PropertyServicesUpdate(services=[PropertyServiceEntry(service_id=services["plumbing"].id, sla={TicketPriority.HIGH: SlaPair(response_minutes=5, resolution_minutes=60)})]),
        user=owner,
        db=db_session,
    )

    def make(property_id, category="plumbing"):
        return create_ticket(
            TicketCreate(organization_id=org.id, title="Leak", description="x", category=category, priority=TicketPriority.HIGH, property_id=property_id),
            user=owner,
            db=db_session,
        )

    assert minutes(make(prop.id)) == (5, 60)  # property + service override
    assert minutes(make(prop.id, category="electrical")) == (20, 200)  # same property, other service → organization
    assert minutes(make(other_prop.id)) == (20, 200)  # other property → organization
    assert minutes(make(None)) == (20, 200)  # no property → organization


def test_changing_category_or_priority_recomputes_the_deadlines(db_session):
    org, owner, prop, services = setup(db_session)
    update_property_services(
        prop.id,
        PropertyServicesUpdate(
            services=[
                PropertyServiceEntry(service_id=services["plumbing"].id, sla={TicketPriority.HIGH: SlaPair(response_minutes=5, resolution_minutes=60)}),
                PropertyServiceEntry(service_id=services["electrical"].id, sla={TicketPriority.HIGH: SlaPair(response_minutes=7, resolution_minutes=70)}),
            ]
        ),
        user=owner,
        db=db_session,
    )
    ticket = create_ticket(
        TicketCreate(organization_id=org.id, title="t", description="x", category="plumbing", priority=TicketPriority.HIGH, property_id=prop.id),
        user=owner,
        db=db_session,
    )
    assert minutes(ticket) == (5, 60)

    assert minutes(update_ticket(ticket.id, TicketUpdate(category="electrical"), user=owner, db=db_session)) == (7, 70)
    assert minutes(update_ticket(ticket.id, TicketUpdate(priority=TicketPriority.LOW), user=owner, db=db_session)) == (480, 4320)
