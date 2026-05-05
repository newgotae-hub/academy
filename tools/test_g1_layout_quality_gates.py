# -*- coding: utf-8 -*-
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

from audit_g1_exam_layout import (
    DEFAULT_ACTUAL,
    DEFAULT_SOURCE,
    Check,
    extract_source_block,
    make_checks,
)
from export_g1_layout_anchor_deltas import rows_for_set as anchor_rows_for_set
from export_g1_layout_density_metrics import rows_for_set as density_rows_for_set
from export_g1_layout_metrics import measure_set as binding_rows_for_set
from export_g1_layout_package_manifest import row_for_set as manifest_row_for_set
from export_g1_layout_release_metrics import EXPECTED_METRIC_KEYS, EXPECTED_RELEASE_ROWS, build_metrics as release_metric_rows
from export_g1_layout_schema_contract import SCHEMAS
from export_g1_layout_short_answer_metrics import rows_for_set as short_answer_rows_for_set
from export_g1_layout_signature import row_for_set as signature_row_for_set
from export_g1_layout_source_order import (
    ordered_detail_rows_for_set as source_order_detail_rows_for_set,
    row_for_set as source_order_row_for_set,
)
from export_g1_layout_source_trace import (
    detail_rows_for_set as source_trace_detail_rows_for_set,
    row_for_set as source_trace_row_for_set,
)


ROOT = Path(__file__).resolve().parents[1]
PDF_DIR = ROOT / "output" / "pdf"
AUDIT_DIR = ROOT / "output" / "layout_audit"
SETS = [str(value) for value in range(51, 63)]


