# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import csv
import subprocess
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PYTHON = Path(sys.executable)
AUDIT_DIR = ROOT / "output" / "layout_audit"
PDF_DIR = ROOT / "output" / "pdf"
DEFAULT_REPORT = AUDIT_DIR / "g1_layout_reproducibility_report.md"


def timestamp_slug() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def run_command(name: str, command: list[str]) -> tuple[str, int]:
    print(f"[repro:{name}] {' '.join(command)}")
    completed = subprocess.run(command, cwd=ROOT)
    status = "PASS" if completed.returncode == 0 else "FAIL"
    print(f"[repro:{name}] {status}")
    return name, completed.returncode


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def latest_rows_by_set(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    latest: dict[str, dict[str, str]] = {}
    for row in rows:
        set_id = row.get("set", "")
        if set_id:
            latest[set_id] = row
    return [latest[key] for key in sorted(latest, key=lambda value: int(value))]


def rows_by_key(rows: list[dict[str, str]], keys: list[str]) -> dict[tuple[str, ...], dict[str, str]]:
    return {tuple(row.get(key, "") for key in keys): row for row in rows}


def compare_rows(
    label: str,
    current_rows: list[dict[str, str]],
    repro_rows: list[dict[str, str]],
    keys: list[str],
    fields: list[str],
) -> tuple[bool, str]:
    current = rows_by_key(current_rows, keys)
    repro = rows_by_key(repro_rows, keys)
    current_keys = set(current)
    repro_keys = set(repro)
    if current_keys != repro_keys:
        missing = sorted(current_keys - repro_keys)[:5]
        extra = sorted(repro_keys - current_keys)[:5]
        return False, f"{label}: key mismatch missing={missing} extra={extra}"

    mismatches: list[str] = []
    for key in sorted(current_keys):
        for field in fields:
            if current[key].get(field, "") != repro[key].get(field, ""):
                mismatches.append(f"{key}:{field}:{current[key].get(field, '')}!={repro[key].get(field, '')}")
                break
    if mismatches:
        return False, f"{label}: value mismatch " + " | ".join(mismatches[:5])
    return True, f"{label}: matched rows={len(current_keys)}"


def status_all_pass(rows: list[dict[str, str]]) -> bool:
    return bool(rows) and all(row.get("status") == "PASS" for row in rows)


def manifest_hash_matches(current_rows: list[dict[str, str]], repro_rows: list[dict[str, str]]) -> tuple[int, int]:
    current = rows_by_key(current_rows, ["set"])
    repro = rows_by_key(repro_rows, ["set"])
    total = len(set(current) & set(repro))
    matches = sum(1 for key in set(current) & set(repro) if current[key].get("sha256") == repro[key].get("sha256"))
    return matches, total


def write_report(
    path: Path,
    repro_root: Path,
    step_results: list[tuple[str, int]],
    comparisons: list[tuple[bool, str]],
    binary_hash_match: tuple[int, int],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    status = "PASS" if all(code == 0 for _name, code in step_results) and all(ok for ok, _detail in comparisons) else "FAIL"
    hash_matches, hash_total = binary_hash_match
    lines = [
        "# 광영여고 고1 레이아웃 재현성 검수 리포트",
        "",
        f"- 생성 시각: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"- 재렌더링 디렉터리: `{repro_root}`",
        f"- 최종 결과: `{status}`",
        f"- 바이너리 SHA 동일: `{hash_matches}/{hash_total}`",
        "- 주의: ReportLab PDF는 메타데이터/ID 때문에 바이너리 SHA가 달라질 수 있으므로, 최종 PASS 기준은 layout signature이다.",
        "",
        "## Steps",
        "",
        "| step | exit_code | status |",
        "|---|---:|---:|",
    ]
    for name, code in step_results:
        lines.append(f"| {name} | {code} | {'PASS' if code == 0 else 'FAIL'} |")
    lines.extend(["", "## Signature Comparisons", "", "| comparison | status | detail |", "|---|---:|---|"])
    for ok, detail in comparisons:
        label = detail.split(":", 1)[0]
        lines.append(f"| {label} | {'PASS' if ok else 'FAIL'} | {detail} |")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sets", default="51-62")
    parser.add_argument("--source", default="")
    parser.add_argument("--expected-pages", type=int, default=4)
    parser.add_argument("--report", default=str(DEFAULT_REPORT))
    args = parser.parse_args()

    repro_root = AUDIT_DIR / "repro_runs" / timestamp_slug()
    repro_pdf_dir = repro_root / "pdf"
    repro_audit_dir = repro_root / "audit"
    repro_pdf_dir.mkdir(parents=True, exist_ok=True)
    repro_audit_dir.mkdir(parents=True, exist_ok=True)

    source_args = ["--source", args.source] if args.source else []
    step_results = [
        run_command(
            "render_audit",
            [
                str(PYTHON),
                "tools/run_g1_layout_quality_loop.py",
                "--sets",
                args.sets,
                "--max-cycles",
                "1",
                "--mode",
                "body",
                "--expected-pages",
                str(args.expected_pages),
                "--out-dir",
                str(repro_pdf_dir),
                "--audit-dir",
                str(repro_audit_dir),
                "--summary-csv",
                str(repro_root / "g1_layout_quality_loop_summary.csv"),
                "--summary-md",
                str(repro_root / "g1_layout_quality_loop_summary.md"),
                *source_args,
            ],
        ),
        run_command(
            "binding_metrics",
            [
                str(PYTHON),
                "tools/export_g1_layout_metrics.py",
                "--sets",
                args.sets,
                "--pdf-dir",
                str(repro_pdf_dir),
                "--out",
                str(repro_root / "g1_layout_binding_metrics.csv"),
            ],
        ),
        run_command(
            "source_trace",
            [
                str(PYTHON),
                "tools/export_g1_layout_source_trace.py",
                "--sets",
                args.sets,
                "--pdf-dir",
                str(repro_pdf_dir),
                "--out",
                str(repro_root / "g1_layout_source_trace.csv"),
                "--detail-out",
                str(repro_root / "g1_layout_source_trace_detail.csv"),
                *source_args,
            ],
        ),
        run_command(
            "source_order",
            [
                str(PYTHON),
                "tools/export_g1_layout_source_order.py",
                "--sets",
                args.sets,
                "--pdf-dir",
                str(repro_pdf_dir),
                "--out",
                str(repro_root / "g1_layout_source_order.csv"),
                "--detail-out",
                str(repro_root / "g1_layout_source_order_detail.csv"),
                *source_args,
            ],
        ),
        run_command(
            "short_answer_metrics",
            [
                str(PYTHON),
                "tools/export_g1_layout_short_answer_metrics.py",
                "--sets",
                args.sets,
                "--pdf-dir",
                str(repro_pdf_dir),
                "--out",
                str(repro_root / "g1_layout_short_answer_metrics.csv"),
            ],
        ),
        run_command(
            "anchor_deltas",
            [
                str(PYTHON),
                "tools/export_g1_layout_anchor_deltas.py",
                "--sets",
                args.sets,
                "--pdf-dir",
                str(repro_pdf_dir),
                "--out",
                str(repro_root / "g1_layout_anchor_deltas.csv"),
            ],
        ),
        run_command(
            "density_metrics",
            [
                str(PYTHON),
                "tools/export_g1_layout_density_metrics.py",
                "--sets",
                args.sets,
                "--pdf-dir",
                str(repro_pdf_dir),
                "--out",
                str(repro_root / "g1_layout_density_metrics.csv"),
            ],
        ),
        run_command(
            "package_manifest",
            [
                str(PYTHON),
                "tools/export_g1_layout_package_manifest.py",
                "--sets",
                args.sets,
                "--pdf-dir",
                str(repro_pdf_dir),
                "--audit-dir",
                str(repro_audit_dir),
                "--expected-pages",
                str(args.expected_pages),
                "--out",
                str(repro_root / "g1_layout_package_manifest.csv"),
            ],
        ),
        run_command(
            "layout_signature",
            [
                str(PYTHON),
                "tools/export_g1_layout_signature.py",
                "--sets",
                args.sets,
                "--pdf-dir",
                str(repro_pdf_dir),
                "--expected-pages",
                str(args.expected_pages),
                "--out",
                str(repro_root / "g1_layout_signature_manifest.csv"),
                "--json-out",
                str(repro_root / "g1_layout_signature_manifest.json"),
            ],
        ),
        run_command(
            "release_metrics",
            [
                str(PYTHON),
                "tools/export_g1_layout_release_metrics.py",
                "--audit-dir",
                str(repro_root),
                "--out",
                str(repro_root / "g1_layout_release_metrics.csv"),
            ],
        ),
    ]

    current_quality = latest_rows_by_set(read_csv(AUDIT_DIR / "g1_layout_quality_loop_summary.csv"))
    repro_quality = latest_rows_by_set(read_csv(repro_root / "g1_layout_quality_loop_summary.csv"))
    current_binding = read_csv(AUDIT_DIR / "g1_layout_binding_metrics.csv")
    repro_binding = read_csv(repro_root / "g1_layout_binding_metrics.csv")
    current_source = read_csv(AUDIT_DIR / "g1_layout_source_trace.csv")
    repro_source = read_csv(repro_root / "g1_layout_source_trace.csv")
    current_source_detail = read_csv(AUDIT_DIR / "g1_layout_source_trace_detail.csv")
    repro_source_detail = read_csv(repro_root / "g1_layout_source_trace_detail.csv")
    current_source_order = read_csv(AUDIT_DIR / "g1_layout_source_order.csv")
    repro_source_order = read_csv(repro_root / "g1_layout_source_order.csv")
    current_source_order_detail = read_csv(AUDIT_DIR / "g1_layout_source_order_detail.csv")
    repro_source_order_detail = read_csv(repro_root / "g1_layout_source_order_detail.csv")
    current_short_answer = read_csv(AUDIT_DIR / "g1_layout_short_answer_metrics.csv")
    repro_short_answer = read_csv(repro_root / "g1_layout_short_answer_metrics.csv")
    current_anchor = read_csv(AUDIT_DIR / "g1_layout_anchor_deltas.csv")
    repro_anchor = read_csv(repro_root / "g1_layout_anchor_deltas.csv")
    current_density = read_csv(AUDIT_DIR / "g1_layout_density_metrics.csv")
    repro_density = read_csv(repro_root / "g1_layout_density_metrics.csv")
    current_manifest = read_csv(AUDIT_DIR / "g1_layout_package_manifest.csv")
    repro_manifest = read_csv(repro_root / "g1_layout_package_manifest.csv")
    current_signature = read_csv(AUDIT_DIR / "g1_layout_signature_manifest.csv")
    repro_signature = read_csv(repro_root / "g1_layout_signature_manifest.csv")
    current_release = read_csv(AUDIT_DIR / "g1_layout_release_metrics.csv")
    repro_release = read_csv(repro_root / "g1_layout_release_metrics.csv")

    comparisons = [
        compare_rows("quality", current_quality, repro_quality, ["set"], ["status", "pass", "warn", "fail", "pages"]),
        compare_rows("binding", current_binding, repro_binding, ["set", "marker", "dependent_type"], ["status", "page", "lead_x", "lead_y", "dependent_y", "gap_pt"]),
        compare_rows("source", current_source, repro_source, ["set"], ["status", "expected_snippets", "matched_snippets", "missing_snippets", "match_rate"]),
        compare_rows("source_detail", current_source_detail, repro_source_detail, ["set", "snippet_index"], ["status", "matched", "snippet_length", "snippet"]),
        compare_rows("source_order", current_source_order, repro_source_order, ["set"], ["status", "expected_snippets", "ordered_snippets", "out_of_order_snippets", "first_bad_snippet"]),
        compare_rows("source_order_detail", current_source_order_detail, repro_source_order_detail, ["set", "snippet_index"], ["status", "ordered", "start_offset", "end_offset", "previous_end_offset", "snippet"]),
        compare_rows("short_answer", current_short_answer, repro_short_answer, ["set", "marker"], ["status", "page", "column_x", "lead_y", "slot_count", "slot_top_y", "slot_bottom_y", "block_height_pt"]),
        compare_rows("anchor", current_anchor, repro_anchor, ["set", "anchor", "page"], ["status", "actual_x", "actual_y", "delta_x", "delta_y"]),
        compare_rows("density", current_density, repro_density, ["set", "page", "column"], ["status", "anchor_count", "used_height_pt", "top_y", "bottom_y", "max_gap_pt", "density_score"]),
        compare_rows("manifest_structure", current_manifest, repro_manifest, ["set"], ["status", "pages", "bytes"]),
        compare_rows("layout_signature", current_signature, repro_signature, ["set"], ["status", "pages", "text_run_count", "line_segment_count", "layout_sha256", "page_signatures"]),
        compare_rows("release_metrics", current_release, repro_release, ["metric_group", "metric"], ["status", "risk", "actual", "limit", "headroom", "utilization_pct", "spread"]),
    ]

    comparisons.extend(
        [
            (status_all_pass(repro_quality), "repro_quality_status: all PASS"),
            (status_all_pass(repro_binding), "repro_binding_status: all PASS"),
            (status_all_pass(repro_source), "repro_source_status: all PASS"),
            (status_all_pass(repro_source_detail), "repro_source_detail_status: all PASS"),
            (status_all_pass(repro_source_order), "repro_source_order_status: all PASS"),
            (status_all_pass(repro_source_order_detail), "repro_source_order_detail_status: all PASS"),
            (status_all_pass(repro_short_answer), "repro_short_answer_status: all PASS"),
            (status_all_pass(repro_anchor), "repro_anchor_status: all PASS"),
            (status_all_pass(repro_density), "repro_density_status: all PASS"),
            (status_all_pass(repro_manifest), "repro_manifest_status: all PASS"),
            (status_all_pass(repro_signature), "repro_signature_status: all PASS"),
            (status_all_pass(repro_release), "repro_release_metrics_status: all PASS"),
        ]
    )
    binary_match = manifest_hash_matches(current_manifest, repro_manifest)
    write_report(Path(args.report), repro_root, step_results, comparisons, binary_match)

    failures = [name for name, code in step_results if code != 0]
    failures.extend(detail for ok, detail in comparisons if not ok)
    if failures:
        print("reproducibility_tests=FAIL")
        for failure in failures[:8]:
            print(failure)
        return 1
    print("reproducibility_tests=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
