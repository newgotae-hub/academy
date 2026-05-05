from __future__ import annotations

import json
import re
from pathlib import Path

from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "site" / "fulltext.local.json"

SCHOOL_PDF = Path(
    r"C:\Users\newgo\OneDrive\바탕 화면\광영여고\2025\1학년\문제지\2025-1 중(1학년-공통영어1교과).pdf"
)
MOCK_DIR = Path(r"C:\Users\newgo\OneDrive\바탕 화면\고1 모의 2026-2023")

CASES = {
    "q12": {"school": "12", "source_file": "2023-3.pdf", "source_q": 30},
    "q13": {"school": "13", "source_file": "2023-3.pdf", "source_q": 29},
    "q14": {"school": "14", "source_file": "2024-3.pdf", "source_q": 30},
    "q15": {"school": "15", "source_file": "2024-3.pdf", "source_q": 29},
    "sa3": {"school": "단답형 3", "source_file": "2023-3.pdf", "source_q": 32},
    "sa4": {"school": "단답형 4", "source_file": "2024-3.pdf", "source_q": 32},
    "q16": {"school": "16", "source_file": "2023-3.pdf", "source_q": 33},
    "q17": {"school": "17", "source_file": "2023-3.pdf", "source_q": 21},
    "q18": {"school": "18", "source_file": "2023-3.pdf", "source_q": 39},
    "q19": {"school": "19", "source_file": "2024-3.pdf", "source_q": 33},
    "q20": {"school": "20", "source_file": "2024-3.pdf", "source_q": 34},
    "q21": {"school": "21", "source_file": "2024-3.pdf", "source_q": 40},
}

SCHOOL_ORDER = [
    "12",
    "13",
    "14",
    "15",
    "단답형 3",
    "단답형 4",
    "16",
    "17",
    "18",
    "19",
    "20",
    "21",
    "22",
]


def pdf_text(path: Path) -> str:
    reader = PdfReader(str(path))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def normalize(text: str) -> str:
    text = text.replace("\uf000", "")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def school_pattern(label: str) -> re.Pattern[str]:
    if label.startswith("단답형"):
        number = re.search(r"\d+", label)
        if not number:
            raise ValueError(label)
        return re.compile(r"[\[【]\s*단답형\s*" + number.group(0) + r"\s*[\]】]")
    return re.compile(r"(?<!\d)" + re.escape(label) + r"\.(?!\d)")


def build_school_chunks(text: str) -> dict[str, str]:
    markers: list[tuple[str, int]] = []
    pos = 0
    for label in SCHOOL_ORDER:
        match = school_pattern(label).search(text, pos)
        if not match:
            match = school_pattern(label).search(text, max(0, pos - 900))
        if not match:
            continue
        markers.append((label, match.start()))
        pos = match.end()

    chunks: dict[str, str] = {}
    for idx, (label, start) in enumerate(markers):
        end = markers[idx + 1][1] if idx + 1 < len(markers) else len(text)
        chunks[label] = normalize(text[start:end])
    return chunks


def source_chunk(text: str, q_number: int) -> str:
    markers = list(re.finditer(r"(?<!\d)(\d{1,2})\.(?!\d)", text))
    for idx, marker in enumerate(markers):
        if int(marker.group(1)) != q_number:
            continue
        end = markers[idx + 1].start() if idx + 1 < len(markers) else len(text)
        return normalize(text[marker.start() : end])
    raise ValueError(f"question {q_number} not found")


def main() -> None:
    school = pdf_text(SCHOOL_PDF)
    school_chunks = build_school_chunks(school)
    source_cache: dict[str, str] = {}
    result: dict[str, dict[str, str]] = {}

    for case_id, spec in CASES.items():
        source_file = spec["source_file"]
        if source_file not in source_cache:
            source_cache[source_file] = pdf_text(MOCK_DIR / source_file)

        result[case_id] = {
            "original": source_chunk(source_cache[source_file], int(spec["source_q"])),
            "exam": school_chunks.get(str(spec["school"]), ""),
        }

    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
