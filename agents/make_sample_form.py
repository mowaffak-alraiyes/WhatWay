"""Sample Google Forms-style CSV for clinic discovery smoke tests."""

import csv
from pathlib import Path

ROWS = [
    ["Clinic Name", "Address", "ZIP", "Phone", "Services", "Languages", "Hours", "Notes"],
    [
        "South Side Community Dental Demo",
        "1234 W 63rd St, Chicago, IL 60629",
        "60629",
        "(773) 555-0199",
        "dental, cleanings, extractions",
        "English, Spanish",
        "Mon-Fri 9-5",
        "Sample row for agent demo — not a real clinic",
    ],
    [
        "Alivio Medical Center Dental at 63rd St.",
        "4255 W 63rd St, Chicago, IL 60629",
        "60629",
        "",
        "dental",
        "English, Spanish",
        "",
        "Should be skipped as duplicate of existing JSON name",
    ],
]

path = Path(__file__).resolve().parent.parent / "data" / "sample_clinic_form.csv"
path.parent.mkdir(parents=True, exist_ok=True)
with path.open("w", newline="", encoding="utf-8") as f:
    csv.writer(f).writerows(ROWS)
print(f"Wrote {path}")
