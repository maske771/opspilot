import uuid

from app.customer_match import find_customer, normalize_email, normalize_phone
from app.models import Customer, CustomerIdentity, Organization


def make_org(db_session):
    org = Organization(id=uuid.uuid4(), name="Test org")
    db_session.add(org)
    db_session.flush()
    return org


def test_normalize_email_and_phone():
    assert normalize_email("  USER@Example.COM ") == "user@example.com"
    assert normalize_phone("+7 (999) 123-45-67") == "79991234567"
    assert normalize_phone("8 999 123 45 67") == "79991234567"


def test_matches_existing_channel_identity_first(db_session):
    org = make_org(db_session)
    customer = Customer(organization_id=org.id, name="Ivan")
    db_session.add(customer)
    db_session.flush()
    db_session.add(CustomerIdentity(
        organization_id=org.id,
        customer_id=customer.id,
        channel_type="telegram",
        external_user_id="42",
    ))
    db_session.commit()

    result = find_customer(db_session, org.id, channel_type="telegram", external_user_id="42")
    assert result.customer.id == customer.id
    assert result.match_type == "identity"
    assert result.confidence == 1.0


def test_matches_email_across_channels(db_session):
    org = make_org(db_session)
    customer = Customer(organization_id=org.id, name="Anna", email="anna@example.com")
    db_session.add(customer)
    db_session.commit()

    result = find_customer(
        db_session, org.id, channel_type="line", external_user_id="line-1", email=" ANNA@example.com "
    )
    assert result.customer.id == customer.id
    assert result.match_type == "email"


def test_matches_phone_across_channels(db_session):
    org = make_org(db_session)
    customer = Customer(organization_id=org.id, name="Petr", phone="+79991234567")
    db_session.add(customer)
    db_session.commit()

    result = find_customer(
        db_session, org.id, channel_type="whatsapp", external_user_id="79991234567", phone="8 (999) 123-45-67"
    )
    assert result.customer.id == customer.id
    assert result.match_type == "phone"


def test_same_name_does_not_auto_merge(db_session):
    org = make_org(db_session)
    customer = Customer(organization_id=org.id, name="Alexey")
    db_session.add(customer)
    db_session.commit()

    result = find_customer(db_session, org.id, channel_type="line", external_user_id="line-2")
    assert result.customer is None
    assert result.match_type == "new"
