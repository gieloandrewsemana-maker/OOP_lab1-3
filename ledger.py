# Name: Gielo Andrew L. Semaña
# Section: CJWZ2
# Date: 2026-10-30

import argparse
import csv
import json
import hashlib
import os
import re
import tempfile
import time
import tracemalloc

from pathlib import Path
from decimal import Decimal, InvalidOperation
from datetime import datetime
from collections import defaultdict


REQUIRED_COLUMNS = [
    "txn_id", "timestamp", "branch",
    "sku", "qty", "unit_price"
]


# Raised when a CSV file does not contain required columns.
class MissingColumnError(Exception):
    pass


# Reads a CSV file one row at a time.
def read_rows(path):
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)

        if reader.fieldnames is None:
            raise MissingColumnError("missing CSV header")

        missing = [
            column for column in REQUIRED_COLUMNS
            if column not in reader.fieldnames
        ]

        if missing:
            raise MissingColumnError(
                f"missing required column: {missing[0]}"
            )

        for line_no, row in enumerate(reader, start=2):
            if not row or all(
                value is None or not value.strip()
                for value in row.values()
            ):
                continue

            yield line_no, row


# Calculates the SHA-256 hash of a file in 64 KB chunks.
def get_file_hash(path):
    hasher = hashlib.sha256()

    with path.open("rb") as file:
        while True:
            chunk = file.read(65536)

            if not chunk:
                break

            hasher.update(chunk)

    return hasher.hexdigest()


# Loads JSON data or returns a default value if the file is missing.
def load_json(path, default):
    if not path.exists():
        return default

    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


