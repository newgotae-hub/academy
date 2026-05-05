# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

from export_g1_layout_source_trace import parse_set_range


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_AUDIT_DIR = ROOT / "output" / "layout_audit"
DEFAULT_OUT = DEFAULT_AUDIT_DIR / "g1_layout_schema_contract.json"
EXPECTED_SNIPPETS_PER_SET = 32
EXPECTED_RELEASE_METRIC_ROWS = 30

HEX64_RE = re.compile(r"^[0-9a-f]{64}$")
STATUS_PASS_FAIL = ["PASS", "FAIL"]
STATUS_PASS_WARN_FAIL = ["PASS", "WARN", "FAIL"]
BOOLEAN_STRINGS = ["True", "False"]
DEFAULT_OPTIONAL_COLUMNS = {"first_fail", "first_warn", "missing_preview", "first_bad_snippet", "detail"}


SCHEMAS: dict[str, dict[str, Any]] = {
    "g1_layout_quality_loop_summary.csv": {
        "columns": ["timestamp", "cycle", "set", "status", "pass", "warn", "fail", "first_fail", "first_warn", "pages", "elapsed_ms", "output", "report"],
        "numeric": ["cycle", "set", "pass", "warn", "fail", "pages", "elapsed_ms"],
        "enums": {"status": STATUS_PASS_WARN_FAIL},
        "unique": ["timestamp", "cycle", "set"],
    },
    "g1_layout_binding_metrics.csv": {
        "columns": ["set", "pdf", "marker", "dependent_type", "max_gap_pt", "status", "page", "lead_x", "lead_y", "dependent_y", "gap_pt", "detail"],
        "numeric": ["set", "max_gap_pt", "page", "lead_x", "lead_y", "dependent_y", "gap_pt"],
        "enums": {"status": STATUS_PASS_FAIL, "dependent_type": ["option", "passage", "short_answer", "grammar_body", "answer_slot"]},
        "unique": ["set", "marker", "dependent_type"],
    },
    "g1_layout_short_answer_metrics.csv": {
        "columns": ["set", "pdf", "marker", "page", "column_x", "lead_y", "slot_count", "slot_top_y", "slot_bottom_y", "block_height_pt", "status", "detail"],
        "numeric": ["set", "page", "column_x", "lead_y", "slot_count", "slot_top_y", "slot_bottom_y", "block_height_pt"],
        "enums": {"status": STATUS_PASS_FAIL},
        "unique": ["set", "marker"],
    },
    "g1_layout_source_trace.csv": {
        "columns": ["set", "source", "pdf", "expected_snippets", "matched_snippets", "missing_snippets", "match_rate", "status", "missing_preview", "detail"],
        "numeric": ["set", "expected_snippets", "matched_snippets", "missing_snippets", "match_rate"],
        "enums": {"status": STATUS_PASS_FAIL},
        "unique": ["set"],
    },
    "g1_layout_source_trace_detail.csv": {
        "columns": ["set", "source", "pdf", "snippet_index", "snippet_length", "matched", "status", "snippet", "detail"],
        "numeric": ["set", "snippet_index", "snippet_length", "matched"],
        "enums": {"status": STATUS_PASS_FAIL, "matched": ["0", "1"]},
        "unique": ["set", "snippet_index"],
    },
    "g1_layout_source_order.csv": {
        "columns": ["set", "source", "pdf", "expected_snippets", "ordered_snippets", "out_of_order_snippets", "first_bad_snippet", "status", "detail"],
        "numeric": ["set", "expected_snippets", "ordered_snippets", "out_of_order_snippets"],
        "enums": {"status": STATUS_PASS_FAIL},
        "unique": ["set"],
    },
    "g1_layout_source_order_detail.csv": {
        "columns": ["set", "source", "pdf", "snippet_index", "start_offset", "end_offset", "previous_end_offset", "ordered", "status", "snippet", "detail"],
        "numeric": ["set", "snippet_index", "start_offset", "end_offset", "previous_end_offset", "ordered"],
        "enums": {"status": STATUS_PASS_FAIL, "ordered": ["0", "1"]},
        "unique": ["set", "snippet_index"],
    },
    "g1_layout_anchor_deltas.csv": {
        "columns": ["set", "pdf", "anchor", "page", "expected_x", "expected_y", "actual_x", "actual_y", "delta_x", "delta_y", "status", "detail"],
        "numeric": ["set", "page", "expected_x", "expected_y", "actual_x", "actual_y", "delta_x", "delta_y"],
        "enums": {"status": STATUS_PASS_FAIL},
        "unique": ["set", "anchor", "page"],
    },
    "g1_layout_density_metrics.csv": {
        "columns": ["set", "pdf", "page", "column", "anchor_count", "used_height_pt", "top_y", "bottom_y", "max_gap_pt", "density_score", "status", "detail"],
        "numeric": ["set", "page", "anchor_count", "used_height_pt", "top_y", "bottom_y", "max_gap_pt", "density_score"],
        "enums": {"status": STATUS_PASS_FAIL, "column": ["L", "R"]},
        "unique": ["set", "page", "column"],
    },
    "g1_layout_package_manifest.csv": {
        "columns": ["set", "pdf", "audit_report", "exists", "pages", "bytes", "sha256", "audit_exists", "status", "detail"],
        "numeric": ["set", "pages", "bytes"],
        "enums": {"status": STATUS_PASS_FAIL, "exists": BOOLEAN_STRINGS, "audit_exists": BOOLEAN_STRINGS},
        "unique": ["set"],
    },
    "g1_layout_signature_manifest.csv": {
        "columns": ["set", "pdf", "pages", "text_run_count", "line_segment_count", "layout_sha256", "page_signatures", "status", "detail"],
        "numeric": ["set", "pages", "text_run_count", "line_segment_count"],
        "enums": {"status": STATUS_PASS_FAIL},
        "unique": ["set"],
    },
    "g1_layout_release_metrics.csv": {
        "columns": ["metric_group", "metric", "n", "actual", "limit", "headroom", "utilization_pct", "spread", "status", "risk", "detail"],
        "numeric": ["n", "actual", "limit", "headroom", "utilization_pct", "spread"],
        "enums": {"status": STATUS_PASS_FAIL, "risk": ["OK", "WATCH", "FAIL"]},
        "unique": ["metric_group", "metric"],
    },
}

