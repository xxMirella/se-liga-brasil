"""Compatibility imports; assessment rules belong to the completeness service."""

from service.completeness.rules import (
    REQUIRED_FIELDS,
    build_completeness_report,
    evaluate_person_completeness,
)

__all__ = ["REQUIRED_FIELDS", "build_completeness_report", "evaluate_person_completeness"]
