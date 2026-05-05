# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass, asdict
from pathlib import Path

from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ACTUAL = ROOT / "tmp_actual_g1_mid.pdf"
DEFAULT_GENERATED = ROOT / "output" / "pdf" / "광영여고_고1_1학기중간_본문동형_세트51_시험지레이아웃.pdf"
DEFAULT_SOURCE = ROOT / "광영여고_고1_1학기중간_본문전용_추가문항_401-500_학생용.md"


@dataclass
class Check:
    name: str
    status: str
    detail: str


def compact(text: str) -> str:
    return " ".join((text or "").split())


def digest_normalize(text: str) -> str:
    text = re.sub(r"`([^`]+)`", r"\1", text or "")
    text = text.replace("**", "")
    text = re.sub(r"[\u3260-\u3266]", "", text)
    text = re.sub(r"[\u0400-\u04FF].", "", text)
    text = re.sub(r"[\u2460-\u2464]", "", text)
    text = re.sub(r"_{4,}", " ", text)
    text = re.sub(r"^\s*[1-5]\.\s+", "", text)
    text = re.sub(r"^###\s+", "", text)
    text = re.sub(r"\[[0-9.]+점\]", "", text)
    return compact(text)


def read_texts(path: Path) -> list[str]:
    reader = PdfReader(str(path))
    return [compact(page.extract_text() or "") for page in reader.pages]


def page_boxes(path: Path) -> list[tuple[float, float]]:
    reader = PdfReader(str(path))
    boxes: list[tuple[float, float]] = []
    for page in reader.pages:
        boxes.append((round(float(page.mediabox.width), 2), round(float(page.mediabox.height), 2)))
    return boxes


def line_segments(path: Path, page_index: int) -> list[tuple[float, float, float, float]]:
    segments: list[tuple[float, float, float, float]] = []
    current: tuple[float, float] | None = None

    def visitor(op, args, cm, tm):
        nonlocal current
        operator = op.decode() if isinstance(op, bytes) else str(op)
        if operator == "m" and len(args) >= 2:
            current = (float(args[0]), float(args[1]))
        elif operator == "l" and len(args) >= 2 and current is not None:
            x1, y1 = current
            x2, y2 = float(args[0]), float(args[1])
            segments.append((round(x1, 2), round(y1, 2), round(x2, 2), round(y2, 2)))
            current = (x2, y2)

    PdfReader(str(path)).pages[page_index].extract_text(visitor_operand_before=visitor)
    return segments


def text_positions(path: Path, page_index: int) -> list[tuple[float, float, str]]:
    positions: list[tuple[float, float, str]] = []

    def visitor(text, cm, tm, font_dict, font_size):
        value = (text or "").strip()
        if value:
            x = float(cm[4]) + float(tm[4])
            y = float(cm[5]) + float(tm[5])
            positions.append((round(x, 1), round(y, 1), value))

    PdfReader(str(path)).pages[page_index].extract_text(visitor_text=visitor)
    return positions


def text_runs(path: Path, page_index: int) -> list[tuple[float, float, float, str]]:
    runs: list[tuple[float, float, float, str]] = []

    def visitor(text, cm, tm, font_dict, font_size):
        value = (text or "").strip()
        if value:
            x = float(cm[4]) + float(tm[4])
            y = float(cm[5]) + float(tm[5])
            runs.append((round(x, 1), round(y, 1), round(float(font_size), 2), value))

    PdfReader(str(path)).pages[page_index].extract_text(visitor_text=visitor)
    return runs


def find_text_position(path: Path, page_index: int, needle: str) -> tuple[float, float] | None:
    for x, y, value in text_positions(path, page_index):
        if needle in value:
            return x, y
    return None


def find_text_positions(path: Path, page_index: int, needle: str) -> list[tuple[float, float]]:
    return [(x, y) for x, y, value in text_positions(path, page_index) if needle in value]


def find_text_run(path: Path, page_index: int, needle: str) -> tuple[float, float, float, str] | None:
    for run in text_runs(path, page_index):
        if needle in run[3]:
            return run
    return None


OPTION_POSITION_PREFIXES = ("①", "②", "③", "④", "⑤", "函", "刻", "券", "刷", "刺")
UNDERLINED_GRAMMAR_MARKERS = ("㉠", "㉡", "㉢", "㉣", "㉤", "㉥", "迂", "迆", "迅", "迄", "巡", "邑", "邢")


def is_objective_option_position(value: str) -> bool:
    return value.startswith(OPTION_POSITION_PREFIXES)


def is_answer_slot_position(value: str) -> bool:
    return value.startswith(("(A)", "(B)", "(C)", "(D)")) and "_" in value


def has_underlined_grammar_marker(value: str) -> bool:
    return any(marker in value for marker in UNDERLINED_GRAMMAR_MARKERS)


def is_body_column_x(x: float) -> bool:
    return approx_equal(x, 23.16, 4.0) or approx_equal(x, 304.44, 4.0)


def is_footer_or_header_text(value: str, y: float) -> bool:
    if y < 45.0 and any(token in value for token in ["Kwangyoung", "공통영어", "광영", "/"]):
        return True
    return False


