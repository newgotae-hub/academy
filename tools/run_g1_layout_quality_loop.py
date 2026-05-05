# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import csv
import re
import time
from datetime import datetime
from pathlib import Path

from audit_g1_exam_layout import make_checks, write_report
from render_g1_exam_layout import DEFAULT_SOURCE, ROOT, render_pdf


DEFAULT_ACTUAL = ROOT / "tmp_actual_g1_mid.pdf"
DEFAULT_OUT_DIR = ROOT / "output" / "pdf"
DEFAULT_AUDIT_DIR = ROOT / "output" / "layout_audit"


def discover_sets(source: Path) -> list[str]:
    text = source.read_text(encoding="utf-8")
    return re.findall(r"(?m)^##\s+세트\s+([0-9]+)\s*$", text)


def parse_set_list(raw: str | None, source: Path) -> list[str]:
    if not raw:
        return discover_sets(source)
    sets: list[str] = []
    for part in raw.split(","):
        item = part.strip()
        if not item:
            continue
        if "-" in item:
            start, end = item.split("-", 1)
            sets.extend(str(value) for value in range(int(start), int(end) + 1))
        else:
            sets.append(item)
    return sets


def summarize_checks(checks) -> tuple[int, int, int, str, str]:
    passed = sum(1 for check in checks if check.status == "PASS")
    warned = sum(1 for check in checks if check.status == "WARN")
    failed = sum(1 for check in checks if check.status == "FAIL")
    first_fail = next((check.name for check in checks if check.status == "FAIL"), "")
    first_warn = next((check.name for check in checks if check.status == "WARN"), "")
    return passed, warned, failed, first_fail, first_warn


def write_markdown_summary(path: Path, rows: list[dict[str, str]]) -> None:
    pass_count = sum(1 for row in rows if row["status"] == "PASS")
    fail_count = sum(1 for row in rows if row["status"] == "FAIL")
    warn_count = sum(1 for row in rows if row["warn"] != "0")
    lines = [
        "# 광영여고 고1 레이아웃 품질 루프 요약",
        "",
        f"- 생성 시각: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"- 세트 수: {len(rows)}",
        f"- 통과 세트: {pass_count}",
        f"- 실패 세트: {fail_count}",
        f"- 경고 포함 세트: {warn_count}",
        "",
        "| cycle | set | status | pass | warn | fail | first issue | pages | output | report |",
        "|---:|---:|---|---:|---:|---:|---|---:|---|---|",
    ]
    for row in rows:
        issue = row["first_fail"] or row["first_warn"]
        lines.append(
            "| {cycle} | {set} | {status} | {pass} | {warn} | {fail} | {issue} | {pages} | `{output}` | `{report}` |".format(
                **row,
                issue=issue,
            )
        )
    path.write_text("\n".join(lines), encoding="utf-8")


def run_once(
    *,
    cycle: int,
    set_id: str,
    source: Path,
    actual: Path,
    out_dir: Path,
    audit_dir: Path,
    mode: str,
    expected_pages: int | None,
    title: str,
) -> dict[str, str]:
    out = out_dir / f"g1_mid_set{set_id}_layout.pdf"
    report = audit_dir / f"g1_mid_set{set_id}_layout_audit.md"
    start = time.perf_counter()

    render_pdf(set_id, source, out, title)
    checks = make_checks(actual, out, mode, expected_pages, source)
    write_report(report, actual, out, checks)
    passed, warned, failed, first_fail, first_warn = summarize_checks(checks)
    elapsed_ms = int((time.perf_counter() - start) * 1000)

    return {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "cycle": str(cycle),
        "set": set_id,
        "status": "FAIL" if failed else "PASS",
        "pass": str(passed),
        "warn": str(warned),
        "fail": str(failed),
        "first_fail": first_fail,
        "first_warn": first_warn,
        "pages": report_pages(out),
        "elapsed_ms": str(elapsed_ms),
        "output": str(out),
        "report": str(report),
    }


def report_pages(path: Path) -> str:
    from pypdf import PdfReader

    return str(len(PdfReader(str(path)).pages))


def append_csv(path: Path, rows: list[dict[str, str]]) -> None:
    fieldnames = [
        "timestamp",
        "cycle",
        "set",
        "status",
        "pass",
        "warn",
        "fail",
        "first_fail",
        "first_warn",
        "pages",
        "elapsed_ms",
        "output",
        "report",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    exists = path.exists()
    with path.open("a", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        if not exists:
            writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", default=str(DEFAULT_SOURCE))
    parser.add_argument("--actual", default=str(DEFAULT_ACTUAL))
    parser.add_argument("--sets", default=None, help="Comma list or range, e.g. 51,52,55-62. Default: all discovered sets.")
    parser.add_argument("--mode", choices=["body", "set51", "full"], default="body")
    parser.add_argument("--expected-pages", type=int, default=4)
    parser.add_argument("--max-cycles", type=int, default=1, help="0 means endless until interrupted.")
    parser.add_argument("--delay-seconds", type=float, default=2.0)
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    parser.add_argument("--audit-dir", default=str(DEFAULT_AUDIT_DIR))
    parser.add_argument("--summary-csv", default=str(DEFAULT_AUDIT_DIR / "g1_layout_quality_loop_summary.csv"))
    parser.add_argument("--summary-md", default=str(DEFAULT_AUDIT_DIR / "g1_layout_quality_loop_summary.md"))
    parser.add_argument("--title", default="광영여고 고1 1학기 중간 본문동형")
    args = parser.parse_args()

    source = Path(args.source)
    actual = Path(args.actual)
    out_dir = Path(args.out_dir)
    audit_dir = Path(args.audit_dir)
    summary_csv = Path(args.summary_csv)
    summary_md = Path(args.summary_md)
    sets = parse_set_list(args.sets, source)
    if not sets:
        raise ValueError(f"no sets found in source: {source}")

    all_rows: list[dict[str, str]] = []
    cycle = 0
    while True:
        cycle += 1
        cycle_rows: list[dict[str, str]] = []
        for set_id in sets:
            row = run_once(
                cycle=cycle,
                set_id=set_id,
                source=source,
                actual=actual,
                out_dir=out_dir,
                audit_dir=audit_dir,
                mode=args.mode,
                expected_pages=args.expected_pages,
                title=args.title,
            )
            cycle_rows.append(row)
            print(
                f"cycle={cycle} set={set_id} status={row['status']} "
                f"PASS={row['pass']} WARN={row['warn']} FAIL={row['fail']} pages={row['pages']}"
            )

        append_csv(summary_csv, cycle_rows)
        all_rows.extend(cycle_rows)
        write_markdown_summary(summary_md, all_rows)

        has_fail = any(row["status"] == "FAIL" for row in cycle_rows)
        if args.max_cycles > 0 and cycle >= args.max_cycles:
            break
        if not has_fail:
            break
        time.sleep(args.delay_seconds)

    return 1 if any(row["status"] == "FAIL" for row in all_rows) else 0


if __name__ == "__main__":
    raise SystemExit(main())
