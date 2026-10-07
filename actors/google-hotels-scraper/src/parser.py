"""Parse hotel cards out of a Google Travel hotel search results page.

The page is server-rendered HTML. Every hotel card starts with an <h2> whose
class contains "BgYkof"; the card's data (prices, rating, amenities) follows it
until the next card's <h2>. Accessible labels (aria-label) carry most values in
a stable, human-readable form, so we read those instead of obfuscated classes.
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass, field

GOOGLE_BASE = "https://www.google.com"

_H2_RE = re.compile(r'<h2 [^>]*class="[^"]*BgYkof[^"]*"[^>]*>(.*?)</h2>', re.S)
_TAG_RE = re.compile(r"<[^>]+>")
_SCRIPT_RE = re.compile(r"<(script|style)\b.*?</\1>", re.S | re.I)
_WS_RE = re.compile(r"\s+")

# Longest prefixes first so "CA$" wins over "$".
_CURRENCY_PREFIXES = [
    ("CA$", "CAD"), ("A$", "AUD"), ("NZ$", "NZD"), ("HK$", "HKD"), ("MX$", "MXN"),
    ("R$", "BRL"), ("S$", "SGD"), ("JP¥", "JPY"), ("CN¥", "CNY"), ("US$", "USD"),
    ("$", "USD"), ("€", "EUR"), ("£", "GBP"), ("¥", "JPY"), ("₹", "INR"),
    ("₩", "KRW"), ("₺", "TRY"), ("₪", "ILS"), ("฿", "THB"), ("CHF", "CHF"),
    ("zł", "PLN"), ("kr", "SEK"), ("Kč", "CZK"),
]

_MONEY = r"((?:[A-Z]{0,3}[$€£¥₹₩₺₪฿]|CHF\s?)\d(?:[\d.,]*\d)?)"
_NIGHTLY_RE = re.compile(_MONEY + r"\s+nightly")
_TOTAL_RE = re.compile(_MONEY + r"\s+total")
_NIGHTS_RE = re.compile(r"(\d+)\s+nights?\s+with taxes")
_START_PRICE_RE = re.compile(r"^Prices starting from\s+" + _MONEY)
_RATING_RE = re.compile(r"^([\d.]+) out of 5 stars from ([\d,]+) reviews?")
_DIST_RE = re.compile(r"^([1-5])-star reviews (\d+) percent")
_DEAL_RE = re.compile(r"\b(GREAT DEAL|DEAL)\b.*?(\d+)% less than usual")
_CLASS_RE = re.compile(r"\b([1-5])-star hotel\b")
_ENTITY_RE = re.compile(r'href="(/travel/hotels/entity/[^"?]+)')
# Hotel photos; excludes reviewer avatars served from /a/.
_IMG_RE = re.compile(r'src="(https://lh\d\.googleusercontent\.com/(?!a/)[^"]+)"')
_AMENITIES_RE = re.compile(r"Amenities for [^:]{1,200}: ((?:[^,]{1,60}, )+)")
_LABEL_RE = re.compile(r'aria-label="([^"]*)"')


@dataclass
class Hotel:
    name: str
    position: int
    googleHotelId: str | None = None
    url: str | None = None
    pricePerNight: float | None = None
    totalPrice: float | None = None
    nights: int | None = None
    currency: str | None = None
    priceText: str | None = None
    rating: float | None = None
    reviewCount: int | None = None
    ratingDistribution: dict[str, int] = field(default_factory=dict)
    hotelClass: int | None = None
    deal: str | None = None
    dealPercentBelowUsual: int | None = None
    amenities: list[str] = field(default_factory=list)
    ecoCertified: bool = False
    imageUrl: str | None = None


def _text(fragment: str) -> str:
    fragment = _SCRIPT_RE.sub(" ", fragment)
    return _WS_RE.sub(" ", html.unescape(_TAG_RE.sub(" ", fragment))).strip()


def parse_money(value: str) -> tuple[float | None, str | None]:
    """'$1,104' -> (1104.0, 'USD'); '€54' -> (54.0, 'EUR')."""
    value = value.strip()
    currency = None
    for prefix, code in _CURRENCY_PREFIXES:
        if value.startswith(prefix):
            currency = code
            value = value[len(prefix):].strip()
            break
    digits = value.replace(",", "")
    try:
        return float(digits), currency
    except ValueError:
        return None, currency


def is_blocked(page: str) -> bool:
    """True when Google served a captcha/'unusual traffic' page instead of results."""
    return "/sorry/index" in page or "detected unusual traffic" in page


def parse_hotels(page: str) -> list[Hotel]:
    starts = [(m.start(), m.end(), _text(m.group(1))) for m in _H2_RE.finditer(page)]
    hotels: list[Hotel] = []
    for i, (start, end, name) in enumerate(starts):
        if not name:
            continue
        stop = starts[i + 1][0] if i + 1 < len(starts) else min(len(page), end + 40_000)
        card = page[end:stop]
        # The card's link (with the hotel id) is rendered just before its <h2>.
        lead = page[max(0, start - 4_000):start]
        hotel = Hotel(name=name, position=len(hotels) + 1)

        # Closest match before the <h2> belongs to this card; fall back to the card body.
        lead_ids, card_ids = _ENTITY_RE.findall(lead), _ENTITY_RE.findall(card)
        path = lead_ids[-1] if lead_ids else (card_ids[0] if card_ids else None)
        if path:
            hotel.googleHotelId = path.rsplit("/", 1)[-1]
            hotel.url = GOOGLE_BASE + path

        lead_imgs, card_imgs = _IMG_RE.findall(lead), _IMG_RE.findall(card)
        image = lead_imgs[-1] if lead_imgs else (card_imgs[0] if card_imgs else None)
        if image:
            hotel.imageUrl = html.unescape(image)

        for raw in _LABEL_RE.findall(card):
            label = html.unescape(raw)
            if m := _START_PRICE_RE.match(label):
                if hotel.priceText is None:
                    hotel.priceText = m.group(1)
            elif m := _RATING_RE.match(label):
                if hotel.rating is None:
                    hotel.rating = float(m.group(1))
                    hotel.reviewCount = int(m.group(2).replace(",", ""))
            elif m := _DIST_RE.match(label):
                hotel.ratingDistribution.setdefault(m.group(1), int(m.group(2)))

        text = _text(card)
        if m := _NIGHTLY_RE.search(text):
            hotel.pricePerNight, hotel.currency = parse_money(m.group(1))
        if m := _TOTAL_RE.search(text):
            total, currency = parse_money(m.group(1))
            hotel.totalPrice = total
            hotel.currency = hotel.currency or currency
        if m := _NIGHTS_RE.search(text):
            hotel.nights = int(m.group(1))
        if hotel.pricePerNight is None and hotel.priceText:
            hotel.pricePerNight, hotel.currency = parse_money(hotel.priceText)
        if m := _AMENITIES_RE.search(text):
            hotel.amenities = [a.strip() for a in m.group(1).split(",") if a.strip()]
        if m := _DEAL_RE.search(text):
            hotel.deal = m.group(1)
            hotel.dealPercentBelowUsual = int(m.group(2))
        if m := _CLASS_RE.search(text):
            hotel.hotelClass = int(m.group(1))
        hotel.ecoCertified = "Eco-certified" in text

        hotels.append(hotel)
    return hotels
