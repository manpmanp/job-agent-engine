# Job-search agent engine
# File:    engine/docx_render.py
# Purpose: Renders a CV or cover-letter spec (JSON) to .docx with python-docx (no Node needed).
# Author:  manpmanp <manp.node@gmail.com>
# Generated with Claude (Anthropic), under the author's direction and review.
# License: MIT (see LICENSE)
# Version: 0.4.0
# Date:    2026-10-28

"""
render_docx(spec, out_path, style) writes the document described in
docs/document_spec.md. All visual choices come from the style (defaults
below, overridden by inputs/document_style.json):

- navy banner with white name, title, subtitle and contact line,
- section headers in the accent colour, upper case, with a thin rule,
  kept with the text that follows,
- job title in bold with the dates right-aligned, organization in grey italics,
- bullets, and a borderless two-column skills table.

Units: spacing in points, font sizes in points.
"""
import os

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_TAB_ALIGNMENT, WD_LINE_SPACING
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt, RGBColor, Twips

DEFAULT_STYLE = {
    "font": "Calibri",
    "banner_color": "1F3864",
    "accent_color": "2E74B5",
    "secondary_text_color": "595959",
    "body_text_color": "222222",
    "page_size": "A4",
}
PAGE_SIZES = {"A4": (11906, 16838), "Letter": (12240, 15840)}
MARGINS = {"top": 500, "bottom": 600, "left": 850, "right": 850}  # twips


def _rgb(hexstr):
    h = str(hexstr or "000000").lstrip("#")
    return RGBColor(int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def _run(par, text, S, size=10, bold=False, italic=False, color=None, spacing=None):
    r = par.add_run(text or "")
    r.font.name = S["font"]
    r._element.rPr.rFonts.set(qn("w:eastAsia"), S["font"])
    r.font.size = Pt(size)
    r.font.bold = bold
    r.font.italic = italic
    r.font.color.rgb = _rgb(color or S["body_text_color"])
    if spacing:
        sp = OxmlElement("w:spacing")
        sp.set(qn("w:val"), str(spacing))
        r._element.rPr.append(sp)
    return r


def _fmt(par, before=0, after=6, line=1.1, keep_next=False, page_break=False):
    pf = par.paragraph_format
    pf.space_before = Pt(before)
    pf.space_after = Pt(after)
    pf.line_spacing_rule = WD_LINE_SPACING.MULTIPLE
    pf.line_spacing = line
    pf.keep_with_next = keep_next
    if page_break:
        pf.page_break_before = True
    return par


def _no_borders(table):
    tbl_pr = table._tbl.tblPr
    borders = OxmlElement("w:tblBorders")
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        el = OxmlElement(f"w:{edge}")
        el.set(qn("w:val"), "nil")
        borders.append(el)
    tbl_pr.append(borders)


def _shade(cell, fill):
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), fill)
    tc_pr.append(shd)


def _cell_margins(cell, top=0, bottom=0, left=0, right=0):
    tc_pr = cell._tc.get_or_add_tcPr()
    mar = OxmlElement("w:tcMar")
    for k, v in (("top", top), ("bottom", bottom), ("left", left), ("right", right)):
        el = OxmlElement(f"w:{k}")
        el.set(qn("w:w"), str(v))
        el.set(qn("w:type"), "dxa")
        mar.append(el)
    tc_pr.append(mar)


def _bottom_rule(par, color):
    p_pr = par._p.get_or_add_pPr()
    bdr = OxmlElement("w:pBdr")
    b = OxmlElement("w:bottom")
    b.set(qn("w:val"), "single")
    b.set(qn("w:sz"), "6")
    b.set(qn("w:space"), "4")
    b.set(qn("w:color"), color)
    bdr.append(b)
    p_pr.append(bdr)


