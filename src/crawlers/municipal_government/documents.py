"""Read immutable official HTML/PDF/JSON evidence locally with bounded subprocess execution."""

import subprocess

from parsing.html import decode_html
from parsing.visible_text import extract_visible_text


def document_text(artifact):
    payload = artifact.path.read_bytes()
    if payload.startswith(b"%PDF"):
        result = subprocess.run(
            ["pdftotext", "-raw", str(artifact.path), "-"],
            check=True,
            capture_output=True,
            timeout=30,
        )
        return result.stdout.decode("utf-8")
    text = extract_visible_text(decode_html(payload))
    if any(marker in text.lower() for marker in ("access denied", "incapsula incident")):
        raise ValueError("MUNICIPAL_GOVERNMENT_SOURCE_ACCESS_BLOCKED")
    return text
