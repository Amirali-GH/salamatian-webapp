"""Unit tests for the Excel sync module — the core of the system.

Covers parse_workbook (happy path, missing columns, bad rows, duplicates),
build_diff (new / updated / removed / unchanged), and the full apply_diff flow
(transaction outcome, audit log entries, archive not hard-delete).
"""
from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import openpyxl
import pytest
from sqlalchemy import select

from app.models import (
    AuditAction,
    AuditLog,
    Car,
    CarSource,
    CarStatus,
    ExcelImportLog,
)
from app.services import excel_sync


def _write_xlsx(
    tmp: Path,
    rows: list[list],
    headers: list[str] = None,
) -> Path:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(headers or ["brand", "model", "year", "price", "mileage", "excel_row_id"])
    for r in rows:
        ws.append(r)
    path = tmp / "cars.xlsx"
    wb.save(path)
    return path


def test_parse_happy_path(tmp_path):
    path = _write_xlsx(
        tmp_path,
        [
            ["Peugeot", "206", 1395, "450000000", 120000, "R-1"],
            ["Samand", "LX", 1398, "350000000", 80000, "R-2"],
        ],
    )
    rows, warnings = excel_sync.parse_workbook(path)
    assert len(rows) == 2
    assert warnings == []
    assert rows[0]["brand"] == "Peugeot"
    assert rows[0]["price"] == Decimal("450000000")
    assert rows[0]["excel_row_id"] == "R-1"


def test_parse_missing_required_column(tmp_path):
    # No "price" column at all -> fatal error
    path = _write_xlsx(
        tmp_path,
        [["Peugeot", "206", 1395, 120000]],
        headers=["brand", "model", "year", "mileage"],
    )
    with pytest.raises(ValueError, match="Missing required columns"):
        excel_sync.parse_workbook(path)


def test_parse_row_level_warnings(tmp_path):
    path = _write_xlsx(
        tmp_path,
        [
            ["Peugeot", "206", 1395, "450000000", 100, "R-1"],
            ["", "", 1395, "100", None, "R-2"],          # missing brand + model
            ["Peugeot", "206", 1395, "bad-price", 0, "R-3"],  # invalid price
            ["Peugeot", "206", 1395, "-5", 0, "R-4"],          # price <= 0
        ],
    )
    rows, warnings = excel_sync.parse_workbook(path)
    assert len(rows) == 1  # only the first row is clean
    issues = [w["issue"] for w in warnings]
    assert any("missing brand" in i for i in issues)
    assert any("invalid price" in i for i in issues)
    assert any("price must be > 0" in i for i in issues)


def test_parse_duplicate_key_warning(tmp_path):
    path = _write_xlsx(
        tmp_path,
        [
            ["Peugeot", "206", 1395, "450000000", 100, None],
            ["Peugeot", "206", 1395, "460000000", 200, None],  # dup by (brand+model+year)
        ],
    )
    rows, warnings = excel_sync.parse_workbook(path)
    assert len(rows) == 1
    assert any("duplicate" in w["issue"] for w in warnings)


async def test_build_diff_new_and_unchanged(db, tmp_path):
    # Seed one existing excel car
    car = Car(
        brand="Peugeot", model="206", year=1395, price=Decimal("450000000"),
        mileage=100000, status=CarStatus.published, source=CarSource.excel,
        excel_row_id="R-1",
    )
    db.add(car)
    await db.commit()

    path = _write_xlsx(
        tmp_path,
        [
            ["Peugeot", "206", 1395, "450000000", 100000, "R-1"],  # unchanged
            ["Samand", "LX", 1398, "350000000", 80000, "R-2"],     # new
        ],
    )
    rows, warnings = excel_sync.parse_workbook(path)
    diff = await excel_sync.build_diff(db, rows, warnings)

    assert diff["unchanged"] == 1
    assert len(diff["new_cars"]) == 1
    assert diff["new_cars"][0]["excel_row_id"] == "R-2"
    assert diff["updated_cars"] == []
    assert diff["removed_cars"] == []


