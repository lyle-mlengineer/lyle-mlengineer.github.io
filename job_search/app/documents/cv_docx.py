"""Resume DOCX, laid out like ``cv/_generate_cvs.py``.

Kept deliberately plain: Calibri, one column, standard section names, no text
boxes or tables. That is what applicant tracking systems read cleanly.
"""

from __future__ import annotations

from io import BytesIO
from typing import Any

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_TAB_ALIGNMENT
from docx.opc.constants import RELATIONSHIP_TYPE as RT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor

from .resume import CONTACT_LINE, LINKS, NAME

DARK = RGBColor(0x1F, 0x2A, 0x37)
LINK = "1F6FB2"
MAX_PROJECT_BULLET_CHARS = 260
MAX_PROJECT_CHARS = 900


def build_cv_docx(resume: dict[str, Any]) -> bytes:
    doc = Document()
    _base_styles(doc)
    identity_header(doc, str(resume.get("headline") or ""))

    _section(doc, "Professional Summary")
    _para(doc, str(resume.get("summary") or ""), size=10.5, space_after=5)

    groups = resume.get("skill_groups") or []
    if groups:
        _section(doc, "Core Competencies")
        for group in groups:
            _labeled(doc, str(group["name"]), ", ".join(group["items"]))

    tech_groups = resume.get("tech_groups") or []
    if tech_groups:
        _section(doc, "Technical Skills")
        for group in tech_groups:
            _labeled(doc, str(group["name"]), ", ".join(group["items"]))

    jobs = resume.get("experience") or []
    if jobs:
        _section(doc, "Professional Experience")
        for job in jobs:
            _role_header(doc, str(job["title"]), str(job["company"]), str(job["dates"]))
            for text in job["bullets"]:
                _bullet(doc, text)

    projects = resume.get("projects") or []
    if projects:
        _section(doc, "Selected Projects")
        for project in projects:
            description = " ".join(
                str(text).strip() for text in (project.get("bullets") or [])[:3] if str(text).strip()
            )
            p = doc.add_paragraph()
            p.paragraph_format.space_after = Pt(1)
            run = p.add_run(str(project["name"]) + " — ")
            run.bold = True
            run.font.size = Pt(10.5)
            body = p.add_run(description[:MAX_PROJECT_CHARS])
            body.font.size = Pt(10.5)
            _project_links(doc, project.get("links") or [])

    education = resume.get("education") or []
    if education:
        _section(doc, "Education")
        for row in education:
            _role_header(doc, str(row["credential"]), str(row["institution"]), str(row.get("dates") or ""))

    if resume.get("certifications"):
        _section(doc, "Certifications")
        _para(doc, str(resume["certifications"]), space_after=4)

    references = _para(doc, "References available on request.", size=9.5, space_after=0)
    references.runs[0].italic = True
    references.paragraph_format.space_before = Pt(6)

    _compact(doc)
    doc.core_properties.title = f"{NAME} — {resume.get('headline', '')}".strip(" —")
    doc.core_properties.author = NAME
    buffer = BytesIO()
    doc.save(buffer)
    return buffer.getvalue()


def _base_styles(doc: Document) -> None:
    doc.styles["Normal"].font.name = "Calibri"
    doc.styles["Normal"].font.size = Pt(10.5)
    doc.styles["List Bullet"].font.name = "Calibri"
    doc.styles["List Bullet"].font.size = Pt(10.5)
    for section in doc.sections:
        section.top_margin = Inches(0.55)
        section.bottom_margin = Inches(0.55)
        section.left_margin = Inches(0.6)
        section.right_margin = Inches(0.6)


def _compact(doc: Document) -> None:
    """Apply the portfolio CVs' compact pass: 10 pt body, tighter margins and spacing."""
    for style_name in ("Normal", "List Bullet"):
        doc.styles[style_name].font.size = Pt(10)
    for section in doc.sections:
        section.top_margin = Inches(0.45)
        section.bottom_margin = Inches(0.45)
        section.left_margin = Inches(0.5)
        section.right_margin = Inches(0.5)
    for paragraph in doc.paragraphs:
        for run in paragraph.runs:
            if run.font.size:
                run.font.size = Pt(max(8.5, run.font.size.pt - 0.5))
        fmt = paragraph.paragraph_format
        if fmt.space_before is not None:
            fmt.space_before = Pt(fmt.space_before.pt * 0.75)
        if fmt.space_after is not None:
            fmt.space_after = Pt(fmt.space_after.pt * 0.75)


