from __future__ import annotations

import html
import re
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    KeepTogether,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    XPreformatted,
)


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "output" / "pdf"
FONT_REGULAR = Path(r"C:\Windows\Fonts\Deng.ttf")
FONT_BOLD = Path(r"C:\Windows\Fonts\Dengb.ttf")

ACCENT = colors.HexColor("#0F766E")
ACCENT_DARK = colors.HexColor("#134E4A")
ACCENT_PALE = colors.HexColor("#ECFDF5")
INK = colors.HexColor("#17202A")
MUTED = colors.HexColor("#64748B")
LINE = colors.HexColor("#DCE3E8")
PAPER = colors.HexColor("#F8FAFC")


def register_fonts() -> None:
    if not FONT_REGULAR.exists() or not FONT_BOLD.exists():
        raise FileNotFoundError("Required Chinese fonts Deng.ttf/Dengb.ttf were not found.")
    pdfmetrics.registerFont(TTFont("CN", str(FONT_REGULAR)))
    pdfmetrics.registerFont(TTFont("CN-Bold", str(FONT_BOLD)))


def inline_markup(value: str) -> str:
    value = html.escape(value.strip())
    value = re.sub(r"`([^`]+)`", r'<font name="CN-Bold" color="#0F766E">\1</font>', value)
    value = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", value)
    return value


def make_styles():
    base = getSampleStyleSheet()
    return {
        "cover_kicker": ParagraphStyle(
            "CoverKicker", parent=base["Normal"], fontName="CN-Bold", fontSize=10,
            leading=15, textColor=ACCENT, alignment=TA_CENTER, spaceAfter=8,
        ),
        "cover_title": ParagraphStyle(
            "CoverTitle", parent=base["Title"], fontName="CN-Bold", fontSize=27,
            leading=36, textColor=INK, alignment=TA_CENTER, wordWrap="CJK", spaceAfter=14,
        ),
        "cover_subtitle": ParagraphStyle(
            "CoverSubtitle", parent=base["Normal"], fontName="CN", fontSize=11,
            leading=19, textColor=MUTED, alignment=TA_CENTER, wordWrap="CJK",
        ),
        "h2": ParagraphStyle(
            "Heading2CN", parent=base["Heading2"], fontName="CN-Bold", fontSize=16,
            leading=23, textColor=ACCENT_DARK, spaceBefore=13, spaceAfter=8,
            keepWithNext=True, wordWrap="CJK",
        ),
        "h3": ParagraphStyle(
            "Heading3CN", parent=base["Heading3"], fontName="CN-Bold", fontSize=12,
            leading=18, textColor=INK, spaceBefore=9, spaceAfter=5, keepWithNext=True,
            wordWrap="CJK",
        ),
        "body": ParagraphStyle(
            "BodyCN", parent=base["BodyText"], fontName="CN", fontSize=9.5,
            leading=16, textColor=INK, spaceAfter=6, wordWrap="CJK",
        ),
        "bullet": ParagraphStyle(
            "BulletCN", parent=base["BodyText"], fontName="CN", fontSize=9.3,
            leading=15, leftIndent=14, firstLineIndent=-8, bulletIndent=3,
            textColor=INK, spaceAfter=3, wordWrap="CJK",
        ),
        "code": ParagraphStyle(
            "CodeCN", parent=base["Code"], fontName="CN", fontSize=8,
            leading=12, textColor=colors.HexColor("#334155"), leftIndent=2,
            rightIndent=2, wordWrap="CJK",
        ),
        "table": ParagraphStyle(
            "TableCN", parent=base["BodyText"], fontName="CN", fontSize=7.8,
            leading=11.5, textColor=INK, wordWrap="CJK",
        ),
        "table_head": ParagraphStyle(
            "TableHeadCN", parent=base["BodyText"], fontName="CN-Bold", fontSize=8,
            leading=11.5, textColor=colors.white, wordWrap="CJK",
        ),
    }


