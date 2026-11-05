"""Reusable, script-free HTML components of the public portal (header, footer, cards, tabs...)."""

from web_components.bloc_legend import render_bloc_legend, render_bloc_swatch
from web_components.choice_links import ChoiceLink, render_choice_links
from web_components.column_chart import ChartColumn, render_column_chart
from web_components.dot_grid import render_dot_grid
from web_components.elements import (
    render_card,
    render_card_grid,
    render_chip,
    render_disclosure,
    render_eyebrow,
    render_hero,
    render_link_button,
    render_notice,
    render_section,
    render_segmented_links,
    render_tab_links,
)
from web_components.fonts import (
    FONT_CONTENT_TYPE,
    FONT_URL_PREFIX,
    font_file_names,
    read_font_file,
)
from web_components.page_shell import SCROLL_REVEAL_SCRIPT, render_page
from web_components.parliament_chart import SeatGroup, render_parliament_chart, seat_fills
from web_components.parliament_layout import (
    SeatPosition,
    canvas_point,
    parliament_seat_positions,
)
from web_components.site_footer import render_site_footer
from web_components.site_header import render_site_header
from web_components.stacked_bar import BarSegment, bloc_class_suffix, render_stacked_bar
from web_components.stylesheet import design_system_stylesheet

__all__ = [
    "SeatGroup", "render_parliament_chart", "seat_fills", "SeatPosition", "canvas_point",
    "parliament_seat_positions",
    "ChoiceLink", "render_choice_links", "ChartColumn", "render_column_chart",
    "render_dot_grid", "render_bloc_legend", "render_bloc_swatch",
    "BarSegment", "bloc_class_suffix", "render_stacked_bar",
    "FONT_CONTENT_TYPE", "FONT_URL_PREFIX", "font_file_names", "read_font_file",
    "design_system_stylesheet", "render_card",
    "render_card_grid", "render_chip",
    "render_disclosure", "render_eyebrow", "render_hero", "render_link_button", "render_notice",
    "SCROLL_REVEAL_SCRIPT",
    "render_page", "render_section", "render_segmented_links", "render_site_footer",
    "render_site_header", "render_tab_links",
]
