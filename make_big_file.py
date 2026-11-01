# Name: Gielo Andrew L. Semaña
# Section: CJWZ2
# Date: 2026-10-30
import csv
from pathlib import Path


# Generates a CSV file containing one million valid sales records.
def make_big_file():
    data_folder = Path("data")
    incoming_folder = data_folder / "incoming"

    incoming_folder.mkdir(parents=True, exist_ok=True)

    file_path = incoming_folder / "sales_2026-10-01.csv"

    columns = [
        "txn_id",
        "timestamp",
        "branch",
        "sku",
        "qty",
        "unit_price"
    ]

    branches = [
        "BXU-MAIN",
        "BXU-ROBINSONS",
        "CDO-CENTRIO"
    ]

    # Writes each row directly without creating a large list.
    with file_path.open(
        "w", encoding="utf-8", newline=""
    ) as file:

        writer = csv.DictWriter(file, fieldnames=columns)
        writer.writeheader()

        for number in range(1, 1_000_001):
            writer.writerow({
                "txn_id": f"T{number:07d}",
                "timestamp": "2026-10-01T09:15:00",
                "branch": branches[number % 3],
                "sku": f"SKU-{number % 100:03d}",
                "qty": 2,
                "unit_price": "150.00"
            })

    print("Successfully generated 1,000,000 sales records.")
    print("File location:", file_path)


# Runs the file generator.
if __name__ == "__main__":
    make_big_file()
