# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_AUDIT_DIR = ROOT / "output" / "layout_audit"
DEFAULT_OUT = DEFAULT_AUDIT_DIR / "g1_layout_quality_dashboard.md"
DEFAULT_JSON_OUT = DEFAULT_AUDIT_DIR / "g1_layout_quality_dashboard.json"
DASHBOARD_VERSION = "g1-mid-layout-dashboard-v1"

INPUT_FILENAMES = [
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


def read_required_csv(label: str, path: Path, input_failures: list[str]) -> list[dict[str, str]]:
    if not path.exists():
        input_failures.append(f"{label}:missing")
        return []
    rows = read_csv(path)
    if not rows:
        input_failures.append(f"{label}:empty")
    return rows


def read_json_payload(path: Path) -> dict[str, object]:
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


def artifact_fingerprints(audit_dir: Path) -> dict[str, dict[str, object]]:
    fingerprints: dict[str, dict[str, object]] = {}
    for filename in INPUT_FILENAMES:
        path = audit_dir / filename
        row_count = len(read_csv(path)) if path.suffix.lower() == ".csv" and path.exists() else None
        fingerprints[filename] = {
            "exists": path.exists(),
            "bytes": path.stat().st_size if path.exists() else 0,
            "sha256": sha256_file(path),
            "rows": row_count,
        }
    return fingerprints


def latest_rows_by_set(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    latest: dict[str, dict[str, str]] = {}
    for row in rows:
        set_id = row.get("set", "")
        if set_id:
            latest[set_id] = row
    return [latest[key] for key in sorted(latest, key=lambda value: int(value))]


def status_summary(rows: list[dict[str, str]]) -> tuple[int, int]:
    failed = sum(1 for row in rows if row.get("status") != "PASS")
    return len(rows) - failed, failed


def grouped(rows: list[dict[str, str]], key: str) -> dict[str, list[dict[str, str]]]:
    groups: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        groups[row.get(key, "")].append(row)
    return dict(groups)


def float_value(row: dict[str, str], key: str) -> float:
    try:
        return float(row.get(key, "0") or "0")
    except ValueError:
        return 0.0


def md_escape(value: str) -> str:
    return value.replace("|", " / ")


def append_status_table(sections: list[str], label_rows: list[tuple[str, list[dict[str, str]]]], schema_status: str, contract_status: str) -> None:
    sections.extend(["## Gate Summary", "", "| 영역 | PASS | FAIL |", "|---|---:|---:|"])
    for label, rows in label_rows:
        passed, failed = status_summary(rows)
        sections.append(f"| {label} | {passed} | {failed} |")
    sections.append(f"| CSV schema contract | {1 if schema_status == 'PASS' else 0} | {0 if schema_status == 'PASS' else 1} |")
    sections.append(f"| Layout contract | {1 if contract_status == 'PASS' else 0} | {0 if contract_status == 'PASS' else 1} |")


def append_release_verdict(sections: list[str], release_rows: list[dict[str, str]], failures: list[str]) -> None:
    failed_metrics = [row for row in release_rows if row.get("status") != "PASS"]
    watch_metrics = [row for row in release_rows if row.get("risk") == "WATCH"]
    verdict = "SHIP" if not failures and not failed_metrics else "NO-SHIP"
    sections.extend(
        [
            "## Release Verdict",
            "",
            f"- 판정: `{verdict}`",
            f"- release metric: `{len(release_rows) - len(failed_metrics)}/{len(release_rows)} PASS`",
            f"- watch metric: `{len(watch_metrics)}`",
            "- 해석: `WATCH`는 실패가 아니라 여유가 적은 지점이다. 판매 전 수동 시각 검수 우선순위로 본다.",
            "",
        ]
    )
    if watch_metrics:
        sections.extend(["### Watch List", "", "| group | metric | util% | headroom | detail |", "|---|---|---:|---:|---|"])
        ranked = sorted(watch_metrics, key=lambda row: float_value(row, "utilization_pct"), reverse=True)
        for row in ranked[:12]:
            sections.append(
                f"| {row.get('metric_group')} | {md_escape(row.get('metric', ''))} | {float_value(row, 'utilization_pct'):.2f} | {float_value(row, 'headroom'):.2f} | {md_escape(row.get('detail', ''))} |"
            )
        sections.append("")


def build_payload(
    audit_dir: Path,
    status: str,
    quality_rows: list[dict[str, str]],
    release_rows: list[dict[str, str]],
    schema_payload: dict[str, object],
    contract_payload: dict[str, object],
    input_failures: list[str],
) -> dict[str, object]:
    sets = [row.get("set", "") for row in quality_rows if row.get("set", "")]
    pages = sorted({int(float(row.get("pages", "0") or "0")) for row in quality_rows})
    failed_metrics = [row for row in release_rows if row.get("status") != "PASS"]
    watch_metrics = [row for row in release_rows if row.get("risk") == "WATCH"]
    return {
        "dashboard_version": DASHBOARD_VERSION,
        "status": status,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "sets": sets,
        "expected_pages": pages[0] if len(pages) == 1 else None,
        "input_failures": input_failures,
        "release_metrics": {
            "rows": len(release_rows),
            "pass": len(release_rows) - len(failed_metrics),
            "fail": len(failed_metrics),
            "watch": len(watch_metrics),
        },
        "schema_contract": {
            "version": schema_payload.get("schema_contract_version", ""),
            "status": schema_payload.get("status", "MISSING"),
            "checks": len(schema_payload.get("checks", [])) if isinstance(schema_payload.get("checks", []), list) else 0,
        },
        "layout_contract": {
            "version": contract_payload.get("contract_version", ""),
            "status": contract_payload.get("status", "MISSING"),
            "checks": len(contract_payload.get("checks", [])) if isinstance(contract_payload.get("checks", []), list) else 0,
        },
        "artifact_fingerprints": artifact_fingerprints(audit_dir),
    }


def append_release_metrics(sections: list[str], release_rows: list[dict[str, str]]) -> None:
    sections.extend(["## Release Metrics", "", "| group | metric | n | actual | limit | headroom | util% | risk |", "|---|---|---:|---:|---:|---:|---:|---:|"])
    for row in release_rows:
        sections.append(
            f"| {row.get('metric_group')} | {md_escape(row.get('metric', ''))} | {row.get('n')} | {row.get('actual')} | {row.get('limit')} | {row.get('headroom')} | {row.get('utilization_pct')} | {row.get('risk')} |"
        )


def append_source_sections(
    sections: list[str],
    source_rows: list[dict[str, str]],
    source_detail_rows: list[dict[str, str]],
    source_order_rows: list[dict[str, str]],
    source_order_detail_rows: list[dict[str, str]],
) -> None:
    sections.extend(["", "## Source Integrity", "", "| set | expected | matched | missing | ordered | out_of_order | status |", "|---:|---:|---:|---:|---:|---:|---:|"])
    order_by_set = {row.get("set", ""): row for row in source_order_rows}
    for row in source_rows:
        order = order_by_set.get(row.get("set", ""), {})
        status = "PASS" if row.get("status") == "PASS" and order.get("status") == "PASS" else "FAIL"
        sections.append(
            f"| {row.get('set')} | {row.get('expected_snippets')} | {row.get('matched_snippets')} | {row.get('missing_snippets')} | {order.get('ordered_snippets')} | {order.get('out_of_order_snippets')} | {status} |"
        )

    sections.extend(["", "### Source Detail Totals", "", "| table | rows | PASS | FAIL |", "|---|---:|---:|---:|"])
    for label, rows in [("source_trace_detail", source_detail_rows), ("source_order_detail", source_order_detail_rows)]:
        passed, failed = status_summary(rows)
        sections.append(f"| {label} | {len(rows)} | {passed} | {failed} |")


def append_package_sections(
    sections: list[str],
    manifest_rows: list[dict[str, str]],
    signature_rows: list[dict[str, str]],
    schema_payload: dict[str, object],
    contract_payload: dict[str, object],
) -> None:
    total_bytes = sum(int(row.get("bytes", "0") or "0") for row in manifest_rows)
    sections.extend(
        [
            "",
            "## Package Integrity",
            "",
            f"- PDF count: `{len(manifest_rows)}`",
            f"- total bytes: `{total_bytes}`",
            f"- schema contract: `{schema_payload.get('status', 'MISSING')}` / `{schema_payload.get('schema_contract_version', '')}`",
            f"- layout contract: `{contract_payload.get('status', 'MISSING')}` / `{contract_payload.get('contract_version', '')}`",
            "",
            "| set | pages | bytes | pdf sha12 | layout sha12 | status |",
            "|---:|---:|---:|---|---|---:|",
        ]
    )
    signature_by_set = {row.get("set", ""): row for row in signature_rows}
    for row in manifest_rows:
        signature = signature_by_set.get(row.get("set", ""), {})
        status = "PASS" if row.get("status") == "PASS" and signature.get("status") == "PASS" else "FAIL"
        sections.append(
            f"| {row.get('set')} | {row.get('pages')} | {row.get('bytes')} | {row.get('sha256', '')[:12]} | {signature.get('layout_sha256', '')[:12]} | {status} |"
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--audit-dir", default=str(DEFAULT_AUDIT_DIR))
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument("--json-out", default=str(DEFAULT_JSON_OUT))
    args = parser.parse_args()

    audit_dir = Path(args.audit_dir)
    input_failures: list[str] = []
    quality_rows = latest_rows_by_set(read_required_csv("quality", audit_dir / "g1_layout_quality_loop_summary.csv", input_failures))
    binding_rows = read_required_csv("binding", audit_dir / "g1_layout_binding_metrics.csv", input_failures)
    short_answer_rows = read_required_csv("short_answer", audit_dir / "g1_layout_short_answer_metrics.csv", input_failures)
    source_rows = read_required_csv("source", audit_dir / "g1_layout_source_trace.csv", input_failures)
    source_detail_rows = read_required_csv("source_detail", audit_dir / "g1_layout_source_trace_detail.csv", input_failures)
    source_order_rows = read_required_csv("source_order", audit_dir / "g1_layout_source_order.csv", input_failures)
    source_order_detail_rows = read_required_csv("source_order_detail", audit_dir / "g1_layout_source_order_detail.csv", input_failures)
    anchor_rows = read_required_csv("anchor", audit_dir / "g1_layout_anchor_deltas.csv", input_failures)
    density_rows = read_required_csv("density", audit_dir / "g1_layout_density_metrics.csv", input_failures)
    manifest_rows = read_required_csv("manifest", audit_dir / "g1_layout_package_manifest.csv", input_failures)
    signature_rows = read_required_csv("signature", audit_dir / "g1_layout_signature_manifest.csv", input_failures)
    release_rows = read_required_csv("release_metrics", audit_dir / "g1_layout_release_metrics.csv", input_failures)
    schema_payload = read_json_payload(audit_dir / "g1_layout_schema_contract.json")
    contract_payload = read_json_payload(audit_dir / "g1_layout_contract.json")
    schema_status = str(schema_payload.get("status", "MISSING"))
    contract_status = str(contract_payload.get("status", "MISSING"))

    label_rows = [
        ("PDF 구조 게이트", quality_rows),
        ("문항 결속", binding_rows),
        ("단답형 블록", short_answer_rows),
        ("원천 누락 추적", source_rows),
        ("원천 누락 상세", source_detail_rows),
        ("원천 순서 추적", source_order_rows),
        ("원천 순서 상세", source_order_detail_rows),
        ("좌표 오차", anchor_rows),
        ("지면 밀도", density_rows),
        ("PDF manifest", manifest_rows),
        ("Layout signature", signature_rows),
        ("Release metrics", release_rows),
    ]

    failures = list(input_failures)
    for label, rows in label_rows:
        _passed, failed = status_summary(rows)
        if failed:
            failures.append(label)
    if schema_status != "PASS":
        failures.append("schema_contract")
    if contract_status != "PASS":
        failures.append("layout_contract")

    sections: list[str] = [
        "# 광영여고 고1 본문동형 레이아웃 Release Dashboard",
        "",
        f"- 생성 시각: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"- 최종 상태: `{'FAIL' if failures else 'PASS'}`",
        "",
    ]

    if input_failures:
        sections.extend(["## Input Failures", "", "| failure |", "|---|"])
        for failure in input_failures:
            sections.append(f"| {failure} |")
        sections.append("")

    append_release_verdict(sections, release_rows, failures)
    append_status_table(sections, label_rows, schema_status, contract_status)
    sections.append("")
    append_release_metrics(sections, release_rows)
    append_source_sections(sections, source_rows, source_detail_rows, source_order_rows, source_order_detail_rows)
    append_package_sections(sections, manifest_rows, signature_rows, schema_payload, contract_payload)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(sections) + "\n", encoding="utf-8")
    payload = build_payload(audit_dir, "FAIL" if failures else "PASS", quality_rows, release_rows, schema_payload, contract_payload, input_failures)
    json_out = Path(args.json_out)
    json_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"dashboard={out} json={json_out} status={'FAIL' if failures else 'PASS'}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
