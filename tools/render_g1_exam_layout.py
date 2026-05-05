# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import re
import uuid
from dataclasses import dataclass
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    FrameBreak,
    KeepTogether,
    NextPageTemplate,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
)
from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = ROOT / "광영여고_고1_1학기중간_본문전용_추가문항_401-500_학생용.md"
DEFAULT_OUT = ROOT / "output" / "pdf" / "g1_mid_set51_layout.pdf"
EXAM_PAGE_SIZE = (595.0, 841.0)


@dataclass
class Block:
    kind: str
    title: str
    lines: list[str]
    score: str | None = None
    qno: str | None = None


def register_fonts() -> tuple[str, str]:
    font_candidates = [
        ("ExamKR", Path(r"C:\Windows\Fonts\NGULIM.TTF")),
        ("ExamKR", Path(r"C:\Windows\Fonts\HANDotum.ttf")),
        ("ExamKR", Path(r"C:\Windows\Fonts\malgun.ttf")),
    ]
    bold_candidates = [
        ("ExamKRBold", Path(r"C:\Windows\Fonts\HANDotumB.ttf")),
        ("ExamKRBold", Path(r"C:\Windows\Fonts\malgunbd.ttf")),
        ("ExamKRBold", Path(r"C:\Windows\Fonts\NGULIM.TTF")),
    ]

    regular = None
    bold = None
    for name, path in font_candidates:
        if path.exists():
            pdfmetrics.registerFont(TTFont(name, str(path)))
            regular = name
            break
    for name, path in bold_candidates:
        if path.exists():
            pdfmetrics.registerFont(TTFont(name, str(path)))
            bold = name
            break
    if regular is None:
        searched = ", ".join(str(path) for _name, path in font_candidates)
        raise RuntimeError(f"Korean-capable font not found. Searched: {searched}")
    if bold is None:
        searched = ", ".join(str(path) for _name, path in bold_candidates)
        raise RuntimeError(f"Korean-capable bold font not found. Searched: {searched}")
    return regular, bold


REGULAR_FONT, BOLD_FONT = register_fonts()