def _add_hyperlink(paragraph, url: str, text: str, size: float = 9) -> None:
    part = paragraph.part
    relationship = part.relate_to(url, RT.HYPERLINK, is_external=True)
    hyperlink = OxmlElement("w:hyperlink")
    hyperlink.set(qn("r:id"), relationship)
    run = OxmlElement("w:r")
    props = OxmlElement("w:rPr")
    color = OxmlElement("w:color")
    color.set(qn("w:val"), LINK)
    props.append(color)
    underline = OxmlElement("w:u")
    underline.set(qn("w:val"), "single")
    props.append(underline)
    size_el = OxmlElement("w:sz")
    size_el.set(qn("w:val"), str(int(size * 2)))
    props.append(size_el)
    run.append(props)
    node = OxmlElement("w:t")
    node.text = text
    run.append(node)
    hyperlink.append(run)
    paragraph._p.append(hyperlink)


def identity_header(doc: Document, headline: str, *, rule: bool = False) -> None:
    """Portfolio CV letterhead: centred name, role tagline, contact line and links.

    Shared with the cover letter so generated documents keep one visual identity.
    """
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_after = Pt(0)
    run = p.add_run(NAME)
    run.bold = True
    run.font.size = Pt(18)
    run.font.color.rgb = DARK

    _para(doc, headline, bold=True, size=11.5, space_after=1, align=WD_ALIGN_PARAGRAPH.CENTER)
    _para(doc, CONTACT_LINE, size=10, space_after=1, align=WD_ALIGN_PARAGRAPH.CENTER)

    links = doc.add_paragraph()
    links.alignment = WD_ALIGN_PARAGRAPH.CENTER
    links.paragraph_format.space_after = Pt(2)
    for index, (label, url) in enumerate(LINKS):
        if index:
            separator = links.add_run("  |  ")
            separator.font.size = Pt(9)
        _add_hyperlink(links, url, label, size=9)

    if rule:
        _rule(doc)


def _rule(doc: Document, *, space_before: float = 6, space_after: float = 8) -> None:
    """Hairline below the letterhead, matching the CV section rules."""
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(space_before)
    p.paragraph_format.space_after = Pt(space_after)
    props = p._p.get_or_add_pPr()
    border = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), "6")
    bottom.set(qn("w:space"), "1")
    bottom.set(qn("w:color"), "1F2A37")
    border.append(bottom)
    props.append(border)
    return


def _section(doc: Document, text: str):
    p = doc.add_paragraph()
    p.paragraph_format.keep_with_next = True
    p.paragraph_format.space_before = Pt(8)
    p.paragraph_format.space_after = Pt(4)
    run = p.add_run(text.upper())
    run.bold = True
    run.font.size = Pt(11)
    run.font.color.rgb = DARK
    props = p._p.get_or_add_pPr()
    border = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), "6")
    bottom.set(qn("w:space"), "2")
    bottom.set(qn("w:color"), "1F2A37")
    border.append(bottom)
    props.append(border)
    return p


def _para(doc: Document, text: str, *, bold: bool = False, size: float = 10.5,
          space_after: float = 3, align=None):
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(space_after)
    p.paragraph_format.space_before = Pt(0)
    if align:
        p.alignment = align
    run = p.add_run(text)
    run.bold = bold
    run.font.size = Pt(size)
    return p


def _link_label(url: str) -> str:
    label = url.removeprefix("https://").removeprefix("http://").removeprefix("www.")
    return label.rstrip("/")


def _project_links(doc: Document, links: list[Any]) -> None:
    if not links:
        return
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(3)
    p.paragraph_format.space_before = Pt(0)
    for index, raw in enumerate(links[:2]):
        url = str(raw)
        if index:
            separator = p.add_run("  ·  ")
            separator.font.size = Pt(9)
        _add_hyperlink(p, url, _link_label(url), size=9)


def _labeled(doc: Document, label: str, text: str) -> None:
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(2)
    lead = p.add_run(f"{label}: ")
    lead.bold = True
    lead.font.size = Pt(10.5)
    body = p.add_run(text)
    body.font.size = Pt(10.5)


def _role_header(doc: Document, title: str, company: str, dates: str) -> None:
    p = doc.add_paragraph()
    p.paragraph_format.keep_with_next = True
    p.paragraph_format.space_before = Pt(5)
    p.paragraph_format.space_after = Pt(2)
    p.paragraph_format.tab_stops.add_tab_stop(Inches(7.3), WD_TAB_ALIGNMENT.RIGHT)
    lead = p.add_run(f"{title} — {company}" if company else title)
    lead.bold = True
    lead.font.size = Pt(11)
    tail = p.add_run("\t" + dates)
    tail.font.size = Pt(10.5)


def _bullet(doc: Document, text: str, *, keep_with_next: bool = False) -> None:
    p = doc.add_paragraph(style="List Bullet")
    p.paragraph_format.space_after = Pt(2)
    p.paragraph_format.keep_together = True
    p.paragraph_format.keep_with_next = keep_with_next
    run = p.add_run(text)
    run.font.size = Pt(10.5)
