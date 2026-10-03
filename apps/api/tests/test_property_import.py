import io
import uuid

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from openpyxl import Workbook
from sqlalchemy import select

from app.auth import create_access_token
from app.db import get_db
from app.main import app
from app.models import AuditEvent, Organization, Property, Unit, User, UserRole
from app.property_import import plan_import, read_rows


def setup(db_session, role=UserRole.OWNER):
    org = Organization(name="Org")
    db_session.add(org)
    db_session.flush()
    user = User(organization_id=org.id, email=f"u-{uuid.uuid4().hex[:6]}@example.com", password_hash="h", role=role)
    db_session.add(user)
    db_session.commit()
    return org, user


def csv_bytes(text: str) -> bytes:
    return text.encode("utf-8")


def test_rows_are_grouped_by_property_and_duplicates_skipped(db_session):
    org, _ = setup(db_session)
    rows = read_rows(csv_bytes("property,address,unit\nSunset,1 Beach Rd,101\nSunset,,102\nsunset,,101\nRiverside,,\n"))
    plan, _ = plan_import(db_session, org.id, rows)
    assert plan.rows == 4 and plan.properties_new == 2 and plan.units_new == 2 and plan.units_skipped == 1
    sunset = next(p for p in plan.properties if p.name == "Sunset")
    assert sunset.address == "1 Beach Rd" and sunset.new_units == ["101", "102"]
    assert not plan.errors


def test_existing_properties_get_only_their_missing_units(db_session):
    org, _ = setup(db_session)
    prop = Property(organization_id=org.id, name="Garden Villas", address="old")
    db_session.add(prop)
    db_session.flush()
    db_session.add(Unit(organization_id=org.id, property_id=prop.id, unit_number="A1"))
    db_session.commit()

    plan, _ = plan_import(db_session, org.id, read_rows(csv_bytes("объект;адрес;квартира\ngarden villas;new address;a1\nGarden Villas;;A2\n")))
    [item] = plan.properties
    assert item.existing and item.name == "Garden Villas" and item.address == "old"
    assert item.new_units == ["A2"] and plan.units_skipped == 1


def test_row_errors_are_reported_with_spreadsheet_row_numbers(db_session):
    org, _ = setup(db_session)
    plan, _ = plan_import(db_session, org.id, read_rows(csv_bytes(f"property,unit\n,5\nOK,{'x' * 101}\n{'y' * 256},1\n")))
    assert [(e.row, e.code) for e in plan.errors] == [(2, "missing_property"), (3, "unit_too_long"), (4, "property_too_long")]


@pytest.mark.parametrize(
    "content, code",
    [
        (b"", "empty_file"),
        (b"unit,address\n1,x\n", "no_property_column"),
        ("property\nОбъект".encode("cp1251"), "not_utf8"),
        (b"PK\x03\x04garbage", "unsupported_file"),
    ],
)
def test_bad_files_are_rejected_with_a_code(db_session, content, code):
    org, _ = setup(db_session)
    with pytest.raises(HTTPException) as exc:
        plan_import(db_session, org.id, read_rows(content))
    assert exc.value.detail == code


def test_xlsx_files_are_read_including_numeric_units(db_session):
    org, _ = setup(db_session)
    wb = Workbook()
    ws = wb.active
    ws.append(["อาคาร", "ที่อยู่", "ห้อง"])
    ws.append(["Baan Suan", "Chiang Mai", 12])
    ws.append(["Baan Suan", None, 12.0])
    buffer = io.BytesIO()
    wb.save(buffer)
    plan, _ = plan_import(db_session, org.id, read_rows(buffer.getvalue()))
    assert plan.properties[0].new_units == ["12"] and plan.units_skipped == 1


def client_for(db_session, user):
    app.dependency_overrides[get_db] = lambda: db_session
    return TestClient(app), {"Authorization": f"Bearer {create_access_token(user)}"}


def test_import_over_http_creates_everything_and_is_audited(db_session):
    org, user = setup(db_session)
    client, headers = client_for(db_session, user)
    try:
        file = {"file": ("props.csv", csv_bytes("property,address,unit\nSunset,1 Beach Rd,101\nSunset,,102\n"), "text/csv")}
        preview = client.post("/properties/import/preview", files=file, headers=headers)
        assert preview.status_code == 200 and preview.json()["units_new"] == 2
        assert db_session.scalar(select(Property).where(Property.organization_id == org.id)) is None

        done = client.post("/properties/import", files=file, headers=headers)
        assert done.status_code == 200
        prop = db_session.scalar(select(Property).where(Property.organization_id == org.id))
        assert prop.name == "Sunset" and prop.address == "1 Beach Rd" and len(prop.code) == 6
        assert sorted(u.unit_number for u in db_session.scalars(select(Unit).where(Unit.property_id == prop.id))) == ["101", "102"]
        event = db_session.scalar(select(AuditEvent).where(AuditEvent.organization_id == org.id, AuditEvent.action == "properties_imported"))
        assert event.details == {"properties_new": 1, "properties_existing": 0, "units_new": 2}

        again = client.post("/properties/import", files=file, headers=headers)
        assert again.json()["properties_new"] == 0 and again.json()["units_skipped"] == 2
    finally:
        app.dependency_overrides.clear()


def test_import_with_row_errors_writes_nothing(db_session):
    org, user = setup(db_session)
    client, headers = client_for(db_session, user)
    try:
        response = client.post("/properties/import", files={"file": ("p.csv", csv_bytes("property,unit\nA,1\n,2\n"), "text/csv")}, headers=headers)
        assert response.status_code == 422 and response.json()["detail"] == "rows_have_errors"
        assert db_session.scalar(select(Property).where(Property.organization_id == org.id)) is None
    finally:
        app.dependency_overrides.clear()


def test_staff_cannot_import(db_session):
    _, staff = setup(db_session, role=UserRole.STAFF)
    client, headers = client_for(db_session, staff)
    try:
        response = client.post("/properties/import/preview", files={"file": ("p.csv", b"property\nA\n", "text/csv")}, headers=headers)
        assert response.status_code == 403
    finally:
        app.dependency_overrides.clear()
