"""Shared PDF building blocks (reportlab). One look for every PDF the system produces."""
import io
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (BaseDocTemplate, CondPageBreak, Frame, HRFlowable, Image, KeepTogether, PageTemplate,
                                Paragraph, Spacer, Table, TableStyle)

# IEML palette: navy ink, IEML blue (brand), champagne gold (rules), warm greys
INK, BRAND, MUTED, LINE, SOFT, GOLD = (colors.HexColor(x) for x in ("#101c3d", "#1d3f91", "#5a647f", "#ddd8cb", "#f5f3ed", "#c19a45"))
LOGO = Path(__file__).resolve().parent.parent / "assets" / "ieml-logo.png"
FONTS = Path(__file__).resolve().parent.parent / "assets" / "fonts"


def _register() -> tuple[str, str, str]:
    try:  # DejaVu covers Hindi-name transliterations, accents and symbols that the built-in fonts do not
        pdfmetrics.registerFont(TTFont("DV", str(FONTS / "DejaVuSans.ttf")))
        pdfmetrics.registerFont(TTFont("DV-B", str(FONTS / "DejaVuSans-Bold.ttf")))
        pdfmetrics.registerFont(TTFont("DV-I", str(FONTS / "DejaVuSans-Oblique.ttf")))
        pdfmetrics.registerFontFamily("DV", normal="DV", bold="DV-B", italic="DV-I", boldItalic="DV-B")
        return "DV", "DV-B", "DV-I"
    except Exception:  # fonts missing -> built-in Helvetica keeps exports working
        return "Helvetica", "Helvetica-Bold", "Helvetica-Oblique"


F, FB, FI = _register()


def st(name: str, **kw) -> ParagraphStyle:
    base = dict(fontName=F, fontSize=9.5, leading=13.5, textColor=INK, alignment=TA_LEFT)
    base.update(kw)
    return ParagraphStyle(name, **base)


S = {
    "title": st("title", fontName=FB, fontSize=22, leading=27),
    "sub": st("sub", fontSize=10.5, leading=15, textColor=MUTED),
    "day": st("day", fontName=FB, fontSize=14, leading=18, textColor=colors.white),
    "meta": st("meta", fontName=FB, fontSize=8.5, leading=12, textColor=BRAND),
    "h": st("h", fontName=FB, fontSize=11.5, leading=15),
    "h2": st("h2", fontName=FB, fontSize=12, leading=16, spaceBefore=10, spaceAfter=4),
    "body": st("body"),
    "small": st("small", fontSize=8.5, leading=12, textColor=MUTED),
    "bullet": st("bullet", leftIndent=12, bulletIndent=2, leading=13),
    "cell": st("cell", fontSize=8.8, leading=12),
    "cellb": st("cellb", fontName=FB, fontSize=8.8, leading=12),
    "th": st("th", fontName=FB, fontSize=8.3, leading=11, textColor=colors.white),
}


def P(text, style="body") -> Paragraph:
    """Paragraph from plain text: escapes markup and keeps line breaks."""
    s = escape(str(text or "")).replace("\r", "").replace("\n", "<br/>")
    return Paragraph(s, S[style] if isinstance(style, str) else style)


def rich(markup: str, style="body") -> Paragraph:
    return Paragraph(markup, S[style] if isinstance(style, str) else style)


def esc(t) -> str:
    return escape(str(t or ""))


def photo_flowable(data: bytes | None, size: float = 22 * mm):
    if not data:
        return None
    try:
        img = Image(io.BytesIO(data), width=size, height=size, kind="proportional")
        img.hAlign = "LEFT"
        return img
    except Exception:
        return None


def initials_flowable(name: str, size: float = 22 * mm):
    """Round initials badge, used when a speaker has no photo."""
    from reportlab.graphics.shapes import Circle, Drawing, String
    words = [w for w in name.replace(".", " ").split() if w.lower() not in {"dr", "prof", "mr", "mrs", "ms", "shri", "smt"}]
    ini = ((words[0][0] + (words[-1][0] if len(words) > 1 else "")) if words else "?").upper()
    d = Drawing(size, size)
    d.add(Circle(size / 2, size / 2, size / 2, fillColor=colors.HexColor("#e4eaf8"), strokeColor=None))
    d.add(String(size / 2, size / 2 - size * 0.13, ini, fontName=FB, fontSize=size * 0.36, fillColor=BRAND, textAnchor="middle"))
    d.hAlign = "LEFT"
    return d


def build(story: list, title: str, left: str, right: str = "") -> bytes:
    """Renders A4 with a running header/footer and page numbers."""
    buf = io.BytesIO()
    doc = BaseDocTemplate(buf, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=20 * mm,
                          bottomMargin=18 * mm, title=title, author="India Exposition Mart Ltd.")

    def deco(c, d):
        c.saveState()
        w, h = A4
        c.setStrokeColor(LINE)
        c.setLineWidth(0.5)
        c.line(18 * mm, h - 14 * mm, w - 18 * mm, h - 14 * mm)
        c.setStrokeColor(GOLD)
        c.setLineWidth(1.4)
        c.line(18 * mm, h - 14 * mm, 18 * mm + 26 * mm, h - 14 * mm)
        x0 = 18 * mm
        try:
            c.drawImage(str(LOGO), x0, h - 13 * mm, width=7.2 * mm, height=9 * mm, mask="auto", preserveAspectRatio=True)
            x0 += 10 * mm
        except Exception:
            pass
        c.setFont(F, 7.8)
        c.setFillColor(MUTED)
        c.drawString(x0, h - 11.5 * mm, left[:90])
        if right:
            c.drawRightString(w - 18 * mm, h - 11.5 * mm, right[:60])
        c.line(18 * mm, 13 * mm, w - 18 * mm, 13 * mm)
        c.drawString(18 * mm, 9 * mm, title[:90])
        c.drawRightString(w - 18 * mm, 9 * mm, f"Page {d.page}")
        c.restoreState()

    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="f", leftPadding=0, rightPadding=0,
                  topPadding=0, bottomPadding=0)
    doc.addPageTemplates([PageTemplate(id="p", frames=[frame], onPage=deco)])
    doc.build(story)
    return buf.getvalue()


def banner(text: str, width: float) -> Table:
    t = Table([[Paragraph(escape(text), S["day"])]], colWidths=[width])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), INK), ("LEFTPADDING", (0, 0), (-1, -1), 10),
                           ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 7)]))
    return t


def grid(rows: list[list], widths: list[float], head: bool = True) -> Table:
    t = Table(rows, colWidths=widths, repeatRows=1 if head else 0)
    style = [("VALIGN", (0, 0), (-1, -1), "TOP"), ("LINEBELOW", (0, 0), (-1, -1), 0.4, LINE),
             ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
             ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5)]
    if head:
        style += [("BACKGROUND", (0, 0), (-1, 0), BRAND)]
    t.setStyle(TableStyle(style))
    return t


__all__ = ["P", "rich", "esc", "S", "build", "banner", "grid", "photo_flowable", "initials_flowable", "Spacer", "KeepTogether",
           "CondPageBreak", "HRFlowable", "Table", "TableStyle", "Paragraph", "A4", "mm", "colors", "INK", "BRAND", "GOLD",
           "MUTED", "LINE", "SOFT", "F", "FB"]