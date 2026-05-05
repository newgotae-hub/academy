# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import csv
import hashlib
import re
import sys
from collections import defaultdict
from pathlib import Path


EXPECTED_PACKAGE_FILE_COUNT = 36
EXPECTED_STUDENT_HEADER_TOTAL = 760
DIST_DIR_NAME = "dist_student"
STUDENT_ANSWER_LEAK = [
    "정답",
    "해설",
    "교사용",
    "채점",
    "출제축",
    "canonical",
    "allowed",
    "forbidden",
]

STUDENT_META_LEAK = [
    "의도 분류",
    "매력오답",
    "오답 설계",
    "템플릿 기준",
    "QA",
    "출제 의도",
    "제작 메모",
]

TEACHER_LEGACY = [
    "which 또는 that",
    "둘 중 하나",
    "have / make",
    "have allowed",
    "has allowed",
    "의도 일괄",
]

REQUIRED_TEACHER_META = [
    "내부",
    "표시용",
    "템플릿 기준:",
]

GRAMMAR_GATES = [
    ("q8_four_errors", ("8",), ("4오류", "오류 4개")),
    ("q11_two_errors", ("11",), ("2오류", "오류 2개")),
    ("q21_one_error", ("21",), ("1오류", "오류 1개")),
]

STRICT_SCHEMA_SET_START = 33
STRICT_SHORT_ANSWER_KEYS = {
    ("단답1", "A"),
    ("단답1", "B"),
    ("단답1", "C"),
    ("단답1", "D"),
    ("단답2", "A"),
    ("단답2", "B"),
    ("단답2", "C"),
    ("단답2", "D"),
    ("단답3", "A"),
    ("단답3", "B"),
    ("단답3", "C"),
    ("단답3", "D"),
    ("단답4", "A"),
    ("단답4", "B"),
}


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def find_literals(text: str, patterns: list[str]) -> list[str]:
    return [p for p in patterns if p in text]


def result(gate: str, status: str, detail: str) -> dict[str, str]:
    return {"gate": gate, "status": status, "detail": detail}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def package_files(root: Path, suffix: str) -> list[Path]:
    return sorted(
        [
            p
            for p in root.glob("*.md")
            if p.name.startswith("광영여고_고1_1학기중간_동형모의고사_")
            and p.name.endswith(suffix)
        ],
        key=lambda p: (set_number(p), p.name),
    )


def set_number(path: Path) -> int:
    match = re.search(r"_(\d+)회_", path.name)
    if match:
        return int(match.group(1))
    if "_3세트_" in path.name:
        return 3
    return 0


def set_label(path: Path) -> str:
    match = re.search(r"_(\d+)회_", path.name)
    if match:
        return f"{int(match.group(1))}회"
    if "_3세트_" in path.name:
        return "3세트"
    return path.stem


def distribution_name(path: Path) -> str:
    if "_3세트_" in path.name:
        return "광영여고_고1_1학기중간_동형모의고사_1-3회_학생용.md"
    match = re.search(r"_(\d+)회_", path.name)
    if match:
        return f"광영여고_고1_1학기중간_동형모의고사_{int(match.group(1))}회_학생용.md"
    return path.name


def expected_count_gate(files: list[Path], label: str) -> dict[str, str]:
    count = len(files)
    return result(
        f"{label}_file_count",
        "PASS" if count == EXPECTED_PACKAGE_FILE_COUNT else "FAIL",
        f"{count}/{EXPECTED_PACKAGE_FILE_COUNT}",
    )


def pairing_gate(student_files: list[Path], teacher_files: list[Path]) -> dict[str, str]:
    student_sets = {set_label(path) for path in student_files}
    teacher_sets = {set_label(path) for path in teacher_files}
    missing_teachers = sorted(student_sets - teacher_sets)
    missing_students = sorted(teacher_sets - student_sets)
    if missing_teachers or missing_students:
        details: list[str] = []
        if missing_teachers:
            details.append(f"missing teacher: {', '.join(missing_teachers)}")
        if missing_students:
            details.append(f"missing student: {', '.join(missing_students)}")
        return result("student_teacher_pairing", "FAIL", "; ".join(details))
    return result("student_teacher_pairing", "PASS", f"{len(student_sets)} paired set(s)")


