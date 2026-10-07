"""Build Google Travel hotel search URLs from actor input."""

from __future__ import annotations

from datetime import date
from urllib.parse import urlencode

SEARCH_URL = "https://www.google.com/travel/search"


def _spoken(d: date) -> str:
    # Google's query parser reliably understands "November 12, 2026".
    return f"{d.strftime('%B')} {d.day}, {d.year}"


def build_query(location: str, check_in: date | None, check_out: date | None, adults: int) -> str:
    query = f"hotels in {location.strip()}"
    if check_in and check_out:
        query += f" {_spoken(check_in)} to {_spoken(check_out)}"
    if adults and adults != 2:
        query += f" for {adults} adults"
    return query


def build_url(query: str, country: str) -> str:
    # English UI keeps the labels the parser reads stable; the country drives the currency.
    return f"{SEARCH_URL}?{urlencode({'q': query, 'hl': 'en', 'gl': country.lower()})}"
