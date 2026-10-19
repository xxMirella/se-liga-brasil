"""Bind the ALESP-specific functions to the reusable source pipeline."""

from crawlers.alesp.discovery import discover_resources, is_selected_resource
from crawlers.alesp.validator import validate_resource


class AlespCrawlerAdapter:
    discover_resources = staticmethod(discover_resources)
    is_selected_resource = staticmethod(is_selected_resource)
    validate_resource = staticmethod(validate_resource)
