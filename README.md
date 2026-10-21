# DealScout

Describe what you want in plain words. DealScout searches the live web for the
cheapest place to buy it, checks the bank and card offers for the cards you
hold, and gives you the direct link to buy.

It's a native desktop app built with Qt, laid out like a shopping site. It doesn't
use a browser or a local server.

## What it does

- **Plain-language search:** e.g. "laptop for coding, 16 GB RAM, under ₹70,000".
  You can also set a max budget.
- **Live price hunt across stores:** Amazon, Flipkart, Croma, Reliance Digital,
  Vijay Sales, Tata CLiQ, brand stores and others. For other countries it uses
  that country's main stores.
- **Offers matched to your cards:** add your cards by bank, Credit or Debit,
  network and card name. You never enter a card number. Each product shows
  **your best price**, which is the lowest you can pay after offers your cards
  qualify for. It also lists strong offers for cards you don't have, so you can
  see what you're missing.
- **Other offers:** coupons, cashback, exchange, no-cost EMI and sale events.
- **A "Best deal for you" pick** with the reason it was chosen, plus buying tips.
- **Filters and sorting:** sort by your best price, listed price, discount or
  rating. Filter by store, in-stock items, or offers on your cards.
- **One-click buy link:** opens the product page on the store in your usual
  browser. You can also copy the link.

## How it works

Searches go through Claude (`claude-opus-5`) with Anthropic's web search and
web fetch tools. Claude reads search results and store pages, then returns the
results through a strict schema (`submit_deals` in `src/dealscout/engine.py`),
so the app always gets data in the same shape.

**It needs an Anthropic API key** (console.anthropic.com). Every search costs a
little in API usage. Quick mode is cheaper than Thorough mode.

## Setup

1. Double-click `setup.bat`. It creates `.venv` and installs the dependencies.
2. Double-click `run.bat`.
3. Open **⚙ Settings**, paste your API key, and pick your country.
4. Open **💳 My Cards** and add your cards.

You can also put the key in `.env` as `ANTHROPIC_API_KEY=` instead of Settings.
Settings and cards are saved in `%LOCALAPPDATA%\DealScout\settings.json`.

## Honest limits

- Prices and offers change often, and bank offers have caps, minimum spends and
  exclusions. Check the final price on the store's checkout page before you pay.
- Some stores block automated reading. In that case Claude may only see the
  price in a search snippet, and it says so in the product's notes.
- Some store images block hotlinking. Those products show a letter placeholder.

## Development

`python scripts/ui_preview.py <out-dir>` renders every screen with sample data
and saves screenshots. It makes no API calls.

## Licence

MIT. See [LICENSE](LICENSE).
