"""Currency conversion with the European Central Bank's daily reference rates.

Google picks the display currency from the visitor's location when dates are
set, so prices can come back in a different currency than requested. We keep
the original values and add converted ones.
"""

from __future__ import annotations

import re

import httpx

ECB_URL = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml"
_DATE_RE = re.compile(r"time=['\"](\d{4}-\d{2}-\d{2})['\"]")
_RATE_RE = re.compile(r"currency=['\"]([A-Z]{3})['\"]\s+rate=['\"]([\d.]+)['\"]")


class Rates:
    def __init__(self, per_eur: dict[str, float], as_of: str | None):
        self.per_eur = {"EUR": 1.0, **per_eur}
        self.as_of = as_of

    def supports(self, code: str | None) -> bool:
        return bool(code) and code in self.per_eur

    def convert(self, amount: float | None, source: str | None, target: str) -> float | None:
        if amount is None or not self.supports(source) or not self.supports(target):
            return None
        return round(amount / self.per_eur[source] * self.per_eur[target], 2)


def parse_ecb(xml: str) -> Rates:
    date = _DATE_RE.search(xml)
    rates = {code: float(rate) for code, rate in _RATE_RE.findall(xml)}
    return Rates(rates, date.group(1) if date else None)


async def fetch_rates() -> Rates:
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(ECB_URL)
        response.raise_for_status()
    return parse_ecb(response.text)
