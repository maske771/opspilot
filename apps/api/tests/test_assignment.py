from app.assignment import find_assignee_for_category
from app.models import Organization, Ticket, TicketPriority, TicketStatus, User, UserRole


def make_org_and_staff(db_session, specialties: list[str], role: UserRole = UserRole.TECHNICIAN) -> tuple[Organization, User]:
    org = Organization(name="Org")
    db_session.add(org)
    db_session.flush()
    staff = User(
        organization_id=org.id,
        email=f"staff-{id(specialties)}@example.com",
        password_hash="hash",
        role=role,
        specialties=specialties,
    )
    db_session.add(staff)
    db_session.commit()
    return org, staff


def test_no_match_returns_none(db_session):
    org, _ = make_org_and_staff(db_session, specialties=["plumbing"])

    assert find_assignee_for_category(db_session, org.id, "electrical") is None


def test_matches_staff_by_specialty(db_session):
    org, staff = make_org_and_staff(db_session, specialties=["plumbing", "hvac"])

    assignee = find_assignee_for_category(db_session, org.id, "hvac")

    assert assignee is not None
    assert assignee.id == staff.id


def test_ignores_non_assignable_roles(db_session):
    org, _ = make_org_and_staff(db_session, specialties=["plumbing"], role=UserRole.MANAGER)

    assert find_assignee_for_category(db_session, org.id, "plumbing") is None


def test_picks_least_loaded_match(db_session):
    org = Organization(name="Org")
    db_session.add(org)
    db_session.flush()

    busy = User(organization_id=org.id, email="busy@example.com", password_hash="hash", role=UserRole.STAFF, specialties=["plumbing"])
    free = User(organization_id=org.id, email="free@example.com", password_hash="hash", role=UserRole.STAFF, specialties=["plumbing"])
    db_session.add_all([busy, free])
    db_session.flush()

    db_session.add_all([
        Ticket(organization_id=org.id, title="t1", description="x", priority=TicketPriority.MEDIUM, status=TicketStatus.ASSIGNED, assignee_id=busy.id, category="plumbing"),
        Ticket(organization_id=org.id, title="t2", description="x", priority=TicketPriority.MEDIUM, status=TicketStatus.IN_PROGRESS, assignee_id=busy.id, category="plumbing"),
        Ticket(organization_id=org.id, title="t3-closed", description="x", priority=TicketPriority.MEDIUM, status=TicketStatus.CLOSED, assignee_id=free.id, category="plumbing"),
    ])
    db_session.commit()

    assignee = find_assignee_for_category(db_session, org.id, "plumbing")

    assert assignee is not None
    assert assignee.id == free.id