def is_structural_body_anchor(value: str) -> bool:
    if re.match(r"^(6-8\.|9-11\.|[6-9]\.|10\.|11\.|단답형\s+[12]\.)", value):
        return True
    return is_objective_option_position(value) or is_answer_slot_position(value)


def is_pseudo_body_line(value: str) -> bool:
    if not value:
        return False
    if is_structural_body_anchor(value):
        return False
    if value.startswith("※") or "OMR" in value or "선택형" in value:
        return False
    return bool(re.search(r"[A-Za-z]", value))


def find_lead_position(
    generated: Path,
    page_count: int,
    marker: str,
    *,
    body_only: bool = True,
) -> tuple[int, float, float, str] | None:
    start_page = 1 if body_only else 0
    for page_index in range(start_page, page_count):
        for x, y, value in text_positions(generated, page_index):
            if value.startswith(marker):
                return page_index, x, y, value
    return None


def first_below_same_column(
    positions: list[tuple[float, float, str]],
    x: float,
    y: float,
    predicate,
) -> tuple[float, float, str] | None:
    candidates = [
        (candidate_x, candidate_y, value)
        for candidate_x, candidate_y, value in positions
        if approx_equal(candidate_x, x, 3.0) and candidate_y < y - 2.0 and predicate(value)
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda item: item[1])


def approx_equal(a: float, b: float, tolerance: float) -> bool:
    return abs(a - b) <= tolerance


def has_segment(segments: list[tuple[float, float, float, float]], target: tuple[float, float, float, float], tolerance: float = 1.0) -> bool:
    tx1, ty1, tx2, ty2 = target
    for x1, y1, x2, y2 in segments:
        if all(
            [
                approx_equal(x1, tx1, tolerance),
                approx_equal(y1, ty1, tolerance),
                approx_equal(x2, tx2, tolerance),
                approx_equal(y2, ty2, tolerance),
            ]
        ):
            return True
    return False


def contains_all(texts: list[str], needles: list[str]) -> tuple[bool, list[str]]:
    full = "\n".join(texts)
    missing = [needle for needle in needles if needle not in full]
    return not missing, missing


def full_text(texts: list[str]) -> str:
    return "\n".join(texts)


def infer_set_id(path: Path) -> str | None:
    match = re.search(r"set([0-9]+)", path.stem)
    return match.group(1) if match else None


def extract_source_block(source: Path, set_id: str) -> str | None:
    if not source.exists():
        return None
    lines = source.read_text(encoding="utf-8").splitlines()
    start = None
    for index, line in enumerate(lines):
        if line.startswith("## ") and "세트" in line and re.search(rf"(?<![0-9]){re.escape(set_id)}(?![0-9])", line):
            start = index
            break
    if start is None:
        return None
    end = len(lines)
    for index in range(start + 1, len(lines)):
        if lines[index].startswith("## "):
            end = index
            break
    return "\n".join(lines[start:end])


def source_digest_snippets(source_block: str) -> list[str]:
    snippets: list[str] = []
    for raw in source_block.splitlines():
        line = raw.strip()
        if not line or line.startswith("##") or line == "---" or "|" in line:
            continue
        if "________" in line:
            continue
        cleaned = digest_normalize(line)
        if len(cleaned) < 18 or cleaned.startswith("세트 "):
            continue
        snippet = cleaned if len(cleaned) <= 95 else cleaned[:95].rsplit(" ", 1)[0]
        if snippet not in snippets:
            snippets.append(snippet)
    return snippets


