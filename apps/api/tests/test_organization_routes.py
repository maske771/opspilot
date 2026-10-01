import pytest

from app.models import Organization, TicketPriority, User, UserRole
from app.organization_routes import (
    OrganizationUpdate,
    OrgSlaUpdate,
    SlaPair,
    get_organization,
    get_organization_sla,
    update_organization,
    update_organization_sla,
)
from app.sla import SLA_MINUTES


def make_org(db_session, **overrides):
    values = dict(name="Org")
    values.update(overrides)
    org = Organization(**values)
    db_session.add(org)
    db_session.flush()
    return org


def make_user(db_session, org, role):
    user = User(organization_id=org.id, email=f"{role.value}@example.com", password_hash="h", role=role)
    db_session.add(user)
    db_session.commit()
    return user


def test_onboarding_defaults_to_incomplete(db_session):
    org = make_org(db_session)
    owner = make_user(db_session, org, UserRole.OWNER)

    result = get_organization(user=owner, db=db_session)

    assert result.onboarding_completed is False


def test_updating_name_leaves_onboarding_completed_untouched(db_session):
    org = make_org(db_session, onboarding_completed=True)
    owner = make_user(db_session, org, UserRole.OWNER)

    result = update_organization(OrganizationUpdate(name="New Name"), user=owner, db=db_session)

    assert result.name == "New Name"
    assert result.onboarding_completed is True


def test_marking_onboarding_complete_leaves_name_untouched(db_session):
    org = make_org(db_session, name="Riverside")
    owner = make_user(db_session, org, UserRole.OWNER)

    result = update_organization(OrganizationUpdate(onboarding_completed=True), user=owner, db=db_session)

    assert result.onboarding_completed is True
    assert result.name == "Riverside"


# ---- SLA settings


def test_sla_defaults_to_the_global_values_marked_not_custom(db_session):
    org = make_org(db_session)
    owner = make_user(db_session, org, UserRole.OWNER)

    result = {row.priority: row for row in get_organization_sla(user=owner, db=db_session)}

    assert set(result) == set(TicketPriority)
    for priority, (response_minutes, resolution_minutes) in SLA_MINUTES.items():
        assert result[priority].response_minutes == response_minutes
        assert result[priority].resolution_minutes == resolution_minutes
        assert result[priority].is_custom is False


def test_setting_an_override_marks_only_that_priority_as_custom(db_session):
    org = make_org(db_session)
    owner = make_user(db_session, org, UserRole.OWNER)

    result = {
        row.priority: row
        for row in update_organization_sla(
            OrgSlaUpdate(critical=SlaPair(response_minutes=5, resolution_minutes=30)), user=owner, db=db_session
        )
    }

    assert result[TicketPriority.CRITICAL].response_minutes == 5
    assert result[TicketPriority.CRITICAL].resolution_minutes == 30
    assert result[TicketPriority.CRITICAL].is_custom is True
    assert result[TicketPriority.HIGH].is_custom is False
    assert result[TicketPriority.HIGH].response_minutes == SLA_MINUTES[TicketPriority.HIGH][0]


def test_override_persists_and_is_returned_by_a_later_get(db_session):
    org = make_org(db_session)
    owner = make_user(db_session, org, UserRole.OWNER)
    update_organization_sla(OrgSlaUpdate(high=SlaPair(response_minutes=20, resolution_minutes=200)), user=owner, db=db_session)

    result = {row.priority: row for row in get_organization_sla(user=owner, db=db_session)}

    assert result[TicketPriority.HIGH].response_minutes == 20
    assert result[TicketPriority.HIGH].resolution_minutes == 200
    assert result[TicketPriority.HIGH].is_custom is True


def test_setting_a_priority_to_null_resets_it_to_default(db_session):
    org = make_org(db_session)
    owner = make_user(db_session, org, UserRole.OWNER)
    update_organization_sla(OrgSlaUpdate(high=SlaPair(response_minutes=20, resolution_minutes=200)), user=owner, db=db_session)

    result = {row.priority: row for row in update_organization_sla(OrgSlaUpdate(high=None), user=owner, db=db_session)}

    assert result[TicketPriority.HIGH].is_custom is False
    assert result[TicketPriority.HIGH].response_minutes == SLA_MINUTES[TicketPriority.HIGH][0]


def test_updating_one_priority_leaves_other_overrides_alone(db_session):
    org = make_org(db_session)
    owner = make_user(db_session, org, UserRole.OWNER)
    update_organization_sla(OrgSlaUpdate(critical=SlaPair(response_minutes=5, resolution_minutes=30)), user=owner, db=db_session)

    result = {
        row.priority: row
        for row in update_organization_sla(OrgSlaUpdate(low=SlaPair(response_minutes=600, resolution_minutes=6000)), user=owner, db=db_session)
    }

    assert result[TicketPriority.CRITICAL].is_custom is True  # untouched by the second call
    assert result[TicketPriority.LOW].is_custom is True


def test_out_of_range_minutes_are_rejected():
    with pytest.raises(Exception):
        SlaPair(response_minutes=0, resolution_minutes=30)
    with pytest.raises(Exception):
        SlaPair(response_minutes=10, resolution_minutes=50000)
