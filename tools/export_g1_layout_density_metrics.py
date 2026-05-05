# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path

from pypdf import PdfReader

from audit_g1_exam_layout import (
    approx_equal,
    is_answer_slot_position,
    is_objective_option_position,
    text_positions,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PDF_DIR = ROOT / "output" / "pdf"
DEFAULT_OUT = ROOT / "output" / "layout_audit" / "g1_layout_density_metrics.csv"


EXPECTED_COLUMN_PROFILES = {
    (2, "R"): {"min_count": 22, "max_count": 25, "max_gap": 190.0, "min_y": 95.0, "max_y_min": 700.0},
    (3, "L"): {"min_count": 13, "max_count": 16, "max_gap": 190.0, "min_y": 210.0, "max_y_min": 700.0},
    (4, "L"): {"min_count": 1, "max_count": 4, "max_gap": 170.0, "min_y": 420.0, "max_y_min": 560.0},
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


def is_top_level_marker(value: str) -> bool:
    return bool(re.match(r"^(6-8\.|9-11\.|[6-9]\. |10\. |11\. )", value))


def is_density_anchor(value: str) -> bool:
    return is_top_level_marker(value) or is_objective_option_position(value) or is_answer_slot_position(value)


def column_name(x: float) -> str | None:
    if approx_equal(x, 23.16, 4.0):
        return "L"
    if approx_equal(x, 304.44, 4.0):
        return "R"
    return None


def density_score(count_ok: bool, gap_ok: bool, bounds_ok: bool) -> int:
    score = 100
    if not count_ok:
        score -= 35
    if not gap_ok:
        score -= 35
    if not bounds_ok:
        score -= 30
    return max(score, 0)


def row_for_profile(set_id: str, pdf: Path, page_no: int, column: str, y_values: list[float]) -> dict[str, str]:
    profile = EXPECTED_COLUMN_PROFILES[(page_no, column)]
    y_sorted = sorted(y_values, reverse=True)
    gaps = [y_sorted[index] - y_sorted[index + 1] for index in range(len(y_sorted) - 1)]
    count = len(y_sorted)
    max_y = max(y_sorted) if y_sorted else 0.0
    min_y = min(y_sorted) if y_sorted else 0.0
    max_gap = max(gaps) if gaps else 0.0
    used_height = max_y - min_y if y_sorted else 0.0

    count_ok = profile["min_count"] <= count <= profile["max_count"]
    gap_ok = max_gap <= profile["max_gap"]
    bounds_ok = min_y >= profile["min_y"] and max_y >= profile["max_y_min"] and max_y <= 726.0
    status = "PASS" if count_ok and gap_ok and bounds_ok else "FAIL"
    detail_parts: list[str] = []
    if not count_ok:
        detail_parts.append(f"count expected {profile['min_count']}-{profile['max_count']}")
    if not gap_ok:
        detail_parts.append(f"max_gap>{profile['max_gap']}")
    if not bounds_ok:
        detail_parts.append("vertical bounds")

    return {
        "set": set_id,
        "pdf": str(pdf),
        "page": str(page_no),
        "column": column,
        "anchor_count": str(count),
        "used_height_pt": f"{used_height:.1f}",
        "top_y": f"{max_y:.1f}",
        "bottom_y": f"{min_y:.1f}",
        "max_gap_pt": f"{max_gap:.1f}",
        "density_score": str(density_score(count_ok, gap_ok, bounds_ok)),
        "status": status,
        "detail": "; ".join(detail_parts),
    }


def rows_for_set(pdf: Path, set_id: str) -> list[dict[str, str]]:
    reader = PdfReader(str(pdf))
    anchors: dict[tuple[int, str], list[float]] = {}
    for page_index in range(1, len(reader.pages)):
        page_no = page_index + 1
        for x, y, value in text_positions(pdf, page_index):
            column = column_name(x)
            if column is None or not is_density_anchor(value):
                continue
            anchors.setdefault((page_no, column), []).append(y)

    rows: list[dict[str, str]] = []
    for page_no, column in EXPECTED_COLUMN_PROFILES:
        rows.append(row_for_profile(set_id, pdf, page_no, column, anchors.get((page_no, column), [])))
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sets", default="51-62")
    parser.add_argument("--pdf-dir", default=str(DEFAULT_PDF_DIR))
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    args = parser.parse_args()

    rows: list[dict[str, str]] = []
    pdf_dir = Path(args.pdf_dir)
    for set_id in parse_set_range(args.sets):
        pdf = pdf_dir / f"g1_mid_set{set_id}_layout.pdf"
        if not pdf.exists():
            rows.append(
                {
                    "set": set_id,
                    "pdf": str(pdf),
                    "page": "",
                    "column": "",
                    "anchor_count": "",
                    "used_height_pt": "",
                    "top_y": "",
                    "bottom_y": "",
                    "max_gap_pt": "",
                    "density_score": "0",
                    "status": "FAIL",
                    "detail": "missing pdf",
                }
            )
            continue
        rows.extend(rows_for_set(pdf, set_id))

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "set",
        "pdf",
        "page",
        "column",
        "anchor_count",
        "used_height_pt",
        "top_y",
        "bottom_y",
        "max_gap_pt",
        "density_score",
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