def count_item_markers(text: str, markers: list[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for marker in markers:
        if marker.startswith("단답형"):
            counts[marker] = len(re.findall(rf"(?<!\S){re.escape(marker)}", text))
        else:
            counts[marker] = len(re.findall(rf"(?<![0-9-]){re.escape(marker)}", text))
    return counts


def normalize_mode(mode: str) -> str:
    return "body" if mode == "set51" else mode


def make_checks(
    actual: Path,
    generated: Path,
    mode: str,
    expected_pages: int | None = None,
    source: Path | None = None,
) -> list[Check]:
    checks: list[Check] = []
    mode = normalize_mode(mode)

    actual_reader = PdfReader(str(actual))
    generated_reader = PdfReader(str(generated))
    actual_boxes = page_boxes(actual)
    generated_boxes = page_boxes(generated)
    generated_texts = read_texts(generated)
    generated_full = full_text(generated_texts)

    aw, ah = actual_boxes[0]
    gw, gh = generated_boxes[0]
    checks.append(
        Check(
            "page_size_a4",
            "PASS" if approx_equal(aw, gw, 1.0) and approx_equal(ah, gh, 1.0) else "FAIL",
            f"actual={aw}x{ah}pt generated={gw}x{gh}pt",
        )
    )

    generated_page_count = len(generated_reader.pages)
    if expected_pages is not None:
        page_count_ok = generated_page_count == expected_pages
        page_detail = f"mode={mode} expected_pages={expected_pages} actual_pages={len(actual_reader.pages)} generated_pages={generated_page_count}"
    elif mode == "full":
        page_count_ok = generated_page_count == len(actual_reader.pages)
        page_detail = f"mode={mode} actual_pages={len(actual_reader.pages)} generated_pages={generated_page_count}"
    else:
        page_count_ok = generated_page_count >= 2
        page_detail = f"mode={mode} actual_pages={len(actual_reader.pages)} generated_pages={generated_page_count}"
    checks.append(Check("page_count", "PASS" if page_count_ok else "FAIL", page_detail))

    header_ok, header_missing = contains_all(
        generated_texts,
        ["광영여자고등학교", "Kwangyoung Girls High School", "공통영어1", "고사계"],
    )
    checks.append(
        Check(
            "header_identity",
            "PASS" if header_ok else "FAIL",
            "missing=" + ", ".join(header_missing) if header_missing else "school/header text present",
        )
    )

    labels_missing: list[str] = []
    for i in range(1, len(generated_reader.pages) + 1):
        spaced = f"( {i} / {len(generated_reader.pages)} )"
        compact_label = f"({i}/{len(generated_reader.pages)})"
        if spaced not in generated_full and compact_label not in generated_full:
            labels_missing.append(f"{spaced} or {compact_label}")
    checks.append(
        Check(
            "page_number_labels",
            "PASS" if not labels_missing else "WARN",
            "missing=" + ", ".join(labels_missing) if labels_missing else "all page labels found",
        )
    )

    footer_failures: list[str] = []
    for page_index in range(len(generated_reader.pages)):
        page_no = page_index + 1
        runs = text_runs(generated, page_index)
        page_label = f"({page_no}/{generated_page_count})"
        label_runs = [run for run in runs if page_label in run[3]]
        if not any(approx_equal(run[0], 288.0, 18.0) and approx_equal(run[1], 31.2, 2.0) for run in label_runs):
            footer_failures.append(f"p{page_no}:page-label")
        school_runs = [run for run in runs if "광영여자고등학교" in run[3] and run[1] < 50.0]
        if not any(approx_equal(run[0], 437.0, 12.0) and approx_equal(run[1], 31.2, 2.0) for run in school_runs):
            footer_failures.append(f"p{page_no}:school")
        english_runs = [run for run in runs if "Kwangyoung Girls High School" in run[3]]
        if not any(approx_equal(run[0], 503.2, 12.0) and approx_equal(run[1], 26.3, 2.0) for run in english_runs):
            footer_failures.append(f"p{page_no}:english-school")
    checks.append(
        Check(
            "footer_per_page_anchor",
            "PASS" if not footer_failures else "FAIL",
            "footer page label and school identity are anchored on every page"
            if not footer_failures
            else "bad=" + ", ".join(footer_failures),
        )
    )

    content_needles = ["6-8.", "9-11.", "6.", "7.", "8.", "9.", "10.", "11.", "단답형 1.", "단답형 2."]
    content_ok, content_missing = contains_all(generated_texts, content_needles)
    checks.append(
        Check(
            "body_item_coverage",
            "PASS" if content_ok else "FAIL",
            "missing=" + ", ".join(content_missing) if content_missing else "question and short-answer markers present",
        )
    )

    notice_ok, notice_missing = contains_all(generated_texts, ["OMR 카드", "영(0)점"])
    checks.append(
        Check(
            "exam_notice",
            "PASS" if notice_ok else "WARN",
            "missing=" + ", ".join(notice_missing) if notice_missing else "OMR notice present",
        )
    )

    expected_markers = ["6.", "7.", "8.", "9.", "10.", "11.", "단답형 1.", "단답형 2."]
    marker_counts = count_item_markers(generated_full, expected_markers)
    bad_counts = [f"{marker}={count}" for marker, count in marker_counts.items() if count != 1]
    checks.append(
        Check(
            "body_item_marker_counts",
            "PASS" if not bad_counts else "FAIL",
            "each marker appears once" if not bad_counts else "bad_counts=" + ", ".join(bad_counts),
        )
    )

    source = source or DEFAULT_SOURCE
    set_id = infer_set_id(generated)
    digest_status = "WARN"
    digest_detail = "set id or source block unavailable"
    order_status = "WARN"
    order_detail = "set id or source block unavailable"
    if set_id is not None:
        source_block = extract_source_block(source, set_id)
        if source_block is None:
            digest_status = "WARN"
            digest_detail = f"source block unavailable for set={set_id}"
            order_status = "WARN"
            order_detail = f"source block unavailable for set={set_id}"
        else:
            snippets = source_digest_snippets(source_block)
            normalized_generated = digest_normalize(generated_full)
            missing_snippets = [snippet for snippet in snippets if snippet not in normalized_generated]
            if len(snippets) < 20:
                digest_status = "FAIL"
                digest_detail = f"too few source snippets={len(snippets)}"
                order_status = "FAIL"
                order_detail = f"too few source snippets={len(snippets)}"
            elif missing_snippets:
                digest_status = "FAIL"
                digest_detail = "missing=" + " | ".join(missing_snippets[:5])
                order_status = "FAIL"
                order_detail = "missing=" + " | ".join(missing_snippets[:5])
            else:
                digest_status = "PASS"
                digest_detail = f"source snippets matched={len(snippets)}"
                offsets: list[int] = []
                cursor = 0
                order_failures: list[str] = []
                for index, snippet in enumerate(snippets, start=1):
                    offset = normalized_generated.find(snippet, cursor)
                    if offset < 0:
                        earlier = normalized_generated.find(snippet)
                        if earlier >= 0:
                            order_failures.append(f"{index}:offset={earlier}<cursor={cursor}")
                        else:
                            order_failures.append(f"{index}:missing")
                        continue
                    offsets.append(offset)
                    cursor = offset + len(snippet)
                if order_failures:
                    order_status = "FAIL"
                    order_detail = "bad=" + ", ".join(order_failures[:5])
                else:
                    order_status = "PASS"
                    order_detail = f"source snippets ordered={len(offsets)}"
    checks.append(Check("source_block_digest_match", digest_status, digest_detail))
    checks.append(Check("source_order_signature_match", order_status, order_detail))

    choice_symbols = ["①", "②", "③", "④", "⑤"]
    symbol_counts = {symbol: generated_full.count(symbol) for symbol in choice_symbols}
    choice_failures = [f"{symbol}={count}" for symbol, count in symbol_counts.items() if count != 5]
    checks.append(
        Check(
            "objective_choice_symbol_counts",
            "PASS" if not choice_failures else "FAIL",
            "five objective questions have ①-⑤ choices" if not choice_failures else "bad_counts=" + ", ".join(choice_failures),
        )
    )

    structural_needles = ["(A)", "(B)", "(C)", "(D)", "->", "2개", "㉠", "㉡", "㉢", "㉣", "㉤"]
    option_block_failures: list[str] = []
    objective_markers = ["6.", "7.", "8.", "9.", "10."]
    for index, marker in enumerate(objective_markers):
        lead = find_lead_position(generated, generated_page_count, f"{marker} ")
        if lead is None:
            option_block_failures.append(f"{marker}:missing")
            continue
        page_index, x, y, _value = lead
        next_boundary_y = 0.0
        next_marker = objective_markers[index + 1] if index + 1 < len(objective_markers) else "11."
        next_lead = find_lead_position(generated, generated_page_count, f"{next_marker} ")
        if next_lead is not None and next_lead[0] == page_index and approx_equal(next_lead[1], x, 3.0):
            next_boundary_y = next_lead[2]
        option_positions = [
            (option_y, value)
            for option_x, option_y, value in text_positions(generated, page_index)
            if approx_equal(option_x, x, 3.0)
            and option_y < y - 2.0
            and option_y > next_boundary_y + 2.0
            and is_objective_option_position(value)
        ]
        option_positions.sort(key=lambda item: item[0], reverse=True)
        if len(option_positions) != 5:
            option_block_failures.append(f"{marker}:options={len(option_positions)}")
            continue
        if any(option_positions[i][0] <= option_positions[i + 1][0] for i in range(4)):
            option_block_failures.append(f"{marker}:option-y-order")
    checks.append(
        Check(
            "objective_full_option_block_containment",
            "PASS" if not option_block_failures else "FAIL",
            "each objective lead keeps all five options in the same page and column"
            if not option_block_failures
            else "bad=" + ", ".join(option_block_failures),
        )
    )

    structure_ok, structure_missing = contains_all(generated_texts, structural_needles)
    checks.append(
        Check(
            "short_and_multi_select_structure",
            "PASS" if structure_ok else "FAIL",
            "단답형 교정선/Q11 복수정답 구조 present" if structure_ok else "missing=" + ", ".join(structure_missing),
        )
    )

    cardinality_failures: list[str] = []
    answer_slot_values = [
        value
        for page_index in range(1, len(generated_reader.pages))
        for _x, _y, value in text_positions(generated, page_index)
        if is_answer_slot_position(value)
    ]
    correction_slots = [value for value in answer_slot_values if "->" in value]
    if len(correction_slots) != 4:
        cardinality_failures.append(f"short1-correction-slots={len(correction_slots)}")
    summary_slots = [value for value in answer_slot_values if "->" not in value and all(label in value for label in ["(A)", "(B)", "(C)", "(D)"])]
    if len(summary_slots) != 1:
        cardinality_failures.append(f"short2-summary-line={len(summary_slots)}")
    for label in ["(A)", "(B)", "(C)", "(D)"]:
        label_slots = [value for value in correction_slots if value.startswith(label)]
        if len(label_slots) != 1:
            cardinality_failures.append(f"short1-{label}={len(label_slots)}")
    q11 = find_lead_position(generated, generated_page_count, "11. ")
    if q11 is not None:
        page_index, x, y, _value = q11
        grammar_lines = [
            value
            for candidate_x, candidate_y, value in text_positions(generated, page_index)
            if approx_equal(candidate_x, x, 3.0) and candidate_y < y - 2.0 and has_underlined_grammar_marker(value)
        ]
        marker_hits = sum(1 for value in grammar_lines for marker in UNDERLINED_GRAMMAR_MARKERS if marker in value)
        if marker_hits < 5:
            cardinality_failures.append(f"q11-grammar-markers={marker_hits}")
    checks.append(
        Check(
            "structured_cardinality_exactness",
            "PASS" if not cardinality_failures else "FAIL",
            "short-answer slots and Q11 underlined marker counts are structurally complete"
            if not cardinality_failures
            else "bad=" + ", ".join(cardinality_failures),
        )
    )

    short_block_failures: list[str] = []
    short_specs = [
        ("\ub2e8\ub2f5\ud615 1.", "correction"),
        ("\ub2e8\ub2f5\ud615 2.", "summary"),
    ]
    slot_labels = ["(A)", "(B)", "(C)", "(D)"]
    for marker, slot_type in short_specs:
        lead = find_lead_position(generated, generated_page_count, marker)
        if lead is None:
            short_block_failures.append(f"{marker}:missing")
            continue
        page_index, x, y, _value = lead
        same_column_slots = [
            (slot_y, value)
            for slot_x, slot_y, value in text_positions(generated, page_index)
            if approx_equal(slot_x, x, 3.0) and slot_y < y - 2.0 and is_answer_slot_position(value)
        ]
        same_column_slots.sort(key=lambda item: item[0], reverse=True)
        if slot_type == "correction":
            correction_slots = [(slot_y, value) for slot_y, value in same_column_slots if "->" in value]
            if len(correction_slots) != 4:
                short_block_failures.append(f"{marker}:correction-slots={len(correction_slots)}")
                continue
            for label in slot_labels:
                if sum(1 for _slot_y, value in correction_slots if value.startswith(label)) != 1:
                    short_block_failures.append(f"{marker}:{label}=bad")
            if any(correction_slots[i][0] <= correction_slots[i + 1][0] for i in range(3)):
                short_block_failures.append(f"{marker}:slot-y-order")
        else:
            summary_slots = [
                (slot_y, value)
                for slot_y, value in same_column_slots
                if "->" not in value and all(label in value for label in slot_labels)
            ]
            if len(summary_slots) != 1:
                short_block_failures.append(f"{marker}:summary-slots={len(summary_slots)}")
    checks.append(
        Check(
            "short_answer_block_containment",
            "PASS" if not short_block_failures else "FAIL",
            "short-answer prompts keep every required answer slot in the same page and column"
            if not short_block_failures
            else "bad=" + ", ".join(short_block_failures),
        )
    )

    orphan_pages: list[str] = []
    for page_no, text in enumerate(generated_texts, start=1):
        if page_no == 1:
            continue
        body_start = text
        marker = "인쇄매수 ( 330 )매"
        if marker in body_start:
            body_start = body_start.split(marker, 1)[1].strip()
        if re.match(r"^\([A-D]\)\s+_{4,}", body_start) or re.match(r"^[①②③④⑤]\s+", body_start):
            orphan_pages.append(str(page_no))
    checks.append(
        Check(
            "no_answerline_orphan_at_page_start",
            "PASS" if not orphan_pages else "FAIL",
            "no page starts with a detached answer line" if not orphan_pages else "orphan_pages=" + ", ".join(orphan_pages),
        )
    )

    overflow_failures: list[str] = []
    for page_index in range(1, len(generated_reader.pages)):
        for x, y, value in text_positions(generated, page_index):
            if not is_body_column_x(x) or is_footer_or_header_text(value, y) or not is_structural_body_anchor(value):
                continue
            if y < 50.0:
                overflow_failures.append(f"p{page_index + 1}:x={x},y={y}:{value[:36]}")
            elif y > 726.0:
                overflow_failures.append(f"p{page_index + 1}:x={x},y={y}:{value[:36]}")
    checks.append(
        Check(
            "body_text_vertical_bounds",
            "PASS" if not overflow_failures else "FAIL",
            "body text stays inside printable body frame"
            if not overflow_failures
            else "overflow=" + " | ".join(overflow_failures[:8]),
        )
    )

    font_failures: list[str] = []
    cover_font_specs = [
        (0, "2025학년도", 26.2, 0.25, 650.0),
        (0, "1학기", 26.2, 0.25, 630.0),
        (0, "( 공통영어1 )", 32.6, 0.25, 550.0),
        (0, "일 시", 16.3, 0.25, 480.0),
        (0, "시험이 시작", 13.1, 0.25, 400.0),
        (0, "인쇄", 9.0, 0.25, 390.0),
    ]
    for page_index, needle, expected_size, tolerance, min_y in cover_font_specs:
        matching_runs = [run for run in text_runs(generated, page_index) if needle in run[3] and run[1] >= min_y]
        if not matching_runs:
            font_failures.append(f"{needle}:missing")
            continue
        run = matching_runs[0]
        _x, _y, font_size, _value = run
        if not approx_equal(font_size, expected_size, tolerance):
            font_failures.append(f"{needle}:font={font_size},expected={expected_size}")
    cover_school_runs = [run for run in text_runs(generated, 0) if "광영여자고등학교" in run[3] and run[1] > 250]
    if not cover_school_runs:
        font_failures.append("cover-school:missing")
    elif not any(approx_equal(run[2], 19.6, 0.35) for run in cover_school_runs):
        sizes = ",".join(str(run[2]) for run in cover_school_runs)
        font_failures.append(f"cover-school:font={sizes},expected=19.6")

    body_font_samples = [
        (1, "6-8.", 8.05),
        (1, "6.", 8.05),
        (1, "7.", 8.05),
        (1, "8.", 8.05),
        (2, "9-11.", 8.05),
        (2, "9.", 8.05),
        (2, "10.", 8.05),
        (2, "11.", 8.05),
    ]
    for page_index, needle, expected_size in body_font_samples:
        if page_index >= len(generated_reader.pages):
            continue
        run = find_text_run(generated, page_index, needle)
        if run is None:
            continue
        _x, _y, font_size, _value = run
        if not approx_equal(font_size, expected_size, 0.2):
            font_failures.append(f"{needle}:font={font_size},expected={expected_size}")

    checks.append(
        Check(
            "font_size_profile",
            "PASS" if not font_failures else "FAIL",
            "cover/body structural font sizes match the fixed template"
            if not font_failures
            else "bad=" + ", ".join(font_failures),
        )
    )

    missing_grid_pages: list[str] = []
    expected_grid = [
        (18.35, 45.55, 18.35, 806.36),
        (578.57, 45.55, 578.57, 806.36),
        (18.35, 806.36, 578.57, 806.36),
        (18.35, 45.55, 578.57, 45.55),
    ]
    for page_index in range(len(generated_reader.pages)):
        segments = line_segments(generated, page_index)
        if not all(has_segment(segments, target, tolerance=1.2) for target in expected_grid):
            missing_grid_pages.append(str(page_index + 1))
    checks.append(
        Check(
            "outer_exam_grid",
            "PASS" if not missing_grid_pages else "FAIL",
            "outer border/grid lines present" if not missing_grid_pages else "missing_or_shifted_pages=" + ", ".join(missing_grid_pages),
        )
    )

    header_table_failures: list[str] = []
    header_segments = [
        (201.85, 806.36, 201.85, 736.35),
        (219.24, 806.36, 219.24, 787.78),
        (377.68, 806.36, 377.68, 791.85),
        (377.68, 754.22, 578.81, 754.22),
        (413.54, 806.36, 413.54, 754.22),
        (298.52, 735.16, 298.52, 47.23),
    ]
    for page_index in range(1, len(generated_reader.pages)):
        segments = line_segments(generated, page_index)
        if not all(has_segment(segments, target, tolerance=1.2) for target in header_segments):
            header_table_failures.append(str(page_index + 1))
    checks.append(
        Check(
            "body_header_table_grid",
            "PASS" if not header_table_failures else "FAIL",
            "body header table/grid lines present" if not header_table_failures else "missing_or_shifted_pages=" + ", ".join(header_table_failures),
        )
    )

    body_pages = range(1, len(generated_reader.pages))
    column_failures: list[str] = []
    for page_index in body_pages:
        xs = [
            x
            for x, _y, value in text_positions(generated, page_index)
            if value and (value[0].isdigit() or value.startswith("단답형"))
        ]
        has_left = any(approx_equal(x, 23.16, 3.0) for x in xs)
        has_right = any(approx_equal(x, 304.44, 3.0) for x in xs)
        if page_index == 1 and not has_right:
            column_failures.append(f"p{page_index + 1}:right")
        elif page_index > 1 and not (has_left or has_right):
            column_failures.append(f"p{page_index + 1}:no-column-anchor")
    checks.append(
        Check(
            "two_column_text_anchors",
            "PASS" if not column_failures else "WARN",
            "expected column text anchors found" if not column_failures else "check=" + ", ".join(column_failures),
        )
    )

    body_anchor_failures: list[str] = []
    anchor_specs = [
        (1, "6-8.", 304.44, 660.0, 730.0),
        (1, "6.", 304.44, 520.0, 635.0),
    ]
    for page_index, needle, expected_x, min_y, max_y in anchor_specs:
        if page_index >= len(generated_reader.pages):
            body_anchor_failures.append(f"{needle}:missing-page")
            continue
        found = find_text_position(generated, page_index, needle)
        if found is None:
            body_anchor_failures.append(f"{needle}:missing")
            continue
        x, y = found
        if not approx_equal(x, expected_x, 3.0) or not (min_y <= y <= max_y):
            body_anchor_failures.append(f"{needle}:x={x},y={y}")

    second_group_positions: list[tuple[int, float, float]] = []
    for page_index in range(1, len(generated_reader.pages)):
        found = find_text_position(generated, page_index, "9-11.")
        if found is not None:
            x, y = found
            second_group_positions.append((page_index + 1, x, y))
    if not second_group_positions:
        body_anchor_failures.append("9-11.:missing")
    else:
        valid_second_group = any(
            page_no >= 3
            and (approx_equal(x, 23.16, 3.0) or approx_equal(x, 304.44, 3.0))
            and 520.0 <= y <= 760.0
            for page_no, x, y in second_group_positions
        )
        if not valid_second_group:
            formatted = ",".join(f"p{page_no}:x={x},y={y}" for page_no, x, y in second_group_positions)
            body_anchor_failures.append(f"9-11.:bad-position:{formatted}")

    short2_positions: list[tuple[int, float, float]] = []
    for page_index in range(1, len(generated_reader.pages)):
        found = find_text_position(generated, page_index, "단답형 2.")
        if found is not None:
            x, y = found
            short2_positions.append((page_index + 1, x, y))
    if not short2_positions:
        body_anchor_failures.append("단답형2:missing")
    else:
        valid_short2 = any(page_no >= 4 and approx_equal(x, 23.16, 3.0) and 680.0 <= y <= 760.0 for page_no, x, y in short2_positions)
        if not valid_short2:
            formatted = ",".join(f"p{page_no}:x={x},y={y}" for page_no, x, y in short2_positions)
            body_anchor_failures.append(f"단답형2:bad-position:{formatted}")
    checks.append(
        Check(
            "body_anchor_positions",
            "PASS" if not body_anchor_failures else "FAIL",
            "main body anchors are in expected columns/bands" if not body_anchor_failures else "bad=" + ", ".join(body_anchor_failures),
        )
    )

    passage_binding_failures: list[str] = []
    for marker, max_gap in [("6-8.", 35.0), ("9-11.", 35.0)]:
        lead = find_lead_position(generated, generated_page_count, marker)
        if lead is None:
            passage_binding_failures.append(f"{marker}:missing")
            continue
        page_index, x, y, _value = lead
        dependent = first_below_same_column(text_positions(generated, page_index), x, y, is_pseudo_body_line)
        if dependent is None:
            passage_binding_failures.append(f"{marker}:no-first-body-line")
            continue
        _dep_x, dep_y, _dep_value = dependent
        gap = y - dep_y
        if gap > max_gap:
            passage_binding_failures.append(f"{marker}:firstline-gap={gap:.1f}pt>{max_gap:.1f}pt")
    checks.append(
        Check(
            "passage_title_firstline_binding",
            "PASS" if not passage_binding_failures else "FAIL",
            "passage titles stay with the first body line in the same column"
            if not passage_binding_failures
            else "bad=" + ", ".join(passage_binding_failures),
        )
    )

    order_failures: list[str] = []
    marker_positions: dict[str, tuple[int, float, float]] = {}
    for marker in ["6.", "7.", "8.", "9.", "10.", "11."]:
        lead = find_lead_position(generated, generated_page_count, f"{marker} ")
        if lead is not None:
            page_index, x, y, _value = lead
            marker_positions[marker] = (page_index, x, y)
    for group in [["6.", "7.", "8."], ["9.", "10.", "11."]]:
        missing = [marker for marker in group if marker not in marker_positions]
        if missing:
            order_failures.append("missing=" + ",".join(missing))
            continue
        for before, after in zip(group, group[1:]):
            before_page, before_x, before_y = marker_positions[before]
            after_page, after_x, after_y = marker_positions[after]
            if before_page == after_page and approx_equal(before_x, after_x, 3.0):
                gap = before_y - after_y
                if gap < 24.0:
                    order_failures.append(f"{before}->{after}:gap={gap:.1f}pt")
                if gap <= 0:
                    order_failures.append(f"{before}->{after}:order")
            elif before_page > after_page:
                order_failures.append(f"{before}->{after}:page-order")
    checks.append(
        Check(
            "top_level_marker_order_and_min_gap",
            "PASS" if not order_failures else "FAIL",
            "top-level question markers preserve order and minimum separation"
            if not order_failures
            else "bad=" + ", ".join(order_failures),
        )
    )

    binding_failures: list[str] = []
    objective_binding_specs = {
        "6.": 70.0,
        "7.": 70.0,
        "8.": 130.0,
        "9.": 70.0,
        "10.": 140.0,
    }
    for marker, max_gap in objective_binding_specs.items():
        lead = find_lead_position(generated, generated_page_count, f"{marker} ")
        if lead is None:
            binding_failures.append(f"{marker}:missing")
            continue
        page_index, x, y, _value = lead
        dependent = first_below_same_column(text_positions(generated, page_index), x, y, is_objective_option_position)
        if dependent is None:
            binding_failures.append(f"{marker}:no-option-same-column")
            continue
        _option_x, option_y, _option_value = dependent
        gap = y - option_y
        if gap > max_gap:
            binding_failures.append(f"{marker}:option-gap={gap:.1f}pt>{max_gap:.1f}pt")

    q11 = find_lead_position(generated, generated_page_count, "11. ")
    if q11 is None:
        binding_failures.append("11.:missing")
    else:
        page_index, x, y, _value = q11
        dependent = first_below_same_column(text_positions(generated, page_index), x, y, has_underlined_grammar_marker)
        if dependent is None:
            binding_failures.append("11.:no-underlined-body-same-column")
        else:
            _dep_x, dep_y, _dep_value = dependent
            gap = y - dep_y
            if gap > 45.0:
                binding_failures.append(f"11.:body-gap={gap:.1f}pt>45.0pt")

    for marker, max_gap in [("단답형 1.", 120.0), ("단답형 2.", 150.0)]:
        lead = find_lead_position(generated, generated_page_count, marker)
        if lead is None:
            binding_failures.append(f"{marker}:missing")
            continue
        page_index, x, y, _value = lead
        dependent = first_below_same_column(text_positions(generated, page_index), x, y, is_answer_slot_position)
        if dependent is None:
            binding_failures.append(f"{marker}:no-answer-slot-same-column")
            continue
        _slot_x, slot_y, _slot_value = dependent
        gap = y - slot_y
        if gap > max_gap:
            binding_failures.append(f"{marker}:answer-gap={gap:.1f}pt>{max_gap:.1f}pt")

    checks.append(
        Check(
            "question_dependent_binding",
            "PASS" if not binding_failures else "FAIL",
            "question leads stay with first option/body/answer slot in the same column"
            if not binding_failures
            else "bad=" + ", ".join(binding_failures),
        )
    )

    cover_failures: list[str] = []
    cover_specs = [
        ("2025학년도", 190.0, 717.3),
        ("1학기", 206.0, 675.4),
        ("공통영어1", 205.0, 596.7),
        ("일 시", 166.0, 520.0),
        ("시험이 시작되기", 153.0, 434.9),
        ("인쇄", 267.0, 415.6),
    ]
    for needle, expected_x, expected_y in cover_specs:
        positions = find_text_positions(generated, 0, needle)
        if not positions:
            cover_failures.append(f"{needle}:missing")
            continue
        if not any(approx_equal(x, expected_x, 15.0) and approx_equal(y, expected_y, 3.0) for x, y in positions):
            formatted = ",".join(f"x={x},y={y}" for x, y in positions[:3])
            cover_failures.append(f"{needle}:{formatted}")
    school_positions = [(x, y) for x, y in find_text_positions(generated, 0, "광영여자고등학교") if y > 250]
    if not school_positions:
        cover_failures.append("cover-school:missing")
    elif not any(approx_equal(x, 221.0, 20.0) and approx_equal(y, 329.4, 3.0) for x, y in school_positions):
        formatted = ",".join(f"x={x},y={y}" for x, y in school_positions)
        cover_failures.append(f"cover-school:{formatted}")
    checks.append(
        Check(
            "cover_fixed_positions",
            "PASS" if not cover_failures else "FAIL",
            "cover title/date/notice/school positions match fixed template" if not cover_failures else "bad=" + ", ".join(cover_failures),
        )
    )

    return checks


def write_report(path: Path, actual: Path, generated: Path, checks: list[Check]) -> None:
    passed = sum(1 for check in checks if check.status == "PASS")
    failed = sum(1 for check in checks if check.status == "FAIL")
    warned = sum(1 for check in checks if check.status == "WARN")
    lines = [
        "# 광영여고 고1 시험지 레이아웃 자동 검수",
        "",
        f"- 원본: `{actual}`",
        f"- 생성본: `{generated}`",
        f"- 결과: PASS {passed}, WARN {warned}, FAIL {failed}",
        "",
        "| 항목 | 상태 | 세부 |",
        "|---|---:|---|",
    ]
    for check in checks:
        lines.append(f"| {check.name} | {check.status} | {check.detail} |")
    lines.append("")
    lines.append("## 다음 수동 검수")
    lines.append("- PDF를 실제 인쇄 배율 100%로 열어 원본 2쪽과 생성본 2쪽의 헤더 baseline, 2단 시작점, 선지 들여쓰기, 문항 간격을 육안 대조한다.")
    lines.append("- 본문 단독 샘플은 듣기 1-5번을 생성하지 않으므로 원본 2쪽 왼쪽 단과 직접 비교하지 않고, 오른쪽 단 6번 시작 위치와 본문 밀도만 비교한다.")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--actual", default=str(DEFAULT_ACTUAL))
    parser.add_argument("--generated", default=str(DEFAULT_GENERATED))
    parser.add_argument("--source", default=str(DEFAULT_SOURCE))
    parser.add_argument("--report", default=str(ROOT / "output" / "layout_audit" / "g1_mid_set51_layout_audit.md"))
    parser.add_argument("--mode", choices=["body", "set51", "full"], default="body")
    parser.add_argument("--expected-pages", type=int, default=None)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    actual = Path(args.actual)
    generated = Path(args.generated)
    source = Path(args.source)
    checks = make_checks(actual, generated, args.mode, args.expected_pages, source)
    write_report(Path(args.report), actual, generated, checks)

    if args.json:
        print(json.dumps([asdict(check) for check in checks], ensure_ascii=False, indent=2))
    else:
        for check in checks:
            print(f"{check.status}\t{check.name}\t{check.detail}")
        print(Path(args.report).resolve())
    return 1 if any(check.status == "FAIL" for check in checks) else 0


if __name__ == "__main__":
    raise SystemExit(main())
