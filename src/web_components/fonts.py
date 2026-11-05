"""Self-hosted font files; only names in the allow-list are ever read from disk."""

from pathlib import Path

FONT_URL_PREFIX = "/assets/fonts/"
FONT_DIRECTORY = Path(__file__).parent / "assets" / "fonts"
FONT_CONTENT_TYPE = "font/woff2"


def font_file_names():
    return sorted(path.name for path in FONT_DIRECTORY.glob("*.woff2"))


def read_font_file(request_path):
    """Return the font bytes for `/assets/fonts/<name>.woff2`, or None for any other path."""
    name = request_path.removeprefix(FONT_URL_PREFIX)
    if not request_path.startswith(FONT_URL_PREFIX) or name not in font_file_names():
        return None
    return (FONT_DIRECTORY / name).read_bytes()
