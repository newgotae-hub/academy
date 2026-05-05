# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from pathlib import Path
from statistics import pstdev

from export_g1_layout_anchor_deltas import BODY_ANCHORS, COVER_ANCHORS
from export_g1_layout_density_metrics import EXPECTED_COLUMN_PROFILES


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_AUDIT_DIR = ROOT / "output" / "layout_audit"
DEFAULT_OUT = DEFAULT_AUDIT_DIR / "g1_layout_release_metrics.csv"

EXPECTED_RELEASE_ROWS = 30
EXPECTED_METRIC_KEYS = [
    ("release", "full_verification_gate_summary"),
    ("binding_margin", "10."),
    ("binding_margin", "11."),
    ("binding_margin", "6."),
    ("binding_margin", "7."),
    ("binding_margin", "8."),
    ("binding_margin", "9."),
    ("binding_margin", "단답형 1."),
    ("binding_margin", "단답형 2."),
    ("short_answer_variance", "단답형 1."),
    ("short_answer_variance", "단답형 2."),
    ("anchor_margin", "body_6_8_title"),
    ("anchor_margin", "body_9_11_title"),
    ("anchor_margin", "body_q6"),
    ("anchor_margin", "body_short2"),
    ("anchor_margin", "cover_date"),
    ("anchor_margin", "cover_notice"),
    ("anchor_margin", "cover_print"),
    ("anchor_margin", "cover_subject"),
    ("anchor_margin", "cover_title_term"),
    ("anchor_margin", "cover_title_year"),
    ("anchor_margin", "footer_page_label"),
    ("anchor_margin", "footer_school"),
    ("anchor_margin", "footer_school_en"),
    ("density_print_risk", "2/R"),
    ("density_print_risk", "3/L"),
    ("density_print_risk", "4/L"),
    ("source_integrity", "source_trace_missing"),
    ("source_integrity", "source_order_out_of_order"),
    ("package_integrity", "manifest_signature_consistency"),
]
BINDING_WATCH_UTILIZATION_PCT = 85.0
BINDING_WATCH_HEADROOM_PT = 20.0
ANCHOR_WATCH_UTILIZATION_PCT = 85.0
DENSITY_WATCH_UTILIZATION_PCT = 95.0
DENSITY_BOTTOM_HEADROOM_WATCH_PT = 12.0
SHORT_ANSWER_SPREAD_LIMIT_PT = 30.0
SHORT_ANSWER_WATCH_UTILIZATION_PCT = 90.0


FOOTER_TOLERANCES = {
    "footer_page_label": (18.0, 2.0),
    "footer_school": (12.0, 2.0),
    "footer_school_en": (12.0, 2.0),
}


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


def group_by(rows: list[dict[str, str]], key: str) -> dict[str, list[dict[str, str]]]:
    groups: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        groups[row.get(key, "")].append(row)
    return dict(groups)


def to_float(value: str, default: float = 0.0) -> float:
    if value == "":
        return default
    try:
        return float(value)
    except ValueError:
        return default


def risk_for(status: str, utilization_pct: float, watch_pct: float, headroom: float | None = None, min_headroom: float | None = None) -> str:
    if status != "PASS":
        return "FAIL"
    if utilization_pct >= watch_pct:
        return "WATCH"
    if headroom is not None and min_headroom is not None and headroom < min_headroom:
        return "WATCH"
    return "OK"


def fmt(value: float) -> str:
    return f"{value:.2f}"


def metric_row(
    metric_group: str,
    metric: str,
    n: int,
    actual: float,
    limit: float,
    headroom: float,
    utilization_pct: float,
    spread: float,
    status: str,
    risk: str,
    detail: str,
) -> dict[str, str]:
    return {
        "metric_group": metric_group,
        "metric": metric,
        "n": str(n),
        "actual": fmt(actual),
        "limit": fmt(limit),
        "headroom": fmt(headroom),
        "utilization_pct": fmt(utilization_pct),
        "spread": fmt(spread),
        "status": status,
        "risk": risk,
        "detail": detail,
    }


