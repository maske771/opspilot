"""Bulk import of properties and units from a CSV or XLSX file.

One row per unit: property name, address (optional), unit number (optional — a row with only a
property creates the property without units). Rows are grouped by property name; a name that
already exists in the organization (case-insensitive) adds units to that property instead of
creating a new one. Units already on the property, or repeated in the file, are skipped.

`preview` and `import` run the same plan; `import` refuses a file with row errors and writes
everything in one transaction. Errors are returned as codes for the UI to translate.
"""
import csv
import io
import uuid
from dataclasses import dataclass, field

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from .audit import record
from .auth import require_roles
from .db import get_db
from .models import Property, Unit, User

router = APIRouter(prefix="/properties/import", tags=["properties"])

MAX_FILE_BYTES = 1024 * 1024
MAX_ROWS = 5000
MAX_NAME = 255
MAX_UNIT = 100

# Header aliases in the three UI languages; matched case-insensitively after trimming.
COLUMNS = {
    "property": ("property", "property_name", "property name", "name", "объект", "название объекта", "название", "อาคาร", "ชื่ออาคาร"),
    "address": ("address", "адрес", "ที่อยู่"),
    "unit": ("unit", "unit_number", "unit number", "юнит", "квартира", "номер", "помещение", "ห้อง", "ยูนิต", "เลขห้อง"),
}


class RowError(BaseModel):
    row: int  # 1-based, as the user sees it in their spreadsheet (header = row 1)
    code: str


class ImportPropertyPlan(BaseModel):
    name: str
    address: str | None
    existing: bool
    new_units: list[str]


class ImportPlan(BaseModel):
    rows: int
    properties: list[ImportPropertyPlan]
    properties_new: int
    properties_existing: int
    units_new: int
    units_skipped: int
    errors: list[RowError]


@dataclass
class _Group:
    name: str
    address: str | None = None
    existing: Property | None = None
    units: list[str] = field(default_factory=list)
    seen: set[str] = field(default_factory=set)


def _cell(value) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        value = int(value)  # Excel stores "12" as 12.0
    return str(value).strip()


def read_rows(content: bytes) -> list[list[str]]:
    if content.startswith(b"PK\x03\x04"):
        try:
            from openpyxl import load_workbook

            sheet = load_workbook(io.BytesIO(content), read_only=True, data_only=True).worksheets[0]
            return [[_cell(v) for v in row] for row in sheet.iter_rows(values_only=True)]
        except Exception as exc:  # a zip that isn't a workbook, a corrupt file
            raise HTTPException(400, "unsupported_file") from exc
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise HTTPException(400, "not_utf8") from exc
    try:
        dialect = csv.Sniffer().sniff(text[:4096], delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    return [[c.strip() for c in row] for row in csv.reader(io.StringIO(text), dialect)]


def _column_indexes(header: list[str]) -> dict[str, int]:
    normalized = [h.strip().lower() for h in header]
    indexes = {}
    for key, aliases in COLUMNS.items():
        for i, h in enumerate(normalized):
            if h in aliases:
                indexes[key] = i
                break
    if "property" not in indexes:
        raise HTTPException(422, "no_property_column")
    return indexes


def plan_import(db: Session, organization_id: uuid.UUID, rows: list[list[str]]) -> tuple[ImportPlan, list[_Group]]:
    rows = [r for r in rows if any(c for c in r)]
    if not rows:
        raise HTTPException(422, "empty_file")
    indexes = _column_indexes(rows[0])
    data = rows[1:]
    if len(data) > MAX_ROWS:
        raise HTTPException(413, "too_many_rows")

    existing = {p.name.strip().lower(): p for p in db.scalars(select(Property).where(Property.organization_id == organization_id))}
    existing_units: dict[uuid.UUID, set[str]] = {}
    for unit in db.scalars(select(Unit).where(Unit.organization_id == organization_id)):
        existing_units.setdefault(unit.property_id, set()).add(unit.unit_number.strip().lower())

    def get(row: list[str], key: str) -> str:
        i = indexes.get(key)
        return row[i].strip() if i is not None and i < len(row) else ""

    groups: dict[str, _Group] = {}
    errors: list[RowError] = []
    skipped = 0
    for number, row in enumerate(data, start=2):
        name, address, unit = get(row, "property"), get(row, "address"), get(row, "unit")
        if not name:
            errors.append(RowError(row=number, code="missing_property"))
            continue
        if len(name) > MAX_NAME:
            errors.append(RowError(row=number, code="property_too_long"))
            continue
        if len(unit) > MAX_UNIT:
            errors.append(RowError(row=number, code="unit_too_long"))
            continue
        key = name.lower()
        group = groups.get(key)
        if group is None:
            match = existing.get(key)
            group = _Group(name=match.name if match else name, existing=match)
            if match is not None:
                group.seen = set(existing_units.get(match.id, set()))
            groups[key] = group
        if address and group.address is None and group.existing is None:
            group.address = address
        if unit:
            if unit.lower() in group.seen:
                skipped += 1
            else:
                group.seen.add(unit.lower())
                group.units.append(unit)

    plans = [
        ImportPropertyPlan(name=g.name, address=g.existing.address if g.existing else g.address, existing=g.existing is not None, new_units=g.units)
        for g in groups.values()
    ]
    plan = ImportPlan(
        rows=len(data),
        properties=plans,
        properties_new=sum(1 for g in groups.values() if g.existing is None),
        properties_existing=sum(1 for g in groups.values() if g.existing is not None),
        units_new=sum(len(g.units) for g in groups.values()),
        units_skipped=skipped,
        errors=errors,
    )
    return plan, list(groups.values())


async def _read_upload(file: UploadFile) -> bytes:
    content = await file.read(MAX_FILE_BYTES + 1)
    if len(content) > MAX_FILE_BYTES:
        raise HTTPException(413, "file_too_large")
    return content


@router.post("/preview", response_model=ImportPlan)
async def preview_import(
    file: UploadFile = File(...),
    user: User = Depends(require_roles("owner", "admin", "manager")),
    db: Session = Depends(get_db),
):
    plan, _ = plan_import(db, user.organization_id, read_rows(await _read_upload(file)))
    return plan


@router.post("", response_model=ImportPlan)
async def run_import(
    file: UploadFile = File(...),
    user: User = Depends(require_roles("owner", "admin", "manager")),
    db: Session = Depends(get_db),
):
    plan, groups = plan_import(db, user.organization_id, read_rows(await _read_upload(file)))
    if plan.errors:
        raise HTTPException(422, "rows_have_errors")
    return apply_import(db, user, plan, groups)


def apply_import(db: Session, user: User, plan: ImportPlan, groups: list[_Group]) -> ImportPlan:
    for group in groups:
        prop = group.existing
        if prop is None:
            prop = Property(id=uuid.uuid4(), organization_id=user.organization_id, name=group.name, address=group.address)
            db.add(prop)
        for unit_number in group.units:
            db.add(Unit(organization_id=user.organization_id, property_id=prop.id, unit_number=unit_number))
    record(
        db,
        organization_id=user.organization_id,
        actor=user,
        entity_type="organization",
        entity_id=user.organization_id,
        action="properties_imported",
        details={"properties_new": plan.properties_new, "properties_existing": plan.properties_existing, "units_new": plan.units_new},
    )
    db.commit()
    return plan
