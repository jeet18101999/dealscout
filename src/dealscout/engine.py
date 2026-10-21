"""Deal search: Claude browses the live web and returns structured deals.

Claude gets three tools: web search, web fetch, and `submit_deals`, a
schema-strict tool it calls exactly once with the final answer. Taking the
answer as a tool call rather than free text is what lets the GUI rely on the
shape of the data.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date
from typing import Callable

import anthropic

MODEL = "claude-opus-5"

# depth -> (effort, max web searches, max page fetches)
DEPTHS = {
    "quick": ("medium", 8, 6),
    "thorough": ("high", 16, 14),
}

_NUM = {"type": ["number", "null"]}
_STR = {"type": ["string", "null"]}

SUBMIT_TOOL = {
    "name": "submit_deals",
    "description": (
        "Submit the final shopping results. Call this exactly once, after "
        "researching, and only with listings and offers you actually found."
    ),
    "strict": True,
    "input_schema": {
        "type": "object",
        "additionalProperties": False,
        "required": ["summary", "products", "best_index", "best_reason", "tips"],
        "properties": {
            "summary": {"type": "string", "description": "2-3 sentence overview of the market for this request."},
            "best_index": {"type": "integer", "description": "Index into products of the overall best deal for this user."},
            "best_reason": {"type": "string"},
            "tips": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Short practical tips: sale dates, price trends, stacking offers, what to avoid.",
            },
            "products": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": [
                        "title", "store", "url", "image_url", "price", "mrp",
                        "currency", "rating", "rating_count", "in_stock",
                        "delivery", "highlights", "card_offers", "other_offers",
                        "effective_price", "effective_price_note", "match_notes",
                    ],
                    "properties": {
                        "title": {"type": "string"},
                        "store": {"type": "string", "description": "Retailer name, e.g. Amazon, Flipkart, Croma."},
                        "url": {"type": "string", "description": "Direct product page link on the retailer."},
                        "image_url": _STR,
                        "price": {"type": "number", "description": "Current selling price before card/bank offers."},
                        "mrp": _NUM,
                        "currency": {"type": "string", "description": "ISO code, e.g. INR, USD."},
                        "rating": _NUM,
                        "rating_count": {"type": ["integer", "null"]},
                        "in_stock": {"type": ["boolean", "null"]},
                        "delivery": _STR,
                        "highlights": {"type": "array", "items": {"type": "string"}},
                        "card_offers": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "additionalProperties": False,
                                "required": [
                                    "card", "applies_to_user", "description",
                                    "discount", "price_after", "conditions", "source_url",
                                ],
                                "properties": {
                                    "card": {"type": "string", "description": "Bank and card type, e.g. 'HDFC Bank Credit Card'."},
                                    "applies_to_user": {"type": "boolean", "description": "True if one of the user's cards qualifies."},
                                    "description": {"type": "string"},
                                    "discount": _NUM,
                                    "price_after": _NUM,
                                    "conditions": _STR,
                                    "source_url": _STR,
                                },
                            },
                        },
                        "other_offers": {
                            "type": "array",
                            "description": "Coupons, cashback, exchange, no-cost EMI, bundle deals.",
                            "items": {
                                "type": "object",
                                "additionalProperties": False,
                                "required": ["kind", "description", "value"],
                                "properties": {
                                    "kind": {"type": "string", "enum": ["coupon", "cashback", "exchange", "emi", "bundle", "sale", "other"]},
                                    "description": {"type": "string"},
                                    "value": _NUM,
                                },
                            },
                        },
                        "effective_price": {"type": "number", "description": "Lowest realistic price for THIS user after offers their cards qualify for."},
                        "effective_price_note": {"type": "string", "description": "How the effective price was reached."},
                        "match_notes": {"type": "string", "description": "How well this matches the requirement; any compromises."},
                    },
                },
            },
        },
    },
}

SYSTEM = """You are the research engine behind a price-comparison shopping app.

The user describes what they want. Search the live web for products that meet
the requirement and find where each is cheapest right now. Cover the major
retailers for the user's country (for India: Amazon.in, Flipkart, Croma,
Reliance Digital, Vijay Sales, Tata CLiQ, brand stores, and category
specialists; elsewhere, the equivalents), plus price-comparison sites to find
leads.

For each strong candidate, check the retailer's current bank and card offers
(instant discounts, cashback, no-cost EMI) and other offers (coupons, exchange,
sale events). The user tells you which cards they hold: mark each card offer
applies_to_user accordingly, and compute effective_price as the lowest price
THIS user can realistically pay, stacking only offers that can actually be
combined. Respect offer caps and minimum spends. List strong card offers for
cards the user does not hold too, so they can see what they are missing.

Return 4-10 products, cheapest effective price first, mixing retailers and
close alternatives where they genuinely fit the requirement. Only report
prices, offers and links you saw in search results or fetched pages; never
invent a URL. Prefer the retailer's product page over search or listing pages.
If a price is from a snippet you could not confirm, say so in match_notes.

