import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.models import Channel, Organization, Service, Ticket, TicketPriority, User, UserRole
from app.service_routes import ServiceCreate, ServiceUpdate, archive_service, create_service, list_services, update_service
from app.services import ensure_services, intake_rules
from app.user_routes import UserSpecialtiesUpdate, update_user_specialties
from app.webhook_service import NormalizedEvent, ingest_normalized_event


def make_org(db_session):
    org = Organization(name="Org")
    db_session.add(org)
    db_session.flush()
    return org


def make_user(db_session, org, role=UserRole.OWNER, specialties=None):
    user = User(organization_id=org.id, email=f"{role.value}-{uuid.uuid4().hex[:6]}@example.com", password_hash="h", role=role, specialties=specialties or [])
    db_session.add(user)
    db_session.commit()
    return user


def services_by_code(db_session, org):
    return {s.code: s for s in db_session.scalars(select(Service).where(Service.organization_id == org.id))}


def ingest(db_session, org, text, conversation="1"):
    channel = db_session.scalar(select(Channel).where(Channel.organization_id == org.id))
    if channel is None:
        channel = Channel(organization_id=org.id, type="telegram", account_id="bot-" + uuid.uuid4().hex[:6], name="Bot", status="connected")
        db_session.add(channel)
        db_session.flush()
    event = NormalizedEvent(external_conversation_id=conversation, external_user_id=conversation, external_message_id=uuid.uuid4().hex, text=text)
    data, _, ticket_created = ingest_normalized_event(db_session, org.id, {"type": channel.type, "id": channel.id}, event)
    return data, ticket_created


# ---- seeding


def test_default_catalog_is_seeded_once_with_a_system_fallback(db_session):
    org = make_org(db_session)
    ensure_services(db_session, org.id)
    ensure_services(db_session, org.id)

    services = services_by_code(db_session, org)

    assert set(services) == {"emergency", "plumbing", "electrical", "hvac", "appliance", "access", "other"}
    assert services["other"].is_system is True
    assert services["emergency"].default_priority == TicketPriority.CRITICAL
    assert services["plumbing"].names["ru"] == "Сантехника"


def test_intake_rules_exclude_the_fallback_and_carry_its_priority(db_session):
    org = make_org(db_session)
    ensure_services(db_session, org.id)
    services_by_code(db_session, org)["other"].default_priority = TicketPriority.LOW
    db_session.flush()

    rules, fallback_priority = intake_rules(db_session, org.id)

    assert "other" not in {r.code for r in rules}
    assert fallback_priority == TicketPriority.LOW


# ---- classification comes from the catalog


def test_a_custom_service_keyword_routes_a_new_ticket(db_session):
    org = make_org(db_session)
    owner = make_user(db_session, org)
    created = create_service(ServiceCreate(names={"ru": "Бассейн"}, keywords=["бассейн"], default_priority=TicketPriority.LOW), user=owner, db=db_session)

    data, ticket_created = ingest(db_session, org, "в бассейне грязная вода")

    assert ticket_created is True
    ticket = db_session.get(Ticket, data["ticket_id"])
    # "вода" also matches plumbing (HIGH); the more severe service wins when two match.
    assert ticket.category == "plumbing"

    data, _ = ingest(db_session, org, "почистите бассейн пожалуйста", conversation="2")
    ticket = db_session.get(Ticket, data["ticket_id"])
    assert ticket.category == created.code
    assert ticket.priority == TicketPriority.LOW


def test_editing_keywords_changes_classification(db_session):
    org = make_org(db_session)
    owner = make_user(db_session, org)
    ensure_services(db_session, org.id)
    hvac = services_by_code(db_session, org)["hvac"]
    update_service(hvac.id, ServiceUpdate(keywords=["кондей"]), user=owner, db=db_session)

    data, _ = ingest(db_session, org, "кондей шумит")

    assert db_session.get(Ticket, data["ticket_id"]).category == "hvac"


def test_archived_services_are_not_matched(db_session):
    org = make_org(db_session)
    owner = make_user(db_session, org)
    ensure_services(db_session, org.id)
    archive_service(services_by_code(db_session, org)["appliance"].id, user=owner, db=db_session)

    data, _ = ingest(db_session, org, "сломался холодильник")

    assert db_session.get(Ticket, data["ticket_id"]).category == "other"


# ---- API rules


def test_only_owner_and_admin_can_change_the_catalog(db_session):
    org = make_org(db_session)
    for role in (UserRole.MANAGER, UserRole.STAFF, UserRole.TECHNICIAN):
        user = make_user(db_session, org, role)
        with pytest.raises(HTTPException) as exc:
            create_service(ServiceCreate(names={"en": "Pool"}), user=user, db=db_session)
        assert exc.value.status_code == 403


