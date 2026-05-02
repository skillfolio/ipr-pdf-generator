"""
IPR PDF Generation Service v1
POST /generate  →  returns .pdf binary
POST /debug     →  echoes received body
GET  /health    →  liveness

Body: { "html": "<html>...</html>", "title": "ИПР_Иванов" }
Auth: X-API-Key header (env API_KEY); if env unset, auth is disabled.
"""

import io
import json
import logging
import os
import re

from flask import Flask, jsonify, request, send_file

from html_to_pdf import html_to_pdf_bytes

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024  # 10 MB

API_KEY = os.environ.get("API_KEY")
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
PAYLOAD_PREVIEW_CHARS = int(os.environ.get("PAYLOAD_PREVIEW_CHARS", "1200"))
LOG_FULL_PAYLOAD = os.environ.get("LOG_FULL_PAYLOAD", "").lower() == "true"

log_level = getattr(logging, LOG_LEVEL, logging.INFO)
gunicorn_logger = logging.getLogger("gunicorn.error")

if gunicorn_logger.handlers:
    app.logger.handlers = gunicorn_logger.handlers
else:
    logging.basicConfig(level=log_level)

app.logger.setLevel(log_level)
logging.getLogger().setLevel(log_level)


def preview_text(value, limit=PAYLOAD_PREVIEW_CHARS):
    value = value or ""
    if LOG_FULL_PAYLOAD or len(value) <= limit:
        return value
    return f"{value[:limit]}... [truncated, total={len(value)} chars]"


def preview_payload(payload):
    if isinstance(payload, str):
        return preview_text(payload)
    try:
        rendered = json.dumps(payload, ensure_ascii=False)
    except TypeError:
        rendered = repr(payload)
    return preview_text(rendered)


def prepare_html(html: str) -> str:
    """Strip <head>/<style>/<script> if no <body>; otherwise keep body content
    and unwrap a single root <div> wrapper (matches ipr-service behaviour)."""
    body_match = re.search(r"<body[^>]*>(.*?)</body>", html, re.DOTALL | re.IGNORECASE)
    content = body_match.group(1) if body_match else html

    if not body_match:
        content = re.sub(r"<head[^>]*>.*?</head>", "", content, flags=re.DOTALL | re.IGNORECASE)
        content = re.sub(r"<script[^>]*>.*?</script>", "", content, flags=re.DOTALL | re.IGNORECASE)

    # Unlike DOCX path, we KEEP <style> blocks for PDF — WeasyPrint honours them.

    return f"<html><head><meta charset='utf-8'></head><body>{content}</body></html>"


def check_auth():
    if not API_KEY:
        return True
    return request.headers.get("X-API-Key") == API_KEY


def safe_filename(name: str, fallback: str = "ipr") -> str:
    cleaned = "".join(c if c.isalnum() or c in " _-" else "_" for c in name).strip()
    return cleaned or fallback


@app.before_request
def log_request_started():
    app.logger.info(
        "HTTP request started method=%s path=%s content_type=%s content_length=%s remote_addr=%s",
        request.method,
        request.path,
        request.content_type,
        request.content_length,
        request.headers.get("X-Forwarded-For", request.remote_addr),
    )


@app.after_request
def log_request_finished(response):
    app.logger.info(
        "HTTP request finished method=%s path=%s status=%s content_length=%s",
        request.method,
        request.path,
        response.status_code,
        response.calculate_content_length(),
    )
    return response


@app.get("/health")
def health():
    return jsonify({"status": "ok", "version": "1.0-pdf"})


@app.post("/debug")
def debug():
    return jsonify({
        "content_type": request.content_type,
        "is_json": request.is_json,
        "body_raw_length": len(request.data),
        "body_parsed": request.get_json(silent=True),
    })


@app.post("/generate")
def generate():
    if not check_auth():
        return jsonify({"error": "Unauthorized"}), 401

    if not request.is_json:
        return jsonify({"error": "Content-Type must be application/json"}), 400

    data = request.get_json(silent=True)
    if data is None:
        return jsonify({"error": "Invalid JSON body"}), 400

    if not isinstance(data, dict) or not data.get("html"):
        return jsonify({"error": "Body must contain 'html' field"}), 400

    html_content = data["html"]
    title = data.get("title") or "ipr"

    app.logger.info(
        "Received /generate request title=%s html_chars=%s preview=%s",
        title,
        len(html_content),
        preview_payload(html_content),
    )

    try:
        pdf_bytes = html_to_pdf_bytes(prepare_html(html_content))
    except Exception as exc:
        app.logger.exception("HTML→PDF failed: %s", exc)
        return jsonify({"error": str(exc)}), 500

    filename = f"{safe_filename(title)}.pdf"
    app.logger.info(
        "Generated PDF filename=%s title=%s size_bytes=%s",
        filename,
        title,
        len(pdf_bytes),
    )

    return send_file(
        io.BytesIO(pdf_bytes),
        mimetype="application/pdf",
        as_attachment=True,
        download_name=filename,
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=False)
