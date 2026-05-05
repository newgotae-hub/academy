# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from export_g1_layout_source_trace import parse_set_range


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_AUDIT_DIR = ROOT / "output" / "layout_audit"
DEFAULT_OUT = DEFAULT_AUDIT_DIR / "g1_layout_contract.json"


CONTRACT_VERSION = "g1-mid-layout-contract-v1"
EXPECTED_GATES_PER_SET = 26
EXPECTED_BINDING_ROWS_PER_SET = 8
EXPECTED_SHORT_ANSWER_ROWS_PER_SET = 2
EXPECTED_SOURCE_SNIPPETS_PER_SET = 32
EXPECTED_SOURCE_ORDER_ROWS_PER_SET = 1
EXPECTED_ANCHOR_ROWS_PER_SET = 22
EXPECTED_DENSITY_ROWS_PER_SET = 3
EXPECTED_SIGNATURE_ROWS_PER_SET = 1
EXPECTED_RELEASE_METRIC_ROWS = 30
DASHBOARD_VERSION = "g1-mid-layout-dashboard-v1"

DASHBOARD_INPUT_FILENAMES = [
    "g1_layout_quality_loop_summary.csv",
    "g1_layout_binding_metrics.csv",
    "g1_layout_short_answer_metrics.csv",
    "g1_layout_source_trace.csv",
    "g1_layout_source_trace_detail.csv",
    "g1_layout_source_order.csv",
    "g1_layout_source_order_detail.csv",
    "g1_layout_anchor_deltas.csv",
    "g1_layout_density_metrics.csv",
    "g1_layout_package_manifest.csv",
    "g1_layout_signature_manifest.csv",
    "g1_layout_release_metrics.csv",
    "g1_layout_schema_contract.json",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def read_json_status(path: Path) -> str:
    if not path.exists():
        return "MISSING"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return "INVALID"
    return str(payload.get("status", "UNKNOWN"))


def read_json_payload(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def sha256_file(path: Path) -> str:
    if not path.exists():
        return ""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def latest_rows_by_set(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    latest: dict[str, dict[str, str]] = {}
    for row in rows:
        set_id = row.get("set", "")
        if set_id:
            latest[set_id] = row
    return [latest[key] for key in sorted(latest, key=lambda value: int(value))]


def status_pass(rows: list[dict[str, str]]) -> bool:
    return bool(rows) and all(row.get("status") == "PASS" for row in rows)


def count_by_set(rows: list[dict[str, str]]) -> dict[str, int]:
    return dict(Counter(row.get("set", "") for row in rows if row.get("set", "")))


def add_check(checks: list[dict[str, Any]], name: str, expected: Any, actual: Any, passed: bool) -> None:
    checks.append(
        {
            "name": name,
            "expected": expected,
            "actual": actual,
            "status": "PASS" if passed else "FAIL",
        }
    )


def contract_for(audit_dir: Path, sets: list[str], expected_pages: int, require_dashboard: bool) -> dict[str, Any]:
    quality_rows = latest_rows_by_set(read_csv(audit_dir / "g1_layout_quality_loop_summary.csv"))
    binding_rows = read_csv(audit_dir / "g1_layout_binding_metrics.csv")
    short_answer_rows = read_csv(audit_dir / "g1_layout_short_answer_metrics.csv")
    source_rows = read_csv(audit_dir / "g1_layout_source_trace.csv")
    source_detail_rows = read_csv(audit_dir / "g1_layout_source_trace_detail.csv")
    source_order_rows = read_csv(audit_dir / "g1_layout_source_order.csv")
    source_order_detail_rows = read_csv(audit_dir / "g1_layout_source_order_detail.csv")
    anchor_rows = read_csv(audit_dir / "g1_layout_anchor_deltas.csv")
    density_rows = read_csv(audit_dir / "g1_layout_density_metrics.csv")
    manifest_rows = read_csv(audit_dir / "g1_layout_package_manifest.csv")
    signature_rows = read_csv(audit_dir / "g1_layout_signature_manifest.csv")
    release_rows = read_csv(audit_dir / "g1_layout_release_metrics.csv")
    schema_payload = read_json_payload(audit_dir / "g1_layout_schema_contract.json")
    schema_status = str(schema_payload.get("status", "MISSING" if not schema_payload else "UNKNOWN"))
    dashboard_payload = read_json_payload(audit_dir / "g1_layout_quality_dashboard.json")

    expected_set_count = len(sets)
    expected_binding_total = expected_set_count * EXPECTED_BINDING_ROWS_PER_SET
    expected_short_answer_total = expected_set_count * EXPECTED_SHORT_ANSWER_ROWS_PER_SET
    expected_source_total = expected_set_count
    expected_source_detail_total = expected_set_count * EXPECTED_SOURCE_SNIPPETS_PER_SET
    expected_source_order_total = expected_set_count * EXPECTED_SOURCE_ORDER_ROWS_PER_SET
    expected_source_order_detail_total = expected_set_count * EXPECTED_SOURCE_SNIPPETS_PER_SET
    expected_anchor_total = expected_set_count * EXPECTED_ANCHOR_ROWS_PER_SET
    expected_density_total = expected_set_count * EXPECTED_DENSITY_ROWS_PER_SET
    expected_signature_total = expected_set_count * EXPECTED_SIGNATURE_ROWS_PER_SET

    checks: list[dict[str, Any]] = []

    quality_sets = [row.get("set", "") for row in quality_rows]
    add_check(checks, "quality_set_list", sets, quality_sets, quality_sets == sets)
    add_check(checks, "quality_rows", expected_set_count, len(quality_rows), len(quality_rows) == expected_set_count)
    add_check(checks, "quality_status", "all PASS", "all PASS" if status_pass(quality_rows) else "has FAIL", status_pass(quality_rows))
    add_check(
        checks,
        "quality_gate_count_per_set",
        EXPECTED_GATES_PER_SET,
        sorted({row.get("pass", "") for row in quality_rows}),
        all(row.get("pass") == str(EXPECTED_GATES_PER_SET) for row in quality_rows),
    )
    add_check(
        checks,
        "quality_warn_fail_zero",
        {"warn": "0", "fail": "0"},
        [{"set": row.get("set"), "warn": row.get("warn"), "fail": row.get("fail")} for row in quality_rows],
        all(row.get("warn") == "0" and row.get("fail") == "0" for row in quality_rows),
    )
    add_check(
        checks,
        "quality_page_count",
        expected_pages,
        sorted({row.get("pages", "") for row in quality_rows}),
        all(row.get("pages") == str(expected_pages) for row in quality_rows),
    )

    add_check(checks, "binding_rows", expected_binding_total, len(binding_rows), len(binding_rows) == expected_binding_total)
    add_check(checks, "binding_status", "all PASS", "all PASS" if status_pass(binding_rows) else "has FAIL", status_pass(binding_rows))
    add_check(
        checks,
        "binding_rows_per_set",
        EXPECTED_BINDING_ROWS_PER_SET,
        count_by_set(binding_rows),
        all(count_by_set(binding_rows).get(set_id, 0) == EXPECTED_BINDING_ROWS_PER_SET for set_id in sets),
    )

    add_check(checks, "short_answer_rows", expected_short_answer_total, len(short_answer_rows), len(short_answer_rows) == expected_short_answer_total)
    add_check(checks, "short_answer_status", "all PASS", "all PASS" if status_pass(short_answer_rows) else "has FAIL", status_pass(short_answer_rows))
    add_check(
        checks,
        "short_answer_rows_per_set",
        EXPECTED_SHORT_ANSWER_ROWS_PER_SET,
        count_by_set(short_answer_rows),
        all(count_by_set(short_answer_rows).get(set_id, 0) == EXPECTED_SHORT_ANSWER_ROWS_PER_SET for set_id in sets),
    )

    add_check(checks, "source_rows", expected_source_total, len(source_rows), len(source_rows) == expected_source_total)
    add_check(checks, "source_status", "all PASS", "all PASS" if status_pass(source_rows) else "has FAIL", status_pass(source_rows))
    add_check(
        checks,
        "source_snippets_per_set",
        EXPECTED_SOURCE_SNIPPETS_PER_SET,
        {row.get("set", ""): row.get("expected_snippets", "") for row in source_rows},
        all(
            row.get("expected_snippets") == str(EXPECTED_SOURCE_SNIPPETS_PER_SET)
            and row.get("matched_snippets") == str(EXPECTED_SOURCE_SNIPPETS_PER_SET)
            and row.get("missing_snippets") == "0"
            and row.get("match_rate") == "1.000"
            for row in source_rows
        ),
    )
    add_check(
        checks,
        "source_detail_rows",
        expected_source_detail_total,
        len(source_detail_rows),
        len(source_detail_rows) == expected_source_detail_total,
    )
    add_check(
        checks,
        "source_detail_status",
        "all PASS",
        "all PASS" if status_pass(source_detail_rows) else "has FAIL",
        status_pass(source_detail_rows),
    )
    add_check(
        checks,
        "source_detail_rows_per_set",
        EXPECTED_SOURCE_SNIPPETS_PER_SET,
        count_by_set(source_detail_rows),
        all(count_by_set(source_detail_rows).get(set_id, 0) == EXPECTED_SOURCE_SNIPPETS_PER_SET for set_id in sets),
    )

    add_check(checks, "source_order_rows", expected_source_order_total, len(source_order_rows), len(source_order_rows) == expected_source_order_total)
    add_check(checks, "source_order_status", "all PASS", "all PASS" if status_pass(source_order_rows) else "has FAIL", status_pass(source_order_rows))
    add_check(
        checks,
        "source_order_snippets_per_set",
        EXPECTED_SOURCE_SNIPPETS_PER_SET,
        {row.get("set", ""): row.get("ordered_snippets", "") for row in source_order_rows},
        all(
            row.get("expected_snippets") == str(EXPECTED_SOURCE_SNIPPETS_PER_SET)
            and row.get("ordered_snippets") == str(EXPECTED_SOURCE_SNIPPETS_PER_SET)
            and row.get("out_of_order_snippets") == "0"
            for row in source_order_rows
        ),
    )
    add_check(
        checks,
        "source_order_detail_rows",
        expected_source_order_detail_total,
        len(source_order_detail_rows),
        len(source_order_detail_rows) == expected_source_order_detail_total,
    )
    add_check(
        checks,
        "source_order_detail_status",
        "all PASS",
        "all PASS" if status_pass(source_order_detail_rows) else "has FAIL",
        status_pass(source_order_detail_rows),
    )

    add_check(checks, "anchor_rows", expected_anchor_total, len(anchor_rows), len(anchor_rows) == expected_anchor_total)
    add_check(checks, "anchor_status", "all PASS", "all PASS" if status_pass(anchor_rows) else "has FAIL", status_pass(anchor_rows))
    add_check(
        checks,
        "anchor_rows_per_set",
        EXPECTED_ANCHOR_ROWS_PER_SET,
        count_by_set(anchor_rows),
        all(count_by_set(anchor_rows).get(set_id, 0) == EXPECTED_ANCHOR_ROWS_PER_SET for set_id in sets),
    )

    add_check(checks, "density_rows", expected_density_total, len(density_rows), len(density_rows) == expected_density_total)
    add_check(checks, "density_status", "all PASS", "all PASS" if status_pass(density_rows) else "has FAIL", status_pass(density_rows))
    add_check(
        checks,
        "density_rows_per_set",
        EXPECTED_DENSITY_ROWS_PER_SET,
        count_by_set(density_rows),
        all(count_by_set(density_rows).get(set_id, 0) == EXPECTED_DENSITY_ROWS_PER_SET for set_id in sets),
    )

    add_check(checks, "manifest_rows", expected_set_count, len(manifest_rows), len(manifest_rows) == expected_set_count)
    add_check(checks, "manifest_status", "all PASS", "all PASS" if status_pass(manifest_rows) else "has FAIL", status_pass(manifest_rows))
    add_check(
        checks,
        "manifest_pages",
        expected_pages,
        {row.get("set", ""): row.get("pages", "") for row in manifest_rows},
        all(row.get("pages") == str(expected_pages) for row in manifest_rows),
    )
    add_check(
        checks,
        "manifest_sha256",
        "64 hex characters",
        {row.get("set", ""): len(row.get("sha256", "")) for row in manifest_rows},
        all(len(row.get("sha256", "")) == 64 for row in manifest_rows),
    )

    add_check(checks, "signature_rows", expected_signature_total, len(signature_rows), len(signature_rows) == expected_signature_total)
    add_check(checks, "signature_status", "all PASS", "all PASS" if status_pass(signature_rows) else "has FAIL", status_pass(signature_rows))
    add_check(
        checks,
        "signature_pages",
        expected_pages,
        {row.get("set", ""): row.get("pages", "") for row in signature_rows},
        all(row.get("pages") == str(expected_pages) for row in signature_rows),
    )
    add_check(
        checks,
        "signature_sha256",
        "64 hex characters",
        {row.get("set", ""): len(row.get("layout_sha256", "")) for row in signature_rows},
        all(len(row.get("layout_sha256", "")) == 64 for row in signature_rows),
    )
    add_check(checks, "schema_contract_status", "PASS", schema_status, schema_status == "PASS")
    add_check(
        checks,
        "schema_contract_version",
        "g1-mid-layout-schema-v2",
        schema_payload.get("schema_contract_version", ""),
        schema_payload.get("schema_contract_version") == "g1-mid-layout-schema-v2",
    )
    add_check(
        checks,
        "schema_contract_check_count",
        13,
        len(schema_payload.get("checks", [])),
        len(schema_payload.get("checks", [])) == 13,
    )
    add_check(checks, "schema_contract_scope_sets", sets, schema_payload.get("sets", []), schema_payload.get("sets", []) == sets)
    add_check(
        checks,
        "schema_contract_scope_pages",
        expected_pages,
        schema_payload.get("expected_pages"),
        schema_payload.get("expected_pages") == expected_pages,
    )
    add_check(checks, "release_metric_rows", EXPECTED_RELEASE_METRIC_ROWS, len(release_rows), len(release_rows) == EXPECTED_RELEASE_METRIC_ROWS)
    add_check(checks, "release_metric_status", "all PASS", "all PASS" if status_pass(release_rows) else "has FAIL", status_pass(release_rows))
    add_check(
        checks,
        "release_metric_no_fail_risk",
        "no FAIL risk",
        [row.get("metric", "") for row in release_rows if row.get("risk") == "FAIL"],
        all(row.get("risk") != "FAIL" for row in release_rows),
    )
    add_check(
        checks,
        "release_metric_no_watch_risk",
        "no WATCH risk",
        [row.get("metric", "") for row in release_rows if row.get("risk") == "WATCH"],
        all(row.get("risk") != "WATCH" for row in release_rows),
    )
    if require_dashboard:
        dashboard_release = dashboard_payload.get("release_metrics", {}) if isinstance(dashboard_payload.get("release_metrics", {}), dict) else {}
        dashboard_fingerprints = (
            dashboard_payload.get("artifact_fingerprints", {})
            if isinstance(dashboard_payload.get("artifact_fingerprints", {}), dict)
            else {}
        )
        add_check(checks, "dashboard_status", "PASS", dashboard_payload.get("status", "MISSING"), dashboard_payload.get("status") == "PASS")
        add_check(
            checks,
            "dashboard_version",
            DASHBOARD_VERSION,
            dashboard_payload.get("dashboard_version", ""),
            dashboard_payload.get("dashboard_version") == DASHBOARD_VERSION,
        )
        add_check(checks, "dashboard_scope_sets", sets, dashboard_payload.get("sets", []), dashboard_payload.get("sets", []) == sets)
        add_check(
            checks,
            "dashboard_scope_pages",
            expected_pages,
            dashboard_payload.get("expected_pages"),
            dashboard_payload.get("expected_pages") == expected_pages,
        )
        add_check(
            checks,
            "dashboard_release_metrics",
            {"rows": EXPECTED_RELEASE_METRIC_ROWS, "fail": 0, "watch": 0},
            dashboard_release,
            dashboard_release.get("rows") == EXPECTED_RELEASE_METRIC_ROWS
            and dashboard_release.get("fail") == 0
            and dashboard_release.get("watch") == 0,
        )
        fingerprint_mismatches: list[str] = []
        for filename in DASHBOARD_INPUT_FILENAMES:
            expected_hash = sha256_file(audit_dir / filename)
            actual_hash = ""
            fingerprint = dashboard_fingerprints.get(filename, {})
            if isinstance(fingerprint, dict):
                actual_hash = str(fingerprint.get("sha256", ""))
            if actual_hash != expected_hash:
                fingerprint_mismatches.append(filename)
        add_check(checks, "dashboard_input_fingerprints", "current input hashes", fingerprint_mismatches, not fingerprint_mismatches)

    required_outputs = [
        "g1_layout_quality_loop_summary.csv",
        "g1_layout_quality_loop_summary.md",
        "g1_layout_binding_metrics.csv",
        "g1_layout_short_answer_metrics.csv",
        "g1_layout_source_trace.csv",
        "g1_layout_source_trace_detail.csv",
        "g1_layout_source_order.csv",
        "g1_layout_source_order_detail.csv",
        "g1_layout_anchor_deltas.csv",
        "g1_layout_density_metrics.csv",
        "g1_layout_package_manifest.csv",
        "g1_layout_signature_manifest.csv",
        "g1_layout_signature_manifest.json",
        "g1_layout_release_metrics.csv",
        "g1_layout_reproducibility_report.md",
        "g1_layout_schema_contract.json",
    ]
    if require_dashboard:
        required_outputs.extend(["g1_layout_quality_dashboard.md", "g1_layout_quality_dashboard.json"])
    missing_outputs = [name for name in required_outputs if not (audit_dir / name).exists()]
    add_check(checks, "required_outputs", "all present", missing_outputs, not missing_outputs)

    status = "PASS" if all(check["status"] == "PASS" for check in checks) else "FAIL"
    return {
        "contract_version": CONTRACT_VERSION,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "status": status,
        "sets": sets,
        "expected_pages": expected_pages,
        "thresholds": {
            "gates_per_set": EXPECTED_GATES_PER_SET,
            "binding_rows_per_set": EXPECTED_BINDING_ROWS_PER_SET,
            "short_answer_rows_per_set": EXPECTED_SHORT_ANSWER_ROWS_PER_SET,
            "source_snippets_per_set": EXPECTED_SOURCE_SNIPPETS_PER_SET,
            "source_order_rows_per_set": EXPECTED_SOURCE_ORDER_ROWS_PER_SET,
            "anchor_rows_per_set": EXPECTED_ANCHOR_ROWS_PER_SET,
            "density_rows_per_set": EXPECTED_DENSITY_ROWS_PER_SET,
            "signature_rows_per_set": EXPECTED_SIGNATURE_ROWS_PER_SET,
            "release_metric_rows": EXPECTED_RELEASE_METRIC_ROWS,
        },
        "checks": checks,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sets", default="51-62")
    parser.add_argument("--audit-dir", default=str(DEFAULT_AUDIT_DIR))
    parser.add_argument("--expected-pages", type=int, default=4)
    parser.add_argument("--require-dashboard", action="store_true")
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    args = parser.parse_args()

    payload = contract_for(Path(args.audit_dir), parse_set_range(args.sets), args.expected_pages, args.require_dashboard)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    failures = [check["name"] for check in payload["checks"] if check["status"] != "PASS"]
    print(f"contract={out} status={payload['status']} checks={len(payload['checks'])} failures={len(failures)}")
    if failures:
        print("contract_failures=" + ",".join(failures))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
