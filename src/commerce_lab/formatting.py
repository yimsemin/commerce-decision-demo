"""Display formatting shared by the app and the lens modules (kept here,
not in `app/`, so lenses can use it without depending on the app package)."""

from __future__ import annotations


def format_pct(value) -> str:
    if value is None:
        return "n/a"
    return f"{value:+.1f}%"


def format_currency(value) -> str:
    if value is None:
        return "n/a"
    sign = "-" if value < 0 else ""
    return f"{sign}${abs(value):,.0f}"


def signed_pct(value) -> str:
    return f"{value:+.1f}%" if value is not None else "n/a"


def number(value, digits: int = 0) -> str:
    return f"{value:,.{digits}f}" if value is not None else "n/a"
