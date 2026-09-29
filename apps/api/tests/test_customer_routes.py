import uuid

from app.customer_routes import list_customers
from app.models import Customer, Organization, User, UserRole


def test_listing_customers_without_a_name_does_not_500(db_session):
    # Channels don't always hand over a name (e.g. a WhatsApp/email sender with no display
    # name) — Customer.name is nullable in the DB, so the response model must allow it too,
    # or FastAPI's response validation 500s for the whole list.
    org = Organization(name="Org")
    db_session.add(org)
    db_session.flush()
    db_session.add(Customer(organization_id=org.id, name=None, phone="+66800000000"))
    user = User(organization_id=org.id, email=f"owner-{uuid.uuid4().hex[:6]}@example.com", password_hash="h", role=UserRole.OWNER)
    db_session.add(user)
    db_session.commit()

    result = list_customers(user=user, db=db_session)

    assert len(result) == 1 and result[0].name is None
