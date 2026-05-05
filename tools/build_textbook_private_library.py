# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path

from extract_hwp_text import extract_hwp


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "site" / "textbook-private.js"
DESKTOP = Path.home() / "OneDrive" / "바탕 화면"
SOURCE_DIR = DESKTOP / "ybm박 교과서"

BOOKS = [
    {
        "id": "common_english_1",
        "label": "공통영어1",
        "course": "공통영어1",
        "grade": "g1",
        "gradeLabel": "고1",
        "semester": "1학기",
        "preset": "g1",
        "examScope": "고1 1학기 중간/기말",
        "file": SOURCE_DIR / "ybm박 고1 1학기_공통영어1 1-4과.hwp",
        "lessonCount": 4,
        "fallbackTitles": [
            "The Magic of Morning Pages",
            "The Mind of an Octopus",
            "English or Englishes?",
            "Artificial Intelligence and the Arts",
        ],
    },
    {
        "id": "common_english_2",
        "label": "공통영어2",
        "course": "공통영어2",
        "grade": "g1",
        "gradeLabel": "고1",
        "semester": "2학기",
        "preset": "g1",
        "examScope": "고1 2학기 중간/기말",
        "file": SOURCE_DIR / "ybm박 고1 2학기_공통영어2 1-4과.hwp",
        "lessonCount": 4,
        "fallbackTitles": [
            "Warning: Fake News Alert!",
            "Lesson 2",
            "Lesson 3",
            "Lesson 4",
        ],
    },
    {
        "id": "english_1",
        "label": "영어1",
        "course": "영어1",
        "grade": "g2",
        "gradeLabel": "고2",
        "semester": "1학기",
        "preset": "g2",
        "examScope": "고2 1학기 중간/기말",
        "file": SOURCE_DIR / "ybm박 고2 영어1 1-5과.hwp",
        "lessonCount": 5,
        "fallbackTitles": [
            "UNIVERSAL DESIGN FOR EVERYONE",
            "Lesson 2",
            "Lesson 3",
            "Lesson 4",
            "Lesson 5",
        ],
    },
    {
        "id": "english_2",
        "label": "영어2",
        "course": "영어2",
        "grade": "g2",
        "gradeLabel": "고2",
        "semester": "2학기",
        "preset": "g2",
        "examScope": "고2 2학기 중간/기말",
        "file": SOURCE_DIR / "ybm박 고2 영어2 1-5과.hwp",
        "lessonCount": 5,
        "fallbackTitles": [
            "본문 파일 미등록",
            "Lesson 2",
            "Lesson 3",
            "Lesson 4",
            "Lesson 5",
        ],
    },
]


JUNK_PATTERNS = [
    "捤獥",
    "汤捯",
    "湰灧",
    "慤桥",
    "潴景",
    "歭扯",
    "漠杳",
    "2022 개정",
    "YBM(박준언)",
    "교과서 본문",
]


def normalize_lines(text: str, course: str) -> list[str]:
    text = text.replace("\r", "\n")
    lines = []
    for raw in text.split("\n"):
        line = re.sub(r"\s+", " ", raw).strip()
        if not line:
            continue
        if any(pattern in line for pattern in JUNK_PATTERNS):
            continue
        if line == course:
            continue
        if re.fullmatch(r"\d+", line):
            continue
        lines.append(line)
    return lines


def detect_title(lines: list[str], fallback: str) -> str:
    for line in lines[:20]:
        alpha_count = len(re.findall(r"[A-Za-z]", line))
        word_count = len(re.findall(r"[A-Za-z][A-Za-z'’?-]*", line))
        if alpha_count >= 8 and word_count <= 9:
            return line
    return fallback


def lesson_body(lines: list[str], title: str) -> str:
    body_lines = []
    skipped_title = False
    for line in lines:
        if not skipped_title and line == title:
            skipped_title = True
            continue
        body_lines.append(line)
    body = "\n\n".join(body_lines).strip()
    return f"{title}\n\n{body}" if body else title


def build_book(book: dict) -> dict:
    source = Path(book["file"])
    if not source.exists():
        return {
            key: value
            for key, value in book.items()
            if key not in {"file", "lessonCount", "fallbackTitles"}
        } | {
            "availability": "not_loaded",
            "sourcePath": str(source),
            "lessons": [],
        }

    sections = [(name, text) for name, text in extract_hwp(source) if name.startswith("Section")]
    english_sections = sections[: book["lessonCount"] * 2]
    lessons = []
    for index in range(book["lessonCount"]):
        pair = english_sections[index * 2 : index * 2 + 2]
        raw_text = "\n\n".join(text for _name, text in pair)
        lines = normalize_lines(raw_text, book["course"])
        fallback = book["fallbackTitles"][index]
        title = detect_title(lines, fallback)
        lessons.append(
            {
                "id": f"{book['id']}_l{index + 1}",
                "lessonNo": index + 1,
                "title": title,
                "body": lesson_body(lines, title),
                "sourceRef": f"YBM박 {book['course']} {index + 1}과",
                "wordCount": len(re.findall(r"[A-Za-z]+", raw_text)),
            }
        )

    return {
        key: value
        for key, value in book.items()
        if key not in {"file", "lessonCount", "fallbackTitles"}
    } | {
        "availability": "ready",
        "sourcePath": str(source),
        "lessons": lessons,
    }


def build_library() -> dict:
    return {
        "schemaVersion": "ky-textbook-private@1",
        "generatedAt": datetime.now().isoformat(timespec="seconds"),
        "publisher": {
            "id": "ybm_park",
            "label": "YBM박",
            "fixed": True,
        },
        "books": [build_book(book) for book in BOOKS],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    args = parser.parse_args()

    out = Path(args.out)
    library = build_library()
    payload = json.dumps(library, ensure_ascii=False, indent=2)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        "(function () {\n"
        "  window.KYTextbookLibrary = "
        + payload
        + ";\n"
        "})();\n",
        encoding="utf-8",
    )
    for book in library["books"]:
        print(f"{book['label']}: {book['availability']} / {len(book.get('lessons', []))} lessons")
        for lesson in book.get("lessons", []):
            print(f"  {lesson['lessonNo']}. {lesson['title']} ({lesson['wordCount']} words)")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