EXPECTED_ROWS_PER_SET = {
    "g1_layout_binding_metrics.csv": 8,
    "g1_layout_short_answer_metrics.csv": 2,
    "g1_layout_source_trace.csv": 1,
    "g1_layout_source_trace_detail.csv": EXPECTED_SNIPPETS_PER_SET,
    "g1_layout_source_order.csv": 1,
    "g1_layout_source_order_detail.csv": EXPECTED_SNIPPETS_PER_SET,
    "g1_layout_anchor_deltas.csv": 22,
    "g1_layout_density_metrics.csv": 3,
    "g1_layout_package_manifest.csv": 1,
    "g1_layout_signature_manifest.csv": 1,
}


def read_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    if not path.exists():
        return [], []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def can_parse_number(value: str) -> bool:
    if value == "":
        return True
    try:
        float(value)
    except ValueError:
        return False
    return True


def latest_rows_by_set(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    latest: dict[str, dict[str, str]] = {}
    for row in rows:
        set_id = row.get("set", "")
        if set_id:
            latest[set_id] = row
    return [latest[key] for key in sorted(latest, key=lambda value: int(value))]


def key_for(row: dict[str, str], columns: list[str]) -> tuple[str, ...]:
    return tuple(row.get(column, "") for column in columns)


def duplicate_keys(rows: list[dict[str, str]], columns: list[str]) -> list[str]:
    counts = Counter(key_for(row, columns) for row in rows)
    return ["|".join(key) for key, count in counts.items() if count > 1]


def rows_by_set(rows: list[dict[str, str]]) -> dict[str, list[dict[str, str]]]:
    grouped: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        grouped.setdefault(row.get("set", ""), []).append(row)
    return grouped


def int_value(row: dict[str, str], key: str, default: int = -1) -> int:
    try:
        return int(float(row.get(key, "")))
    except ValueError:
        return default


def is_hex64(value: str) -> bool:
    return bool(HEX64_RE.match(value))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_expected_sets(filename: str, rows: list[dict[str, str]], expected_sets: list[str], failures: list[str]) -> None:
    if filename == "g1_layout_release_metrics.csv":
        return
    if filename == "g1_layout_quality_loop_summary.csv":
        latest_rows = latest_rows_by_set(rows)
        actual_sets = [row.get("set", "") for row in latest_rows]
        if actual_sets != expected_sets:
            failures.append(f"latest set list mismatch actual={actual_sets}")
        return

    actual_sets = sorted({row.get("set", "") for row in rows}, key=lambda value: int(value) if value.isdigit() else -1)
    if actual_sets != expected_sets:
        failures.append(f"set list mismatch actual={actual_sets}")


def validate_rows_per_set(filename: str, rows: list[dict[str, str]], expected_sets: list[str], failures: list[str]) -> None:
    expected_count = EXPECTED_ROWS_PER_SET.get(filename)
    if expected_count is None:
        return
    counts = Counter(row.get("set", "") for row in rows)
    bad_counts = {set_id: counts.get(set_id, 0) for set_id in expected_sets if counts.get(set_id, 0) != expected_count}
    extra_sets = sorted(set(counts) - set(expected_sets))
    if bad_counts or extra_sets:
        failures.append(f"rows per set mismatch expected={expected_count} bad={bad_counts} extra={extra_sets}")


def validate_quality_rows(rows: list[dict[str, str]], expected_sets: list[str], expected_pages: int, expected_gates: int, failures: list[str]) -> None:
    latest_rows = latest_rows_by_set(rows)
    bad_latest: list[str] = []
    for row in latest_rows:
        if row.get("set") not in expected_sets:
            continue
        if row.get("status") != "PASS":
            bad_latest.append(f"{row.get('set')}:status={row.get('status')}")
        if row.get("pass") != str(expected_gates) or row.get("warn") != "0" or row.get("fail") != "0":
            bad_latest.append(
                f"{row.get('set')}:gates pass={row.get('pass')} warn={row.get('warn')} fail={row.get('fail')}"
            )
        if row.get("pages") != str(expected_pages):
            bad_latest.append(f"{row.get('set')}:pages={row.get('pages')}")
    if bad_latest:
        failures.append("latest quality rows invalid " + "; ".join(bad_latest[:5]))


def validate_source_trace(rows: list[dict[str, str]], failures: list[str]) -> None:
    bad: list[str] = []
    for row in rows:
        if (
            row.get("status") != "PASS"
            or row.get("expected_snippets") != str(EXPECTED_SNIPPETS_PER_SET)
            or row.get("matched_snippets") != str(EXPECTED_SNIPPETS_PER_SET)
            or row.get("missing_snippets") != "0"
            or row.get("match_rate") != "1.000"
        ):
            bad.append(row.get("set", ""))
    if bad:
        failures.append("source trace summary invalid sets=" + ",".join(bad[:8]))


def validate_source_detail(rows: list[dict[str, str]], expected_sets: list[str], failures: list[str]) -> None:
    grouped = rows_by_set(rows)
    bad: list[str] = []
    for set_id in expected_sets:
        indices = sorted(int_value(row, "snippet_index") for row in grouped.get(set_id, []))
        if indices != list(range(1, EXPECTED_SNIPPETS_PER_SET + 1)):
            bad.append(f"{set_id}:indices={indices[:6]}..{indices[-3:] if indices else []}")
            continue
        for row in grouped.get(set_id, []):
            if row.get("status") != "PASS" or row.get("matched") != "1" or int_value(row, "snippet_length", 0) <= 0:
                bad.append(f"{set_id}:{row.get('snippet_index')}")
                break
    if bad:
        failures.append("source trace detail invalid " + "; ".join(bad[:5]))


def validate_source_order(rows: list[dict[str, str]], failures: list[str]) -> None:
    bad: list[str] = []
    for row in rows:
        if (
            row.get("status") != "PASS"
            or row.get("expected_snippets") != str(EXPECTED_SNIPPETS_PER_SET)
            or row.get("ordered_snippets") != str(EXPECTED_SNIPPETS_PER_SET)
            or row.get("out_of_order_snippets") != "0"
            or row.get("first_bad_snippet") not in {"", None}
        ):
            bad.append(row.get("set", ""))
    if bad:
        failures.append("source order summary invalid sets=" + ",".join(bad[:8]))


def validate_source_order_detail(rows: list[dict[str, str]], expected_sets: list[str], failures: list[str]) -> None:
    grouped = rows_by_set(rows)
    bad: list[str] = []
    for set_id in expected_sets:
        ordered_rows = sorted(grouped.get(set_id, []), key=lambda row: int_value(row, "snippet_index"))
        indices = [int_value(row, "snippet_index") for row in ordered_rows]
        if indices != list(range(1, EXPECTED_SNIPPETS_PER_SET + 1)):
            bad.append(f"{set_id}:indices={indices[:6]}..{indices[-3:] if indices else []}")
            continue
        previous_end = 0
        for row in ordered_rows:
            start = int_value(row, "start_offset")
            end = int_value(row, "end_offset")
            declared_previous = int_value(row, "previous_end_offset")
            if row.get("status") != "PASS" or row.get("ordered") != "1":
                bad.append(f"{set_id}:{row.get('snippet_index')}:status")
                break
            if declared_previous != previous_end or start < previous_end or end <= start:
                bad.append(
                    f"{set_id}:{row.get('snippet_index')}:offset prev={previous_end} declared={declared_previous} start={start} end={end}"
                )
                break
            if end - start != len(row.get("snippet", "")):
                bad.append(
                    f"{set_id}:{row.get('snippet_index')}:length span={end - start} snippet={len(row.get('snippet', ''))}"
                )
                break
            previous_end = end
    if bad:
        failures.append("source order detail invalid " + "; ".join(bad[:5]))


def validate_manifest(rows: list[dict[str, str]], expected_pages: int, failures: list[str]) -> None:
    bad: list[str] = []
    for row in rows:
        pdf = Path(row.get("pdf", ""))
        audit_report = Path(row.get("audit_report", ""))
        if row.get("status") != "PASS" or row.get("exists") != "True" or row.get("audit_exists") != "True":
            bad.append(f"{row.get('set')}:status")
            continue
        if row.get("pages") != str(expected_pages) or int_value(row, "bytes", 0) <= 0 or not is_hex64(row.get("sha256", "")):
            bad.append(f"{row.get('set')}:metadata")
            continue
        if not pdf.exists() or sha256_file(pdf) != row.get("sha256"):
            bad.append(f"{row.get('set')}:sha mismatch")
            continue
        if not audit_report.exists():
            bad.append(f"{row.get('set')}:audit missing")
    if bad:
        failures.append("package manifest invalid " + "; ".join(bad[:5]))


def validate_signature(rows: list[dict[str, str]], expected_pages: int, failures: list[str]) -> None:
    bad: list[str] = []
    for row in rows:
        page_signatures = [part for part in row.get("page_signatures", "").split("|") if part]
        if row.get("status") != "PASS":
            bad.append(f"{row.get('set')}:status")
            continue
        if row.get("pages") != str(expected_pages) or len(page_signatures) != expected_pages:
            bad.append(f"{row.get('set')}:pages/signatures")
            continue
        if not is_hex64(row.get("layout_sha256", "")) or any(not is_hex64(signature) for signature in page_signatures):
            bad.append(f"{row.get('set')}:hash")
            continue
        if int_value(row, "text_run_count", 0) <= 0 or int_value(row, "line_segment_count", 0) <= 0:
            bad.append(f"{row.get('set')}:empty layout counts")
    if bad:
        failures.append("layout signature invalid " + "; ".join(bad[:5]))


def validate_generic_pass_rows(filename: str, rows: list[dict[str, str]], failures: list[str]) -> None:
    if filename == "g1_layout_quality_loop_summary.csv":
        return
    bad = [f"{row.get('set')}:{row.get('status')}" for row in rows if row.get("status") != "PASS"]
    if bad:
        failures.append("non-pass status rows " + "; ".join(bad[:5]))


def validate_semantics(
    filename: str,
    rows: list[dict[str, str]],
    expected_sets: list[str],
    expected_pages: int,
    expected_gates: int,
    failures: list[str],
) -> None:
    validate_expected_sets(filename, rows, expected_sets, failures)
    validate_rows_per_set(filename, rows, expected_sets, failures)
    validate_generic_pass_rows(filename, rows, failures)
    if filename == "g1_layout_quality_loop_summary.csv":
        validate_quality_rows(rows, expected_sets, expected_pages, expected_gates, failures)
    elif filename == "g1_layout_source_trace.csv":
        validate_source_trace(rows, failures)
    elif filename == "g1_layout_source_trace_detail.csv":
        validate_source_detail(rows, expected_sets, failures)
    elif filename == "g1_layout_source_order.csv":
        validate_source_order(rows, failures)
    elif filename == "g1_layout_source_order_detail.csv":
        validate_source_order_detail(rows, expected_sets, failures)
    elif filename == "g1_layout_package_manifest.csv":
        validate_manifest(rows, expected_pages, failures)
    elif filename == "g1_layout_signature_manifest.csv":
        validate_signature(rows, expected_pages, failures)
    elif filename == "g1_layout_release_metrics.csv":
        if len(rows) != EXPECTED_RELEASE_METRIC_ROWS:
            failures.append(f"release metric rows expected={EXPECTED_RELEASE_METRIC_ROWS} actual={len(rows)}")
        failed_risk = [row.get("metric", "") for row in rows if row.get("risk") == "FAIL"]
        if failed_risk:
            failures.append("release metric FAIL risk " + ",".join(failed_risk[:8]))


def check_file(
    audit_dir: Path,
    filename: str,
    schema: dict[str, Any],
    expected_sets: list[str],
    expected_pages: int,
    expected_gates: int,
) -> dict[str, Any]:
    path = audit_dir / filename
    expected_columns = schema["columns"]
    numeric_columns = schema["numeric"]
    actual_columns, rows = read_rows(path)
    failures: list[str] = []
    if not path.exists():
        failures.append("missing file")
    if actual_columns != expected_columns:
        failures.append(f"columns mismatch actual={actual_columns}")
    if not rows:
        failures.append("empty rows")

    required_columns = [column for column in expected_columns if column not in DEFAULT_OPTIONAL_COLUMNS]
    bad_required: list[str] = []
    for row_index, row in enumerate(rows, start=1):
        for column in required_columns:
            if row.get(column, "").strip() == "":
                bad_required.append(f"r{row_index}:{column}")
                if len(bad_required) >= 5:
                    break
        if len(bad_required) >= 5:
            break
    if bad_required:
        failures.append("blank required " + "; ".join(bad_required))

    bad_numeric: list[str] = []
    for row_index, row in enumerate(rows, start=1):
        for column in numeric_columns:
            if not can_parse_number(row.get(column, "")):
                bad_numeric.append(f"r{row_index}:{column}={row.get(column, '')}")
                if len(bad_numeric) >= 5:
                    break
        if len(bad_numeric) >= 5:
            break
    if bad_numeric:
        failures.append("bad numeric " + "; ".join(bad_numeric))

    for column, allowed_values in schema.get("enums", {}).items():
        bad_values = [
            f"r{row_index}:{column}={row.get(column, '')}"
            for row_index, row in enumerate(rows, start=1)
            if row.get(column, "") not in set(allowed_values)
        ]
        if bad_values:
            failures.append("bad enum " + "; ".join(bad_values[:5]))

    unique_columns = schema.get("unique", [])
    if unique_columns:
        duplicates = duplicate_keys(rows, unique_columns)
        if duplicates:
            failures.append(f"duplicate key {unique_columns} " + "; ".join(duplicates[:5]))

    if rows and actual_columns == expected_columns:
        validate_semantics(filename, rows, expected_sets, expected_pages, expected_gates, failures)

    return {
        "file": filename,
        "path": str(path),
        "expected_columns": expected_columns,
        "actual_columns": actual_columns,
        "rows": len(rows),
        "status": "PASS" if not failures else "FAIL",
        "detail": "schema valid" if not failures else " | ".join(failures),
    }


def check_cross_file_contract(audit_dir: Path, expected_sets: list[str], expected_pages: int) -> dict[str, Any]:
    failures: list[str] = []
    rows_by_name = {filename: read_rows(audit_dir / filename)[1] for filename in SCHEMAS}

    source_summary = {row.get("set", ""): row for row in rows_by_name["g1_layout_source_trace.csv"]}
    source_detail = rows_by_set(rows_by_name["g1_layout_source_trace_detail.csv"])
    source_order_summary = {row.get("set", ""): row for row in rows_by_name["g1_layout_source_order.csv"]}
    source_order_detail = rows_by_set(rows_by_name["g1_layout_source_order_detail.csv"])
    manifest = {row.get("set", ""): row for row in rows_by_name["g1_layout_package_manifest.csv"]}
    signature = {row.get("set", ""): row for row in rows_by_name["g1_layout_signature_manifest.csv"]}

    for set_id in expected_sets:
        source_row = source_summary.get(set_id, {})
        detail_rows = source_detail.get(set_id, [])
        matched_count = sum(1 for row in detail_rows if row.get("matched") == "1")
        expected = int_value(source_row, "expected_snippets", 0)
        matched = int_value(source_row, "matched_snippets", -1)
        missing = int_value(source_row, "missing_snippets", -1)
        if expected != EXPECTED_SNIPPETS_PER_SET or matched != matched_count or missing != expected - matched_count:
            failures.append(f"{set_id}:source summary/detail mismatch")
        if expected > 0:
            expected_rate = f"{matched_count / expected:.3f}"
            if source_row.get("match_rate") != expected_rate:
                failures.append(f"{set_id}:match_rate {source_row.get('match_rate')}!={expected_rate}")

        order_row = source_order_summary.get(set_id, {})
        order_detail_rows = source_order_detail.get(set_id, [])
        ordered_count = sum(1 for row in order_detail_rows if row.get("ordered") == "1")
        order_expected = int_value(order_row, "expected_snippets", 0)
        ordered = int_value(order_row, "ordered_snippets", -1)
        out_of_order = int_value(order_row, "out_of_order_snippets", -1)
        if order_expected != EXPECTED_SNIPPETS_PER_SET or ordered != ordered_count or out_of_order != order_expected - ordered_count:
            failures.append(f"{set_id}:source order summary/detail mismatch")

        manifest_row = manifest.get(set_id, {})
        signature_row = signature.get(set_id, {})
        if manifest_row.get("pages") != signature_row.get("pages") or manifest_row.get("pages") != str(expected_pages):
            failures.append(f"{set_id}:manifest/signature page mismatch")
        if f"set{set_id}" not in manifest_row.get("pdf", "") or f"set{set_id}" not in signature_row.get("pdf", ""):
            failures.append(f"{set_id}:pdf path does not match set id")

    return {
        "file": "__cross_file_semantics__",
        "path": str(audit_dir),
        "expected_columns": [],
        "actual_columns": [],
        "rows": 0,
        "status": "PASS" if not failures else "FAIL",
        "detail": "cross-file semantics valid" if not failures else " | ".join(failures[:8]),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--audit-dir", default=str(DEFAULT_AUDIT_DIR))
    parser.add_argument("--sets", default="51-62")
    parser.add_argument("--expected-pages", type=int, default=4)
    parser.add_argument("--expected-gates", type=int, default=26)
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    args = parser.parse_args()

    audit_dir = Path(args.audit_dir)
    expected_sets = parse_set_range(args.sets)
    checks = [
        check_file(audit_dir, filename, schema, expected_sets, args.expected_pages, args.expected_gates)
        for filename, schema in SCHEMAS.items()
    ]
    checks.append(check_cross_file_contract(audit_dir, expected_sets, args.expected_pages))
    status = "PASS" if all(check["status"] == "PASS" for check in checks) else "FAIL"
    payload = {
        "schema_contract_version": "g1-mid-layout-schema-v2",
        "status": status,
        "sets": expected_sets,
        "expected_pages": args.expected_pages,
        "expected_gates": args.expected_gates,
        "checks": checks,
    }

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    failures = [check for check in checks if check["status"] != "PASS"]
    print(f"schema_contract={out} status={status} checks={len(checks)} failures={len(failures)}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