def distribution_integrity_gate(root: Path, student_files: list[Path]) -> dict[str, str]:
    out_dir = root / DIST_DIR_NAME
    if not out_dir.is_dir():
        return result("distribution_integrity", "FAIL", f"missing {DIST_DIR_NAME}")

    manifest = out_dir / "manifest.csv"
    if not manifest.is_file():
        return result("distribution_integrity", "FAIL", "missing manifest.csv")

    expected_files = {distribution_name(path): path for path in student_files}
    allowed_files = set(expected_files) | {"manifest.csv", "README.md"}
    actual_files = {path.name for path in out_dir.iterdir() if path.is_file()}
    unexpected = sorted(actual_files - allowed_files)
    missing = sorted(set(expected_files) - actual_files)
    directories = sorted(path.name for path in out_dir.iterdir() if path.is_dir())

    rows = list(csv.DictReader(manifest.open("r", encoding="utf-8-sig", newline="")))
    manifest_files = [row.get("distribution_file", "") for row in rows]
    manifest_missing = sorted(set(expected_files) - set(manifest_files))
    manifest_extra = sorted(set(manifest_files) - set(expected_files))
    hash_mismatches = [
        name
        for name, source in expected_files.items()
        if (out_dir / name).is_file() and sha256(source) != sha256(out_dir / name)
    ]

    failures: list[str] = []
    if len(rows) != EXPECTED_PACKAGE_FILE_COUNT:
        failures.append(f"manifest rows {len(rows)}/{EXPECTED_PACKAGE_FILE_COUNT}")
    if len([name for name in actual_files if name.endswith("학생용.md")]) != EXPECTED_PACKAGE_FILE_COUNT:
        failures.append("student md count mismatch")
    if unexpected:
        failures.append(f"unexpected files: {', '.join(unexpected)}")
    if directories:
        failures.append(f"unexpected directories: {', '.join(directories)}")
    if missing:
        failures.append(f"missing files: {', '.join(missing)}")
    if manifest_missing:
        failures.append(f"manifest missing: {', '.join(manifest_missing)}")
    if manifest_extra:
        failures.append(f"manifest extra: {', '.join(manifest_extra)}")
    if hash_mismatches:
        failures.append(f"hash mismatches: {', '.join(hash_mismatches)}")

    if failures:
        return result("distribution_integrity", "FAIL", "; ".join(failures))
    return result(
        "distribution_integrity",
        "PASS",
        f"{EXPECTED_PACKAGE_FILE_COUNT} files, manifest and hashes match",
    )


def expected_header_count(path: Path) -> int:
    return 60 if "_3세트_" in path.name else 20


def strip_markdown(line: str) -> str:
    line = re.sub(r"\*\*(.*?)\*\*", r"\1", line)
    line = re.sub(r"`([^`]*)`", r"\1", line)
    line = re.sub(r"^\s*>+\s*", "", line)
    return line.strip()


def is_student_surface_line(line: str) -> bool:
    if not line:
        return False
    if line.startswith(("#", "---", "|")):
        return False
    if line.startswith(("범위:", "구성:", "제외:", "문항", "다음", "윗글", "밑줄")):
        return False
    if re.match(r"^\(?[A-E]\)", line):
        return True
    if re.match(r"^[1-5]\)", line):
        return True
    if line.startswith("Summary:"):
        return True
    ascii_letters = len(re.findall(r"[A-Za-z]", line))
    return ascii_letters >= 30 and len(line) >= 45


def split_surface_units(text: str) -> list[str]:
    units: list[str] = []
    for raw_line in text.splitlines():
        line = strip_markdown(raw_line)
        if not is_student_surface_line(line):
            continue
        line = re.sub(r"\s+", " ", line)
        pieces = re.split(r"(?<=[.!?])\s+", line)
        for piece in pieces:
            piece = piece.strip()
            if not piece:
                continue
            ascii_letters = len(re.findall(r"[A-Za-z]", piece))
            if ascii_letters < 24 or len(piece) < 35:
                continue
            units.append(piece)
    return units


