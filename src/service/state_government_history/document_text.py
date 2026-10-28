"""Extract bounded local archived documents without following links or executing contents."""

import subprocess

from crawlers.state_government.parsing import visible_text


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
    text = visible_text(payload)
    if any(marker in text.lower() for marker in ("incapsula incident", "access denied")):
        raise ValueError("STATE_GOVERNMENT_SOURCE_ACCESS_BLOCKED")
    return text
