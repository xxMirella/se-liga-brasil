"""HTML escaping for component arguments; the library never trusts caller-provided text."""

from html import escape


def escape_text(value):
    return escape(str(value), quote=True)
