# Google Hotels Scraper

Get hotel prices, ratings, review counts, deals and amenities from **Google Hotels** for any city, neighbourhood or area, for your exact travel dates and number of guests.

Built for **reliability**: every search retries automatically with a fresh connection until Google answers, so runs finish instead of failing.

## What you get

For every hotel on the Google Hotels results page:

| Field | Example |
|---|---|
| `name` | Glint Paris |
| `pricePerNight` / `totalPrice` / `currency` | 72 / 171 / USD |
| `nights` | 2 |
| `convertedPricePerNight` / `convertedTotalPrice` / `convertedCurrency` | 64.42 / 153.00 / EUR (optional) |
| `rating` / `reviewCount` | 4.5 / 3255 |
| `ratingDistribution` | `{"5": 72, "4": 18, "3": 5, "2": 2, "1": 3}` |
| `deal` / `dealPercentBelowUsual` | GREAT DEAL / 47 |
| `amenities` | Free Wi-Fi, Breakfast ($), Parking, … |
| `ecoCertified` | true |
| `googleHotelId` / `url` | Google Hotels entity link |
| `imageUrl` | Hotel photo |
| `position` | Rank on the results page |

Plus the search context (`location`, `checkIn`, `checkOut`, `adults`, `scrapedAt`).

## How to use

1. Enter one or more **locations**, e.g. `Paris`, `Berlin Mitte`, `near Times Square`.
2. Optionally set **check-in / check-out** dates and the number of **adults**.
3. Optionally pick **Convert prices to** (e.g. EUR) to get prices in a fixed currency.
4. Run and download the results as JSON, CSV, Excel or via API.

### Example input

```json
{
  "locations": ["Paris", "Vienna"],
  "checkIn": "2026-12-04",
  "checkOut": "2026-12-07",
  "adults": 2,
  "currency": "EUR"
}
```

## About currencies

Google chooses the display currency from the location of the server that runs the search, so the original price usually comes back in USD. Pick **Convert prices to** and the actor adds converted prices using the **European Central Bank's daily reference rates** (`exchangeRateDate` tells you which day). Original prices are always kept.

## Use cases

- Hotel price monitoring and rate parity checks
- Market research for hotels, travel agencies and property managers
- Price comparison websites and travel apps
- Datasets for analytics and AI

## Limits

- Returns the hotels Google shows on the first results page (about 18–20 per location). Use more specific locations (neighbourhoods, landmarks) to cover a city in more detail.
- Prices are Google's "starting from" prices across its booking partners at the time of the run.

## Legal

This actor collects publicly available hotel information (no personal data). Make sure your use complies with Google's terms and the laws that apply to you.
