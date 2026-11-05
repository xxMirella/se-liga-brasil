"""Design tokens and component styles, served together as the base of every page."""

from pathlib import Path

from web_components.static_text import read_static_text

ASSET_DIRECTORY = Path(__file__).parent / "assets"
STYLESHEET_PARTS = (
    "fonts.css", "design-tokens.css", "design-system.css",
    "majority-components.css", "majority-components-timeline.css",
    "majority-components-period.css", "motion.css",
    "people-search-filters.css", "people-search-results.css",
    "profile-identity.css", "profile-career-attendance.css", "profile-activity.css",
    "profile-assets.css",
)


def design_system_stylesheet():
    return "\n".join(
        read_static_text(ASSET_DIRECTORY / name) for name in STYLESHEET_PARTS
    )
