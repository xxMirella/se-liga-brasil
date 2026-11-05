"""The /panorama page: opening, timeline, selected period and reading notes, in that order."""

from service.majority_panorama.opening_section import render_opening_section
from service.majority_panorama.period_section import render_period_section
from service.majority_panorama.reading_section import render_reading_section
from service.majority_panorama.timeline_section import render_timeline_section
from web_components import SCROLL_REVEAL_SCRIPT, render_page

PAGE_TITLE = "Panorama político"
ENHANCEMENT_SCRIPT = "/assets/panorama-enhance.js"


def render_majority_panorama(panorama, state):
    sections = (
        render_opening_section(panorama, state),
        render_timeline_section(panorama, state),
        render_period_section(panorama, state),
        render_reading_section(panorama, state),
    )
    return render_page(
        PAGE_TITLE, f'<div class="ds-container ds-majority">{"".join(sections)}</div>',
        active_section="panorama", scripts=(SCROLL_REVEAL_SCRIPT, ENHANCEMENT_SCRIPT),
    )
