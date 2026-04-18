from __future__ import annotations

import argparse
import csv
import re
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from pathlib import Path


PDF_FILENAME_RE = re.compile(
    r"^(?P<department>[A-Z]{2})_"
    r"(?P<system>[A-Z]{2})_"
    r"(?P<subsystem>[A-Z]{3})_"
    r"(?P<doc_type>[A-Z]{2})_"
    r"(?P<serial>[0-9]{4})_"
    r"(?P<title>[A-Za-z0-9]+(?:_[A-Za-z0-9]+)*)_"
    r"(?P<revision>R[0-9]{3})_"
    r"(?P<year>[0-9]{4})_(?P<month>[0-9]{2})_(?P<day>[0-9]{2})\.pdf$"
)

EXPECTED_COLUMNS = [
    "filename",
    "document_family",
    "revision",
    "document_date",
    "language",
    "department_code",
    "system_code",
    "subsystem_code",
    "doc_type_code",
    "serial",
    "title",
    "previous_revision_filename",
    "has_table",
    "has_image",
]

EXPECTED_LANGUAGES = {"en", "tr"}
REVISION_FAMILIES = {
    "AV_FL_NAV_CL_1001_Preflight_Checklist": ["R000", "R001", "R002"],
    "MT_EN_FUE_PR_1002_Engine_Maintenance_Procedure": ["R000", "R001", "R002"],
}


@dataclass(frozen=True)
class PoolRow:
    filename: str
    document_family: str
    revision: str
    document_date: str
    language: str
    department_code: str
    system_code: str
    subsystem_code: str
    doc_type_code: str
    serial: str
    title: str
    previous_revision_filename: str
    has_table: str
    has_image: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate the XDTS PDF test pool.")
    parser.add_argument(
        "--pool-dir",
        default=str(Path(__file__).resolve().parents[1] / "pdf_pool"),
        help="Path to the pdf_pool directory.",
    )
    parser.add_argument(
        "--meta-dir",
        default=str(Path(__file__).resolve().parents[1] / "pdf_pool_meta"),
        help="Path to the pdf_pool metadata directory.",
    )
    parser.add_argument(
        "--manifest-only",
        action="store_true",
        help="Validate README/index.csv contracts without requiring PDF files to exist yet.",
    )
    return parser.parse_args()


def fail(errors: list[str], message: str) -> None:
    errors.append(message)


def validate_date(date_text: str, *, filename: str, errors: list[str]) -> None:
    try:
        year, month, day = [int(part) for part in date_text.split("_")]
        date(year, month, day)
    except Exception:
        fail(errors, f"{filename}: invalid document_date '{date_text}'.")


def load_rows(index_path: Path, errors: list[str]) -> list[PoolRow]:
    if not index_path.exists():
        fail(errors, f"Missing inventory file: {index_path}")
        return []

    with index_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != EXPECTED_COLUMNS:
            fail(errors, f"index.csv columns must be exactly: {', '.join(EXPECTED_COLUMNS)}")
            return []

        rows: list[PoolRow] = []
        for raw_row in reader:
            rows.append(PoolRow(**{column: raw_row[column] for column in EXPECTED_COLUMNS}))
        return rows


def validate_row(row: PoolRow, errors: list[str]) -> None:
    match = PDF_FILENAME_RE.match(row.filename)
    if not match:
        fail(errors, f"{row.filename}: filename does not match the required pattern.")
        return

    extracted = match.groupdict()
    family = (
        f"{extracted['department']}_{extracted['system']}_{extracted['subsystem']}_"
        f"{extracted['doc_type']}_{extracted['serial']}_{extracted['title']}"
    )
    filename_date = f"{extracted['year']}_{extracted['month']}_{extracted['day']}"

    if row.document_family != family:
        fail(errors, f"{row.filename}: document_family does not match filename-derived family.")
    if row.revision != extracted["revision"]:
        fail(errors, f"{row.filename}: revision does not match filename.")
    if row.document_date != filename_date:
        fail(errors, f"{row.filename}: document_date does not match filename.")
    if row.department_code != extracted["department"]:
        fail(errors, f"{row.filename}: department_code does not match filename.")
    if row.system_code != extracted["system"]:
        fail(errors, f"{row.filename}: system_code does not match filename.")
    if row.subsystem_code != extracted["subsystem"]:
        fail(errors, f"{row.filename}: subsystem_code does not match filename.")
    if row.doc_type_code != extracted["doc_type"]:
        fail(errors, f"{row.filename}: doc_type_code does not match filename.")
    if row.serial != extracted["serial"]:
        fail(errors, f"{row.filename}: serial does not match filename.")
    if row.title != extracted["title"]:
        fail(errors, f"{row.filename}: title does not match filename.")
    if row.language not in EXPECTED_LANGUAGES:
        fail(errors, f"{row.filename}: language must be one of {sorted(EXPECTED_LANGUAGES)}.")
    if row.has_table != "true":
        fail(errors, f"{row.filename}: has_table must be 'true'.")
    if row.has_image != "true":
        fail(errors, f"{row.filename}: has_image must be 'true'.")

    validate_date(row.document_date, filename=row.filename, errors=errors)


