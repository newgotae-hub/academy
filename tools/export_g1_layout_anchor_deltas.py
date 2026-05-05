# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import csv
from pathlib import Path

from pypdf import PdfReader

from audit_g1_exam_layout import approx_equal, find_text_positions, text_runs


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PDF_DIR = ROOT / "output" / "pdf"
DEFAULT_OUT = ROOT / "output" / "layout_audit" / "g1_layout_anchor_deltas.csv"


COVER_ANCHORS = [
    ("cover_title_year", "2025학년도", 190.0, 717.3, 15.0, 3.0, 650.0),
    ("cover_title_term", "1학기", 206.0, 675.4, 15.0, 3.0, 630.0),
    ("cover_subject", "공통영어1", 205.0, 596.7, 15.0, 3.0, 550.0),
    ("cover_date", "일 시", 166.0, 520.0, 20.0, 3.0, 480.0),
    ("cover_notice", "시험이 시작", 153.0, 434.9, 25.0, 3.0, 400.0),
    ("cover_print", "인쇄", 267.0, 415.6, 20.0, 3.0, 390.0),
]

BODY_ANCHORS = [
    ("body_6_8_title", 2, "6-8.", 304.44, 716.0, 3.0, 3.0),
    ("body_q6", 2, "6.", 304.44, 540.1, 3.0, 30.0),
    ("body_9_11_title", 3, "9-11.", 23.16, 716.0, 3.0, 6.0),
    ("body_short2", 4, "단답형 2.", 23.16, 715.9, 3.0, 6.0),
]


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


def choose_position(pdf: Path, page_index: int, needle: str, min_y: float | None = None) -> tuple[float, float] | None:
    positions = find_text_positions(pdf, page_index, needle)
    if min_y is not None:
        positions = [(x, y) for x, y in positions if y >= min_y]
    if not positions:
        return None
    return max(positions, key=lambda pos: pos[1])


def footer_rows(pdf: Path, set_id: str, page_count: int) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for page_index in range(page_count):
        page_no = page_index + 1
        label = f"({page_no}/{page_count})"
        runs = text_runs(pdf, page_index)
        footer_specs = [
            ("footer_page_label", label, 288.0, 31.2, 18.0, 2.0),
            ("footer_school", "광영여자고등학교", 437.0, 31.2, 12.0, 2.0),
            ("footer_school_en", "Kwangyoung Girls High School", 503.2, 26.3, 12.0, 2.0),
        ]
        for name, needle, expected_x, expected_y, tol_x, tol_y in footer_specs:
            candidates = [(x, y) for x, y, _font_size, value in runs if needle in value and y < 50.0]
            actual = candidates[0] if candidates else None
            rows.append(make_row(set_id, pdf, name, page_no, expected_x, expected_y, tol_x, tol_y, actual))
    return rows


def make_row(
    set_id: str,
    pdf: Path,
    anchor: str,
    page_no: int,
    expected_x: float,
    expected_y: float,
    tolerance_x: float,
    tolerance_y: float,
    actual: tuple[float, float] | None,
) -> dict[str, str]:
    if actual is None:
        return {
            "set": set_id,
            "pdf": str(pdf),
            "anchor": anchor,
            "page": str(page_no),
            "expected_x": f"{expected_x:.2f}",
            "expected_y": f"{expected_y:.2f}",
            "actual_x": "",
            "actual_y": "",
            "delta_x": "",
            "delta_y": "",
            "status": "FAIL",
            "detail": "missing",
        }
    actual_x, actual_y = actual
    delta_x = actual_x - expected_x
    delta_y = actual_y - expected_y
    status = "PASS" if approx_equal(actual_x, expected_x, tolerance_x) and approx_equal(actual_y, expected_y, tolerance_y) else "FAIL"
    return {
        "set": set_id,
        "pdf": str(pdf),
        "anchor": anchor,
        "page": str(page_no),
        "expected_x": f"{expected_x:.2f}",
        "expected_y": f"{expected_y:.2f}",
        "actual_x": f"{actual_x:.2f}",
        "actual_y": f"{actual_y:.2f}",
        "delta_x": f"{delta_x:.2f}",
        "delta_y": f"{delta_y:.2f}",
        "status": status,
        "detail": "",
    }


def rows_for_set(pdf: Path, set_id: str) -> list[dict[str, str]]:
    page_count = len(PdfReader(str(pdf)).pages)
    rows: list[dict[str, str]] = []

    for name, needle, expected_x, expected_y, tol_x, tol_y, min_y in COVER_ANCHORS:
        actual = choose_position(pdf, 0, needle, min_y)
        rows.append(make_row(set_id, pdf, name, 1, expected_x, expected_y, tol_x, tol_y, actual))

    for name, page_no, needle, expected_x, expected_y, tol_x, tol_y in BODY_ANCHORS:
        page_index = page_no - 1
        actual = choose_position(pdf, page_index, needle) if page_index < page_count else None
        rows.append(make_row(set_id, pdf, name, page_no, expected_x, expected_y, tol_x, tol_y, actual))

    rows.extend(footer_rows(pdf, set_id, page_count))
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
                    "anchor": "",
                    "page": "",
                    "expected_x": "",
                    "expected_y": "",
                    "actual_x": "",
                    "actual_y": "",
                    "delta_x": "",
                    "delta_y": "",
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
        "anchor",
        "page",
        "expected_x",
        "expected_y",
        "actual_x",
        "actual_y",
        "delta_x",
        "delta_y",
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
