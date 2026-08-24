"""
Pluggable PDF rendering (Phase 1.31).

A single ``render_pdf(document)`` entry point dispatches on ``settings.NEXUS_PDF_BACKEND``:

  - ``reportlab`` (default) — pure-Python, no system libraries; works everywhere.
  - ``weasyprint`` — HTML/CSS → PDF; requires the GTK/pango/cairo runtime on the host
    (lazy-imported so the default path never touches it).

``document`` shape (backend-agnostic)::

    {
      "title": str, "subtitle": str, "watermark": str,
      "metrics": [{"label": str, "value": str}],
      "tables":  [{"title": str, "columns": [{"key","label"}], "rows": [ {...} ]}],
    }
"""
from __future__ import annotations

import html
import io

from django.conf import settings

MAX_PDF_ROWS = 1000  # bound table size so a PDF never balloons; surfaced to the caller


def render_pdf(document: dict) -> bytes:
    backend = getattr(settings, "NEXUS_PDF_BACKEND", "reportlab")
    if backend == "weasyprint":
        return _render_weasyprint(document)
    return _render_reportlab(document)


def _cell(value) -> str:
    return "" if value is None else str(value)


# ── reportlab backend ─────────────────────────────────────────────────────────
def _render_reportlab(document: dict) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )

    watermark = document.get("watermark") or ""

    def _on_page(canvas, doc):
        if not watermark:
            return
        canvas.saveState()
        canvas.setFont("Helvetica-Bold", 48)
        canvas.setFillColor(colors.Color(0.6, 0.6, 0.6, alpha=0.12))
        canvas.translate(doc.pagesize[0] / 2, doc.pagesize[1] / 2)
        canvas.rotate(45)
        canvas.drawCentredString(0, 0, watermark)
        canvas.restoreState()

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(A4),
                            leftMargin=15 * mm, rightMargin=15 * mm,
                            topMargin=15 * mm, bottomMargin=15 * mm)
    styles = getSampleStyleSheet()
    story = []
    if document.get("title"):
        story.append(Paragraph(html.escape(str(document["title"])), styles["Title"]))
    if document.get("subtitle"):
        story.append(Paragraph(html.escape(str(document["subtitle"])), styles["Normal"]))
    story.append(Spacer(1, 6 * mm))

    metrics = document.get("metrics") or []
    if metrics:
        data = [[Paragraph(f"<b>{html.escape(_cell(m.get('value')))}</b>", styles["Normal"]),
                 Paragraph(html.escape(_cell(m.get("label"))), styles["Normal"])]
                for m in metrics]
        t = Table(data, hAlign="LEFT")
        t.setStyle(TableStyle([
            ("BOX", (0, 0), (-1, -1), 0.5, colors.grey),
            ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]))
        story.append(t)
        story.append(Spacer(1, 6 * mm))

    for table in document.get("tables") or []:
        if table.get("title"):
            story.append(Paragraph(html.escape(str(table["title"])), styles["Heading2"]))
        columns = table.get("columns") or []
        keys = [c["key"] for c in columns]
        header = [c.get("label", c["key"]) for c in columns]
        rows = (table.get("rows") or [])[:MAX_PDF_ROWS]
        body = [header] + [[_cell(r.get(k)) for k in keys] for r in rows]
        if not columns:
            story.append(Paragraph("(no columns)", styles["Italic"]))
            continue
        tbl = Table(body, repeatRows=1)
        tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#6366f1")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
        ]))
        story.append(tbl)
        if len(table.get("rows") or []) > MAX_PDF_ROWS:
            story.append(Paragraph(
                f"<i>Showing first {MAX_PDF_ROWS} of {len(table['rows'])} rows.</i>",
                styles["Italic"]))
        story.append(Spacer(1, 6 * mm))

    doc.build(story, onFirstPage=_on_page, onLaterPages=_on_page)
    return buf.getvalue()


# ── weasyprint backend (HTML/CSS) ─────────────────────────────────────────────
def _render_weasyprint(document: dict) -> bytes:
    from weasyprint import HTML  # lazy: needs the GTK/pango/cairo runtime

    parts = ["<html><head><meta charset='utf-8'><style>",
             "body{font-family:sans-serif;font-size:10px}",
             "h1{font-size:20px} h2{font-size:14px}",
             "table{border-collapse:collapse;width:100%;margin-bottom:12px}",
             "th{background:#6366f1;color:#fff;padding:4px;text-align:left}",
             "td{border:1px solid #e2e8f0;padding:4px}",
             ".wm{position:fixed;top:40%;left:20%;font-size:48px;color:rgba(150,150,150,0.12);"
             "transform:rotate(-45deg)}",
             "</style></head><body>"]
    if document.get("watermark"):
        parts.append(f"<div class='wm'>{html.escape(str(document['watermark']))}</div>")
    if document.get("title"):
        parts.append(f"<h1>{html.escape(str(document['title']))}</h1>")
    if document.get("subtitle"):
        parts.append(f"<p>{html.escape(str(document['subtitle']))}</p>")
    for m in document.get("metrics") or []:
        parts.append(f"<p><b>{html.escape(_cell(m.get('value')))}</b> "
                     f"{html.escape(_cell(m.get('label')))}</p>")
    for table in document.get("tables") or []:
        if table.get("title"):
            parts.append(f"<h2>{html.escape(str(table['title']))}</h2>")
        columns = table.get("columns") or []
        keys = [c["key"] for c in columns]
        parts.append("<table><thead><tr>")
        parts.extend(f"<th>{html.escape(c.get('label', c['key']))}</th>" for c in columns)
        parts.append("</tr></thead><tbody>")
        for r in (table.get("rows") or [])[:MAX_PDF_ROWS]:
            parts.append("<tr>")
            parts.extend(f"<td>{html.escape(_cell(r.get(k)))}</td>" for k in keys)
            parts.append("</tr>")
        parts.append("</tbody></table>")
    parts.append("</body></html>")
    return HTML(string="".join(parts)).write_pdf()
