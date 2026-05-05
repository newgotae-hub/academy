# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PYTHON = Path(sys.executable)
DEFAULT_REPORT = ROOT / "output" / "layout_audit" / "g1_layout_full_verification_report.md"


def run_step(name: str, args: list[str]) -> int:
    print(f"[{name}] {' '.join(args)}")
    completed = subprocess.run(args, cwd=ROOT)
    if completed.returncode != 0:
        print(f"[{name}] FAIL exit={completed.returncode}")
    else:
        print(f"[{name}] PASS")
    return completed.returncode


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sets", default="51-62")
    parser.add_argument("--source", default="")
    parser.add_argument("--expected-pages", type=int, default=4)
    parser.add_argument("--report", default=str(DEFAULT_REPORT))
    args = parser.parse_args()

    source_args: list[str] = []
    if args.source:
        source_args = ["--source", args.source]

    steps = [
        (
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
                *source_args,
            ],
        ),
        (
            "binding_metrics",
            [
                str(PYTHON),
                "tools/export_g1_layout_metrics.py",
                "--sets",
                args.sets,
            ],
        ),
        (
            "short_answer_metrics",
            [
                str(PYTHON),
                "tools/export_g1_layout_short_answer_metrics.py",
                "--sets",
                args.sets,
            ],
        ),
        (
            "source_trace",
            [
                str(PYTHON),
                "tools/export_g1_layout_source_trace.py",
                "--sets",
                args.sets,
                *source_args,
            ],
        ),
        (
            "source_order",
            [
                str(PYTHON),
                "tools/export_g1_layout_source_order.py",
                "--sets",
                args.sets,
                *source_args,
            ],
        ),
        (
            "anchor_deltas",
            [
                str(PYTHON),
                "tools/export_g1_layout_anchor_deltas.py",
                "--sets",
                args.sets,
            ],
        ),
        (
            "density_metrics",
            [
                str(PYTHON),
                "tools/export_g1_layout_density_metrics.py",
                "--sets",
                args.sets,
            ],
        ),
        (
            "package_manifest",
            [
                str(PYTHON),
                "tools/export_g1_layout_package_manifest.py",
                "--sets",
                args.sets,
                "--expected-pages",
                str(args.expected_pages),
            ],
        ),
        (
            "layout_signature",
            [
                str(PYTHON),
                "tools/export_g1_layout_signature.py",
                "--sets",
                args.sets,
                "--expected-pages",
                str(args.expected_pages),
            ],
        ),
        (
            "release_metrics",
            [
                str(PYTHON),
                "tools/export_g1_layout_release_metrics.py",
            ],
        ),
        (
            "gate_meta_tests",
            [
                str(PYTHON),
                "tools/test_g1_layout_quality_gates.py",
            ],
        ),
        (
            "schema_contract",
            [
                str(PYTHON),
                "tools/export_g1_layout_schema_contract.py",
                "--sets",
                args.sets,
                "--expected-pages",
                str(args.expected_pages),
                "--expected-gates",
                "26",
            ],
        ),
        (
            "layout_contract_pre",
            [
                str(PYTHON),
                "tools/export_g1_layout_contract.py",
                "--sets",
                args.sets,
                "--expected-pages",
                str(args.expected_pages),
            ],
        ),
        (
            "quality_dashboard",
            [
                str(PYTHON),
                "tools/export_g1_layout_quality_dashboard.py",
            ],
        ),
        (
            "dashboard_contract",
            [
                str(PYTHON),
                "tools/export_g1_layout_contract.py",
                "--sets",
                args.sets,
                "--expected-pages",
                str(args.expected_pages),
                "--require-dashboard",
            ],
        ),
        (
            "editable_package_export",
            [
                str(PYTHON),
                "tools/export_g1_editable_package.py",
                "--sets",
                args.sets,
                *source_args,
            ],
        ),
        (
            "editable_package_contract",
            [
                str(PYTHON),
                "tools/audit_g1_editable_package.py",
                "--sets",
                args.sets,
                "--expected-pages",
                str(args.expected_pages),
                *source_args,
            ],
        ),
        (
            "reproducibility_tests",
            [
                str(PYTHON),
                "tools/test_g1_layout_reproducibility.py",
                "--sets",
                args.sets,
                "--expected-pages",
                str(args.expected_pages),
                *source_args,
            ],
        ),
        (
            "py_compile",
            [
                str(PYTHON),
                "-m",
                "py_compile",
                "tools/render_g1_exam_layout.py",
                "tools/audit_g1_exam_layout.py",
                "tools/run_g1_layout_quality_loop.py",
                "tools/export_g1_layout_metrics.py",
                "tools/export_g1_layout_short_answer_metrics.py",
                "tools/export_g1_layout_source_trace.py",
                "tools/export_g1_layout_source_order.py",
                "tools/export_g1_layout_anchor_deltas.py",
                "tools/export_g1_layout_density_metrics.py",
                "tools/export_g1_layout_package_manifest.py",
                "tools/export_g1_layout_signature.py",
                "tools/export_g1_layout_release_metrics.py",
                "tools/test_g1_layout_quality_gates.py",
                "tools/export_g1_layout_quality_dashboard.py",
                "tools/export_g1_layout_contract.py",
                "tools/export_g1_layout_schema_contract.py",
                "tools/export_g1_editable_package.py",
                "tools/audit_g1_editable_package.py",
                "tools/test_g1_layout_reproducibility.py",
                "tools/run_g1_layout_full_verification.py",
            ],
        ),
    ]

    failures: list[str] = []
    step_results: list[tuple[str, int]] = []
    skipped_steps: list[str] = []
    for index, (name, command) in enumerate(steps):
        exit_code = run_step(name, command)
        step_results.append((name, exit_code))
        if exit_code != 0:
            failures.append(name)
            skipped_steps = [step_name for step_name, _command in steps[index + 1 :]]
            print("[fail_fast] skipped=" + ",".join(skipped_steps))
            break

    write_report(Path(args.report), args.sets, args.source, args.expected_pages, step_results, skipped_steps)
    if failures:
        print("FULL_VERIFICATION=FAIL " + ",".join(failures))
        return 1
    print("FULL_VERIFICATION=PASS")
    return 0


