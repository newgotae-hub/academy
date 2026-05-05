# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from typing import Any

from audit_g1_exam_layout import compact, line_segments, page_boxes, text_runs
from export_g1_layout_source_trace import parse_set_range


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PDF_DIR = ROOT / "output" / "pdf"
DEFAULT_OUT = ROOT / "output" / "layout_audit" / "g1_layout_signature_manifest.csv"
DEFAULT_JSON_OUT = ROOT / "output" / "layout_audit" / "g1_layout_signature_manifest.json"


def sha256_payload(payload: Any) -> str:
    data = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def normalized_text_runs(pdf: Path, page_index: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for x, y, font_size, value in text_runs(pdf, page_index):
        text = compact(value)
        if not text:
            continue
        rows.append(
            {
                "x": round(x, 1),
                "y": round(y, 1),
                "font": round(font_size, 2),
                "text": text,
            }
        )
    return rows


def normalized_line_segments(pdf: Path, page_index: int) -> list[dict[str, float]]:
    return [
        {
            "x1": round(x1, 2),
            "y1": round(y1, 2),
            "x2": round(x2, 2),
            "y2": round(y2, 2),
        }
        for x1, y1, x2, y2 in line_segments(pdf, page_index)
    ]


def signature_for_pdf(pdf: Path) -> dict[str, Any]:
    boxes = page_boxes(pdf)
    pages: list[dict[str, Any]] = []
    for page_index, box in enumerate(boxes):
        runs = normalized_text_runs(pdf, page_index)
        segments = normalized_line_segments(pdf, page_index)
        page_payload = {
            "page": page_index + 1,
            "box": box,
            "text_runs": runs,
            "line_segments": segments,
        }
        pages.append(
            {
                "page": page_index + 1,
                "box": box,
                "text_run_count": len(runs),
                "line_segment_count": len(segments),
                "page_sha256": sha256_payload(page_payload),
            }
        )
    layout_payload = {"pages": pages}
    return {
        "pages": len(boxes),
        "text_run_count": sum(page["text_run_count"] for page in pages),
        "line_segment_count": sum(page["line_segment_count"] for page in pages),
        "page_signatures": [page["page_sha256"] for page in pages],
        "layout_sha256": sha256_payload(layout_payload),
        "page_details": pages,
    }


def row_for_set(set_id: str, pdf_dir: Path, expected_pages: int) -> tuple[dict[str, str], dict[str, Any]]:
    pdf = pdf_dir / f"g1_mid_set{set_id}_layout.pdf"
    row = {
        "set": set_id,
        "pdf": str(pdf),
        "pages": "0",
        "text_run_count": "0",
        "line_segment_count": "0",
        "layout_sha256": "",
        "page_signatures": "",
        "status": "FAIL",
        "detail": "",
    }
    detail: dict[str, Any] = {"set": set_id, "pdf": str(pdf), "status": "FAIL", "detail": ""}
    if not pdf.exists():
        row["detail"] = "missing pdf"
        detail["detail"] = row["detail"]
        return row, detail
    try:
        signature = signature_for_pdf(pdf)
    except Exception as exc:  # pragma: no cover - defensive diagnostic path
        row["detail"] = f"signature error: {type(exc).__name__}: {exc}"
        detail["detail"] = row["detail"]
        return row, detail

    failures: list[str] = []
    if signature["pages"] != expected_pages:
        failures.append(f"pages={signature['pages']} expected={expected_pages}")
    if signature["text_run_count"] < 120:
        failures.append(f"text_runs={signature['text_run_count']}")
    if signature["line_segment_count"] < 80:
        failures.append(f"line_segments={signature['line_segment_count']}")

    row.update(
        {
            "pages": str(signature["pages"]),
            "text_run_count": str(signature["text_run_count"]),
            "line_segment_count": str(signature["line_segment_count"]),
            "layout_sha256": signature["layout_sha256"],
            "page_signatures": "|".join(signature["page_signatures"]),
            "status": "PASS" if not failures else "FAIL",
            "detail": "layout signature captured" if not failures else "; ".join(failures),
        }
    )
    detail.update(
        {
            "status": row["status"],
            "detail": row["detail"],
            **signature,
        }
    )
    return row, detail


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sets", default="51-62")
    parser.add_argument("--pdf-dir", default=str(DEFAULT_PDF_DIR))
    parser.add_argument("--expected-pages", type=int, default=4)
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument("--json-out", default=str(DEFAULT_JSON_OUT))
    args = parser.parse_args()

    pdf_dir = Path(args.pdf_dir)
    rows: list[dict[str, str]] = []
    details: list[dict[str, Any]] = []
    for set_id in parse_set_range(args.sets):
        row, detail = row_for_set(set_id, pdf_dir, args.expected_pages)
        rows.append(row)
        details.append(detail)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "set",
        "pdf",
        "pages",
        "text_run_count",
        "line_segment_count",
        "layout_sha256",
        "page_signatures",
        "status",
        "detail",
    ]
    with out.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    json_out = Path(args.json_out)
    json_out.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "sets": parse_set_range(args.sets),
        "expected_pages": args.expected_pages,
        "rows": rows,
        "details": details,
    }
    json_out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    failures = [row for row in rows if row["status"] != "PASS"]
    print(f"rows={len(rows)} pass={len(rows) - len(failures)} fail={len(failures)} out={out} json={json_out}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