def normalize_surface(unit: str) -> str:
    unit = unit.replace("**", "")
    unit = re.sub(r"\([A-D]\)", "(slot)", unit)
    unit = re.sub(r"_{3,}", "____", unit)
    unit = re.sub(r"\s+", " ", unit)
    return unit.strip().casefold()


def recent_three_surface_gate(student_files: list[Path]) -> dict[str, str]:
    numbered = [p for p in student_files if set_number(p) >= 4]
    latest = sorted(numbered, key=set_number)[-3:]
    seen: dict[str, list[str]] = defaultdict(list)
    originals: dict[str, str] = {}
    for path in latest:
        text = read_text(path)
        for unit in split_surface_units(text):
            normalized = normalize_surface(unit)
            seen[normalized].append(path.name)
            originals.setdefault(normalized, unit)
    duplicates = [
        (originals[key], sorted(set(names)))
        for key, names in seen.items()
        if len(set(names)) > 1
    ]
    if duplicates:
        detail = "; ".join(
            f"{unit[:90]}... :: {', '.join(names)}" for unit, names in duplicates[:5]
        )
        return result("recent_3_surface_lint", "FAIL", detail)
    names = ", ".join(p.name for p in latest)
    return result("recent_3_surface_lint", "PASS", f"checked {names}")


def split_option_units(text: str) -> list[str]:
    units: list[str] = []
    for raw_line in text.splitlines():
        line = strip_markdown(raw_line)
        match = re.match(r"^\d+\.\s+(.+?)\s*$", line)
        if not match:
            continue
        option = re.sub(r"\s+", " ", match.group(1)).strip()
        option = option.rstrip()
        ascii_letters = len(re.findall(r"[A-Za-z]", option))
        if ascii_letters < 5:
            continue
        if re.fullmatch(r"\(\d+\)", option):
            continue
        units.append(option)
    return units


def recent_three_option_gate(student_files: list[Path]) -> dict[str, str]:
    numbered = [p for p in student_files if set_number(p) >= 4]
    latest = sorted(numbered, key=set_number)[-3:]
    seen: dict[str, list[str]] = defaultdict(list)
    originals: dict[str, str] = {}
    for path in latest:
        text = read_text(path)
        for unit in split_option_units(text):
            normalized = unit.casefold()
            seen[normalized].append(path.name)
            originals.setdefault(normalized, unit)
    duplicates = [
        (originals[key], sorted(set(names)))
        for key, names in seen.items()
        if len(set(names)) > 1
    ]
    if duplicates:
        detail = "; ".join(
            f"{unit[:90]} :: {', '.join(names)}" for unit, names in duplicates[:8]
        )
        return result("recent_3_option_lint", "FAIL", detail)
    names = ", ".join(p.name for p in latest)
    return result("recent_3_option_lint", "PASS", f"checked {names}")


def answer_distribution_gate(teacher_files: list[Path]) -> dict[str, str]:
    failures: list[str] = []
    checked = 0
    objective_questions = [str(number) for number in range(6, 22)]
    for path in teacher_files:
        if set_number(path) < STRICT_SCHEMA_SET_START:
            continue
        checked += 1
        answers = quick_answer_rows(read_text(path))
        objective_answers = [answers.get(question, "") for question in objective_questions]
        missing = [
            question
            for question, answer in zip(objective_questions, objective_answers)
            if answer not in {"1", "2", "3", "4", "5"}
        ]
        counts = {str(number): objective_answers.count(str(number)) for number in range(1, 6)}
        crowded = {option: count for option, count in counts.items() if count > 6}
        if missing:
            failures.append(f"{path.name}: missing objective answers {', '.join(missing)}")
        if crowded:
            detail = ", ".join(f"{option}={count}" for option, count in crowded.items())
            failures.append(f"{path.name}: crowded {detail}")
    return result(
        "teacher_answer_distribution",
        "PASS" if not failures else "FAIL",
        f"checked {checked} strict set(s)" if not failures else "; ".join(failures[:8]),
    )