def test_anyone_in_the_org_can_list_services(db_session):
    org = make_org(db_session)
    staff = make_user(db_session, org, UserRole.STAFF)

    codes = [s.code for s in list_services(include_archived=False, user=staff, db=db_session)]

    assert codes[-1] == "other"  # the fallback always sorts last
    assert "plumbing" in codes


def test_new_services_go_above_the_fallback(db_session):
    org = make_org(db_session)
    owner = make_user(db_session, org)
    create_service(ServiceCreate(names={"en": "Pool"}), user=owner, db=db_session)

    codes = [s.code for s in list_services(include_archived=False, user=owner, db=db_session)]

    assert codes[-1] == "other"
    assert codes[-2].startswith("svc_")


def test_the_fallback_service_cannot_be_archived_or_given_keywords(db_session):
    org = make_org(db_session)
    owner = make_user(db_session, org)
    ensure_services(db_session, org.id)
    other = services_by_code(db_session, org)["other"]

    with pytest.raises(HTTPException) as exc:
        archive_service(other.id, user=owner, db=db_session)
    assert exc.value.status_code == 400
    with pytest.raises(HTTPException):
        update_service(other.id, ServiceUpdate(keywords=["x"]), user=owner, db=db_session)

    renamed = update_service(other.id, ServiceUpdate(names={"en": "Misc"}), user=owner, db=db_session)
    assert renamed.names == {"en": "Misc"}


def test_archived_services_stay_listable_for_old_ticket_labels(db_session):
    org = make_org(db_session)
    owner = make_user(db_session, org)
    ensure_services(db_session, org.id)
    archive_service(services_by_code(db_session, org)["access"].id, user=owner, db=db_session)

    active = {s.code for s in list_services(include_archived=False, user=owner, db=db_session)}
    everything = {s.code for s in list_services(include_archived=True, user=owner, db=db_session)}

    assert "access" not in active and "access" in everything


def test_services_are_scoped_to_the_organization(db_session):
    org, other_org = make_org(db_session), make_org(db_session)
    owner = make_user(db_session, org)
    ensure_services(db_session, other_org.id)
    foreign = services_by_code(db_session, other_org)["plumbing"]

    with pytest.raises(HTTPException) as exc:
        update_service(foreign.id, ServiceUpdate(names={"en": "Hijacked"}), user=owner, db=db_session)
    assert exc.value.status_code == 404


@pytest.mark.parametrize(
    "names",
    [{}, {"en": "   "}, {"fr": "Piscine"}, {"en": "x" * 101}],
)
def test_invalid_names_are_rejected(names):
    with pytest.raises(Exception):
        ServiceCreate(names=names)


def test_keywords_are_trimmed_lowercased_and_deduplicated():
    assert ServiceCreate(names={"en": "Pool"}, keywords=[" Pool ", "pool", "", "Filter"]).keywords == ["pool", "filter"]


# ---- tickets


def test_tickets_only_accept_active_service_codes(db_session):
    from app.tickets import TicketCreate, TicketUpdate, create_ticket, update_ticket

    org = make_org(db_session)
    owner = make_user(db_session, org)

    with pytest.raises(HTTPException) as exc:
        create_ticket(TicketCreate(organization_id=org.id, title="t", description="x", category="made_up"), user=owner, db=db_session)
    assert exc.value.status_code == 400

    ticket = create_ticket(TicketCreate(organization_id=org.id, title="t", description="x", category="plumbing"), user=owner, db=db_session)
    with pytest.raises(HTTPException):
        update_ticket(ticket.id, TicketUpdate(category="made_up"), user=owner, db=db_session)
    assert update_ticket(ticket.id, TicketUpdate(category="hvac"), user=owner, db=db_session).category == "hvac"


# ---- executors


def test_specialties_only_accept_active_service_codes(db_session):
    org = make_org(db_session)
    owner = make_user(db_session, org)
    tech = make_user(db_session, org, UserRole.TECHNICIAN)

    with pytest.raises(HTTPException) as exc:
        update_user_specialties(tech.id, UserSpecialtiesUpdate(specialties=["plumbing", "made_up"]), user=owner, db=db_session)
    assert exc.value.status_code == 400

    result = update_user_specialties(tech.id, UserSpecialtiesUpdate(specialties=["plumbing"]), user=owner, db=db_session)
    assert result.specialties == ["plumbing"]


def test_archiving_a_service_removes_it_from_executors(db_session):
    org = make_org(db_session)
    owner = make_user(db_session, org)
    tech = make_user(db_session, org, UserRole.TECHNICIAN, specialties=["plumbing", "hvac"])
    ensure_services(db_session, org.id)

    archive_service(services_by_code(db_session, org)["plumbing"].id, user=owner, db=db_session)

    db_session.refresh(tech)
    assert tech.specialties == ["hvac"]
