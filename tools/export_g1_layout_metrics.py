# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import csv
from pathlib import Path

from pypdf import PdfReader

from audit_g1_exam_layout import (
    first_below_same_column,
    find_lead_position,
    has_underlined_grammar_marker,
    is_answer_slot_position,
    is_objective_option_position,
    text_positions,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PDF_DIR = ROOT / "output" / "pdf"
DEFAULT_OUT = ROOT / "output" / "layout_audit" / "g1_layout_binding_metrics.csv"


OBJECTIVE_SPECS = {
    "6.": ("option", 70.0),
    "7.": ("option", 70.0),
    "8.": ("option", 130.0),
    "9.": ("option", 70.0),
    "10.": ("option", 140.0),
}

DEPENDENT_PREDICATES = {
    "option": is_objective_option_position,
    "grammar_body": has_underlined_grammar_marker,
    "answer_slot": is_answer_slot_position,
}


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


def measure_marker(pdf: Path, marker: str, dep_type: str, max_gap: float) -> dict[str, str]:
    page_count = len(PdfReader(str(pdf)).pages)
    lead_marker = f"{marker} " if marker[0].isdigit() else marker
    lead = find_lead_position(pdf, page_count, lead_marker)
    row = {
        "marker": marker,
        "dependent_type": dep_type,
        "max_gap_pt": f"{max_gap:.1f}",
        "status": "FAIL",
        "page": "",
        "lead_x": "",
        "lead_y": "",
        "dependent_y": "",
        "gap_pt": "",
        "detail": "",
    }
    if lead is None:
        row["detail"] = "missing lead"
        return row

    page_index, x, y, _value = lead
    dependent = first_below_same_column(text_positions(pdf, page_index), x, y, DEPENDENT_PREDICATES[dep_type])
    row.update({"page": str(page_index + 1), "lead_x": f"{x:.1f}", "lead_y": f"{y:.1f}"})
    if dependent is None:
        row["detail"] = "missing dependent in same column"
        return row

    _dep_x, dep_y, dep_value = dependent
    gap = y - dep_y
    row.update({"dependent_y": f"{dep_y:.1f}", "gap_pt": f"{gap:.1f}"})
    if gap <= max_gap:
        row["status"] = "PASS"
        row["detail"] = dep_value[:80]
    else:
        row["detail"] = f"gap exceeds limit; dependent={dep_value[:80]}"
    return row


def measure_set(pdf: Path, set_id: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for marker, (dep_type, max_gap) in OBJECTIVE_SPECS.items():
        row = measure_marker(pdf, marker, dep_type, max_gap)
        row["set"] = set_id
        row["pdf"] = str(pdf)
        rows.append(row)

    for marker, dep_type, max_gap in [
        ("11.", "grammar_body", 45.0),
        ("단답형 1.", "answer_slot", 120.0),
        ("단답형 2.", "answer_slot", 150.0),
    ]:
        row = measure_marker(pdf, marker, dep_type, max_gap)
        row["set"] = set_id
        row["pdf"] = str(pdf)
        rows.append(row)
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sets", default="51-62")
    parser.add_argument("--pdf-dir", default=str(DEFAULT_PDF_DIR))
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    args = parser.parse_args()

    pdf_dir = Path(args.pdf_dir)
    out = Path(args.out)
    rows: list[dict[str, str]] = []
    for set_id in parse_set_range(args.sets):
        pdf = pdf_dir / f"g1_mid_set{set_id}_layout.pdf"
        if not pdf.exists():
            rows.append(
                {
                    "set": set_id,
                    "pdf": str(pdf),
                    "marker": "",
                    "dependent_type": "",
                    "max_gap_pt": "",
                    "status": "FAIL",
                    "page": "",
                    "lead_x": "",
                    "lead_y": "",
                    "dependent_y": "",
                    "gap_pt": "",
                    "detail": "missing pdf",
                }
            )
            continue
        rows.extend(measure_set(pdf, set_id))

    out.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "set",
        "pdf",
        "marker",
        "dependent_type",
        "max_gap_pt",
        "status",
        "page",
        "lead_x",
        "lead_y",
        "dependent_y",
        "gap_pt",
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