async def test_build_diff_updated_price(db, tmp_path):
    car = Car(
        brand="Peugeot", model="206", year=1395, price=Decimal("450000000"),
        status=CarStatus.published, source=CarSource.excel, excel_row_id="R-1",
    )
    db.add(car); await db.commit()

    path = _write_xlsx(
        tmp_path,
        [["Peugeot", "206", 1395, "500000000", None, "R-1"]],
    )
    rows, warnings = excel_sync.parse_workbook(path)
    diff = await excel_sync.build_diff(db, rows, warnings)

    assert len(diff["updated_cars"]) == 1
    assert diff["updated_cars"][0]["changes"]["price"]["new"] == "500000000"


async def test_build_diff_removed(db, tmp_path):
    car = Car(
        brand="Kia", model="Pride", year=1390, price=Decimal("100000000"),
        status=CarStatus.published, source=CarSource.excel, excel_row_id="R-X",
    )
    db.add(car); await db.commit()

    # Excel does not contain R-X
    path = _write_xlsx(
        tmp_path,
        [["Peugeot", "206", 1395, "450000000", None, "R-1"]],
    )
    rows, warnings = excel_sync.parse_workbook(path)
    diff = await excel_sync.build_diff(db, rows, warnings)

    assert len(diff["removed_cars"]) == 1
    assert diff["removed_cars"][0]["car_id"] == car.id


async def test_apply_diff_full_flow(db, tmp_path, monkeypatch):
    # Seed: one to update, one to remove
    to_update = Car(
        brand="Peugeot", model="206", year=1395, price=Decimal("450000000"),
        status=CarStatus.published, source=CarSource.excel, excel_row_id="R-1",
    )
    to_remove = Car(
        brand="Kia", model="Pride", year=1390, price=Decimal("100000000"),
        status=CarStatus.published, source=CarSource.excel, excel_row_id="R-X",
    )
    db.add_all([to_update, to_remove])
    await db.commit()

    path = _write_xlsx(
        tmp_path,
        [
            ["Peugeot", "206", 1395, "500000000", None, "R-1"],  # updated
            ["Samand", "LX", 1398, "350000000", 80000, "R-NEW"],  # new
        ],
    )
    diff, token = await excel_sync.parse_and_stage(db, path)
    assert token
    result = await excel_sync.apply_diff(db, token, user_id=None)
    assert result["added"] == 1
    assert result["updated"] == 1
    assert result["removed"] == 1

    # Confirm state in DB
    await db.refresh(to_update)
    await db.refresh(to_remove)
    assert to_update.price == Decimal("500000000")
    assert to_remove.status == CarStatus.archived  # archived, NOT hard deleted
    assert to_remove.deleted_at is None  # never hard deletes

    new_car = (
        await db.execute(select(Car).where(Car.excel_row_id == "R-NEW"))
    ).scalar_one()
    assert new_car.status == CarStatus.pending
    assert new_car.source == CarSource.excel

    # Audit: price_change entry exists for to_update
    logs = (await db.execute(select(AuditLog))).scalars().all()
    actions = {l.action for l in logs}
    assert AuditAction.price_change in actions
    assert AuditAction.create in actions
    assert AuditAction.archive in actions

    # Excel import log written
    imp_logs = (await db.execute(select(ExcelImportLog))).scalars().all()
    assert len(imp_logs) == 1
    assert imp_logs[0].added_rows == 1
    assert imp_logs[0].updated_rows == 1
    assert imp_logs[0].removed_rows == 1


async def test_apply_diff_with_invalid_token(db):
    with pytest.raises(ValueError):
        await excel_sync.apply_diff(db, "no-such-token", user_id=None)


async def test_row_key_matching_by_brand_model_year(db, tmp_path):
    """Rows without excel_row_id should match on (brand, model, year)."""
    car = Car(
        brand="Peugeot", model="206", year=1395, price=Decimal("450000000"),
        status=CarStatus.published, source=CarSource.excel,
        excel_row_id=None,  # pure brand+model+year match
    )
    db.add(car); await db.commit()

    path = _write_xlsx(
        tmp_path,
        [["peugeot", "206", 1395, "500000000", None, None]],  # case-insensitive match
    )
    rows, warnings = excel_sync.parse_workbook(path)
    diff = await excel_sync.build_diff(db, rows, warnings)
    assert len(diff["updated_cars"]) == 1
    assert diff["removed_cars"] == []
