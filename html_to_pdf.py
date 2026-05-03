"""
html_to_pdf.py — HTML → PDF via WeasyPrint.

Adds @page CSS (A4, 2 cm margins, page number bottom-right) and a font
fallback that prevents Noto Emoji from breaking digit kerning inside URLs
and numeric runs.
"""

from __future__ import annotations

import io

from weasyprint import HTML, CSS
from weasyprint.text.fonts import FontConfiguration


# ── Page styling ──────────────────────────────────────────────────────────────

_PAGE_CSS = """
@page {
    size: A4;
    margin: 2cm;

    @bottom-right {
        content: counter(page) " / " counter(pages);
        font-family: "DejaVu Sans", "Liberation Sans", sans-serif;
        font-size: 9pt;
        color: #6B7280;
    }
}

/* Force WeasyPrint to render all colours and backgrounds from HTML styles. */
* {
    -webkit-print-color-adjust: exact !important;
    print-color-adjust: exact !important;
    color-adjust: exact !important;
}

/* Default body typography matches n8n template (Calibri-like fallback). */
body {
    font-family: "DejaVu Sans", "Liberation Sans", "Calibri", Arial, sans-serif;
    color: #1A1A1A;
}

/* Prevent emoji font from polluting digit/URL kerning — known WeasyPrint
   issue when Noto Color Emoji is in the fallback chain. */
a, code, .num, span.num, td, th {
    font-variant-numeric: tabular-nums;
}
a {
    font-family: "DejaVu Sans", "Liberation Sans", sans-serif !important;
    word-break: break-all;
}

/* Tables — keep header rows when paginating. */
thead { display: table-header-group; }
tr, td, th { page-break-inside: avoid; }

/* overflow-x:auto from the HTML template has no effect in PDF —
   constrain tables to page width instead. */
.table-wrap { overflow: visible !important; }
table {
    max-width: 100% !important;
    table-layout: fixed !important;
}
td, th {
    word-break: break-word !important;
    overflow-wrap: anywhere !important;
}

/* Shrink font for tables with many columns to prevent right-side clipping. */
.md-table.wide { font-size: 10px; }
.md-table.wide td, .md-table.wide th { padding: 4px 5px; }

/* Headings should not be orphaned at bottom of a page. */
h1, h2, h3, h4 { page-break-after: avoid; }
"""


_font_config = FontConfiguration()
_base_css = CSS(string=_PAGE_CSS, font_config=_font_config)


def html_to_pdf_bytes(html: str, base_url: str | None = None) -> bytes:
    """Render HTML string to PDF bytes."""
    pdf_buf = io.BytesIO()
    HTML(string=html, base_url=base_url).write_pdf(
        pdf_buf,
        stylesheets=[_base_css],
        font_config=_font_config,
    )
    return pdf_buf.getvalue()
