"""One-page cover letter in DOCX, then PDF via LibreOffice or reportlab.

Set in the same letterhead as ``cv/*.docx``: centred name, uppercase role
tagline, contact line with real hyperlinks, a navy hairline, then the letter
body at the CV's 10.5 pt Calibri. One page, always.
"""

from __future__ import annotations

import html
from datetime import UTC, datetime
from io import BytesIO
from typing import Any

from docx import Document
from docx.shared import Inches, Pt
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import HRFlowable, Paragraph, SimpleDocTemplate, Spacer

from .cv_docx import identity_header
from .cv_pdf import PdfResult, convert_docx_to_pdf, pdf_page_count
from .resume import CONTACT_LINE, LINKS, NAME

DARK = colors.HexColor("#1F2A37")
MUTED = "4A5568"


def letter_date() -> str:
    return datetime.now(UTC).strftime("%d %B %Y")


def build_letter_docx(letter: dict[str, Any], headline: str = "") -> bytes:
    doc = Document()
    doc.styles["Normal"].font.name = "Calibri"
    doc.styles["Normal"].font.size = Pt(10.5)
    for section in doc.sections:
        section.top_margin = Inches(0.6)
        section.bottom_margin = Inches(0.6)
        section.left_margin = Inches(0.75)
        section.right_margin = Inches(0.75)

    identity_header(doc, headline.upper() or "LETTER OF APPLICATION", rule=True)

    date = doc.add_paragraph()
    date.paragraph_format.space_after = Pt(14)
    date_run = date.add_run(letter_date())
    date_run.font.size = Pt(9)
    date_run.font.color.rgb = _rgb(MUTED)

    _para(doc, str(letter.get("greeting") or "Hello,"), space_after=10)
    for paragraph in letter.get("paragraphs") or []:
        _para(doc, str(paragraph), space_after=10)
    _para(doc, str(letter.get("closing") or "Sincerely,"), space_after=16)
    _para(doc, NAME, bold=True, space_after=0)

    doc.core_properties.title = f"{NAME} — cover letter"
    doc.core_properties.author = NAME
    buffer = BytesIO()
    doc.save(buffer)
    return buffer.getvalue()


def render_letter_pdf(
    docx_bytes: bytes,
    letter: dict[str, Any],
    *,
    soffice_path: str = "soffice",
    headline: str = "",
) -> PdfResult:
    converted = convert_docx_to_pdf(docx_bytes, soffice_path)
    if converted is not None:
        return PdfResult(converted, "libreoffice", pdf_page_count(converted))
    content = _reportlab_letter(letter, headline)
    return PdfResult(content, "reportlab", pdf_page_count(content))


def _para(doc: Document, value: str, *, bold: bool = False, space_after: float = 0) -> None:
    paragraph = doc.add_paragraph()
    paragraph.paragraph_format.space_after = Pt(space_after)
    paragraph.paragraph_format.line_spacing = 1.15
    run = paragraph.add_run(value)
    run.bold = bold
    run.font.size = Pt(10.5)


def _rgb(value: str):
    from docx.shared import RGBColor

    return RGBColor.from_string(value)


def _reportlab_letter(letter: dict[str, Any], headline: str = "") -> bytes:
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=0.75 * inch,
        rightMargin=0.75 * inch,
        topMargin=0.6 * inch,
        bottomMargin=0.6 * inch,
        title=f"{NAME} — cover letter",
        author=NAME,
        pageCompression=0,
    )
    styles = getSampleStyleSheet()
    name_style = ParagraphStyle(
        "LetterName", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=18,
        leading=21, alignment=1, textColor=DARK, spaceAfter=1,
    )
    tagline = ParagraphStyle(
        "LetterTagline", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=11.5,
        leading=14, alignment=1, textColor=DARK, spaceAfter=1,
    )
    contact = ParagraphStyle(
        "LetterContact", parent=styles["Normal"], fontSize=10, leading=12, alignment=1, spaceAfter=1,
    )
    links = ParagraphStyle(
        "LetterLinks", parent=styles["Normal"], fontSize=9, leading=11, alignment=1,
        textColor=colors.HexColor("#1F6FB2"), spaceAfter=2,
    )
    date_style = ParagraphStyle(
        "LetterDate", parent=styles["Normal"], fontSize=9, leading=12, spaceAfter=14,
        textColor=colors.HexColor("#4A5568"),
    )
    body = ParagraphStyle("LetterBody", parent=styles["Normal"], fontSize=10.5, leading=14.5, spaceAfter=10)

    link_line = "  |  ".join(
        f'<link href="{html.escape(url, quote=True)}">{html.escape(label)}</link>' for label, url in LINKS
    )
    story = [
        Paragraph(html.escape(NAME), name_style),
        Paragraph(html.escape((headline or "Letter of application").upper()), tagline),
        Paragraph(html.escape(CONTACT_LINE), contact),
        Paragraph(link_line, links),
        Spacer(1, 4),
        HRFlowable(width="100%", thickness=0.7, color=DARK, spaceBefore=0, spaceAfter=10),
        Paragraph(html.escape(letter_date()), date_style),
        Paragraph(html.escape(str(letter.get("greeting") or "Hello,")), body),
    ]
    for paragraph in letter.get("paragraphs") or []:
        story.append(Paragraph(html.escape(str(paragraph)).replace("\n", "<br/>"), body))
    story.append(Paragraph(html.escape(str(letter.get("closing") or "Sincerely,")), body))
    story.append(Spacer(1, 6))
    story.append(Paragraph(html.escape(NAME), ParagraphStyle(
        "LetterSign", parent=body, fontName="Helvetica-Bold", spaceAfter=0,
    )))
    doc.build(story)
    return buffer.getvalue()
