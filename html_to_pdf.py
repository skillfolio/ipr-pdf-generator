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