def anchor_tolerances() -> dict[str, tuple[float, float]]:
    tolerances: dict[str, tuple[float, float]] = {}
    for name, _needle, _expected_x, _expected_y, tol_x, tol_y, _min_y in COVER_ANCHORS:
        tolerances[name] = (tol_x, tol_y)
    for name, _page_no, _needle, _expected_x, _expected_y, tol_x, tol_y in BODY_ANCHORS:
        tolerances[name] = (tol_x, tol_y)
    tolerances.update(FOOTER_TOLERANCES)
    return tolerances


def quality_metric(rows: list[dict[str, str]]) -> dict[str, str]:
    latest = latest_rows_by_set(rows)
    total_warn = sum(int(to_float(row.get("warn", ""))) for row in latest)
    total_fail = sum(int(to_float(row.get("fail", ""))) for row in latest)
    bad_status = sum(1 for row in latest if row.get("status") != "PASS")
    actual = float(total_warn + total_fail + bad_status)
    status = "PASS" if actual == 0 and len(latest) == 12 else "FAIL"
    return metric_row(
        "release",
        "full_verification_gate_summary",
        len(latest),
        actual,
        0.0,
        0.0 if actual == 0 else -actual,
        0.0 if actual == 0 else 100.0,
        0.0,
        status,
        "OK" if status == "PASS" else "FAIL",
        "latest quality rows have zero WARN/FAIL and PASS status" if status == "PASS" else "quality rows contain WARN/FAIL",
    )


