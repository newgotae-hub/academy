# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import csv
import hashlib
from pathlib import Path

from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PDF_DIR = ROOT / "output" / "pdf"
DEFAULT_AUDIT_DIR = ROOT / "output" / "layout_audit"
DEFAULT_OUT = DEFAULT_AUDIT_DIR / "g1_layout_package_manifest.csv"


def parse_set_range(value: str) -> list[str]:
    sets: list[str] = []
    for part in value.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            start, end = part.split("-", 1)
            sets.extend(str(i) for i in range(int(start), int(end) + 1))
        else:
            sets.append(str(int(part)))
    return sets


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def row_for_set(set_id: str, pdf_dir: Path, audit_dir: Path, expected_pages: int) -> dict[str, str]:
    pdf = pdf_dir / f"g1_mid_set{set_id}_layout.pdf"
    audit_report = audit_dir / f"g1_mid_set{set_id}_layout_audit.md"
    row = {
        "set": set_id,
        "pdf": str(pdf),
        "audit_report": str(audit_report),
        "exists": "False",
        "pages": "",
        "bytes": "",
        "sha256": "",
        "audit_exists": str(audit_report.exists()),
        "status": "FAIL",
        "detail": "",
    }
    if not pdf.exists():
        row["detail"] = "missing pdf"
        return row

    pages = len(PdfReader(str(pdf)).pages)
    row.update(
        {
            "exists": "True",
            "pages": str(pages),
            "bytes": str(pdf.stat().st_size),
            "sha256": sha256_file(pdf),
        }
    )
    failures: list[str] = []
    if pages != expected_pages:
        failures.append(f"pages={pages},expected={expected_pages}")
    if not audit_report.exists():
        failures.append("missing audit report")
    row["status"] = "PASS" if not failures else "FAIL"
    row["detail"] = "; ".join(failures)
    return row


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sets", default="51-62")
    parser.add_argument("--pdf-dir", default=str(DEFAULT_PDF_DIR))
    parser.add_argument("--audit-dir", default=str(DEFAULT_AUDIT_DIR))
    parser.add_argument("--expected-pages", type=int, default=4)
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    args = parser.parse_args()

    pdf_dir = Path(args.pdf_dir)
    audit_dir = Path(args.audit_dir)
    rows = [row_for_set(set_id, pdf_dir, audit_dir, args.expected_pages) for set_id in parse_set_range(args.sets)]

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "set",
        "pdf",
        "audit_report",
        "exists",
        "pages",
        "bytes",
        "sha256",
        "audit_exists",
        "status",
        "detail",
    ]
    with out.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    failures = [row for row in rows if row["status"] != "PASS"]
    print(f"rows={len(rows)} pass={len(rows) - len(failures)} fail={len(failures)} out={out}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())

