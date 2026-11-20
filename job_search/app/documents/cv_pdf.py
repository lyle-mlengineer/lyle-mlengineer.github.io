"""DOCX → PDF with LibreOffice, plus a deterministic reportlab fallback."""

from __future__ import annotations

import html
import logging
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    HRFlowable,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from .resume import CONTACT_LINE, LINKS, NAME

logger = logging.getLogger("skipper.documents.pdf")
DARK = colors.HexColor("#1F2A37")


@dataclass(frozen=True)
class PdfResult:
    content: bytes
    engine: str
    pages: int


def render_pdf(docx_bytes: bytes, resume: dict[str, Any], *, soffice_path: str = "soffice") -> PdfResult:
    """Prefer LibreOffice (matches the DOCX exactly), fall back to reportlab."""
    soffice = find_soffice(soffice_path)
    if soffice:
        converted = _convert_with_soffice(docx_bytes, soffice)
        if converted is not None:
            return PdfResult(converted, "libreoffice", pdf_page_count(converted))
        logger.warning("LibreOffice conversion failed; using the reportlab fallback")
    content = _reportlab_pdf(resume)
    return PdfResult(content, "reportlab", pdf_page_count(content))


def pdf_page_count(content: bytes) -> int:
    return len(re.findall(rb"/Type\s*/Page[^s]", content))


def find_soffice(path: str = "soffice") -> str | None:
    """Find LibreOffice on PATH or in the usual install locations.

    Windows installs do not add ``soffice`` to PATH, which used to leave every
    CV on the plainer reportlab fallback. A configured absolute path still wins.
    """
    if path:
        found = shutil.which(path)
        if found:
            return found
        candidate = Path(path)
        if candidate.is_file():
            return str(candidate)
        if path != "soffice":
            return None
    for candidate in (
        Path(r"C:/Program Files/LibreOffice/program/soffice.exe"),
        Path(r"C:/Program Files (x86)/LibreOffice/program/soffice.exe"),
        Path("/Applications/LibreOffice.app/Contents/MacOS/soffice"),
        Path("/usr/bin/libreoffice"),
        Path("/usr/bin/soffice"),
        Path("/usr/local/bin/soffice"),
    ):
        if candidate.is_file():
            return str(candidate)
    return None


def convert_docx_to_pdf(docx_bytes: bytes, soffice_path: str) -> bytes | None:
    """Public seam for any DOCX→PDF caller; returns None when LibreOffice cannot help."""
    soffice = find_soffice(soffice_path)
    return _convert_with_soffice(docx_bytes, soffice) if soffice else None


def _convert_with_soffice(docx_bytes: bytes, soffice: str) -> bytes | None:
    with tempfile.TemporaryDirectory(prefix="skipper-cv-") as temp:
        root = Path(temp)
        source = root / "resume.docx"
        source.write_bytes(docx_bytes)
        profile = (root / "profile").as_uri()
        command = [
            soffice,
            f"-env:UserInstallation={profile}",
            "--headless",
            "--norestore",
            "--convert-to",
            "pdf",
            "--outdir",
            str(root),
            str(source),
        ]
        try:
            result = subprocess.run(command, capture_output=True, timeout=60, check=False)
        except (OSError, subprocess.TimeoutExpired):
            logger.exception("soffice did not finish")
            return None
        target = root / "resume.pdf"
        if result.returncode != 0 or not target.is_file():
            logger.warning("soffice returned %s: %s", result.returncode, result.stderr[-400:])
            return None
        content = target.read_bytes()
        return content if content.startswith(b"%PDF-") else None