# Writes data to a temporary file and replaces the original safely.
def atomic_write(path, writer, binary=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = None

    try:
        with tempfile.NamedTemporaryFile(
            mode="wb" if binary else "w",
            encoding=None if binary else "utf-8",
            newline=None if binary else "",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)
            writer(temporary_file)

        os.replace(temporary_path, path)
        temporary_path = None

    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()


# Saves JSON data using an atomic write.
def save_json(path, data):
    def write_data(file):
        json.dump(data, file, indent=4)

    atomic_write(path, write_data)


# Saves CSV rows using an atomic write.
def save_csv(path, fieldnames, rows):
    def write_data(file):
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    atomic_write(path, write_data)


# Gets the sales date from the CSV filename.
def get_file_date(filename):
    match = re.search(r"(\d{4}-\d{2}-\d{2})", filename)

    if not match:
        raise ValueError("filename does not contain a valid date")

    return datetime.strptime(match.group(1), "%Y-%m-%d").date()


# Checks a sales row and returns its first error reason.
def validate_row(row, file_date, branches, used_transactions):
    transaction_id = (row.get("txn_id") or "").strip()

    if not transaction_id:
        return "missing txn_id"

    if transaction_id in used_transactions:
        return "duplicate txn_id"

    try:
        quantity = int((row.get("qty") or "").strip())

        if quantity <= 0:
            return "qty must be a positive integer"

    except ValueError:
        return "qty must be a positive integer"

    try:
        price_text = (row.get("unit_price") or "").strip()
        price = Decimal(price_text)

        if not price.is_finite() or price < 0:
            return "unit_price must be a non-negative Decimal"

        if price.as_tuple().exponent < -2:
            return "unit_price must have at most 2 decimal places"

    except InvalidOperation:
        return "unit_price must be a non-negative Decimal"

    try:
        timestamp = datetime.fromisoformat(
            (row.get("timestamp") or "").strip()
        )

        if timestamp.date() != file_date:
            return (
                f"timestamp date {timestamp.date()} "
                f"does not match file date {file_date}"
            )

    except ValueError:
        return "invalid ISO 8601 timestamp"

    branch = (row.get("branch") or "").strip()

    if branch not in branches:
        return f"unknown branch {branch}"

    return None


# Creates the initial cumulative sales summary.
def create_summary():
    return {
        "branch_totals": {},
        "daily_totals": {},
        "sku_totals": {},
        "processed_rows": 0,
        "rejected_rows": 0,
        "processed_files": [],
        "txn_ids": []
    }


# Updates sales totals using exact Decimal calculations.
def update_summary(summary, row, file_date):
    branch = row["branch"].strip()
    sku = row["sku"].strip()
    quantity = int(row["qty"].strip())
    price = Decimal(row["unit_price"].strip())
    revenue = price * quantity
    day = str(file_date)

    branch_totals = summary["branch_totals"]
    daily_totals = summary["daily_totals"]
    sku_totals = summary["sku_totals"]

    branch_totals[branch] = str(
        Decimal(branch_totals.get(branch, "0.00")) + revenue
    )

    daily_totals[day] = str(
        Decimal(daily_totals.get(day, "0.00")) + revenue
    )

    sku_totals[sku] = str(
        Decimal(sku_totals.get(sku, "0.00")) + revenue
    )

    summary["processed_rows"] += 1
    summary["txn_ids"].append(row["txn_id"].strip())


# Loads the approved branch names.
def load_branches(data_folder):
    path = data_folder / "branches.json"
    branches = load_json(path, [])

    if not isinstance(branches, list):
        raise ValueError("branches.json must contain a list")

    return set(branches)


# Creates the rejects CSV header using the original columns.
def get_reject_headers(original_columns):
    return list(original_columns) + [
        "source_file", "line_no", "reason"
    ]


# Processes all CSV files and updates the sales report.
def process_files(input_folder, output_folder, dry_run=False):
    input_folder = Path(input_folder)
    output_folder = Path(output_folder)
    data_folder = input_folder.parent

    branches = load_branches(data_folder)

    summary_path = output_folder / "summary.json"
    manifest_path = output_folder / "manifest.json"
    rejects_path = output_folder / "rejects.csv"

    summary = load_json(summary_path, create_summary())
    manifest = load_json(manifest_path, {})

    used_transactions = set(summary.get("txn_ids", []))

    if isinstance(manifest, list):
        manifest = {
            item["name"]: item["sha256"]
            for item in manifest
        }

    known_hashes = set(manifest.values())

    rejected_rows = []
    rejected_messages = []
    processed_count = 0
    skipped_count = 0
    quarantined_count = 0
    valid_count = 0
    archive_moves = []
    quarantine_moves = []

    files = sorted(input_folder.glob("*.csv"))

    for path in files:
        try:
            file_hash = get_file_hash(path)

            if file_hash in known_hashes:
                print(f"Skipped: {path.name} (already processed)")
                skipped_count += 1
                continue

            file_date = get_file_date(path.name)

            original_columns = None
            file_rejects = []
            file_valid_count = 0

            for line_no, row in read_rows(path):
                if original_columns is None:
                    original_columns = list(row.keys())

                reason = validate_row(
                    row, file_date, branches, used_transactions
                )

                if reason:
                    reject = dict(row)
                    reject["source_file"] = path.name
                    reject["line_no"] = line_no
                    reject["reason"] = reason

                    file_rejects.append(reject)
                    rejected_messages.append(
                        f"{path.name}:{line_no} "
                        f"{row.get('txn_id', '')} {reason}"
                    )

                else:
                    update_summary(summary, row, file_date)
                    used_transactions.add(row["txn_id"].strip())
                    file_valid_count += 1

            if original_columns is None:
                raise MissingColumnError("missing CSV header")

            rejected_rows.extend(file_rejects)

            summary["rejected_rows"] += len(file_rejects)
            valid_count += file_valid_count

            summary["processed_files"].append(path.name)

            manifest[path.name] = file_hash
            known_hashes.add(file_hash)

            processed_count += 1

            archive_moves.append((
                path,
                data_folder / "archive" / file_date.strftime("%Y-%m")
            ))

        except (
            UnicodeDecodeError,
            PermissionError,
            MissingColumnError,
            ValueError,
            csv.Error
        ) as error:
            quarantined_count += 1

            print(f"Quarantined: {path.name} - {error}")

            quarantine_moves.append((path, str(error)))

    # Displays the processing report.
    print("\n========== SALES LEDGER REPORT ==========")
    print(f"Processed files : {processed_count} Skipped: "
          f"{skipped_count} Quarantined: {quarantined_count}")
    print(f"Valid rows : {valid_count} Rejected rows: "
          f"{len(rejected_rows)}")

    print("\nRejected:")
    for message in rejected_messages:
        print(message)

    print("\nBranch totals:")
    for branch, total in sorted(summary["branch_totals"].items()):
        print(f"{branch} {Decimal(total):,.2f}")

    print("\nDaily totals:")
    for day, total in sorted(summary["daily_totals"].items()):
        print(f"{day} {Decimal(total):,.2f}")

    print("\nTop SKUs:")
    top_skus = sorted(
        summary["sku_totals"].items(),
        key=lambda item: (-Decimal(item[1]), item[0])
    )[:5]

    for sku, total in top_skus:
        print(f"{sku} {Decimal(total):,.2f}")

    grand_total = sum(
        (Decimal(value) for value in summary["branch_totals"].values()),
        Decimal("0.00")
    )

    print(f"\nGrand total : PHP {grand_total:,.2f}")

    if dry_run:
        print("\nDRY RUN: No files were written or moved.")
        return summary

    # Writes the cumulative rejects file.
    if rejected_rows:
        old_rows = []

        if rejects_path.exists():
            with rejects_path.open(
                "r", encoding="utf-8-sig", newline=""
            ) as file:
                old_rows = list(csv.DictReader(file))

        all_rows = old_rows + rejected_rows
        headers = get_reject_headers(
            list(rejected_rows[0].keys())[:-3]
        )

        if old_rows:
            headers = list(old_rows[0].keys())

        save_csv(rejects_path, headers, all_rows)

    # Saves the cumulative summary and manifest.
    save_json(summary_path, summary)
    save_json(manifest_path, manifest)

    # Moves processed files to their archive folders.
    for source, archive_folder in archive_moves:
        archive_folder.mkdir(parents=True, exist_ok=True)
        destination = archive_folder / source.name
        source.replace(destination)

    # Moves unreadable files to quarantine and writes error notes.
    quarantine_folder = data_folder / "quarantine"
    quarantine_folder.mkdir(parents=True, exist_ok=True)

    for source, reason in quarantine_moves:
        destination = quarantine_folder / source.name

        if destination.exists():
            destination = quarantine_folder / (
                f"{source.stem}_{time.time_ns()}{source.suffix}"
            )

        source.replace(destination)

        note_path = destination.with_name(
            destination.name + ".error.txt"
        )

        atomic_write(
            note_path,
            lambda file, message=reason: file.write(message)
        )

    return summary


# Starts the command-line program and reads its arguments.
def main():
    parser = argparse.ArgumentParser(
        description="Multi-Branch Sales Ledger"
    )

    parser.add_argument(
        "--input",
        type=Path,
        default=Path("data/incoming")
    )

    parser.add_argument(
        "--out",
        type=Path,
        default=Path("data/out")
    )

    parser.add_argument(
        "--dry-run",
        action="store_true"
    )

    args = parser.parse_args()

    process_files(
        args.input,
        args.out,
        args.dry_run
    )


# Runs the program when this file is opened directly.
if __name__ == "__main__":
    main()