def validate_revision_families(rows: list[PoolRow], errors: list[str]) -> None:
    rows_by_family: dict[str, list[PoolRow]] = defaultdict(list)
    row_by_filename = {row.filename: row for row in rows}

    for row in rows:
        rows_by_family[row.document_family].append(row)

    for family, family_rows in rows_by_family.items():
        ordered = sorted(family_rows, key=lambda row: (row.revision, row.document_date))
        revisions = [row.revision for row in ordered]
        dates = [row.document_date for row in ordered]

        if len(set(revisions)) != len(revisions):
            fail(errors, f"{family}: duplicate revision entries found in index.csv.")
        if dates != sorted(dates):
            fail(errors, f"{family}: revision dates must increase monotonically.")

        expected_revisions = REVISION_FAMILIES.get(family, ["R000"])
        if revisions != expected_revisions:
            fail(
                errors,
                f"{family}: expected revisions {expected_revisions}, found {revisions}.",
            )

        for index, row in enumerate(ordered):
            expected_previous = "" if index == 0 else ordered[index - 1].filename
            if row.previous_revision_filename != expected_previous:
                fail(
                    errors,
                    f"{row.filename}: previous_revision_filename should be "
                    f"'{expected_previous}'.",
                )
            if row.previous_revision_filename and row.previous_revision_filename not in row_by_filename:
                fail(
                    errors,
                    f"{row.filename}: previous_revision_filename does not exist in index.csv.",
                )


def validate_filesystem(pool_dir: Path, rows: list[PoolRow], errors: list[str]) -> None:
    expected_files = {row.filename for row in rows}
    actual_files = {path.name for path in pool_dir.glob("*.pdf")}

    missing = sorted(expected_files - actual_files)
    unexpected = sorted(actual_files - expected_files)

    if missing:
        fail(errors, f"Missing PDF files: {', '.join(missing)}")
    if unexpected:
        fail(errors, f"Unexpected PDF files in pool: {', '.join(unexpected)}")


def main() -> int:
    args = parse_args()
    pool_dir = Path(args.pool_dir)
    meta_dir = Path(args.meta_dir)
    readme_path = meta_dir / "README.md"
    index_path = meta_dir / "index.csv"
    errors: list[str] = []

    if not pool_dir.exists():
        fail(errors, f"Missing pool directory: {pool_dir}")
    if not meta_dir.exists():
        fail(errors, f"Missing metadata directory: {meta_dir}")
    if not readme_path.exists():
        fail(errors, f"Missing README file: {readme_path}")

    rows = load_rows(index_path, errors)
    if rows:
        filenames = [row.filename for row in rows]
        if len(rows) != 12:
            fail(errors, f"index.csv must contain exactly 12 planned PDF rows; found {len(rows)}.")
        if len(set(filenames)) != len(filenames):
            fail(errors, "index.csv contains duplicate filenames.")

        for row in rows:
            validate_row(row, errors)
        validate_revision_families(rows, errors)

        if not args.manifest_only:
            validate_filesystem(pool_dir, rows, errors)

    if errors:
        print("XDTS PDF pool validation failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    mode = "manifest-only" if args.manifest_only else "full"
    print(f"XDTS PDF pool validation passed ({mode}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
