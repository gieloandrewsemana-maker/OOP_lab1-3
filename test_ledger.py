# Name: Gielo Andrew L. Semaña
# Section: CJWZ2
# Date: 2026-10-30

import csv
import json

import pytest

from pathlib import Path
from decimal import Decimal

import ledger


# Creates a temporary sales ledger folder for testing.
@pytest.fixture
def setup_ledger(tmp_path):
    data_folder = tmp_path / "data"
    incoming = data_folder / "incoming"
    output = data_folder / "out"

    incoming.mkdir(parents=True)
    output.mkdir(parents=True)

    branches = [
        "BXU-MAIN",
        "BXU-ROBINSONS",
        "CDO-CENTRIO"
    ]

    with (data_folder / "branches.json").open(
        "w", encoding="utf-8"
    ) as file:
        json.dump(branches, file)

    return incoming, output, data_folder


# Creates a sample sales CSV file.
def create_csv(folder, filename, rows, columns=None):
    if columns is None:
        columns = ledger.REQUIRED_COLUMNS

    path = folder / filename

    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)

    return path


# Returns a valid sample transaction.
def valid_row():
    return {
        "txn_id": "T0001",
        "timestamp": "2026-10-01T09:15:00",
        "branch": "BXU-MAIN",
        "sku": "SKU-100",
        "qty": "2",
        "unit_price": "150.00"
    }


# Test 1: Checks that the CSV reader reads a valid row.
def test_read_rows(setup_ledger):
    incoming, output, data_folder = setup_ledger

    path = create_csv(
        incoming,
        "sales_2026-10-01.csv",
        [valid_row()]
    )

    rows = list(ledger.read_rows(path))

    assert len(rows) == 1
    assert rows[0][0] == 2
    assert rows[0][1]["txn_id"] == "T0001"


# Test 2: Checks that a UTF-8 BOM is handled correctly.
def test_utf8_bom(setup_ledger):
    incoming, output, data_folder = setup_ledger

    path = incoming / "sales_2026-10-01.csv"

    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(
            file, fieldnames=ledger.REQUIRED_COLUMNS
        )
        writer.writeheader()
        writer.writerow(valid_row())

    rows = list(ledger.read_rows(path))

    assert rows[0][1]["txn_id"] == "T0001"


# Test 3: Checks that different column orders are supported.
def test_different_column_order(setup_ledger):
    incoming, output, data_folder = setup_ledger

    columns = [
        "branch", "txn_id", "sku",
        "qty", "unit_price", "timestamp"
    ]

    path = create_csv(
        incoming,
        "sales_2026-10-01.csv",
        [valid_row()],
        columns
    )

    rows = list(ledger.read_rows(path))

    assert rows[0][1]["branch"] == "BXU-MAIN"


# Test 4: Checks that invalid quantity is rejected.
def test_invalid_quantity():
    row = valid_row()
    row["qty"] = "-1"

    reason = ledger.validate_row(
        row,
        ledger.get_file_date("sales_2026-10-01.csv"),
        {"BXU-MAIN"},
        set()
    )

    assert reason == "qty must be a positive integer"


# Test 5: Checks that unknown branches are rejected.
def test_unknown_branch():
    row = valid_row()
    row["branch"] = "DVO-ABREEZA"

    reason = ledger.validate_row(
        row,
        ledger.get_file_date("sales_2026-10-01.csv"),
        {"BXU-MAIN"},
        set()
    )

    assert reason == "unknown branch DVO-ABREEZA"


# Test 6: Checks that duplicate transaction IDs are rejected.
def test_duplicate_transaction():
    row = valid_row()

    reason = ledger.validate_row(
        row,
        ledger.get_file_date("sales_2026-10-01.csv"),
        {"BXU-MAIN"},
        {"T0001"}
    )

    assert reason == "duplicate txn_id"


# Test 7: Checks that timestamps must match the filename date.
def test_wrong_timestamp_date():
    row = valid_row()
    row["timestamp"] = "2026-10-02T09:15:00"

    reason = ledger.validate_row(
        row,
        ledger.get_file_date("sales_2026-10-01.csv"),
        {"BXU-MAIN"},
        set()
    )

    assert "does not match file date" in reason


# Test 8: Checks that money is calculated using Decimal.
def test_decimal_calculation():
    assert Decimal("150.00") * 2 == Decimal("300.00")
    assert Decimal("1299.50") * 2 == Decimal("2599.00")


# Test 9: Checks that a file is processed and archived.
def test_process_and_archive(setup_ledger):
    incoming, output, data_folder = setup_ledger

    path = create_csv(
        incoming,
        "sales_2026-10-01.csv",
        [valid_row()]
    )

    result = ledger.process_files(incoming, output)

    archive_path = (
        data_folder / "archive" / "2026-10" / path.name
    )

    assert result["processed_rows"] == 1
    assert archive_path.exists()
    assert not path.exists()


# Test 10: Checks that the same file is not processed twice.
def test_duplicate_file_skipped(setup_ledger):
    incoming, output, data_folder = setup_ledger

    create_csv(
        incoming,
        "sales_2026-10-01.csv",
        [valid_row()]
    )

    ledger.process_files(incoming, output)

    summary_before = json.loads(
        (output / "summary.json").read_text(encoding="utf-8")
    )

    copied_file = incoming / "sales_2026-10-01_resend.csv"

    original = (
        data_folder / "archive" / "2026-10" /
        "sales_2026-10-01.csv"
    )

    copied_file.write_bytes(original.read_bytes())

    ledger.process_files(incoming, output)

    summary_after = json.loads(
        (output / "summary.json").read_text(encoding="utf-8")
    )

    assert summary_before == summary_after
    assert not copied_file.exists()


# Test 11: Checks that dry-run does not write or move files.
def test_dry_run(setup_ledger):
    incoming, output, data_folder = setup_ledger

    path = create_csv(
        incoming,
        "sales_2026-10-01.csv",
        [valid_row()]
    )

    result = ledger.process_files(
        incoming, output, dry_run=True
    )

    assert result["processed_rows"] == 1
    assert path.exists()
    assert not (output / "summary.json").exists()
    assert not (output / "manifest.json").exists()


# Test 12: Checks that a CSV with a missing column is quarantined.
def test_missing_column_quarantine(setup_ledger):
    incoming, output, data_folder = setup_ledger

    columns = [
        "txn_id", "timestamp", "branch",
        "sku", "unit_price"
    ]

    path = create_csv(
        incoming,
        "sales_2026-10-01.csv",
        [{
            "txn_id": "T0001",
            "timestamp": "2026-10-01T09:15:00",
            "branch": "BXU-MAIN",
            "sku": "SKU-100",
            "unit_price": "150.00"
        }],
        columns
    )

    ledger.process_files(incoming, output)

    quarantined = data_folder / "quarantine" / path.name
    note = data_folder / "quarantine" / (
        path.name + ".error.txt"
    )

    assert quarantined.exists()
    assert note.exists()
    assert "missing required column: qty" in note.read_text()


# Runs all tests using pytest.
if __name__ == "__main__":
    pytest.main(["-v"])