REQUIRED_GATES = {
    "page_size_a4",
    "page_count",
    "header_identity",
    "page_number_labels",
    "footer_per_page_anchor",
    "body_item_coverage",
    "exam_notice",
    "body_item_marker_counts",
    "source_block_digest_match",
    "source_order_signature_match",
    "objective_choice_symbol_counts",
    "objective_full_option_block_containment",
    "short_and_multi_select_structure",
    "structured_cardinality_exactness",
    "short_answer_block_containment",
    "no_answerline_orphan_at_page_start",
    "body_text_vertical_bounds",
    "font_size_profile",
    "outer_exam_grid",
    "body_header_table_grid",
    "two_column_text_anchors",
    "body_anchor_positions",
    "passage_title_firstline_binding",
    "top_level_marker_order_and_min_gap",
    "question_dependent_binding",
    "cover_fixed_positions",
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def by_name(checks: list[Check], name: str) -> Check:
    for check in checks:
        if check.name == name:
            return check
    raise AssertionError(f"missing check: {name}")


def assert_main_audit_passes() -> None:
    for set_id in SETS:
        pdf = PDF_DIR / f"g1_mid_set{set_id}_layout.pdf"
        checks = make_checks(DEFAULT_ACTUAL, pdf, "body", 4, DEFAULT_SOURCE)
        names = {check.name for check in checks}
        missing = sorted(REQUIRED_GATES - names)
        require(not missing, f"set {set_id} missing required gates: " + ", ".join(missing))
        failures = [check for check in checks if check.status == "FAIL"]
        warnings = [check for check in checks if check.status == "WARN"]
        require(not failures, f"set {set_id} unexpected audit failures: " + ", ".join(check.name for check in failures))
        require(not warnings, f"set {set_id} unexpected audit warnings: " + ", ".join(check.name for check in warnings))


def assert_negative_controls_fail() -> None:
    pdf = PDF_DIR / "g1_mid_set51_layout.pdf"
    page_checks = make_checks(DEFAULT_ACTUAL, pdf, "body", 5, DEFAULT_SOURCE)
    require(by_name(page_checks, "page_count").status == "FAIL", "page_count negative control did not fail")

    source_block = extract_source_block(DEFAULT_SOURCE, "51")
    require(source_block is not None, "could not read set 51 source block")
    first_line = source_block.splitlines()[0]
    temp_dir = ROOT / "output" / "layout_audit" / "_gate_test_tmp"
    temp_dir.mkdir(parents=True, exist_ok=True)
    bad_source = temp_dir / "bad_source.md"
    try:
        bad_source.write_text(first_line + "\n\n### 6-8. bad source\nNot enough snippets.\n", encoding="utf-8")
        bad_checks = make_checks(DEFAULT_ACTUAL, pdf, "body", 4, bad_source)
        digest_gate = by_name(bad_checks, "source_block_digest_match")
        require(digest_gate.status == "FAIL", "source digest negative control did not fail")
    finally:
        try:
            bad_source.unlink()
            temp_dir.rmdir()
        except OSError:
            pass


def assert_metric_rows_pass() -> None:
    binding_rows = []
    short_answer_rows = []
    source_rows = []
    source_detail_rows = []
    source_order_rows = []
    source_order_detail_rows = []
    anchor_rows = []
    density_rows = []
    manifest_rows = []
    signature_rows = []
    for set_id in SETS:
        pdf = PDF_DIR / f"g1_mid_set{set_id}_layout.pdf"
        binding_rows.extend(binding_rows_for_set(pdf, set_id))
        short_answer_rows.extend(short_answer_rows_for_set(pdf, set_id))
        source_rows.append(source_trace_row_for_set(set_id, DEFAULT_SOURCE, PDF_DIR))
        source_detail_rows.extend(source_trace_detail_rows_for_set(set_id, DEFAULT_SOURCE, PDF_DIR))
        source_order_rows.append(source_order_row_for_set(set_id, DEFAULT_SOURCE, PDF_DIR))
        source_order_detail_rows.extend(source_order_detail_rows_for_set(set_id, DEFAULT_SOURCE, PDF_DIR))
        anchor_rows.extend(anchor_rows_for_set(pdf, set_id))
        density_rows.extend(density_rows_for_set(pdf, set_id))
        manifest_rows.append(manifest_row_for_set(set_id, PDF_DIR, AUDIT_DIR, 4))
        signature_row, _signature_detail = signature_row_for_set(set_id, PDF_DIR, 4)
        signature_rows.append(signature_row)

    require(len(binding_rows) == 96, f"binding row count changed: {len(binding_rows)}")
    require(len(short_answer_rows) == 24, f"short answer row count changed: {len(short_answer_rows)}")
    require(len(source_rows) == 12, f"source row count changed: {len(source_rows)}")
    require(len(source_detail_rows) == 384, f"source detail row count changed: {len(source_detail_rows)}")
    require(len(source_order_rows) == 12, f"source order row count changed: {len(source_order_rows)}")
    require(len(source_order_detail_rows) == 384, f"source order detail row count changed: {len(source_order_detail_rows)}")
    require(len(anchor_rows) == 264, f"anchor row count changed: {len(anchor_rows)}")
    require(len(density_rows) == 36, f"density row count changed: {len(density_rows)}")
    require(len(manifest_rows) == 12, f"manifest row count changed: {len(manifest_rows)}")
    require(len(signature_rows) == 12, f"signature row count changed: {len(signature_rows)}")
    release_rows = release_metric_rows(AUDIT_DIR)
    require(len(release_rows) == EXPECTED_RELEASE_ROWS, f"release metric row count changed: {len(release_rows)}")
    release_keys = [(row["metric_group"], row["metric"]) for row in release_rows]
    require(release_keys == EXPECTED_METRIC_KEYS, "release metric key set changed")
    require(not [row for row in release_rows if row["risk"] == "FAIL"], "release metric has FAIL risk")

    for label, rows in [
        ("binding", binding_rows),
        ("short_answer", short_answer_rows),
        ("source", source_rows),
        ("source_detail", source_detail_rows),
        ("source_order", source_order_rows),
        ("source_order_detail", source_order_detail_rows),
        ("anchor", anchor_rows),
        ("density", density_rows),
        ("manifest", manifest_rows),
        ("signature", signature_rows),
        ("release_metrics", release_rows),
    ]:
        bad = [row for row in rows if row["status"] != "PASS"]
        require(not bad, f"{label} rows failed: " + "; ".join(str(row) for row in bad[:3]))


def assert_dashboard_missing_input_fails() -> None:
    temp_dir = AUDIT_DIR / "_dashboard_missing_input"
    out = temp_dir / "dashboard.md"
    json_out = temp_dir / "g1_layout_quality_dashboard.json"
    if temp_dir.exists():
        shutil.rmtree(temp_dir)
    temp_dir.mkdir(parents=True, exist_ok=True)
    try:
        completed = subprocess.run(
            [
                sys.executable,
                "tools/export_g1_layout_quality_dashboard.py",
                "--audit-dir",
                str(temp_dir),
                "--out",
                str(out),
                "--json-out",
                str(json_out),
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        require(completed.returncode != 0, "dashboard missing-input negative control did not fail")
        require(out.exists(), "dashboard missing-input negative control did not write diagnostic report")
        require(json_out.exists(), "dashboard missing-input negative control did not write diagnostic json")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def assert_schema_missing_input_fails() -> None:
    temp_dir = AUDIT_DIR / "_schema_missing_input"
    out = temp_dir / "schema.json"
    if temp_dir.exists():
        shutil.rmtree(temp_dir)
    temp_dir.mkdir(parents=True, exist_ok=True)
    try:
        completed = subprocess.run(
            [
                sys.executable,
                "tools/export_g1_layout_schema_contract.py",
                "--audit-dir",
                str(temp_dir),
                "--out",
                str(out),
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        require(completed.returncode != 0, "schema missing-input negative control did not fail")
        require(out.exists(), "schema missing-input negative control did not write diagnostic report")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def assert_schema_corrupt_input_fails() -> None:
    temp_dir = AUDIT_DIR / "_schema_corrupt_input"
    out = temp_dir / "schema.json"
    if temp_dir.exists():
        shutil.rmtree(temp_dir)
    temp_dir.mkdir(parents=True, exist_ok=True)
    try:
        for filename in SCHEMAS:
            shutil.copy2(AUDIT_DIR / filename, temp_dir / filename)

        source_order_detail = temp_dir / "g1_layout_source_order_detail.csv"
        with source_order_detail.open("r", encoding="utf-8-sig", newline="") as handle:
            rows = list(handle.readlines())
        require(len(rows) > 2, "source order detail fixture is unexpectedly empty")
        rows.append(rows[1])
        source_order_detail.write_text("".join(rows), encoding="utf-8-sig")

        completed = subprocess.run(
            [
                sys.executable,
                "tools/export_g1_layout_schema_contract.py",
                "--audit-dir",
                str(temp_dir),
                "--sets",
                "51-62",
                "--expected-pages",
                "4",
                "--expected-gates",
                "26",
                "--out",
                str(out),
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        require(completed.returncode != 0, "schema corrupt-input negative control did not fail")
        require(out.exists(), "schema corrupt-input negative control did not write diagnostic report")
        require("status=FAIL" in completed.stdout, "schema corrupt-input negative control did not report FAIL")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def main() -> int:
    assert_main_audit_passes()
    assert_negative_controls_fail()
    assert_metric_rows_pass()
    assert_dashboard_missing_input_fails()
    assert_schema_missing_input_fails()
    assert_schema_corrupt_input_fails()
    print("gate_meta_tests=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