When you have enough, call submit_deals once with the results."""


@dataclass
class Card:
    bank: str
    kind: str  # Credit / Debit
    name: str = ""  # optional product name, e.g. "Millennia", "Amazon Pay"
    network: str = ""  # Visa / Mastercard / RuPay / Amex / Diners

    def label(self) -> str:
        parts = [self.bank, self.name, self.network, f"{self.kind} Card"]
        return " ".join(p for p in parts if p)


@dataclass
class DealResult:
    summary: str
    products: list[dict]
    best_index: int
    best_reason: str
    tips: list[str]
    searches: list[str] = field(default_factory=list)
    sources: list[tuple[str, str]] = field(default_factory=list)  # (title, url)


class SearchError(Exception):
    pass


def _user_prompt(requirement: str, cards: list[Card], country: str, budget: str) -> str:
    card_lines = "\n".join(f"- {c.label()}" for c in cards) or "- (none given)"
    lines = [
        f"Today is {date.today():%d %B %Y}. Country: {country}.",
        f"Requirement: {requirement}",
    ]
    if budget:
        lines.append(f"Budget: {budget}")
    lines += ["Cards I hold:", card_lines]
    return "\n".join(lines)


def search_deals(
    requirement: str,
    cards: list[Card],
    *,
    country: str = "India",
    budget: str = "",
    depth: str = "quick",
    api_key: str | None = None,
    on_progress: Callable[[str], None] = lambda _msg: None,
    should_stop: Callable[[], bool] = lambda: False,
) -> DealResult:
    effort, max_searches, max_fetches = DEPTHS[depth]
    client = anthropic.Anthropic(api_key=api_key or None, max_retries=3)
    tools = [
        {"type": "web_search_20260209", "name": "web_search", "max_uses": max_searches},
        {"type": "web_fetch_20260209", "name": "web_fetch", "max_uses": max_fetches},
        SUBMIT_TOOL,
    ]
    messages: list = [{"role": "user", "content": _user_prompt(requirement, cards, country, budget)}]
    searches: list[str] = []
    sources: dict[str, str] = {}

    for _turn in range(8):
        if should_stop():
            raise SearchError("Search cancelled.")
        try:
            with client.beta.messages.stream(
                model=MODEL,
                max_tokens=64000,
                system=SYSTEM,
                messages=messages,
                tools=tools,
                thinking={"type": "adaptive"},
                output_config={"effort": effort},
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
            ) as stream:
                for event in stream:
                    if should_stop():
                        raise SearchError("Search cancelled.")
                    _report(event, on_progress, searches, sources)
                response = stream.get_final_message()
        except anthropic.AuthenticationError as e:
            raise SearchError("The Anthropic API key was rejected. Check it in Settings.") from e
        except anthropic.PermissionDeniedError as e:
            raise SearchError(f"API key lacks permission: {e.message}") from e
        except anthropic.RateLimitError as e:
            raise SearchError("Rate limited by the API. Wait a minute and try again.") from e
        except anthropic.APIStatusError as e:
            raise SearchError(f"API error ({e.status_code}): {e.message}") from e
        except anthropic.APIConnectionError as e:
            raise SearchError("Could not reach the Anthropic API. Check your internet connection.") from e

        if response.stop_reason == "refusal":
            raise SearchError("The request was declined. Try rephrasing what you are looking for.")

        for block in response.content:
            if block.type == "tool_use" and block.name == "submit_deals":
                return _to_result(block.input, searches, sources)

        messages.append({"role": "assistant", "content": response.content})
        if response.stop_reason == "pause_turn":
            continue  # server tools hit their per-turn limit; resend to resume
        if response.stop_reason == "max_tokens":
            raise SearchError("The response was cut off. Try a narrower request.")
        # Finished in prose without submitting: ask for the structured answer.
        messages.append({"role": "user", "content": "Now call submit_deals with your findings."})

    raise SearchError("The search did not finish. Try again or use a narrower request.")


def _report(event, on_progress, searches: list[str], sources: dict[str, str]) -> None:
    if event.type != "content_block_stop":
        return
    block = getattr(event, "content_block", None)
    if block is None:
        return
    if block.type == "server_tool_use":
        args = block.input if isinstance(block.input, dict) else {}
        if block.name == "web_search" and args.get("query"):
            searches.append(args["query"])
            on_progress(f"Searching: {args['query']}")
        elif block.name == "web_fetch" and args.get("url"):
            on_progress(f"Reading: {args['url']}")
    elif block.type == "web_search_tool_result":
        content = block.content
        if isinstance(content, list):  # an error arrives as an object, not a list
            for r in content:
                url = getattr(r, "url", None)
                if url:
                    sources.setdefault(url, getattr(r, "title", "") or url)
    elif block.type == "tool_use" and block.name == "submit_deals":
        on_progress("Comparing offers…")


def _to_result(data, searches, sources) -> DealResult:
    if isinstance(data, str):
        data = json.loads(data)
    raw = data.get("products", [])
    idx = data.get("best_index", 0)
    best_item = raw[idx] if isinstance(idx, int) and 0 <= idx < len(raw) else None
    products = [p for p in raw if p.get("url") and p.get("title")]
    if not products:
        raise SearchError("No matching products were found. Try a broader description.")
    best = next((i for i, p in enumerate(products) if p is best_item), 0)
    return DealResult(
        summary=data.get("summary", ""),
        products=products,
        best_index=best,
        best_reason=data.get("best_reason", ""),
        tips=list(data.get("tips", [])),
        searches=searches,
        sources=[(t, u) for u, t in sources.items()],
    )
