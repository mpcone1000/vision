import gzip
from datetime import date
from pathlib import Path

from src.parser import is_blocked, parse_hotels, parse_money
from src.query import build_query, build_url

FIXTURES = Path(__file__).parent / "fixtures"


def load(name: str) -> str:
    return gzip.decompress((FIXTURES / name).read_bytes()).decode("utf-8")


def test_parses_all_cards_with_core_fields():
    hotels = parse_hotels(load("paris_2026-11-12.html.gz"))
    assert len(hotels) == 18
    for hotel in hotels:
        assert hotel.name
        assert hotel.googleHotelId and hotel.url.startswith("https://www.google.com/travel/hotels/entity/")
        assert hotel.pricePerNight and hotel.currency == "USD"
        assert hotel.rating and hotel.reviewCount
    assert [h.position for h in hotels] == list(range(1, 19))


def test_first_card_details():
    first = parse_hotels(load("paris_2026-11-12.html.gz"))[0]
    assert first.name == "Glint Paris"
    assert (first.pricePerNight, first.totalPrice, first.nights) == (72.0, 171.0, 2)
    assert (first.rating, first.reviewCount) == (4.5, 3255)
    assert first.ratingDistribution == {"5": 72, "4": 18, "3": 5, "2": 2, "1": 3}
    assert (first.deal, first.dealPercentBelowUsual) == ("GREAT DEAL", 47)
    assert "Free Wi-Fi" in first.amenities
    assert first.imageUrl and "/a/" not in first.imageUrl


def test_other_currency():
    hotels = parse_hotels(load("paris_gb.html.gz"))
    assert hotels and all(h.currency == "GBP" for h in hotels if h.pricePerNight)


def test_parse_money():
    assert parse_money("$1,104") == (1104.0, "USD")
    assert parse_money("€54") == (54.0, "EUR")
    assert parse_money("CA$210") == (210.0, "CAD")
    assert parse_money("£99") == (99.0, "GBP")


def test_blocked_detection():
    assert is_blocked('<a href="https://www.google.com/sorry/index?continue=...">')
    assert not is_blocked(load("paris_gb.html.gz"))


def test_query_and_url():
    q = build_query(" Paris ", date(2026, 11, 12), date(2026, 11, 14), 3)
    assert q == "hotels in Paris November 12, 2026 to November 14, 2026 for 3 adults"
    assert build_query("Rome", None, None, 2) == "hotels in Rome"
    assert build_url("hotels in Rome", "DE") == "https://www.google.com/travel/search?q=hotels+in+Rome&hl=en&gl=de"


def test_ecb_conversion():
    from src.fx import parse_ecb

    xml = """<Cube time='2026-10-06'><Cube currency='USD' rate='1.10'/><Cube currency='GBP' rate='0.85'/></Cube>"""
    rates = parse_ecb(xml)
    assert rates.as_of == "2026-10-06"
    assert rates.convert(110.0, "USD", "EUR") == 100.0
    assert rates.convert(100.0, "EUR", "GBP") == 85.0
    assert rates.convert(110.0, "USD", "GBP") == 85.0
    assert rates.convert(10.0, "XXX", "EUR") is None
