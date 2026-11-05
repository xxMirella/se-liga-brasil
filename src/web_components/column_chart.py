"""Column chart whose columns are links. Heights use classes (tens + ones), never inline style."""

from dataclasses import dataclass

from web_components.escaping import escape_text
from web_components.stacked_bar import bloc_class_suffix


@dataclass(frozen=True)
class ChartColumn:
    bloc_key: str  # color class of the bar
    percent: float  # 0-100; drawn at 1% resolution
    value_text: str  # printed above the bar
    axis_label: str  # printed below the axis
    aria_label: str
    url: str
    selected: bool = False


def percent_height_classes(percent):
    """`37.4` -> `ds-pct-tens-3 ds-pct-ones-7`; the CSS sums both parts into a height."""
    rounded = min(100, max(0, int(percent + 0.5)))
    tens, ones = divmod(rounded, 10)
    return f"ds-pct-tens-{tens} ds-pct-ones-{ones}"


def _render_column(column):
    current = ' aria-current="true"' if column.selected else ""
    bar_classes = f"ds-column-chart__bar ds-bloc--{bloc_class_suffix(column.bloc_key)} "
    return (
        f'<a class="ds-column-chart__column" href="{escape_text(column.url)}" '
        f'aria-label="{escape_text(column.aria_label)}"{current}>'
        f'<span class="ds-column-chart__value">{escape_text(column.value_text)}</span>'
        f'<span class="{bar_classes}{percent_height_classes(column.percent)}"></span></a>'
    )


def render_column_chart(title, columns, *, half_label="metade"):
    """Dashed line at 50% labeled `half_label`; columns share the plot width equally."""
    plot = "".join(_render_column(column) for column in columns)
    axis = "".join(
        f"<span>{escape_text(column.axis_label)}</span>" for column in columns
    )
    return (
        f'<figure class="ds-column-chart"><figcaption class="ds-column-chart__title">'
        f"{escape_text(title)}</figcaption>"
        f'<div class="ds-column-chart__plot">{plot}'
        f'<span class="ds-column-chart__half" aria-hidden="true">{escape_text(half_label)}</span>'
        f'</div><div class="ds-column-chart__axis" aria-hidden="true">{axis}</div></figure>'
    )