def _reportlab_pdf(resume: dict[str, Any]) -> bytes:
    from io import BytesIO

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=0.5 * inch,
        rightMargin=0.5 * inch,
        topMargin=0.45 * inch,
        bottomMargin=0.45 * inch,
        title=f"{NAME} — {resume.get('headline', '')}".strip(" —"),
        author=NAME,
        pageCompression=0,
    )
    styles = _styles()
    story: list[Any] = [
        Paragraph(_safe(NAME), styles["name"]),
        Paragraph(_safe(str(resume.get("headline") or "")), styles["headline"]),
        Paragraph(_safe(CONTACT_LINE), styles["contact"]),
        Paragraph(
            _safe("  |  ".join(label for label, _url in LINKS)),
            styles["links"],
        ),
        Spacer(1, 5),
    ]

    _section(story, "Professional Summary", styles)
    story.append(Paragraph(_safe(str(resume.get("summary") or "")), styles["body"]))

    groups = resume.get("skill_groups") or []
    if groups:
        _section(story, "Core Competencies", styles)
        for group in groups:
            story.append(
                Paragraph(
                    f"<b>{_safe(str(group['name']))}:</b> {_safe(', '.join(group['items']))}",
                    styles["body"],
                )
            )

    tech_groups = resume.get("tech_groups") or []
    if tech_groups:
        _section(story, "Technical Skills", styles)
        for group in tech_groups:
            story.append(
                Paragraph(
                    f"<b>{_safe(str(group['name']))}:</b> {_safe(', '.join(group['items']))}",
                    styles["body"],
                )
            )

    jobs = resume.get("experience") or []
    if jobs:
        _section(story, "Professional Experience", styles)
        for job in jobs:
            story.append(_role_table(str(job["title"]), str(job["company"]), str(job["dates"]), styles))
            for text in job["bullets"]:
                story.append(Paragraph(_safe(str(text)), styles["bullet"], bulletText="•"))

    projects = resume.get("projects") or []
    if projects:
        _section(story, "Selected Projects", styles)
        for project in projects:
            description = " ".join(
                str(text).strip() for text in (project.get("bullets") or [])[:3] if str(text).strip()
            )
            label = f"<b>{_safe(str(project['name']))} — </b>{_safe(description[:900])}"
            story.append(Paragraph(label, styles["body"]))
            links = [str(link) for link in (project.get("links") or [])[:2]]
            if links:
                label = "  ·  ".join(
                    f'<link href="{_safe(link)}">{_safe(_link_label(link))}</link>' for link in links
                )
                story.append(Paragraph(label, styles["project_links"]))

    education = resume.get("education") or []
    if education:
        _section(story, "Education", styles)
        for row in education:
            story.append(
                _role_table(
                    str(row["credential"]),
                    str(row["institution"]),
                    str(row.get("dates") or ""),
                    styles,
                )
            )

    if resume.get("certifications"):
        _section(story, "Certifications", styles)
        story.append(Paragraph(_safe(str(resume["certifications"])), styles["body"]))

    story.append(Paragraph("References available on request.", styles["references"]))
    doc.build(story)
    return buffer.getvalue()


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "name": ParagraphStyle(
            "CvName", parent=base["Normal"], fontName="Helvetica-Bold", fontSize=18,
            leading=21, alignment=TA_CENTER, textColor=DARK, spaceAfter=1,
        ),
        "headline": ParagraphStyle(
            "CvHeadline", parent=base["Normal"], fontName="Helvetica-Bold", fontSize=10.5,
            leading=13, alignment=TA_CENTER, spaceAfter=1,
        ),
        "contact": ParagraphStyle(
            "CvContact", parent=base["Normal"], fontSize=8.5, leading=11, alignment=TA_CENTER,
            spaceAfter=1,
        ),
        "links": ParagraphStyle(
            "CvLinks", parent=base["Normal"], fontSize=8, leading=10, alignment=TA_CENTER,
            textColor=colors.HexColor("#1F6FB2"), spaceAfter=2,
        ),
        "section": ParagraphStyle(
            "CvSection", parent=base["Normal"], fontName="Helvetica-Bold", fontSize=9.5,
            leading=12, textColor=DARK, spaceBefore=5, spaceAfter=1,
        ),
        "body": ParagraphStyle(
            "CvBody", parent=base["Normal"], fontSize=9, leading=11.4, spaceAfter=1.5,
        ),
        "role": ParagraphStyle(
            "CvRole", parent=base["Normal"], fontName="Helvetica-Bold", fontSize=9.5, leading=11.5,
        ),
        "dates": ParagraphStyle(
            "CvDates", parent=base["Normal"], fontSize=8.5, leading=11.5, alignment=TA_RIGHT,
        ),
        "bullet": ParagraphStyle(
            "CvBullet", parent=base["Normal"], fontSize=9, leading=11.2, leftIndent=12,
            bulletIndent=3, spaceAfter=0.8,
        ),
        "project": ParagraphStyle(
            "CvProject", parent=base["Normal"], fontName="Helvetica-Bold", fontSize=9.2, leading=11.4,
            spaceBefore=2, spaceAfter=0.5,
        ),
        "references": ParagraphStyle(
            "CvReferences", parent=base["Normal"], fontSize=8.2, leading=10.2,
            fontName="Helvetica-Oblique", spaceBefore=5,
        ),
        "project_links": ParagraphStyle(
            "CvProjectLinks", parent=base["Normal"], fontSize=8.2, leading=10.2,
            textColor=colors.HexColor("#1F6FB2"), spaceAfter=2,
        ),
    }


def _section(story: list[Any], title: str, styles: dict[str, ParagraphStyle]) -> None:
    story.append(
        KeepTogether(
            [
                Paragraph(_safe(title.upper()), styles["section"]),
                HRFlowable(width="100%", thickness=0.7, color=DARK, spaceBefore=0, spaceAfter=3),
            ]
        )
    )


def _role_table(title: str, company: str, dates: str, styles: dict[str, ParagraphStyle]) -> Table:
    left = f"{_safe(title)} — {_safe(company)}" if company else _safe(title)
    table = Table(
        [[Paragraph(f"<b>{left}</b>", styles["role"]), Paragraph(_safe(dates), styles["dates"])]],
        colWidths=[5.65 * inch, 1.65 * inch],
    )
    table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )
    return table


def _link_label(url: str) -> str:
    label = url.removeprefix("https://").removeprefix("http://").removeprefix("www.")
    return label.rstrip("/")


def _safe(value: str) -> str:
    return html.escape(value or "", quote=False)