def table_cells(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def quick_answer_rows(text: str) -> dict[str, str]:
    rows: dict[str, str] = {}
    for line in text.splitlines():
        if "|" not in line:
            continue
        cells = table_cells(line)
        if len(cells) != 2:
            continue
        key, value = cells[0], cells[1]
        if re.fullmatch(r"\d+", key):
            rows[key] = value
        match = re.fullmatch(r"단답형(\d+)", key)
        if match:
            rows[f"단답{match.group(1)}"] = value
    return rows


def schema_short_answer_rows(text: str) -> dict[tuple[str, str], tuple[int, str, str]]:
    rows: dict[tuple[str, str], tuple[int, str, str]] = {}
    for line_no, line in enumerate(text.splitlines(), start=1):
        if "|" not in line:
            continue
        cells = table_cells(line)
        if len(cells) < 6:
            continue
        question, slot, canonical, allowed = cells[0], cells[1], cells[2], cells[3]
        if not re.fullmatch(r"단답[1-4]", question):
            continue
        if slot not in {"A", "B", "C", "D"}:
            continue
        if canonical == "canonical":
            continue
        rows[(question, slot)] = (line_no, canonical, allowed)
    return rows


def short_answer_rows(text: str) -> list[tuple[int, list[str]]]:
    rows: list[tuple[int, list[str]]] = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        if "|" not in line or "단답4" not in line or "A" not in line:
            continue
        cells = table_cells(line)
        if "단답4" in cells:
            rows.append((line_no, cells))
    return rows


def check_short_answer_canonical(path: Path, text: str) -> dict[str, str]:
    failures: list[str] = []
    rows = short_answer_rows(text)
    for line_no, cells in rows:
        idx = cells.index("단답4")
        if idx + 3 >= len(cells):
            failures.append(f"line {line_no}: too few cells")
            continue
        slot = cells[idx + 1]
        canonical = cells[idx + 2]
        allowed = cells[idx + 3]
        if slot != "A":
            continue
        if not canonical.startswith("getting "):
            failures.append(f"line {line_no}: canonical={canonical}")
        if not allowed.startswith("being "):
            failures.append(f"line {line_no}: allowed={allowed}")
    if failures:
        return result(
            f"teacher_short_answer_canonical:{path.name}",
            "FAIL",
            "; ".join(failures),
        )
    return result(
        f"teacher_short_answer_canonical:{path.name}",
        "PASS" if rows else "FAIL",
        f"{len(rows)} row(s)",
    )


def check_strict_short_answer_schema(path: Path, text: str) -> dict[str, str]:
    if set_number(path) < STRICT_SCHEMA_SET_START:
        return result(
            f"teacher_strict_short_answer_schema:{path.name}",
            "PASS",
            f"strict gate applies from {STRICT_SCHEMA_SET_START}회",
        )
    rows = schema_short_answer_rows(text)
    missing = sorted(STRICT_SHORT_ANSWER_KEYS - set(rows))
    extras = sorted(set(rows) - STRICT_SHORT_ANSWER_KEYS)
    blank = [
        f"{question}-{slot}@{line_no}"
        for (question, slot), (line_no, canonical, _allowed) in rows.items()
        if not canonical or canonical in {"없음", "canonical"}
    ]
    failures: list[str] = []
    if missing:
        failures.append("missing " + ", ".join(f"{q}-{s}" for q, s in missing))
    if extras:
        failures.append("extra " + ", ".join(f"{q}-{s}" for q, s in extras))
    if blank:
        failures.append("blank canonical " + ", ".join(blank))
    return result(
        f"teacher_strict_short_answer_schema:{path.name}",
        "PASS" if not failures else "FAIL",
        f"{len(rows)} row(s)" if not failures else "; ".join(failures),
    )


def check_short_answer_quick_alignment(path: Path, text: str) -> dict[str, str]:
    if set_number(path) < STRICT_SCHEMA_SET_START:
        return result(
            f"teacher_short_answer_quick_alignment:{path.name}",
            "PASS",
            f"strict gate applies from {STRICT_SCHEMA_SET_START}회",
        )
    quick = quick_answer_rows(text)
    rows = schema_short_answer_rows(text)
    failures: list[str] = []
    for (question, slot), (line_no, canonical, allowed) in sorted(rows.items()):
        answer_text = quick.get(question, "")
        if not answer_text:
            failures.append(f"{question}: missing quick answer")
            continue
        if canonical and canonical not in answer_text:
            failures.append(f"{question}-{slot}@{line_no}: canonical `{canonical}` not in quick answer")
        if allowed and allowed != "없음" and allowed not in answer_text:
            failures.append(f"{question}-{slot}@{line_no}: allowed `{allowed}` not in quick answer")
    return result(
        f"teacher_short_answer_quick_alignment:{path.name}",
        "PASS" if not failures else "FAIL",
        "0" if not failures else "; ".join(failures[:8]),
    )


def check_short_answer_quick_order(path: Path, text: str) -> dict[str, str]:
    failures: list[str] = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        if "단답4" not in line:
            continue
        if "being/getting" in line:
            failures.append(f"line {line_no}: being/getting")
        if "(A) being " in line and " 또는 getting " in line:
            failures.append(f"line {line_no}: being before getting")
    return result(
        f"teacher_short_answer_quick_order:{path.name}",
        "PASS" if not failures else "FAIL",
        "0" if not failures else "; ".join(failures),
    )


def check_grammar_trace(path: Path, text: str) -> dict[str, str]:
    if set_number(path) < 11:
        return result(
            f"teacher_grammar_trace:{path.name}",
            "PASS",
            "legacy set skipped; strict gate applies from 11회",
        )
    missing: list[str] = []
    for gate, question_markers, accepted_markers in GRAMMAR_GATES:
        has_marker = any(marker in text for marker in accepted_markers)
        has_question = any(q in text for q in question_markers)
        if not (has_marker and has_question):
            missing.append(gate)
    return result(
        f"teacher_grammar_trace:{path.name}",
        "PASS" if not missing else "FAIL",
        "0" if not missing else ", ".join(missing),
    )


def question_section(text: str, question: str) -> str:
    match = re.search(rf"(?m)^###\s+{re.escape(question)}\.", text)
    if not match:
        return ""
    start = match.start()
    next_match = re.search(r"(?m)^###\s+\S+", text[match.end() :])
    if not next_match:
        return text[start:]
    return text[start : match.end() + next_match.start()]


def option_rows(section: str) -> dict[str, str]:
    options: dict[str, str] = {}
    for line in section.splitlines():
        line = strip_markdown(line)
        match = re.match(r"^([1-5])\.\s+(.+?)\s*$", line)
        if match:
            options[match.group(1)] = match.group(2).strip()
    return options


def normalize_letter_set(text: str) -> str:
    letters = re.findall(r"\b[A-E]\b", text)
    return "".join(sorted(dict.fromkeys(letters)))


def expected_error_letters_from_trace(text: str, question: str) -> str:
    for line in text.splitlines():
        if "|" not in line:
            continue
        cells = table_cells(line)
        if len(cells) < 2 or cells[0] != question:
            continue
        trace = cells[1]
        match = re.search(r"([A-E](?:/[A-E])*)\s*(?:\d+)?오류", trace)
        if match:
            return "".join(sorted(match.group(1).split("/")))
    return ""


def check_teacher_student_grammar_alignment(
    root: Path, path: Path, text: str
) -> dict[str, str]:
    if set_number(path) < STRICT_SCHEMA_SET_START:
        return result(
            f"teacher_student_grammar_alignment:{path.name}",
            "PASS",
            f"strict gate applies from {STRICT_SCHEMA_SET_START}회",
        )
    student_path = root / path.name.replace("교사용.md", "학생용.md")
    if not student_path.exists():
        return result(
            f"teacher_student_grammar_alignment:{path.name}",
            "FAIL",
            f"missing student file {student_path.name}",
        )
    student_text = read_text(student_path)
    quick = quick_answer_rows(text)
    failures: list[str] = []
    for question in ["8", "11", "21"]:
        answer_no = quick.get(question, "")
        section = question_section(student_text, question)
        options = option_rows(section)
        option_text = options.get(answer_no, "")
        actual = normalize_letter_set(option_text)
        expected = expected_error_letters_from_trace(text, question)
        if not answer_no:
            failures.append(f"Q{question}: missing quick answer")
        elif not option_text:
            failures.append(f"Q{question}: quick answer {answer_no} missing in student options")
        elif not expected:
            failures.append(f"Q{question}: missing QA error letters")
        elif actual != expected:
            failures.append(
                f"Q{question}: answer {answer_no} gives `{actual}`, QA trace expects `{expected}`"
            )
    return result(
        f"teacher_student_grammar_alignment:{path.name}",
        "PASS" if not failures else "FAIL",
        "0" if not failures else "; ".join(failures),
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[1]))
    args = parser.parse_args()

    root = Path(args.root)
    student_files = package_files(root, "학생용.md")
    teacher_files = package_files(root, "교사용.md")
    results: list[dict[str, str]] = []

    results.append(
        result(
            "student_files_exist",
            "PASS" if student_files else "FAIL",
            f"{len(student_files)} files",
        )
    )
    results.append(expected_count_gate(student_files, "student"))
    results.append(expected_count_gate(teacher_files, "teacher"))
    results.append(pairing_gate(student_files, teacher_files))

    total_headers = 0
    for path in student_files:
        text = read_text(path)
        answer_hits = find_literals(text, STUDENT_ANSWER_LEAK)
        meta_hits = find_literals(text, STUDENT_META_LEAK)
        headers = len(re.findall(r"(?m)^### ", text))
        total_headers += headers
        expected = expected_header_count(path)
        results.append(
            result(
                f"student_header_count:{path.name}",
                "PASS" if headers == expected else "FAIL",
                f"{headers}/{expected}",
            )
        )
        results.append(
            result(
                f"student_answer_leak:{path.name}",
                "PASS" if not answer_hits else "FAIL",
                "0" if not answer_hits else ", ".join(answer_hits),
            )
        )
        results.append(
            result(
                f"student_meta_leak:{path.name}",
                "PASS" if not meta_hits else "FAIL",
                "0" if not meta_hits else ", ".join(meta_hits),
            )
        )

    results.append(
        result(
            "student_header_total",
            "PASS" if total_headers == EXPECTED_STUDENT_HEADER_TOTAL else "FAIL",
            f"{total_headers}/{EXPECTED_STUDENT_HEADER_TOTAL}",
        )
    )
    if student_files:
        results.append(recent_three_surface_gate(student_files))
        results.append(recent_three_option_gate(student_files))
    results.append(answer_distribution_gate(teacher_files))
    results.append(distribution_integrity_gate(root, student_files))

    for path in teacher_files:
        text = read_text(path)
        legacy_hits = find_literals(text, TEACHER_LEGACY)
        has_meta = all(key in text for key in REQUIRED_TEACHER_META)
        has_schema = all(key in text for key in ["canonical", "allowed", "forbidden", "reason"])
        results.append(
            result(
                f"teacher_legacy:{path.name}",
                "PASS" if not legacy_hits else "FAIL",
                "0" if not legacy_hits else ", ".join(legacy_hits),
            )
        )
        results.append(
            result(
                f"teacher_meta:{path.name}",
                "PASS" if has_meta else "FAIL",
                f"meta={has_meta}",
            )
        )
        results.append(
            result(
                f"teacher_short_answer_schema:{path.name}",
                "PASS" if has_schema else "FAIL",
                f"schema={has_schema}",
            )
        )
        results.append(check_short_answer_canonical(path, text))
        results.append(check_strict_short_answer_schema(path, text))
        results.append(check_short_answer_quick_alignment(path, text))
        results.append(check_short_answer_quick_order(path, text))
        results.append(check_grammar_trace(path, text))
        results.append(check_teacher_student_grammar_alignment(root, path, text))

    width = max(len(r["gate"]) for r in results) if results else 10
    for row in results:
        print(f"{row['status']:<5} {row['gate']:<{width}} {row['detail']}")

    failures = [r for r in results if r["status"] == "FAIL"]
    if failures:
        print(f"FAIL: {len(failures)} gate(s) failed", file=sys.stderr)
        return 1
    print("PASS: G1 midterm package lint passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
