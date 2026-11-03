"""Minimal OOXML writer for ATS-friendly CVs.

Single-column flow, no tables/text boxes/floating objects, real paragraph
styles only, so plain-text extraction by applicant tracking systems is lossless.
"""

import re
import zipfile

NS = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'

CONTENT_TYPES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
<Override PartName="/word/settings.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.settings+xml"/>
<Override PartName="/word/fontTable.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.fontTable+xml"/>
<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>
<Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>
</Types>"""

ROOT_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>
<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>
</Relationships>"""

DOC_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/settings" Target="settings.xml"/>
<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/fontTable" Target="fontTable.xml"/>
</Relationships>"""

SETTINGS = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:settings {NS}>
<w:zoom w:percent="100"/>
<w:defaultTabStop w:val="720"/>
<w:compat><w:compatSetting w:name="compatibilityMode" w:uri="http://schemas.microsoft.com/office/word" w:val="15"/></w:compat>
</w:settings>"""

FONT_TABLE = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:fonts {NS}>
<w:font w:name="Calibri"><w:family w:val="swiss"/><w:pitch w:val="variable"/></w:font>
<w:font w:name="Cambria"><w:family w:val="roman"/><w:pitch w:val="variable"/></w:font>
</w:fonts>"""

STYLES = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles {NS}>
<w:docDefaults>
<w:rPrDefault><w:rPr><w:rFonts w:ascii="Calibri" w:hAnsi="Calibri" w:cs="Calibri"/><w:sz w:val="21"/><w:szCs w:val="21"/><w:lang w:val="en-GB"/></w:rPr></w:rPrDefault>
<w:pPrDefault><w:pPr><w:spacing w:after="60" w:line="240" w:lineRule="auto"/></w:pPr></w:pPrDefault>
</w:docDefaults>
<w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/><w:qFormat/></w:style>
<w:style w:type="paragraph" w:styleId="Name"><w:name w:val="Name"/><w:basedOn w:val="Normal"/><w:pPr><w:spacing w:after="20"/><w:jc w:val="center"/></w:pPr><w:rPr><w:b/><w:color w:val="1F3864"/><w:sz w:val="40"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="Headline"><w:name w:val="Headline"/><w:basedOn w:val="Normal"/><w:pPr><w:spacing w:after="30"/><w:jc w:val="center"/></w:pPr><w:rPr><w:b/><w:color w:val="1F3864"/><w:sz w:val="23"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="Contact"><w:name w:val="Contact"/><w:basedOn w:val="Normal"/><w:pPr><w:spacing w:after="120"/><w:jc w:val="center"/></w:pPr><w:rPr><w:sz w:val="18"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="Section"><w:name w:val="Section Heading"/><w:basedOn w:val="Normal"/><w:pPr><w:keepNext/><w:pBdr><w:bottom w:val="single" w:sz="6" w:space="2" w:color="1F3864"/></w:pBdr><w:spacing w:before="150" w:after="80"/></w:pPr><w:rPr><w:b/><w:caps/><w:color w:val="1F3864"/><w:sz w:val="22"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="Role"><w:name w:val="Role"/><w:basedOn w:val="Normal"/><w:pPr><w:keepNext/><w:spacing w:before="90" w:after="20"/></w:pPr><w:rPr><w:b/><w:sz w:val="22"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="Sub"><w:name w:val="Sub"/><w:basedOn w:val="Normal"/><w:pPr><w:keepNext/><w:spacing w:after="40"/></w:pPr><w:rPr><w:i/><w:color w:val="404040"/><w:sz w:val="20"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="Bullet"><w:name w:val="Bullet"/><w:basedOn w:val="Normal"/><w:pPr><w:spacing w:after="40"/><w:ind w:left="340" w:hanging="340"/></w:pPr></w:style>
<w:style w:type="paragraph" w:styleId="Body"><w:name w:val="Body"/><w:basedOn w:val="Normal"/><w:pPr><w:spacing w:after="80"/></w:pPr></w:style>
</w:styles>"""


def esc(text):
    return (text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            .replace('"', '&quot;'))


def runs(markup, base=None):
    """Split **bold** segments into runs; base overrides live inside <w:rPr>."""
    out = []
    for piece in re.split(r'(\*\*.+?\*\*)', markup):
        if not piece:
            continue
        bold = piece.startswith('**') and piece.endswith('**')
        text = piece[2:-2] if bold else piece
        props = []
        if bold:
            props.append('<w:b/>')
        if base:
            props.append(base)
        rpr = f'<w:rPr>{"".join(props)}</w:rPr>' if props else ''
        out.append(f'<w:r>{rpr}<w:t xml:space="preserve">{esc(text)}</w:t></w:r>')
    return ''.join(out)


def para(markup, style=None, jc=None, spacing=None, ind=None, keep=False, border=None):
    # Word requires a fixed child order inside <w:pPr>: pStyle, keepNext, pBdr, tabs, spacing, ind, jc.
    ppr = []
    if style:
        ppr.append(f'<w:pStyle w:val="{style}"/>')
    if keep:
        ppr.append('<w:keepNext/>')
    if border:
        ppr.append(border)
    if spacing:
        ppr.append(f'<w:spacing {spacing}/>')
    if ind:
        ppr.append(f'<w:ind {ind}/>')
    if jc:
        ppr.append(f'<w:jc w:val="{jc}"/>')
    ppr = f'<w:pPr>{"".join(ppr)}</w:pPr>' if ppr else ''
    return f'<w:p>{ppr}{runs(markup)}</w:p>'


def tab_row(left_markup, right_markup, style='Role'):
    """Right-aligned date via a single tab stop: still one text line for parsers."""
    body = runs(left_markup) + '<w:r><w:tab/></w:r>' + runs(right_markup)
    return (f'<w:p><w:pPr><w:pStyle w:val="{style}"/><w:keepNext/>'
            f'<w:tabs><w:tab w:val="right" w:pos="10200"/></w:tabs></w:pPr>{body}</w:p>')


def document_xml(paragraphs):
    sect = ('<w:sectPr><w:pgSz w:w="11906" w:h="16838"/>'
            '<w:pgMar w:top="720" w:right="850" w:bottom="720" w:left="850" '
            'w:header="425" w:footer="425" w:gutter="0"/>'
            '<w:docGrid w:linePitch="360"/></w:sectPr>')
    return (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            f'<w:document {NS}><w:body>{"".join(paragraphs)}{sect}</w:body></w:document>')


def core_xml(name, title, description):
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
<dc:title>{esc(title)}</dc:title>
<dc:subject>{esc(title)}</dc:subject>
<dc:creator>{esc(name)}</dc:creator>
<cp:keywords>{esc(description)}</cp:keywords>
<dc:description>{esc(description)}</dc:description>
</cp:coreProperties>"""


APP_XML = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">
<Application>Microsoft Office Word</Application>
<Company>Lyle Okoth</Company>
</Properties>"""


def write_docx(path, paragraphs, name, title, keywords):
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr('[Content_Types].xml', CONTENT_TYPES)
        zf.writestr('_rels/.rels', ROOT_RELS)
        zf.writestr('word/_rels/document.xml.rels', DOC_RELS)
        zf.writestr('word/document.xml', document_xml(paragraphs))
        zf.writestr('word/styles.xml', STYLES)
        zf.writestr('word/settings.xml', SETTINGS)
        zf.writestr('word/fontTable.xml', FONT_TABLE)
        zf.writestr('docProps/core.xml', core_xml(name, title, keywords))
        zf.writestr('docProps/app.xml', APP_XML)
