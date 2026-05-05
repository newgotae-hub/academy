# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import csv
import shutil
from pathlib import Path


PACKAGE_PREFIX = "광영여고_고1_1학기중간_동형모의고사_"
EXPECTED_DISTRIBUTION_COUNT = 36


def student_sources(root: Path) -> list[Path]:
    files = [
        p
        for p in root.glob("*.md")
        if p.name.startswith(PACKAGE_PREFIX) and p.name.endswith("학생용.md")
    ]
    return sorted(files, key=distribution_order)


def distribution_order(path: Path) -> tuple[int, str]:
    name = path.name
    if "_3세트_" in name:
        return (1, name)
    import re

    match = re.search(r"_(\d+)회_", name)
    if match:
        return (int(match.group(1)), name)
    return (999, name)


def distribution_name(path: Path) -> str:
    name = path.name
    if "_3세트_" in name:
        return f"{PACKAGE_PREFIX}1-3회_학생용.md"
    import re

    match = re.search(r"_(\d+)회_", name)
    if not match:
        raise ValueError(f"cannot determine set number: {name}")
    return f"{PACKAGE_PREFIX}{int(match.group(1))}회_학생용.md"


def manifest_note(source_name: str, target_name: str) -> str:
    if source_name == target_name:
        return "student-facing name already clean"
    return "student-facing name removes internal production label"


def clear_distribution_outputs(out_dir: Path) -> None:
    for path in out_dir.iterdir():
        if path.is_dir():
            raise ValueError(f"unexpected directory in distribution output: {path.name}")
        path.unlink()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--out", default="dist_student")
    args = parser.parse_args()

    root = Path(args.root)
    out_dir = root / args.out
    out_dir.mkdir(parents=True, exist_ok=True)
    clear_distribution_outputs(out_dir)

    sources = student_sources(root)
    if len(sources) != EXPECTED_DISTRIBUTION_COUNT:
        raise ValueError(
            f"expected {EXPECTED_DISTRIBUTION_COUNT} student source file(s), got {len(sources)}"
        )

    rows: list[dict[str, str]] = []
    seen_targets: dict[str, str] = {}
    for source in sources:
        target_name = distribution_name(source)
        if target_name in seen_targets:
            raise ValueError(
                f"duplicate distribution target {target_name}: "
                f"{seen_targets[target_name]} and {source.name}"
            )
        seen_targets[target_name] = source.name
        target = out_dir / target_name
        shutil.copyfile(source, target)
        rows.append(
            {
                "distribution_file": target_name,
                "source_file": source.name,
                "note": manifest_note(source.name, target_name),
            }
        )

    manifest = out_dir / "manifest.csv"
    with manifest.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["distribution_file", "source_file", "note"],
        )
        writer.writeheader()
        writer.writerows(rows)

    if len(rows) != EXPECTED_DISTRIBUTION_COUNT:
        raise ValueError(f"expected {EXPECTED_DISTRIBUTION_COUNT} manifest row(s), got {len(rows)}")

    readme = out_dir / "README.md"
    readme.write_text(
        "# 광영여고 고1 1학기 중간 학생 배포본\n\n"
        "- 이 폴더의 파일명은 학생 배포용으로 내부 제작 라벨을 제거했거나 이미 제거된 형태입니다.\n"
        "- 원본 제작 파일명과의 대응 관계는 `manifest.csv`에서 확인합니다.\n"
        "- 교사용 파일과 검수 리포트는 이 폴더에 넣지 않습니다.\n",
        encoding="utf-8",
    )

    print(f"built {len(rows)} student distribution file(s) in {out_dir}")
    print(f"manifest: {manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
