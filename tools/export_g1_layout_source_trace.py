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


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PDF_DIR = ROOT / "output" / "pdf"
DEFAULT_OUT = ROOT / "output" / "layout_audit" / "g1_layout_source_trace.csv"
DEFAULT_DETAIL_OUT = ROOT / "output" / "layout_audit" / "g1_layout_source_trace_detail.csv"


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


def detail_rows_for_set(set_id: str, source: Path, pdf_dir: Path) -> list[dict[str, str]]:
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
                "snippet_length": "0",
                "matched": "0",
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
                "snippet_length": "0",
                "matched": "0",
                "status": "FAIL",
                "snippet": "",
                "detail": "missing source block",
            }
        ]

    snippets = source_digest_snippets(source_block)
    normalized_pdf = digest_normalize(full_text(read_texts(pdf)))
    rows: list[dict[str, str]] = []
    for index, snippet in enumerate(snippets, start=1):
        matched = snippet in normalized_pdf
        rows.append(
            {
                **base,
                "snippet_index": str(index),
                "snippet_length": str(len(snippet)),
                "matched": "1" if matched else "0",
                "status": "PASS" if matched else "FAIL",
                "snippet": snippet,
                "detail": "matched" if matched else "missing source digest snippet",
            }
        )
    return rows


def row_for_set(set_id: str, source: Path, pdf_dir: Path) -> dict[str, str]:
    pdf = pdf_dir / f"g1_mid_set{set_id}_layout.pdf"
    row = {
        "set": set_id,
        "source": str(source),
        "pdf": str(pdf),
        "expected_snippets": "0",
        "matched_snippets": "0",
        "missing_snippets": "0",
        "match_rate": "0.000",
        "status": "FAIL",
        "missing_preview": "",
        "detail": "",
    }
    if not pdf.exists():
        row["detail"] = "missing pdf"
        return row

    source_block = extract_source_block(source, set_id)
    if source_block is None:
        row["detail"] = "missing source block"
        return row

    detail_rows = detail_rows_for_set(set_id, source, pdf_dir)
    snippet_rows = [detail for detail in detail_rows if detail["snippet_index"]]
    missing = [detail["snippet"] for detail in snippet_rows if detail["status"] != "PASS"]
    expected = len(snippet_rows)
    matched = expected - len(missing)
    match_rate = matched / expected if expected else 0.0
    row.update(
        {
            "expected_snippets": str(expected),
            "matched_snippets": str(matched),
            "missing_snippets": str(len(missing)),
            "match_rate": f"{match_rate:.3f}",
            "missing_preview": " | ".join(missing[:3]),
        }
    )
    if expected < 20:
        row["detail"] = f"too few snippets={expected}"
        return row
    if missing:
        row["detail"] = "missing source digest snippets"
        return row
    row["status"] = "PASS"
    row["detail"] = "all snippets matched"
    return row


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
    rows = [row_for_set(set_id, source, pdf_dir) for set_id in parse_set_range(args.sets)]
    detail_rows = [
        detail
        for set_id in parse_set_range(args.sets)
        for detail in detail_rows_for_set(set_id, source, pdf_dir)
    ]

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "set",
        "source",
        "pdf",
        "expected_snippets",
        "matched_snippets",
        "missing_snippets",
        "match_rate",
        "status",
        "missing_preview",
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
        "snippet_length",
        "matched",
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
        "rows="
        f"{len(rows)} pass={len(rows) - len(failures)} fail={len(failures)} out={out} "
        f"detail_rows={len(detail_rows)} detail_fail={len(detail_failures)} detail_out={detail_out}"
    )
    return 1 if failures or detail_failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