def binding_metrics(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    metrics: list[dict[str, str]] = []
    for marker, marker_rows in sorted(group_by(rows, "marker").items()):
        gaps = [to_float(row.get("gap_pt", "")) for row in marker_rows]
        limits = [to_float(row.get("max_gap_pt", "")) for row in marker_rows]
        headrooms = [limit - gap for gap, limit in zip(gaps, limits)]
        utilization = max((gap / limit * 100.0 for gap, limit in zip(gaps, limits) if limit > 0), default=100.0)
        min_headroom = min(headrooms) if headrooms else -1.0
        max_gap = max(gaps) if gaps else 0.0
        limit = max(limits) if limits else 0.0
        spread = max(gaps) - min(gaps) if gaps else 0.0
        status = "PASS" if marker_rows and all(row.get("status") == "PASS" for row in marker_rows) and min_headroom >= 0 else "FAIL"
        metrics.append(
            metric_row(
                "binding_margin",
                marker,
                len(marker_rows),
                max_gap,
                limit,
                min_headroom,
                utilization,
                spread,
                status,
                risk_for(status, utilization, BINDING_WATCH_UTILIZATION_PCT, min_headroom, BINDING_WATCH_HEADROOM_PT),
                f"max first-dependent gap by marker; min headroom={min_headroom:.1f}pt",
            )
        )
    return metrics


def short_answer_metrics(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    metrics: list[dict[str, str]] = []
    for marker, marker_rows in sorted(group_by(rows, "marker").items()):
        heights = [to_float(row.get("block_height_pt", "")) for row in marker_rows if row.get("block_height_pt", "")]
        spread = max(heights) - min(heights) if heights else SHORT_ANSWER_SPREAD_LIMIT_PT + 1.0
        status = "PASS" if marker_rows and all(row.get("status") == "PASS" for row in marker_rows) and spread <= SHORT_ANSWER_SPREAD_LIMIT_PT else "FAIL"
        utilization = spread / SHORT_ANSWER_SPREAD_LIMIT_PT * 100.0
        metrics.append(
            metric_row(
                "short_answer_variance",
                marker,
                len(marker_rows),
                spread,
                SHORT_ANSWER_SPREAD_LIMIT_PT,
                SHORT_ANSWER_SPREAD_LIMIT_PT - spread,
                utilization,
                pstdev(heights) if len(heights) > 1 else 0.0,
                status,
                risk_for(status, utilization, SHORT_ANSWER_WATCH_UTILIZATION_PCT),
                f"block-height range {min(heights):.1f}-{max(heights):.1f}pt" if heights else "missing height values",
            )
        )
    return metrics


def anchor_metrics(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    metrics: list[dict[str, str]] = []
    tolerances = anchor_tolerances()
    for anchor, anchor_rows in sorted(group_by(rows, "anchor").items()):
        tol_x, tol_y = tolerances.get(anchor, (1.0, 1.0))
        utilizations = []
        abs_dx = []
        abs_dy = []
        for row in anchor_rows:
            dx = abs(to_float(row.get("delta_x", "")))
            dy = abs(to_float(row.get("delta_y", "")))
            abs_dx.append(dx)
            abs_dy.append(dy)
            utilizations.append(max(dx / tol_x * 100.0 if tol_x else 100.0, dy / tol_y * 100.0 if tol_y else 100.0))
        utilization = max(utilizations) if utilizations else 100.0
        max_dx = max(abs_dx) if abs_dx else 0.0
        max_dy = max(abs_dy) if abs_dy else 0.0
        status = "PASS" if anchor_rows and all(row.get("status") == "PASS" for row in anchor_rows) and utilization <= 100.0 else "FAIL"
        metrics.append(
            metric_row(
                "anchor_margin",
                anchor,
                len(anchor_rows),
                utilization,
                100.0,
                100.0 - utilization,
                utilization,
                max(max(abs_dx) - min(abs_dx), max(abs_dy) - min(abs_dy)) if abs_dx and abs_dy else 0.0,
                status,
                risk_for(status, utilization, ANCHOR_WATCH_UTILIZATION_PCT),
                f"max dx={max_dx:.2f}pt/{tol_x:.1f}pt, max dy={max_dy:.2f}pt/{tol_y:.1f}pt",
            )
        )
    return metrics


def density_metrics(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    metrics: list[dict[str, str]] = []
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[f"{row.get('page')}/{row.get('column')}"].append(row)
    for key, profile_rows in sorted(grouped.items()):
        page, column = key.split("/", 1)
        profile = EXPECTED_COLUMN_PROFILES[(int(page), column)]
        gaps = [to_float(row.get("max_gap_pt", "")) for row in profile_rows]
        bottoms = [to_float(row.get("bottom_y", "")) for row in profile_rows]
        counts = [int(to_float(row.get("anchor_count", ""))) for row in profile_rows]
        max_gap = max(gaps) if gaps else profile["max_gap"] + 1.0
        min_bottom = min(bottoms) if bottoms else 0.0
        gap_utilization = max_gap / profile["max_gap"] * 100.0
        bottom_headroom = min_bottom - profile["min_y"]
        count_ok = all(profile["min_count"] <= count <= profile["max_count"] for count in counts)
        status = "PASS" if profile_rows and all(row.get("status") == "PASS" for row in profile_rows) and count_ok and bottom_headroom >= 0 else "FAIL"
        utilization = max(gap_utilization, 0.0 if bottom_headroom >= 0 else 100.0)
        risk = risk_for(status, utilization, DENSITY_WATCH_UTILIZATION_PCT)
        if status == "PASS" and bottom_headroom < DENSITY_BOTTOM_HEADROOM_WATCH_PT:
            risk = "WATCH"
        metrics.append(
            metric_row(
                "density_print_risk",
                key,
                len(profile_rows),
                max_gap,
                profile["max_gap"],
                min(profile["max_gap"] - max_gap, bottom_headroom),
                utilization,
                (max(gaps) - min(gaps)) if gaps else 0.0,
                status,
                risk,
                f"count range={min(counts) if counts else 0}-{max(counts) if counts else 0}, bottom headroom={bottom_headroom:.1f}pt",
            )
        )
    return metrics


def source_metrics(source_rows: list[dict[str, str]], order_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    missing = sum(int(to_float(row.get("missing_snippets", ""))) for row in source_rows)
    out_of_order = sum(int(to_float(row.get("out_of_order_snippets", ""))) for row in order_rows)
    coverage_status = "PASS" if source_rows and missing == 0 and all(row.get("status") == "PASS" for row in source_rows) else "FAIL"
    order_status = "PASS" if order_rows and out_of_order == 0 and all(row.get("status") == "PASS" for row in order_rows) else "FAIL"
    return [
        metric_row("source_integrity", "source_trace_missing", len(source_rows), float(missing), 0.0, 0.0 if missing == 0 else -float(missing), 0.0 if missing == 0 else 100.0, 0.0, coverage_status, "OK" if coverage_status == "PASS" else "FAIL", "all source digest snippets are present"),
        metric_row("source_integrity", "source_order_out_of_order", len(order_rows), float(out_of_order), 0.0, 0.0 if out_of_order == 0 else -float(out_of_order), 0.0 if out_of_order == 0 else 100.0, 0.0, order_status, "OK" if order_status == "PASS" else "FAIL", "all source snippets preserve extraction order"),
    ]


def package_metric(manifest_rows: list[dict[str, str]], signature_rows: list[dict[str, str]]) -> dict[str, str]:
    failures = sum(1 for row in manifest_rows + signature_rows if row.get("status") != "PASS")
    page_failures = sum(1 for row in manifest_rows + signature_rows if row.get("pages") != "4")
    actual = float(failures + page_failures)
    status = "PASS" if manifest_rows and signature_rows and actual == 0 else "FAIL"
    return metric_row(
        "package_integrity",
        "manifest_signature_consistency",
        min(len(manifest_rows), len(signature_rows)),
        actual,
        0.0,
        0.0 if actual == 0 else -actual,
        0.0 if actual == 0 else 100.0,
        0.0,
        status,
        "OK" if status == "PASS" else "FAIL",
        "manifest and layout signature rows are captured for every 4-page PDF",
    )


def build_metrics(audit_dir: Path) -> list[dict[str, str]]:
    quality_rows = read_csv(audit_dir / "g1_layout_quality_loop_summary.csv")
    binding_rows = read_csv(audit_dir / "g1_layout_binding_metrics.csv")
    short_rows = read_csv(audit_dir / "g1_layout_short_answer_metrics.csv")
    anchor_rows = read_csv(audit_dir / "g1_layout_anchor_deltas.csv")
    density_rows = read_csv(audit_dir / "g1_layout_density_metrics.csv")
    source_rows = read_csv(audit_dir / "g1_layout_source_trace.csv")
    order_rows = read_csv(audit_dir / "g1_layout_source_order.csv")
    manifest_rows = read_csv(audit_dir / "g1_layout_package_manifest.csv")
    signature_rows = read_csv(audit_dir / "g1_layout_signature_manifest.csv")

    metrics: list[dict[str, str]] = [quality_metric(quality_rows)]
    metrics.extend(binding_metrics(binding_rows))
    metrics.extend(short_answer_metrics(short_rows))
    metrics.extend(anchor_metrics(anchor_rows))
    metrics.extend(density_metrics(density_rows))
    metrics.extend(source_metrics(source_rows, order_rows))
    metrics.append(package_metric(manifest_rows, signature_rows))
    return metrics


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--audit-dir", default=str(DEFAULT_AUDIT_DIR))
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    args = parser.parse_args()

    rows = build_metrics(Path(args.audit_dir))
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "metric_group",
        "metric",
        "n",
        "actual",
        "limit",
        "headroom",
        "utilization_pct",
        "spread",
        "status",
        "risk",
        "detail",
    ]
    with out.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    failures = [row for row in rows if row["status"] != "PASS"]
    actual_keys = [(row["metric_group"], row["metric"]) for row in rows]
    key_mismatch = actual_keys != EXPECTED_METRIC_KEYS
    print(f"rows={len(rows)} pass={len(rows) - len(failures)} fail={len(failures)} out={out}")
    if key_mismatch:
        print("release_metric_keys=FAIL")
    return 1 if failures or len(rows) != EXPECTED_RELEASE_ROWS or key_mismatch else 0


if __name__ == "__main__":
    raise SystemExit(main())