def write_report(
    path: Path,
    sets: str,
    source: str,
    expected_pages: int,
    step_results: list[tuple[str, int]],
    skipped_steps: list[str],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    status = "PASS" if all(exit_code == 0 for _name, exit_code in step_results) else "FAIL"
    lines = [
        "# 광영여고 고1 레이아웃 통합 검증 리포트",
        "",
        f"- 생성 시각: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"- 세트: `{sets}`",
        f"- source: `{source or 'default'}`",
        f"- expected pages: `{expected_pages}`",
        f"- fail-fast skipped steps: `{', '.join(skipped_steps) if skipped_steps else 'none'}`",
        f"- 최종 결과: `{status}`",
        "",
        "| step | exit_code | status |",
        "|---|---:|---:|",
    ]
    for name, exit_code in step_results:
        lines.append(f"| {name} | {exit_code} | {'PASS' if exit_code == 0 else 'FAIL'} |")
    lines.extend(
        [
            "",
            "## 산출물",
            "",
            "- `output/layout_audit/g1_layout_quality_loop_summary.csv`",
            "- `output/layout_audit/g1_layout_quality_loop_summary.md`",
            "- `output/layout_audit/g1_layout_binding_metrics.csv`",
            "- `output/layout_audit/g1_layout_short_answer_metrics.csv`",
            "- `output/layout_audit/g1_layout_source_trace.csv`",
            "- `output/layout_audit/g1_layout_source_trace_detail.csv`",
            "- `output/layout_audit/g1_layout_source_order.csv`",
            "- `output/layout_audit/g1_layout_source_order_detail.csv`",
            "- `output/layout_audit/g1_layout_anchor_deltas.csv`",
            "- `output/layout_audit/g1_layout_density_metrics.csv`",
            "- `output/layout_audit/g1_layout_package_manifest.csv`",
            "- `output/layout_audit/g1_layout_signature_manifest.csv`",
            "- `output/layout_audit/g1_layout_signature_manifest.json`",
            "- `output/layout_audit/g1_layout_release_metrics.csv`",
            "- `output/layout_audit/g1_layout_quality_dashboard.md`",
            "- `output/layout_audit/g1_layout_quality_dashboard.json`",
            "- `output/layout_audit/g1_layout_contract.json`",
            "- `output/layout_audit/g1_layout_schema_contract.json`",
            "- `output/layout_audit/g1_layout_reproducibility_report.md`",
            "- `output/pdf/g1_mid_set51_layout.pdf` ... `output/pdf/g1_mid_set62_layout.pdf`",
            "- `output/editable_package/g1_mid_editable_package_manifest.csv`",
            "- `output/editable_package/g1_mid_editable_package_contract.md`",
            "- `output/editable_package/g1_mid_editable_package_contract.json`",
            "- `output/editable_package/README.md`",
            "- `output/editable_package/BUYER_README.md`",
            "- `output/editable_package/OPERATOR_README.md`",
            "- `output/editable_package/g1_mid_editable_release_dashboard.md`",
            "- `output/editable_package/g1_mid_editable_release_dashboard.json`",
            "- `output/editable_package/g1_mid_editable_release_receipt.md`",
            "- `output/editable_package/g1_mid_editable_release_receipt.json`",
            "- `output/editable_package/pdf/g1_mid_set51_layout.pdf` ... `output/editable_package/pdf/g1_mid_set62_layout.pdf`",
            "- `output/editable_package/docx/g1_mid_set51_editable.docx` ... `output/editable_package/docx/g1_mid_set62_editable.docx`",
            "- `output/광영여고_고1_1학기중간_본문동형_PDF_DOCX_편집패키지.zip`",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
