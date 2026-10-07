"""Google Hotels Scraper: hotel prices, ratings and amenities from Google Travel."""

from __future__ import annotations

import asyncio
import random
from dataclasses import asdict
from datetime import date, datetime, timezone

import httpx
from apify import Actor

from .fx import fetch_rates
from .parser import is_blocked, parse_hotels
from .query import build_query, build_url

MAX_ATTEMPTS = 6
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:131.0) Gecko/20100101 Firefox/131.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_6) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.6 Safari/605.1.15",
]


def _parse_date(value: str | None, field: str) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError as exc:
        raise ValueError(f"'{field}' must be a date like 2026-11-12, got {value!r}") from exc


async def _fetch(url: str, proxy_cfg, attempt_tag: str) -> str | None:
    """Fetch the results page, rotating proxy session and user agent until Google answers."""
    for attempt in range(1, MAX_ATTEMPTS + 1):
        proxy_url = await proxy_cfg.new_url(session_id=f"{attempt_tag}_{attempt}_{random.randint(0, 10**6)}") if proxy_cfg else None
        headers = {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept-Language": "en-US,en;q=0.9",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
        try:
            async with httpx.AsyncClient(proxy=proxy_url, headers=headers, timeout=45, follow_redirects=True) as client:
                response = await client.get(url)
            page = response.text
            if response.status_code == 200 and not is_blocked(page):
                return page
            Actor.log.warning(f"Attempt {attempt}/{MAX_ATTEMPTS}: status {response.status_code}, blocked={is_blocked(page)}")
        except httpx.HTTPError as exc:
            Actor.log.warning(f"Attempt {attempt}/{MAX_ATTEMPTS}: {type(exc).__name__}: {exc}")
        await asyncio.sleep(min(2 ** attempt, 20) + random.random())
    return None


def _converted(hotel, rates, target: str | None) -> dict:
    if not rates or not target:
        return {}
    return {
        "convertedCurrency": target,
        "convertedPricePerNight": rates.convert(hotel.pricePerNight, hotel.currency, target),
        "convertedTotalPrice": rates.convert(hotel.totalPrice, hotel.currency, target),
        "exchangeRateDate": rates.as_of,
    }


async def main() -> None:
    async with Actor:
        actor_input = await Actor.get_input() or {}
        locations = [loc for loc in actor_input.get("locations", []) if str(loc).strip()]
        if not locations:
            raise ValueError("Add at least one location, e.g. 'Paris' or 'Berlin Mitte'.")

        check_in = _parse_date(actor_input.get("checkIn"), "checkIn")
        check_out = _parse_date(actor_input.get("checkOut"), "checkOut")
        if bool(check_in) != bool(check_out):
            raise ValueError("Set both 'checkIn' and 'checkOut', or neither.")
        if check_in and check_out <= check_in:
            raise ValueError("'checkOut' must be after 'checkIn'.")
        expected_nights = (check_out - check_in).days if check_in else None

        adults = int(actor_input.get("adults", 2))
        country = actor_input.get("country", "us")
        max_results = int(actor_input.get("maxResultsPerLocation", 20))
        target_currency = (actor_input.get("currency") or "").upper() or None
        rates = None
        if target_currency:
            rates = await fetch_rates()
            if not rates.supports(target_currency):
                raise ValueError(f"Currency {target_currency!r} is not supported for conversion.")
        proxy_cfg = await Actor.create_proxy_configuration(actor_proxy_input=actor_input.get("proxyConfiguration"))

        failed: list[str] = []
        for index, location in enumerate(locations):
            query = build_query(location, check_in, check_out, adults)
            url = build_url(query, country)
            Actor.log.info(f"Searching: {query}")
            page = await _fetch(url, proxy_cfg, attempt_tag=f"loc{index}")
            if page is None:
                failed.append(location)
                Actor.log.error(f"Google did not return results for {location!r} after {MAX_ATTEMPTS} attempts.")
                continue

            hotels = parse_hotels(page)[:max_results]
            if not hotels:
                failed.append(location)
                Actor.log.error(f"No hotels found on the results page for {location!r}.")
                continue
            if expected_nights and not any(h.nights == expected_nights for h in hotels if h.nights):
                Actor.log.warning(f"Google may not have applied the dates for {location!r}; check 'nights' in the results.")

            scraped_at = datetime.now(timezone.utc).isoformat()
            await Actor.push_data([
                {
                    "location": location,
                    **asdict(hotel),
                    **_converted(hotel, rates, target_currency),
                    "checkIn": check_in.isoformat() if check_in else None,
                    "checkOut": check_out.isoformat() if check_out else None,
                    "adults": adults,
                    "country": country,
                    "searchUrl": url,
                    "scrapedAt": scraped_at,
                }
                for hotel in hotels
            ])
            Actor.log.info(f"{location}: {len(hotels)} hotels saved.")

        if failed:
            await Actor.set_status_message(f"Finished. No results for: {', '.join(failed)}")
            if len(failed) == len(locations):
                await Actor.fail(status_message="Google returned no results for any location.")
