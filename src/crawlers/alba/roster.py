"""Current Bahia roster on the official portal linked by ALBA since2025."""

from crawlers.nopapercloud.roster import parse_current_roster as parse_nopaper


def parse_current_roster(payload):
    return parse_nopaper(payload, "https://albalegis.nopapercloud.com.br/spl/", 63)