class CompetitionDocTemplate(BaseDocTemplate):
    def __init__(self, filename: str, title: str):
        super().__init__(
            filename,
            pagesize=A4,
            leftMargin=20 * mm,
            rightMargin=20 * mm,
            topMargin=18 * mm,
            bottomMargin=18 * mm,
            title=title,
            author="挑战杯项目组",
            subject="软件模块参赛交付材料",
        )
        self.display_title = title
        frame = Frame(self.leftMargin, self.bottomMargin, self.width, self.height, id="content")
        self.addPageTemplates(PageTemplate(id="main", frames=[frame], onPage=self._decorate_page))

    def _decorate_page(self, canvas, doc):
        canvas.saveState()
        if doc.page > 1:
            canvas.setStrokeColor(LINE)
            canvas.setLineWidth(0.5)
            canvas.line(20 * mm, A4[1] - 13 * mm, A4[0] - 20 * mm, A4[1] - 13 * mm)
            canvas.setFont("CN", 7.5)
            canvas.setFillColor(MUTED)
            canvas.drawString(20 * mm, A4[1] - 10 * mm, "挑战杯 · 软件模块交付材料")
            canvas.drawRightString(A4[0] - 20 * mm, A4[1] - 10 * mm, self.display_title)
        canvas.setStrokeColor(LINE)
        canvas.line(20 * mm, 13 * mm, A4[0] - 20 * mm, 13 * mm)
        canvas.setFont("CN", 7.5)
        canvas.setFillColor(MUTED)
        canvas.drawString(20 * mm, 9 * mm, "competition-final-v1.0 · 2026-09-03")
        canvas.drawRightString(A4[0] - 20 * mm, 9 * mm, f"第 {doc.page} 页")
        canvas.restoreState()


def cover(title: str, summary: str, styles) -> list:
    banner = Table([[Paragraph("多源异构数据驱动的岗位与能力图谱构建智能系统", styles["cover_kicker"])]], colWidths=[155 * mm])
    banner.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), ACCENT_PALE),
        ("BOX", (0, 0), (-1, -1), 0.7, colors.HexColor("#A7F3D0")),
        ("TOPPADDING", (0, 0), (-1, -1), 11),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 11),
    ]))
    summary_box = Table([[Paragraph(inline_markup(summary), styles["body"])]], colWidths=[145 * mm])
    summary_box.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), PAPER),
        ("BOX", (0, 0), (-1, -1), 0.7, LINE),
        ("LEFTPADDING", (0, 0), (-1, -1), 14),
        ("RIGHTPADDING", (0, 0), (-1, -1), 14),
        ("TOPPADDING", (0, 0), (-1, -1), 12),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
    ]))
    return [
        Spacer(1, 20 * mm), banner, Spacer(1, 24 * mm),
        Paragraph(title, styles["cover_title"]),
        Paragraph("软件模块 · 正式参赛版本", styles["cover_subtitle"]),
        Spacer(1, 19 * mm), summary_box, Spacer(1, 15 * mm),
        Paragraph("版本标签  competition-final-v1.0", styles["cover_subtitle"]),
        Paragraph("整理日期  2026年9月3日", styles["cover_subtitle"]),
        PageBreak(),
    ]


