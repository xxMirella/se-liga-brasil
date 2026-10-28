"""Current Sergipe roster, excluding the separate group of former active mandates."""

from crawlers.nopapercloud.roster import parse_current_roster as parse_nopaper


def parse_current_roster(payload):
    return parse_nopaper(payload, "https://aleselegis.al.se.leg.br/spl/", 24)
