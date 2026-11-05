"""Compatibility re-export; the cached reader now lives in the shared web_components library."""

from web_components.static_text import clear_static_text_cache, read_static_text

__all__ = ["clear_static_text_cache", "read_static_text"]
