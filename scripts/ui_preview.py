"""Render the storefront with sample data (no API calls) and save screenshots."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from dealscout import gui
from dealscout.engine import Card, DealResult

out = Path(sys.argv[1] if len(sys.argv) > 1 else ".")

def product(title, store, price, mrp, eff, rating, mine):
    return {
        "title": title, "store": store, "url": f"https://example.com/{store.lower()}/item",
        "image_url": None, "price": price, "mrp": mrp, "currency": "INR", "rating": rating,
        "rating_count": 12840, "in_stock": True, "delivery": "Free delivery by Friday",
        "highlights": ["ANC up to 45 dB", "30 h battery", "Bluetooth 5.3"],
        "card_offers": [
            {"card": "HDFC Bank Credit Card", "applies_to_user": mine, "description": "10% instant discount up to ₹1,500",
             "discount": price - eff, "price_after": eff, "conditions": "Min. purchase ₹5,000. Not valid on EMI.", "source_url": None},
            {"card": "SBI Credit Card", "applies_to_user": False, "description": "₹750 off on EMI transactions",
             "discount": 750, "price_after": price - 750, "conditions": None, "source_url": None},
        ],
        "other_offers": [{"kind": "coupon", "description": "Extra ₹200 off with coupon", "value": 200},
                         {"kind": "emi", "description": "No-cost EMI from ₹1,083/month", "value": None}],
        "effective_price": eff, "effective_price_note": f"₹{price - eff} HDFC instant discount",
        "match_notes": "Meets every requirement.",
    }

products = [
    product("Sony WF-1000XM5 Truly Wireless Noise Cancelling Earbuds", "Amazon", 19990, 29990, 17990, 4.4, True),
    product("Sony WF-1000XM5 Wireless Earbuds (Black)", "Flipkart", 20490, 29990, 18990, 4.5, True),
    product("Bose QuietComfort Earbuds II", "Croma", 18999, 25900, 18999, 4.3, False),
    product("Samsung Galaxy Buds3 Pro", "Reliance Digital", 17999, 24999, 16499, 4.2, True),
    product("Nothing Ear (2)", "Vijay Sales", 8999, 11999, 8499, 4.1, True),
]
result = DealResult("Premium ANC earbuds are 30-40% below launch price right now.", products, 4,
                    "Lowest price after your HDFC discount while still meeting the ANC requirement.",
                    ["Big Billion Days starts next week — prices may dip a further 5%.",
                     "Card discounts are capped; check the minimum spend."], ["sony earbuds price"],
                    [("Amazon listing", "https://example.com/a")])

app = QApplication(sys.argv)
app.setStyleSheet(gui.STYLE)
win = gui.MainWindow()
win.settings.cards = [Card("HDFC Bank", "Credit", "Millennia", "Visa"), Card("SBI", "Debit")]
win._refresh_cards()
win.show()
steps = []
steps.append(lambda: win.grab().save(str(out / "1_home.png")))
def loading():
    win.stack.setCurrentWidget(win.loading)
    win.loading_title.setText("Finding the best deal for “noise cancelling earbuds”…")
    for m in ["Searching: best noise cancelling earbuds price India", "Reading: https://www.amazon.in/…", "Searching: HDFC credit card offer earbuds"]:
        win.log.addItem(m)
steps.append(loading)
steps.append(lambda: win.grab().save(str(out / "2_loading.png")))
def results():
    win.last_query = "noise cancelling earbuds under 20000"
    win._done(result)
steps.append(results)
steps.append(lambda: win.grab().save(str(out / "3_results.png")))
def detail():
    d = gui.ProductDialog(products[0], win.loader, win)
    d.show()
    QTimer.singleShot(400, lambda: (d.grab().save(str(out / "4_detail.png")), d.close()))
steps.append(detail)
steps.append(lambda: None)
steps.append(app.quit)
for i, s in enumerate(steps):
    QTimer.singleShot(600 * (i + 1), s)
app.exec()
print("saved to", out)