def markdown_table(rows: list[list[str]], styles, available_width: float):
    columns = max(len(row) for row in rows)
    normalized = [row + [""] * (columns - len(row)) for row in rows]
    weights = []
    for index in range(columns):
        longest = max(len(re.sub(r"[`*]", "", row[index])) for row in normalized)
        weights.append(max(8, min(longest, 38)))
    total = sum(weights)
    widths = [available_width * weight / total for weight in weights]
    data = []
    for row_index, row in enumerate(normalized):
        style = styles["table_head"] if row_index == 0 else styles["table"]
        data.append([Paragraph(inline_markup(cell), style) for cell in row])
    table = Table(data, colWidths=widths, repeatRows=1, hAlign="LEFT")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), ACCENT),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, PAPER]),
        ("GRID", (0, 0), (-1, -1), 0.45, LINE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    return table


def markdown_story(markdown: str, styles, available_width: float) -> list:
    lines = markdown.splitlines()
    story = []
    index = 1  # h1 is represented by the cover
    while index < len(lines):
        raw = lines[index].rstrip()
        stripped = raw.strip()
        if not stripped:
            index += 1
            continue
        if stripped.startswith("```"):
            code = []
            index += 1
            while index < len(lines) and not lines[index].strip().startswith("```"):
                code.append(lines[index].rstrip())
                index += 1
            index += 1
            block = Table([[XPreformatted(html.escape("\n".join(code)), styles["code"]) ]], colWidths=[available_width])
            block.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F1F5F9")),
                ("BOX", (0, 0), (-1, -1), 0.6, LINE),
                ("LEFTPADDING", (0, 0), (-1, -1), 9),
                ("RIGHTPADDING", (0, 0), (-1, -1), 9),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]))
            if story and isinstance(story[-1], Paragraph):
                label = story.pop()
                story.append(KeepTogether([label, Spacer(1, 1.5 * mm), block]))
            else:
                story.append(block)
            story.append(Spacer(1, 2 * mm))
            continue
        if stripped.startswith("|"):
            table_lines = []
            while index < len(lines) and lines[index].strip().startswith("|"):
                table_lines.append(lines[index].strip())
                index += 1
            rows = []
            for table_line in table_lines:
                cells = [cell.strip() for cell in table_line.strip("|").split("|")]
                if all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells):
                    continue
                rows.append(cells)
            if rows:
                story.extend([markdown_table(rows, styles, available_width), Spacer(1, 3 * mm)])
            continue
        if stripped.startswith("## "):
            story.append(Paragraph(inline_markup(stripped[3:]), styles["h2"]))
        elif stripped.startswith("### "):
            story.append(Paragraph(inline_markup(stripped[4:]), styles["h3"]))
        elif re.match(r"^\d+\.\s+", stripped):
            number, text = stripped.split(". ", 1)
            story.append(Paragraph(f"<b>{number}.</b> {inline_markup(text)}", styles["bullet"]))
        elif stripped.startswith("- "):
            story.append(Paragraph(inline_markup(stripped[2:]), styles["bullet"], bulletText="•"))
        else:
            paragraph_lines = [stripped]
            index += 1
            while index < len(lines):
                candidate = lines[index].strip()
                if not candidate or candidate.startswith(("#", "- ", "|", "```")) or re.match(r"^\d+\.\s+", candidate):
                    break
                paragraph_lines.append(candidate)
                index += 1
            story.append(Paragraph(inline_markup(" ".join(paragraph_lines)), styles["body"]))
            continue
        index += 1
    return story


DOCUMENTS = [
    (
        ROOT / "docs" / "source_code_and_version.md",
        OUTPUT / "源代码及版本说明.pdf",
        "源代码及版本说明",
        "固定 GitHub 公开仓库、正式分支、源代码基线和参赛标签，并说明前后端、测试目录及 Web 系统不提供 EXE 的理由。",
    ),
    (
        ROOT / "docs" / "deployment_guide.md",
        OUTPUT / "部署说明.pdf",
        "部署说明",
        "覆盖本地安装、前后端启动、环境变量、数据库、Render 正式部署、在线验收与免费实例冷启动边界。",
    ),
    (
        ROOT / "docs" / "testing_and_coverage.md",
        OUTPUT / "单元测试与覆盖率说明.pdf",
        "单元测试与覆盖率说明",
        "记录 167 项自动化测试和两端真实覆盖率，提供 60% 自动失败门槛、机器可读报告与一键复现命令。",
    ),
]


def build_all() -> None:
    register_fonts()
    styles = make_styles()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    for source, destination, title, summary in DOCUMENTS:
        markdown = source.read_text(encoding="utf-8")
        doc = CompetitionDocTemplate(str(destination), title)
        story = cover(title, summary, styles)
        story.extend(markdown_story(markdown, styles, doc.width))
        doc.build(story)
        print(destination)


if __name__ == "__main__":
    build_all()
