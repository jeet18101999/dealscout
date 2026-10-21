"""Settings and saved cards, kept in a JSON file in the user's config folder."""
from __future__ import annotations

import json
import os
from dataclasses import asdict
from pathlib import Path

from dotenv import load_dotenv
from platformdirs import user_config_dir

from .engine import Card

CONFIG_DIR = Path(user_config_dir("DealScout", appauthor=False))
CONFIG_FILE = CONFIG_DIR / "settings.json"

# Project-root .env, for running from source.
load_dotenv(Path(__file__).resolve().parents[2] / ".env")

BANKS = [
    "HDFC Bank", "ICICI Bank", "SBI", "Axis Bank", "Kotak Mahindra Bank",
    "IDFC FIRST Bank", "IndusInd Bank", "Yes Bank", "Bank of Baroda",
    "AU Small Finance Bank", "RBL Bank", "Federal Bank", "HSBC",
    "Standard Chartered", "American Express", "OneCard", "Punjab National Bank",
    "Canara Bank", "Union Bank of India", "Citi", "Chase", "Capital One",
    "Bank of America", "Wells Fargo", "Barclays",
]
NETWORKS = ["", "Visa", "Mastercard", "RuPay", "American Express", "Diners Club"]
COUNTRIES = ["India", "United States", "United Kingdom", "Canada", "Australia",
             "United Arab Emirates", "Singapore", "Germany"]


class Settings:
    def __init__(self) -> None:
        self.api_key = ""
        self.country = "India"
        self.depth = "quick"
        self.cards: list[Card] = []
        self.load()

    def load(self) -> None:
        try:
            data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        self.api_key = data.get("api_key", "")
        self.country = data.get("country", self.country)
        self.depth = data.get("depth", self.depth) if data.get("depth") in ("quick", "thorough") else "quick"
        self.cards = [Card(**c) for c in data.get("cards", []) if isinstance(c, dict)]

    def save(self) -> None:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        data = {
            "api_key": self.api_key,
            "country": self.country,
            "depth": self.depth,
            "cards": [asdict(c) for c in self.cards],
        }
        CONFIG_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def effective_api_key(self) -> str:
        return self.api_key or os.environ.get("ANTHROPIC_API_KEY", "")
