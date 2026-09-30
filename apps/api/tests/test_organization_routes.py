from app.models import Organization, User, UserRole
from app.organization_routes import OrganizationUpdate, get_organization, update_organization


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