class _Writer:
    def __init__(self, style):
        self.S = {**DEFAULT_STYLE, **{k: v for k, v in (style or {}).items() if not str(k).startswith("_") and v}}
        self.doc = Document()
        sec = self.doc.sections[0]
        w, h = PAGE_SIZES.get(self.S.get("page_size"), PAGE_SIZES["A4"])
        sec.page_width, sec.page_height = Twips(w), Twips(h)
        sec.top_margin, sec.bottom_margin = Twips(MARGINS["top"]), Twips(MARGINS["bottom"])
        sec.left_margin, sec.right_margin = Twips(MARGINS["left"]), Twips(MARGINS["right"])
        self.text_width = w - MARGINS["left"] - MARGINS["right"]
        normal = self.doc.styles["Normal"]
        normal.font.name = self.S["font"]
        normal.font.size = Pt(10)
        # python-docx starts with one empty paragraph; it is reused or removed.
        self._first = self.doc.paragraphs[0] if self.doc.paragraphs else None

    def par(self):
        if self._first is not None:
            p, self._first = self._first, None
            return p
        return self.doc.add_paragraph()

    def banner(self, b):
        if self._first is not None:  # a table cannot be the very first block in python-docx's body order otherwise
            self._first._p.getparent().remove(self._first._p)
            self._first = None
        t = self.doc.add_table(rows=1, cols=1)
        t.alignment = WD_TABLE_ALIGNMENT.CENTER
        _no_borders(t)
        cell = t.rows[0].cells[0]
        cell.width = Twips(self.text_width)
        _shade(cell, self.S["banner_color"])
        _cell_margins(cell, top=160, bottom=160, left=120, right=120)
        p = cell.paragraphs[0]
        _fmt(p, before=10, after=2)
        _run(p, b.get("name"), self.S, size=22, bold=True, color="FFFFFF")
        p = cell.add_paragraph(); _fmt(p, after=3)
        _run(p, b.get("title"), self.S, size=12, color="FFFFFF")
        if b.get("subtitle"):
            p = cell.add_paragraph(); _fmt(p, after=3)
            _run(p, b["subtitle"], self.S, size=9, color="FFFFFF")
        p = cell.add_paragraph(); _fmt(p, after=10)
        _run(p, b.get("contact"), self.S, size=9, color="FFFFFF")

    def body(self, text, after=6, size=10, italic=False, bold=False, color=None):
        p = _fmt(self.par(), after=after)
        _run(p, text, self.S, size=size, italic=italic, bold=bold, color=color)
        return p

    def heading(self, text, page_break=False):
        p = _fmt(self.par(), before=13, after=5, keep_next=True, page_break=page_break)
        p.paragraph_format.keep_together = True
        _bottom_rule(p, self.S["accent_color"])
        _run(p, str(text).upper(), self.S, size=10, bold=True, color=self.S["accent_color"], spacing=20)

    def job_header(self, title, dates):
        p = _fmt(self.par(), before=13, after=1.5, keep_next=True)
        p.paragraph_format.tab_stops.add_tab_stop(Twips(self.text_width), WD_TAB_ALIGNMENT.RIGHT)
        _run(p, title, self.S, bold=True)
        _run(p, "\t" + (dates or ""), self.S, color=self.S["secondary_text_color"])

    def org(self, text):
        p = _fmt(self.par(), after=7, keep_next=True)
        _run(p, text, self.S, size=9.5, italic=True, color=self.S["secondary_text_color"])

    def bullet(self, text):
        p = self.par()
        try:
            p.style = self.doc.styles["List Bullet"]
        except KeyError:
            text = "• " + text
        _fmt(p, after=6.5)
        _run(p, text, self.S)

    def skills(self, rows):
        t = self.doc.add_table(rows=0, cols=2)
        _no_borders(t)
        t.autofit = False
        w1 = int(self.text_width * 0.22)
        layout = OxmlElement("w:tblLayout")
        layout.set(qn("w:type"), "fixed")
        t._tbl.tblPr.append(layout)
        for col, width in zip(t._tbl.tblGrid.findall(qn("w:gridCol")), (w1, self.text_width - w1)):
            col.set(qn("w:w"), str(width))
        for label, value in rows:
            cells = t.add_row().cells
            for c, txt, bold, width in ((cells[0], label, True, w1), (cells[1], value, False, self.text_width - w1)):
                c.width = Twips(width)
                _cell_margins(c, top=40, bottom=40, left=0, right=120 if bold else 0)
                p = c.paragraphs[0]
                _fmt(p, after=0)
                _run(p, txt, self.S, size=9.5, bold=bold)
        self._first = None

    def save(self, path):
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        self.doc.save(path)


def render_docx(spec, out_path, style=None):
    W = _Writer(style)
    W.banner(spec.get("banner") or {})
    if spec.get("template_note"):
        W.body(spec["template_note"], after=3, size=8.5, italic=True, color=W.S["secondary_text_color"])
    if spec.get("type") == "cl":
        W.body("", after=6)
        if spec.get("date"):
            W.body(spec["date"], after=8)
        rec = spec.get("recipient") or []
        for i, line in enumerate(rec):
            W.body(line, after=10 if i == len(rec) - 1 else 0)
        if spec.get("salutation"):
            W.body(spec["salutation"], after=8)
        for p in spec.get("paragraphs") or []:
            W.body(p, after=8)
        W.body(spec.get("closing") or "Kind regards,", after=3)
        W.body(spec.get("signature") or (spec.get("banner") or {}).get("name") or "", bold=True)
    else:
        for sec in spec.get("sections") or []:
            if sec.get("heading"):
                W.heading(sec["heading"], page_break=bool(sec.get("page_break_before")))
            for p in sec.get("paragraphs") or []:
                W.body(p)
            for e in sec.get("entries") or []:
                W.job_header(e.get("title"), e.get("dates"))
                if e.get("org"):
                    W.org(e["org"])
                for p in e.get("paragraphs") or []:
                    W.body(p)
                for b in e.get("bullets") or []:
                    W.bullet(b)
            if sec.get("table"):
                W.skills(sec["table"])
            for b in sec.get("bullets") or []:
                W.bullet(b)
    W.save(out_path)
    return out_path
