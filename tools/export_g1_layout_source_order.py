# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import csv
from pathlib import Path

from audit_g1_exam_layout import (
    DEFAULT_SOURCE,
    digest_normalize,
    extract_source_block,
    full_text,
    read_texts,
    source_digest_snippets,
)
from export_g1_layout_source_trace import parse_set_range


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PDF_DIR = ROOT / "output" / "pdf"
DEFAULT_OUT = ROOT / "output" / "layout_audit" / "g1_layout_source_order.csv"
DEFAULT_DETAIL_OUT = ROOT / "output" / "layout_audit" / "g1_layout_source_order_detail.csv"


def ordered_detail_rows_for_set(set_id: str, source: Path, pdf_dir: Path) -> list[dict[str, str]]:
    pdf = pdf_dir / f"g1_mid_set{set_id}_layout.pdf"
    base = {
        "set": set_id,
        "source": str(source),
        "pdf": str(pdf),
    }
    if not pdf.exists():
        return [
            {
                **base,
                "snippet_index": "",
                "start_offset": "",
                "end_offset": "",
                "previous_end_offset": "",
                "ordered": "0",
                "status": "FAIL",
                "snippet": "",
                "detail": "missing pdf",
            }
        ]
    source_block = extract_source_block(source, set_id)
    if source_block is None:
        return [
            {
                **base,
                "snippet_index": "",
                "start_offset": "",
                "end_offset": "",
                "previous_end_offset": "",
                "ordered": "0",
                "status": "FAIL",
                "snippet": "",
                "detail": "missing source block",
            }
        ]

    snippets = source_digest_snippets(source_block)
    normalized_pdf = digest_normalize(full_text(read_texts(pdf)))
    cursor = 0
    rows: list[dict[str, str]] = []
    for index, snippet in enumerate(snippets, start=1):
        previous_end = cursor
        start = normalized_pdf.find(snippet, cursor)
        if start >= 0:
            end = start + len(snippet)
            cursor = end
            rows.append(
                {
                    **base,
                    "snippet_index": str(index),
                    "start_offset": str(start),
                    "end_offset": str(end),
                    "previous_end_offset": str(previous_end),
                    "ordered": "1",
                    "status": "PASS",
                    "snippet": snippet,
                    "detail": "ordered",
                }
            )
            continue

        earlier = normalized_pdf.find(snippet)
        rows.append(
            {
                **base,
                "snippet_index": str(index),
                "start_offset": str(earlier) if earlier >= 0 else "",
                "end_offset": str(earlier + len(snippet)) if earlier >= 0 else "",
                "previous_end_offset": str(previous_end),
                "ordered": "0",
                "status": "FAIL",
                "snippet": snippet,
                "detail": "found before expected cursor" if earlier >= 0 else "missing snippet",
            }
        )
    return rows


def row_for_set(set_id: str, source: Path, pdf_dir: Path) -> dict[str, str]:
    detail_rows = ordered_detail_rows_for_set(set_id, source, pdf_dir)
    snippet_rows = [row for row in detail_rows if row["snippet_index"]]
    failures = [row for row in snippet_rows if row["status"] != "PASS"]
    expected = len(snippet_rows)
    ordered = expected - len(failures)
    first_bad = failures[0]["snippet_index"] if failures else ""
    return {
        "set": set_id,
        "source": str(source),
        "pdf": str(pdf_dir / f"g1_mid_set{set_id}_layout.pdf"),
        "expected_snippets": str(expected),
        "ordered_snippets": str(ordered),
        "out_of_order_snippets": str(len(failures)),
        "first_bad_snippet": first_bad,
        "status": "PASS" if expected >= 20 and not failures else "FAIL",
        "detail": "source snippets preserve PDF extraction order" if expected >= 20 and not failures else "source order failure",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sets", default="51-62")
    parser.add_argument("--source", default=str(DEFAULT_SOURCE))
    parser.add_argument("--pdf-dir", default=str(DEFAULT_PDF_DIR))
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument("--detail-out", default=str(DEFAULT_DETAIL_OUT))
    args = parser.parse_args()

    source = Path(args.source)
    pdf_dir = Path(args.pdf_dir)
    sets = parse_set_range(args.sets)
    rows = [row_for_set(set_id, source, pdf_dir) for set_id in sets]
    detail_rows = [row for set_id in sets for row in ordered_detail_rows_for_set(set_id, source, pdf_dir)]

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "set",
        "source",
        "pdf",
        "expected_snippets",
        "ordered_snippets",
        "out_of_order_snippets",
        "first_bad_snippet",
        "status",
        "detail",
    ]
    with out.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    detail_out = Path(args.detail_out)
    detail_out.parent.mkdir(parents=True, exist_ok=True)
    detail_fieldnames = [
        "set",
        "source",
        "pdf",
        "snippet_index",
        "start_offset",
        "end_offset",
        "previous_end_offset",
        "ordered",
        "status",
        "snippet",
        "detail",
    ]
    with detail_out.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=detail_fieldnames)
        writer.writeheader()
        writer.writerows(detail_rows)

    failures = [row for row in rows if row["status"] != "PASS"]
    detail_failures = [row for row in detail_rows if row["status"] != "PASS"]
    print(
        f"rows={len(rows)} pass={len(rows) - len(failures)} fail={len(failures)} out={out} "
        f"detail_rows={len(detail_rows)} detail_fail={len(detail_failures)} detail_out={detail_out}"
    )
    return 1 if failures or detail_failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