def escape_xml(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def md_inline_to_reportlab(text: str) -> str:
    text = escape_xml(text)
    text = re.sub(r"`([^`]+)`", r"<u>\1</u>", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<u>\1</u>", text)
    return text


def normalize_line(line: str) -> str:
    line = line.rstrip()
    line = line.replace("  ", " ")
    return line


def extract_set(source: Path, set_id: str) -> str:
    text = source.read_text(encoding="utf-8")
    pattern = rf"(?ms)^##\s+세트\s+{re.escape(set_id)}\s*$.*?(?=^##\s+|\Z)"
    match = re.search(pattern, text)
    if not match:
        raise ValueError(f"set not found: {set_id}")
    return match.group(0)


def parse_blocks(set_text: str) -> list[Block]:
    lines = set_text.splitlines()
    blocks: list[Block] = []
    current_title: str | None = None
    current_lines: list[str] = []

    def flush() -> None:
        nonlocal current_title, current_lines
        if current_title is None:
            return
        title = current_title.strip()
        body = [normalize_line(x) for x in current_lines]
        body = trim_blank_edges(body)

        score = None
        qno = None
        kind = "section"

        qmatch = re.match(r"^([0-9]+)\.\s*\[([0-9.]+)점\]\s*$", title)
        samatch = re.match(r"^(단답형\s+[0-9]+)\.\s*\[([0-9.]+)점\]\s*$", title)
        if qmatch:
            qno = qmatch.group(1)
            score = qmatch.group(2)
            kind = "question"
        elif samatch:
            qno = samatch.group(1)
            score = samatch.group(2)
            kind = "short"
        elif re.match(r"^[0-9]+-[0-9]+\.", title):
            kind = "passage"

        blocks.append(Block(kind=kind, title=title, lines=body, score=score, qno=qno))
        current_title = None
        current_lines = []

    for line in lines:
        if line.startswith("### "):
            flush()
            current_title = line[4:].strip()
            current_lines = []
        elif current_title is not None:
            current_lines.append(line)
    flush()
    return blocks


def trim_blank_edges(lines: list[str]) -> list[str]:
    start = 0
    end = len(lines)
    while start < end and not lines[start].strip():
        start += 1
    while end > start and not lines[end - 1].strip():
        end -= 1
    return lines[start:end]


def make_styles() -> dict[str, ParagraphStyle]:
    base = dict(
        fontName=REGULAR_FONT,
        fontSize=8.05,
        leading=11.55,
        textColor=colors.black,
        spaceAfter=0,
        splitLongWords=1,
        wordWrap="CJK",
        allowWidows=0,
        allowOrphans=0,
    )
    return {
        "normal": ParagraphStyle("normal", alignment=TA_JUSTIFY, **base),
        "question": ParagraphStyle(
            "question",
            parent=ParagraphStyle("normal", **base),
            fontName=BOLD_FONT,
            leading=11.8,
            spaceBefore=5.5,
            spaceAfter=2.4,
        ),
        "passage_title": ParagraphStyle(
            "passage_title",
            parent=ParagraphStyle("normal", **base),
            fontName=BOLD_FONT,
            spaceBefore=2.4,
            spaceAfter=2.4,
        ),
        "option": ParagraphStyle(
            "option",
            parent=ParagraphStyle("normal", **base),
            leftIndent=9.8,
            firstLineIndent=-9.8,
            leading=11.35,
        ),
        "short": ParagraphStyle(
            "short",
            parent=ParagraphStyle("normal", **base),
            fontName=BOLD_FONT,
            spaceBefore=6,
            spaceAfter=2.4,
        ),
        "answerline": ParagraphStyle(
            "answerline",
            parent=ParagraphStyle("normal", **base),
            leftIndent=0,
            leading=13.2,
        ),
        "cover_title": ParagraphStyle(
            "cover_title",
            fontName=BOLD_FONT,
            fontSize=21,
            leading=30,
            alignment=TA_CENTER,
        ),
        "cover_mid": ParagraphStyle(
            "cover_mid",
            fontName=REGULAR_FONT,
            fontSize=13.5,
            leading=22,
            alignment=TA_CENTER,
        ),
        "cover_small": ParagraphStyle(
            "cover_small",
            fontName=REGULAR_FONT,
            fontSize=8,
            leading=13,
            alignment=TA_CENTER,
        ),
    }


STYLES = make_styles()


def option_symbol(num: str) -> str:
    symbols = {"1": "①", "2": "②", "3": "③", "4": "④", "5": "⑤"}
    return symbols.get(num, num + ".")


def block_to_flowables(block: Block) -> list:
    flows: list = []
    if block.kind == "passage":
        flows.append(Paragraph(md_inline_to_reportlab(block.title), STYLES["passage_title"]))
        flows.extend(lines_to_paragraphs(block.lines))
        flows.append(Spacer(1, 3))
        return flows

    if block.kind == "question":
        prompt = first_nonblank(block.lines)
        score = f" ({block.score})" if block.score else ""
        flows.append(Paragraph(f"{block.qno}. {md_inline_to_reportlab(prompt)}{score}", STYLES["question"]))
        rest = lines_after_first_nonblank(block.lines)
        flows.extend(lines_to_paragraphs(rest))
        if block.qno == "11":
            return [KeepTogether(flows[:1])] + flows[1:]
        return keep_lead_with_first_dependent(flows)

    if block.kind == "short":
        prompt = first_nonblank(block.lines)
        score = f" ({block.score})" if block.score else ""
        flows.append(Paragraph(f"{block.qno}. {md_inline_to_reportlab(prompt)}{score}", STYLES["short"]))
        rest = lines_after_first_nonblank(block.lines)
        flows.extend(short_lines_to_paragraphs(rest))
        return keep_lead_with_first_dependent(flows)

    flows.append(Paragraph(md_inline_to_reportlab(block.title), STYLES["normal"]))
    flows.extend(lines_to_paragraphs(block.lines))
    return flows


def keep_lead_with_first_dependent(flows: list) -> list:
    if len(flows) <= 1:
        return [KeepTogether(flows)]
    return [KeepTogether(flows[:2])] + flows[2:]


def first_nonblank(lines: list[str]) -> str:
    for line in lines:
        if line.strip():
            return line.strip()
    return ""


def lines_after_first_nonblank(lines: list[str]) -> list[str]:
    found = False
    out: list[str] = []
    for line in lines:
        if not found and line.strip():
            found = True
            continue
        if found:
            out.append(line)
    return trim_blank_edges(out)


def lines_to_paragraphs(lines: list[str]) -> list:
    flows: list = []
    paragraph_acc: list[str] = []

    def flush_paragraph() -> None:
        nonlocal paragraph_acc
        if paragraph_acc:
            text = " ".join(x.strip() for x in paragraph_acc if x.strip())
            if text:
                flows.append(Paragraph(md_inline_to_reportlab(text), STYLES["normal"]))
                flows.append(Spacer(1, 2.4))
        paragraph_acc = []

    for raw in lines:
        line = raw.strip()
        if not line or line == "---":
            flush_paragraph()
            flows.append(Spacer(1, 3.8))
            continue

        option = re.match(r"^([1-5])\.\s+(.+)$", line)
        if option:
            flush_paragraph()
            flows.append(
                Paragraph(
                    f"{option_symbol(option.group(1))} {md_inline_to_reportlab(option.group(2))}",
                    STYLES["option"],
                )
            )
            continue

        if re.match(r"^\([A-D]\)", line) or "__________" in line or "->" in line:
            flush_paragraph()
            clean = line.replace("__________", "________________")
            flows.append(Paragraph(md_inline_to_reportlab(clean), STYLES["answerline"]))
            continue

        if line.startswith("(") and re.match(r"^\([A-C]\)", line):
            flush_paragraph()
            flows.append(Paragraph(md_inline_to_reportlab(line), STYLES["normal"]))
            continue

        paragraph_acc.append(line)

    flush_paragraph()
    return flows


def short_lines_to_paragraphs(lines: list[str]) -> list:
    flows: list = []
    for raw in lines:
        line = raw.strip()
        if not line or line == "---":
            flows.append(Spacer(1, 3.8))
            continue
        if re.match(r"^\([A-D]\)", line) or "__________" in line or "->" in line:
            clean = line.replace("__________", "________________")
            flows.append(Paragraph(md_inline_to_reportlab(clean), STYLES["answerline"]))
            continue
        flows.append(Paragraph(md_inline_to_reportlab(line), STYLES["normal"]))
        flows.append(Spacer(1, 2.4))
    return flows


class KwangyoungDocTemplate(BaseDocTemplate):
    def __init__(self, filename: str, set_id: str, **kwargs):
        self.set_id = set_id
        super().__init__(filename, **kwargs)


def draw_header(canvas, doc):
    width, height = EXAM_PAGE_SIZE
    canvas.saveState()
    canvas.setFillColor(colors.black)
    canvas.setStrokeColor(colors.black)
    canvas.setLineWidth(0.35)

    draw_page_grid(canvas, width, height)
    draw_body_header_table(canvas)
    draw_footer_identity(canvas, doc)

    canvas.setFont(REGULAR_FONT, 14.75)
    canvas.drawString(48.6, 775.7, "2025학년도  1학년")
    canvas.drawString(53.2, 756.6, "1학기  중간고사")
    canvas.setFont(BOLD_FONT, 24.5)
    canvas.drawString(231.6, 762.0, "공통영어1")
    canvas.setFont(REGULAR_FONT, 16.3)
    canvas.drawString(357.1, 764.9, "과")
    canvas.setFont(REGULAR_FONT, 12.2)
    canvas.drawString(383.6, 776.0, "일시")
    canvas.drawString(435.4, 785.7, "4월 29일 (화)요일")
    canvas.drawString(469.9, 766.1, "( 2 )교시")
    canvas.setFont(REGULAR_FONT, 8.15)
    canvas.drawString(441.8, 742.4, "인쇄매수 ( 330 )매")
    canvas.restoreState()


def draw_cover(canvas, doc):
    width, height = EXAM_PAGE_SIZE
    canvas.saveState()
    draw_page_grid(canvas, width, height)
    draw_footer_identity(canvas, doc)

    canvas.setFont(BOLD_FONT, 26.2)
    canvas.drawCentredString(width / 2, 717.3, "2025학년도  1학년")
    canvas.drawCentredString(width / 2, 675.4, "1학기  중간고사")
    canvas.setFont(BOLD_FONT, 32.6)
    canvas.drawCentredString(width / 2, 596.7, "( 공통영어1 )")
    canvas.setFont(REGULAR_FONT, 16.3)
    canvas.drawCentredString(width / 2, 520.0, "일 시 : ( 4 )월 ( 29 )일 ( 2 )교시")
    canvas.rect(106.26, 427.21, 397.95, 25.54, stroke=1, fill=0)
    canvas.setFont(REGULAR_FONT, 13.1)
    canvas.drawCentredString(width / 2, 434.9, "※ 시험이 시작되기 전까지 표지를 넘기지 마시오.")
    canvas.setFont(REGULAR_FONT, 9.0)
    canvas.drawCentredString(width / 2, 415.6, "인쇄 ( 330 )매")
    canvas.setFont(BOLD_FONT, 19.6)
    canvas.drawCentredString(width / 2, 329.4, "광영여자고등학교")
    canvas.restoreState()


def draw_page_grid(canvas, width: float, height: float) -> None:
    canvas.setStrokeColor(colors.black)
    canvas.setLineWidth(0.35)
    left = 18.35
    right = 578.57
    top = 806.36
    bottom = 45.55
    canvas.line(left, bottom, left, top)
    canvas.line(right, bottom, right, top)
    canvas.line(left, top, right, top)
    canvas.line(left, bottom, right, bottom)

    y_top = 44.47
    y_bottom = 23.73
    footer_xs = [24.35, 248.51, 345.65, 428.89, 579.17]
    canvas.line(footer_xs[0], y_top, footer_xs[-1], y_top)
    canvas.line(footer_xs[0], y_bottom, footer_xs[-1], y_bottom)
    for x in footer_xs:
        canvas.line(x, y_bottom, x, y_top)


def draw_body_header_table(canvas) -> None:
    canvas.setStrokeColor(colors.black)
    canvas.setLineWidth(0.35)
    segments = [
        (18.11, 806.36, 201.85, 806.36),
        (201.85, 806.36, 201.85, 736.35),
        (201.85, 736.35, 18.11, 736.35),
        (201.85, 806.36, 219.24, 806.36),
        (219.24, 806.36, 219.24, 787.78),
        (219.24, 787.78, 201.85, 787.78),
        (219.24, 806.36, 355.85, 806.36),
        (355.85, 806.36, 355.85, 791.85),
        (355.85, 791.85, 219.24, 791.85),
        (355.85, 806.36, 377.68, 806.36),
        (377.68, 806.36, 377.68, 791.85),
        (377.68, 791.85, 355.85, 791.85),
        (377.68, 806.36, 413.54, 806.36),
        (413.54, 806.36, 413.54, 754.22),
        (413.54, 754.22, 377.68, 754.22),
        (413.54, 806.36, 578.81, 806.36),
        (578.81, 806.36, 578.81, 754.22),
        (578.81, 754.22, 413.54, 754.22),
        (219.24, 791.85, 355.85, 791.85),
        (355.85, 791.85, 355.85, 749.54),
        (355.85, 749.54, 219.24, 749.54),
        (355.85, 791.85, 377.68, 791.85),
        (377.68, 791.85, 377.68, 749.54),
        (377.68, 749.54, 355.85, 749.54),
        (201.85, 787.78, 219.24, 787.78),
        (219.24, 787.78, 219.24, 754.22),
        (219.24, 754.22, 201.85, 754.22),
        (201.85, 754.22, 219.24, 754.22),
        (219.24, 754.22, 219.24, 736.35),
        (219.24, 736.35, 201.85, 736.35),
        (377.68, 754.22, 578.81, 754.22),
        (578.81, 754.22, 578.81, 736.35),
        (578.81, 736.35, 377.68, 736.35),
        (219.24, 749.54, 355.85, 749.54),
        (355.85, 749.54, 355.85, 736.35),
        (355.85, 736.35, 219.24, 736.35),
        (355.85, 749.54, 377.68, 749.54),
        (377.68, 749.54, 377.68, 736.35),
        (377.68, 736.35, 355.85, 736.35),
    ]
    for x1, y1, x2, y2 in segments:
        canvas.line(x1, y1, x2, y2)
    canvas.line(298.52, 735.16, 298.52, 47.23)


def draw_footer_identity(canvas, doc) -> None:
    width, _height = EXAM_PAGE_SIZE
    total = max(getattr(doc, "page_count_estimate", doc.page), doc.page)
    page_no = doc.page
    canvas.setFont(REGULAR_FONT, 8.15)
    canvas.drawString(28.4, 31.2, "(  1  ) 학년  ( 공통영어1 )과")
    canvas.drawCentredString(width / 2, 31.2, f"({page_no}/{total})")
    canvas.drawString(382.5, 31.2, "고사계  印")
    canvas.drawString(437.0, 31.2, "광영여자고등학교")
    canvas.setFont(REGULAR_FONT, 5.75)
    canvas.drawString(503.2, 26.3, "Kwangyoung Girls High School")


def build_story(set_id: str, source: Path, title: str) -> list:
    set_text = extract_set(source, set_id)
    blocks = parse_blocks(set_text)
    story: list = []

    story.append(Spacer(1, 1))
    story.append(NextPageTemplate("body"))
    story.append(PageBreak())

    notice = (
        "※ OMR 카드(객관식 문항)는 컴퓨터용 수성사인펜으로 표기해야 하며, "
        "그 외의 표기는 모두 영(0)점 처리됩니다."
    )
    story.append(Paragraph(notice, STYLES["normal"]))
    story.append(Spacer(1, 4))
    story.append(
        Paragraph("선택형 ( 6 )문항    단답형 ( 2 )문항    서·논술형 ( 0 )문항", STYLES["normal"])
    )
    story.append(Spacer(1, 8))
    story.append(FrameBreak())

    for block in blocks:
        if block.kind == "passage" and block.title.startswith("9-11."):
            story.append(FrameBreak())
        if block.kind == "short" and block.qno == "단답형 2":
            story.append(PageBreak())
        story.extend(block_to_flowables(block))
    return story


def render_pdf_once(set_id: str, source: Path, out: Path, title: str, page_count_estimate: int) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)

    width, height = EXAM_PAGE_SIZE
    left_x = 23.16
    col_w = 264.0
    gutter = 17.28
    right_x = left_x + col_w + gutter
    bottom = 52.0
    top = 724.0
    frame_h = top - bottom

    cover_frame = Frame(68, 145, width - 136, height - 250, id="cover")
    left_frame = Frame(left_x, bottom, col_w, frame_h, id="left", leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
    right_frame = Frame(right_x, bottom, col_w, frame_h, id="right", leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)

    doc = KwangyoungDocTemplate(
        str(out),
        set_id=set_id,
        pagesize=EXAM_PAGE_SIZE,
        leftMargin=0,
        rightMargin=0,
        topMargin=0,
        bottomMargin=0,
    )
    doc.page_count_estimate = page_count_estimate
    doc.addPageTemplates(
        [
            PageTemplate(id="cover", frames=[cover_frame], onPage=draw_cover),
            PageTemplate(id="body", frames=[left_frame, right_frame], onPage=draw_header),
        ]
    )

    story = build_story(set_id, source, title)
    doc.build(story)


def render_pdf(set_id: str, source: Path, out: Path, title: str) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_name(f"{out.stem}.__tmp__.{uuid.uuid4().hex}.pdf")
    render_pdf_once(set_id, source, tmp, title, page_count_estimate=99)
    page_count = len(PdfReader(str(tmp)).pages)
    render_pdf_once(set_id, source, out, title, page_count_estimate=page_count)
    try:
        tmp.unlink()
    except OSError:
        pass


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", default=str(DEFAULT_SOURCE))
    parser.add_argument("--set", default="51")
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument("--title", default="광영여고 고1 1학기 중간 본문동형")
    args = parser.parse_args()

    render_pdf(args.set, Path(args.source), Path(args.out), args.title)
    print(Path(args.out).resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
