from app.models import Organization, TicketPriority, User, UserRole
from app.sla import SLA_MINUTES
from app.sla_routes import sla_defaults


def test_sla_defaults_matches_the_sla_module(db_session):
    org = Organization(name="Org")
    db_session.add(org)
    db_session.flush()
    user = User(organization_id=org.id, email="owner@example.com", password_hash="h", role=UserRole.OWNER)
    db_session.add(user)
    db_session.commit()

    result = {row.priority: row for row in sla_defaults(user=user)}

    assert set(result) == set(TicketPriority)
    for priority, (response_minutes, resolution_minutes) in SLA_MINUTES.items():
        assert result[priority].response_minutes == response_minutes
        assert result[priority].resolution_minutes == resolution_minutes
