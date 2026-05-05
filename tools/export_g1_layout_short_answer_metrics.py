# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import csv
from pathlib import Path

from audit_g1_exam_layout import (
    approx_equal,
    find_lead_position,
    is_answer_slot_position,
    text_positions,
)
from export_g1_layout_source_trace import parse_set_range


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PDF_DIR = ROOT / "output" / "pdf"
DEFAULT_OUT = ROOT / "output" / "layout_audit" / "g1_layout_short_answer_metrics.csv"
SHORT1_MARKER = "\ub2e8\ub2f5\ud615 1."
SHORT2_MARKER = "\ub2e8\ub2f5\ud615 2."
SLOT_LABELS = ["(A)", "(B)", "(C)", "(D)"]


def row_for_block(pdf: Path, set_id: str, marker: str, slot_type: str) -> dict[str, str]:
    row = {
        "set": set_id,
        "pdf": str(pdf),
        "marker": marker,
        "page": "",
        "column_x": "",
        "lead_y": "",
        "slot_count": "0",
        "slot_top_y": "",
        "slot_bottom_y": "",
        "block_height_pt": "",
        "status": "FAIL",
        "detail": "",
    }
    if not pdf.exists():
        row["detail"] = "missing pdf"
        return row
    lead = find_lead_position(pdf, 4, marker)
    if lead is None:
        row["detail"] = "missing lead"
        return row
    page_index, x, y, _value = lead
    same_column_slots = [
        (slot_y, value)
        for slot_x, slot_y, value in text_positions(pdf, page_index)
        if approx_equal(slot_x, x, 3.0) and slot_y < y - 2.0 and is_answer_slot_position(value)
    ]
    same_column_slots.sort(key=lambda item: item[0], reverse=True)
    if slot_type == "correction":
        slots = [(slot_y, value) for slot_y, value in same_column_slots if "->" in value]
        failures = []
        if len(slots) != 4:
            failures.append(f"slots={len(slots)}")
        for label in SLOT_LABELS:
            if sum(1 for _slot_y, value in slots if value.startswith(label)) != 1:
                failures.append(f"{label}=bad")
        if len(slots) == 4 and any(slots[i][0] <= slots[i + 1][0] for i in range(3)):
            failures.append("slot-y-order")
    else:
        slots = [
            (slot_y, value)
            for slot_y, value in same_column_slots
            if "->" not in value and all(label in value for label in SLOT_LABELS)
        ]
        failures = [] if len(slots) == 1 else [f"summary-slots={len(slots)}"]

    slot_ys = [slot_y for slot_y, _value in slots]
    row.update(
        {
            "page": str(page_index + 1),
            "column_x": f"{x:.1f}",
            "lead_y": f"{y:.1f}",
            "slot_count": str(len(slots)),
            "slot_top_y": f"{max(slot_ys):.1f}" if slot_ys else "",
            "slot_bottom_y": f"{min(slot_ys):.1f}" if slot_ys else "",
            "block_height_pt": f"{(y - min(slot_ys)):.1f}" if slot_ys else "",
            "status": "PASS" if not failures else "FAIL",
            "detail": "short-answer block envelope captured" if not failures else "; ".join(failures),
        }
    )
    return row


def rows_for_set(pdf: Path, set_id: str) -> list[dict[str, str]]:
    return [
        row_for_block(pdf, set_id, SHORT1_MARKER, "correction"),
        row_for_block(pdf, set_id, SHORT2_MARKER, "summary"),
    ]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sets", default="51-62")
    parser.add_argument("--pdf-dir", default=str(DEFAULT_PDF_DIR))
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    args = parser.parse_args()

    pdf_dir = Path(args.pdf_dir)
    rows = [
        row
        for set_id in parse_set_range(args.sets)
        for row in rows_for_set(pdf_dir / f"g1_mid_set{set_id}_layout.pdf", set_id)
    ]

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "set",
        "pdf",
        "marker",
        "page",
        "column_x",
        "lead_y",
        "slot_count",
        "slot_top_y",
        "slot_bottom_y",
        "block_height_pt",
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
