import uuid
from datetime import datetime, timedelta, timezone

from app.dashboard_routes import dashboard_summary
from app.models import Customer, Organization, Property, Ticket, TicketPriority, TicketStatus, Unit, User, UserRole


def test_dashboard_summary_is_tenant_scoped(db_session):
    org1 = Organization(name="Org 1")
    org2 = Organization(name="Org 2")
    db_session.add_all([org1, org2])
    db_session.flush()

    user = User(
        organization_id=org1.id,
        email="owner@example.com",
        password_hash="hash",
        role=UserRole.OWNER,
    )
    db_session.add(user)
    db_session.flush()

    db_session.add_all([
        Ticket(
            organization_id=org1.id,
            title="Open",
            description="x",
            priority=TicketPriority.HIGH,
            status=TicketStatus.IN_PROGRESS,
            resolution_deadline=datetime.now(timezone.utc) + timedelta(hours=1),
        ),
        Ticket(
            organization_id=org1.id,
            title="Overdue",
            description="x",
            priority=TicketPriority.CRITICAL,
            status=TicketStatus.NEW,
            resolution_deadline=datetime.now(timezone.utc) - timedelta(hours=1),
        ),
        Ticket(
            organization_id=org2.id,
            title="Other tenant",
            description="x",
            priority=TicketPriority.CRITICAL,
            status=TicketStatus.NEW,
            resolution_deadline=datetime.now(timezone.utc) - timedelta(hours=1),
        ),
        Customer(organization_id=org1.id, name="Customer"),
        Property(organization_id=org1.id, name="Property"),
    ])
    db_session.flush()
    prop = db_session.scalar(
        __import__("sqlalchemy").select(Property).where(Property.organization_id == org1.id)
    )
    db_session.add(Unit(organization_id=org1.id, property_id=prop.id, unit_number="101"))
    db_session.commit()

    result = dashboard_summary(user=user, db=db_session)

    assert result.tickets_total == 2
    assert result.tickets_open == 2
    assert result.tickets_overdue == 1
    assert result.customers_total == 1
    assert result.properties_total == 1
    assert result.units_total == 1
    assert sum(item.count for item in result.tickets_by_status) == 2
    assert sum(item.count for item in result.tickets_by_priority) == 2


def test_dashboard_summary_empty_organization(db_session):
    org = Organization(name="Empty")
    db_session.add(org)
    db_session.flush()
    user = User(
        organization_id=org.id,
        email="owner@example.com",
        password_hash="hash",
        role=UserRole.OWNER,
    )
    db_session.add(user)
    db_session.commit()

    result = dashboard_summary(user=user, db=db_session)

    assert result.tickets_total == 0
    assert result.tickets_open == 0
    assert result.tickets_overdue == 0
    assert result.customers_total == 0
    assert result.properties_total == 0
    assert result.units_total == 0
    assert all(item.count == 0 for item in result.tickets_by_status)
    assert all(item.count == 0 for item in result.tickets_by_priority)
