"""DealScout storefront: a native Qt window laid out like a shopping site."""
from __future__ import annotations

import sys

from PySide6.QtCore import QObject, Qt, QThread, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QFont, QGuiApplication, QPixmap
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest
from PySide6.QtWidgets import (
    QApplication, QButtonGroup, QCheckBox, QComboBox, QDialog, QDialogButtonBox,
    QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QListWidget,
    QListWidgetItem, QMainWindow, QMessageBox, QProgressBar, QPushButton,
    QRadioButton, QScrollArea, QStackedWidget, QVBoxLayout, QWidget,
)

from .config import BANKS, COUNTRIES, NETWORKS, Settings
from .engine import Card, DealResult, SearchError, search_deals

ORANGE = "#ff6a00"
NAVY = "#131a2b"
GREEN = "#138a36"

STYLE = f"""
QMainWindow, #page {{ background: #f1f3f6; }}
QWidget {{ font-family: 'Segoe UI'; font-size: 10pt; color: #212121; }}
#header {{ background: {NAVY}; }}
#logo {{ color: white; font-size: 20pt; font-weight: 700; }}
#logoAccent {{ color: {ORANGE}; font-size: 20pt; font-weight: 700; }}
#tagline {{ color: #9aa4bf; font-size: 8pt; }}
#searchBox {{ background: white; border: none; border-radius: 4px; padding: 9px 12px; font-size: 11pt; }}
#budgetBox {{ background: white; border: none; border-radius: 4px; padding: 9px 10px; }}
#searchBtn {{ background: {ORANGE}; color: white; border: none; border-radius: 4px;
              padding: 9px 22px; font-weight: 700; font-size: 11pt; }}
#searchBtn:hover {{ background: #e65f00; }}
#searchBtn:disabled {{ background: #7a5a44; }}
#headerBtn {{ background: transparent; color: white; border: 1px solid #3a4460;
              border-radius: 4px; padding: 8px 12px; }}
#headerBtn:hover {{ border-color: {ORANGE}; }}
#catBar {{ background: white; border-bottom: 1px solid #e0e0e0; }}
#chip {{ background: transparent; border: none; padding: 8px 12px; color: #333; font-weight: 600; }}
#chip:hover {{ color: {ORANGE}; }}
#panel, #tile {{ background: white; border: 1px solid #e4e6eb; border-radius: 6px; }}
#tile:hover {{ border: 1px solid {ORANGE}; }}
#hero {{ background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #1d2742, stop:1 #3a1f5c);
         border-radius: 8px; }}
#heroTitle {{ color: white; font-size: 22pt; font-weight: 700; }}
#heroText {{ color: #d5d9e6; font-size: 11pt; }}
#bestBanner {{ background: #fff8ee; border: 2px solid {ORANGE}; border-radius: 8px; }}
#ribbon {{ background: {ORANGE}; color: white; font-weight: 700; font-size: 8pt;
           padding: 3px 8px; border-radius: 3px; }}
#storeBadge {{ background: #eef2ff; color: #3949ab; font-weight: 600; font-size: 8pt;
               padding: 2px 8px; border-radius: 3px; }}
#price {{ font-size: 15pt; font-weight: 700; }}
#bigPrice {{ font-size: 22pt; font-weight: 700; }}
#mrp {{ color: #878787; text-decoration: line-through; }}
#off {{ color: {GREEN}; font-weight: 700; }}
#yourPrice {{ background: #e9f7ee; color: {GREEN}; font-weight: 700; border-radius: 4px; padding: 5px 8px; }}
#rating {{ background: {GREEN}; color: white; font-weight: 700; font-size: 8pt; padding: 1px 6px; border-radius: 3px; }}
#muted {{ color: #6b7280; font-size: 9pt; }}
#sectionTitle {{ font-size: 13pt; font-weight: 700; }}
#buyBtn {{ background: {ORANGE}; color: white; border: none; border-radius: 4px;
           padding: 11px 26px; font-weight: 700; font-size: 11pt; }}
#buyBtn:hover {{ background: #e65f00; }}
#plainBtn {{ background: white; border: 1px solid #c9ced8; border-radius: 4px; padding: 8px 16px; }}
#plainBtn:hover {{ border-color: {ORANGE}; }}
#offerRow {{ background: #fafbfc; border: 1px solid #eceef2; border-radius: 4px; }}
#offerRowMine {{ background: #eefaf2; border: 1px solid #b7e4c7; border-radius: 4px; }}
#cardChip {{ background: #1d2742; color: white; border-radius: 6px; padding: 10px 14px; font-weight: 600; }}
QProgressBar {{ border: none; background: #e6e8ee; height: 6px; border-radius: 3px; }}
QProgressBar::chunk {{ background: {ORANGE}; border-radius: 3px; }}
QScrollArea {{ border: none; background: transparent; }}
"""

CATEGORIES = [
    ("Mobiles", "A 5G smartphone with a great camera"),
    ("Laptops", "A laptop for programming, 16GB RAM, SSD"),
    ("TVs", "A 55 inch 4K smart TV"),
    ("Headphones", "Noise cancelling wireless earbuds"),
    ("Appliances", "A 7kg front load washing machine"),
    ("Watches", "A smartwatch with GPS and AMOLED display"),
    ("Cameras", "A mirrorless camera for beginners"),
    ("Home", "An air purifier for a 400 sq ft room"),
]

SYMBOLS = {"INR": "₹", "USD": "$", "EUR": "€", "GBP": "£", "AUD": "A$", "CAD": "C$", "AED": "AED ", "SGD": "S$"}


def money(value, currency: str = "INR") -> str:
    if value is None:
        return "—"
    sym = SYMBOLS.get((currency or "").upper(), (currency or "") + " ")
    whole = int(round(value))
    if (currency or "").upper() == "INR":  # Indian digit grouping: 1,23,456
        s = str(abs(whole))
        if len(s) > 3:
            head, tail = s[:-3], s[-3:]
            groups = []
            while len(head) > 2:
                groups.insert(0, head[-2:])
                head = head[:-2]
            if head:
                groups.insert(0, head)
            s = ",".join(groups) + "," + tail
        return f"{'-' if whole < 0 else ''}{sym}{s}"
    return f"{sym}{whole:,}"


def label(text: str = "", name: str = "", wrap: bool = False) -> QLabel:
    lbl = QLabel(text)
    if name:
        lbl.setObjectName(name)
    lbl.setWordWrap(wrap)
    return lbl


def open_url(url: str) -> None:
    if url.startswith(("http://", "https://")):
        QDesktopServices.openUrl(QUrl(url))


class ImageLoader(QObject):
    """Fetches product images once and hands pixmaps to whoever asked."""

    def __init__(self) -> None:
        super().__init__()
        self.net = QNetworkAccessManager(self)
        self.cache: dict[str, QPixmap] = {}
        self.waiting: dict[str, list] = {}

    def load(self, url: str | None, target: QLabel, size: int) -> None:
        if not url or not url.startswith("http"):
            return
        if url in self.cache:
            self._apply(self.cache[url], target, size)
            return
        first = url not in self.waiting
        self.waiting.setdefault(url, []).append((target, size))
        if first:
            req = QNetworkRequest(QUrl(url))
            req.setHeader(QNetworkRequest.KnownHeaders.UserAgentHeader,
                          "Mozilla/5.0 (Windows NT 10.0; Win64; x64) DealScout/1.0")
            req.setAttribute(QNetworkRequest.Attribute.RedirectPolicyAttribute,
                             QNetworkRequest.RedirectPolicy.NoLessSafeRedirectPolicy)
            reply = self.net.get(req)
            reply.finished.connect(lambda r=reply, u=url: self._done(r, u))

    def _done(self, reply: QNetworkReply, url: str) -> None:
        pix = QPixmap()
        if reply.error() == QNetworkReply.NetworkError.NoError:
            pix.loadFromData(reply.readAll())
        reply.deleteLater()
        if not pix.isNull():
            self.cache[url] = pix
        for target, size in self.waiting.pop(url, []):
            if not pix.isNull():
                self._apply(pix, target, size)

    @staticmethod
    def _apply(pix: QPixmap, target: QLabel, size: int) -> None:
        try:
            target.setPixmap(pix.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatio,
                                        Qt.TransformationMode.SmoothTransformation))
        except RuntimeError:  # the label was destroyed while the image loaded
            pass


def image_slot(loader: ImageLoader, url: str | None, size: int, title: str) -> QLabel:
    lbl = QLabel()
    lbl.setFixedSize(size, size)
    lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    initial = (title.strip()[:1] or "?").upper()
    lbl.setText(initial)
    lbl.setStyleSheet(f"background:#f5f6f8; color:#b8bdc9; font-size:{size // 3}px; font-weight:700; border-radius:4px;")
    loader.load(url, lbl, size)
    return lbl


def discount_pct(p: dict) -> int | None:
    mrp, price = p.get("mrp"), p.get("price")
    if mrp and price and mrp > price:
        return round((mrp - price) / mrp * 100)
    return None


def best_user_offer(p: dict) -> dict | None:
    mine = [o for o in p.get("card_offers", []) if o.get("applies_to_user")]
    return min(mine, key=lambda o: o.get("price_after") or p.get("price") or 0) if mine else None


# ---------------------------------------------------------------- worker

class SearchWorker(QObject):
    progress = Signal(str)
    done = Signal(object)
    failed = Signal(str)

    def __init__(self, requirement, cards, country, budget, depth, api_key):
        super().__init__()
        self.args = (requirement, cards, country, budget, depth, api_key)
        self.cancelled = False

    def run(self) -> None:
        requirement, cards, country, budget, depth, api_key = self.args
        try:
            result = search_deals(
                requirement, cards, country=country, budget=budget, depth=depth,
                api_key=api_key, on_progress=self.progress.emit,
                should_stop=lambda: self.cancelled,
            )
        except SearchError as e:
            self.failed.emit(str(e))
        except Exception as e:  # keep the window alive on anything unexpected
            self.failed.emit(f"Unexpected error: {e}")
        else:
            self.done.emit(result)


# ---------------------------------------------------------------- dialogs

class CardsDialog(QDialog):
    def __init__(self, settings: Settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.setWindowTitle("My Cards")
        self.setMinimumWidth(560)
        lay = QVBoxLayout(self)
        lay.addWidget(label("Your saved cards", "sectionTitle"))
        lay.addWidget(label("Add the cards you hold. Offers are matched on bank and card type — "
                            "no card numbers are ever asked for or stored.", "muted", wrap=True))
        self.list = QListWidget()
        self.list.setMinimumHeight(160)
        lay.addWidget(self.list)

        form = QGridLayout()
        self.bank = QComboBox(); self.bank.setEditable(True); self.bank.addItems(BANKS)
        self.kind = QComboBox(); self.kind.addItems(["Credit", "Debit"])
        self.network = QComboBox(); self.network.addItems(NETWORKS)
        self.name = QLineEdit(); self.name.setPlaceholderText("Card name (optional), e.g. Millennia, Amazon Pay")
        form.addWidget(label("Bank"), 0, 0); form.addWidget(self.bank, 0, 1)
        form.addWidget(label("Type"), 0, 2); form.addWidget(self.kind, 0, 3)
        form.addWidget(label("Network"), 1, 0); form.addWidget(self.network, 1, 1)
        form.addWidget(self.name, 1, 2, 1, 2)
        lay.addLayout(form)

        row = QHBoxLayout()
        add = QPushButton("Add card"); add.setObjectName("buyBtn"); add.clicked.connect(self.add)
        rm = QPushButton("Remove selected"); rm.setObjectName("plainBtn"); rm.clicked.connect(self.remove)
        row.addWidget(add); row.addWidget(rm); row.addStretch()
        close = QPushButton("Done"); close.setObjectName("plainBtn"); close.clicked.connect(self.accept)
        row.addWidget(close)
        lay.addLayout(row)
        self.refresh()

    def refresh(self) -> None:
        self.list.clear()
        for c in self.settings.cards:
            self.list.addItem(QListWidgetItem(f"💳  {c.label()}"))

    def add(self) -> None:
        bank = self.bank.currentText().strip()
        if not bank:
            return
        card = Card(bank=bank, kind=self.kind.currentText(), name=self.name.text().strip(),
                    network=self.network.currentText())
        if card.label() not in {c.label() for c in self.settings.cards}:
            self.settings.cards.append(card)
            self.settings.save()
        self.name.clear()
        self.refresh()

    def remove(self) -> None:
        row = self.list.currentRow()
        if row >= 0:
            del self.settings.cards[row]
            self.settings.save()
            self.refresh()


class SettingsDialog(QDialog):
    def __init__(self, settings: Settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.setWindowTitle("Settings")
        self.setMinimumWidth(480)
        lay = QVBoxLayout(self)
        lay.addWidget(label("Anthropic API key", "sectionTitle"))
        lay.addWidget(label("DealScout uses Claude with live web search to read retailer pages. "
                            "Get a key at console.anthropic.com. It is stored only on this PC.",
                            "muted", wrap=True))
        self.key = QLineEdit(settings.api_key)
        self.key.setEchoMode(QLineEdit.EchoMode.Password)
        self.key.setPlaceholderText("sk-ant-…  (leave blank to use ANTHROPIC_API_KEY)")
        lay.addWidget(self.key)

        lay.addSpacing(8)
        lay.addWidget(label("Shopping country", "sectionTitle"))
        self.country = QComboBox(); self.country.setEditable(True); self.country.addItems(COUNTRIES)
        self.country.setCurrentText(settings.country)
        lay.addWidget(self.country)

        lay.addSpacing(8)
        lay.addWidget(label("Search depth", "sectionTitle"))
        self.quick = QRadioButton("Quick — about 1–2 minutes, fewer stores checked")
        self.thorough = QRadioButton("Thorough — 3–5 minutes, more stores and offer pages read")
        group = QButtonGroup(self); group.addButton(self.quick); group.addButton(self.thorough)
        (self.thorough if settings.depth == "thorough" else self.quick).setChecked(True)
        lay.addWidget(self.quick); lay.addWidget(self.thorough)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.save); buttons.rejected.connect(self.reject)
        lay.addWidget(buttons)

    def save(self) -> None:
        self.settings.api_key = self.key.text().strip()
        self.settings.country = self.country.currentText().strip() or "India"
        self.settings.depth = "thorough" if self.thorough.isChecked() else "quick"
        self.settings.save()
        self.accept()


class ProductDialog(QDialog):
    def __init__(self, p: dict, loader: ImageLoader, parent=None):
        super().__init__(parent)
        self.setWindowTitle(p["title"])
        self.resize(900, 680)
        cur = p.get("currency", "INR")
        outer = QVBoxLayout(self)
        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        body = QWidget(); body.setObjectName("page")
        scroll.setWidget(body)
        outer.addWidget(scroll)
        lay = QHBoxLayout(body)
        lay.setContentsMargins(18, 18, 18, 18)
        lay.setSpacing(22)

        left = QVBoxLayout()
        left.addWidget(image_slot(loader, p.get("image_url"), 300, p["title"]))
        buy = QPushButton(f"Buy on {p['store']}  →"); buy.setObjectName("buyBtn")
        buy.clicked.connect(lambda: open_url(p["url"]))
        copy = QPushButton("Copy link"); copy.setObjectName("plainBtn")
        copy.clicked.connect(lambda: (QGuiApplication.clipboard().setText(p["url"]), copy.setText("Copied ✓")))
        left.addWidget(buy); left.addWidget(copy)
        link = label(f'<a href="{p["url"]}">{p["url"][:60]}{"…" if len(p["url"]) > 60 else ""}</a>', "muted", wrap=True)
        link.setOpenExternalLinks(True)
        left.addWidget(link)
        left.addStretch()
        lay.addLayout(left)

        right = QVBoxLayout(); right.setSpacing(8)
        badge_row = QHBoxLayout()
        badge_row.addWidget(label(p["store"], "storeBadge"))
        if p.get("rating"):
            badge_row.addWidget(label(f"{p['rating']:.1f} ★", "rating"))
            if p.get("rating_count"):
                badge_row.addWidget(label(f"{p['rating_count']:,} ratings", "muted"))
        badge_row.addStretch()
        right.addLayout(badge_row)
        t = label(p["title"], wrap=True); t.setStyleSheet("font-size:15pt; font-weight:600;")
        right.addWidget(t)

        prow = QHBoxLayout()
        prow.addWidget(label(money(p.get("price"), cur), "bigPrice"))
        if p.get("mrp") and p["mrp"] > (p.get("price") or 0):
            prow.addWidget(label(money(p["mrp"], cur), "mrp"))
        pct = discount_pct(p)
        if pct:
            prow.addWidget(label(f"{pct}% off", "off"))
        prow.addStretch()
        right.addLayout(prow)

        eff = p.get("effective_price")
        if eff is not None and eff < (p.get("price") or eff + 1):
            right.addWidget(label(f"Your best price: {money(eff, cur)} — {p.get('effective_price_note', '')}",
                                  "yourPrice", wrap=True))
        elif p.get("effective_price_note"):
            right.addWidget(label(p["effective_price_note"], "muted", wrap=True))

        meta = []
        if p.get("in_stock") is not None:
            meta.append("In stock" if p["in_stock"] else "Out of stock")
        if p.get("delivery"):
            meta.append(p["delivery"])
        if meta:
            right.addWidget(label(" · ".join(meta), "muted", wrap=True))

        if p.get("card_offers"):
            right.addSpacing(6)
            right.addWidget(label("Bank & card offers", "sectionTitle"))
            offers = sorted(p["card_offers"], key=lambda o: not o.get("applies_to_user"))
            for o in offers:
                right.addWidget(self._offer_row(o, cur))

        if p.get("other_offers"):
            right.addSpacing(6)
            right.addWidget(label("More offers", "sectionTitle"))
            icons = {"coupon": "🏷", "cashback": "💰", "exchange": "🔁", "emi": "📅", "bundle": "🎁", "sale": "⚡"}
            for o in p["other_offers"]:
                val = f"  (worth {money(o['value'], cur)})" if o.get("value") else ""
                right.addWidget(label(f"{icons.get(o.get('kind'), '•')}  {o['description']}{val}", wrap=True))

        if p.get("highlights"):
            right.addSpacing(6)
            right.addWidget(label("Highlights", "sectionTitle"))
            for h in p["highlights"]:
                right.addWidget(label(f"•  {h}", wrap=True))

        if p.get("match_notes"):
            right.addSpacing(6)
            right.addWidget(label("How it matches your need", "sectionTitle"))
            right.addWidget(label(p["match_notes"], wrap=True))
        right.addStretch()
        lay.addLayout(right, 1)

    @staticmethod
    def _offer_row(o: dict, cur: str) -> QFrame:
        f = QFrame(); f.setObjectName("offerRowMine" if o.get("applies_to_user") else "offerRow")
        v = QVBoxLayout(f); v.setContentsMargins(10, 8, 10, 8); v.setSpacing(2)
        head = QHBoxLayout()
        tag = "✓ Your card  " if o.get("applies_to_user") else ""
        h = label(f"{tag}{o['card']}"); h.setStyleSheet(f"font-weight:700; color:{GREEN if tag else '#333'};")
        head.addWidget(h); head.addStretch()
        if o.get("price_after"):
            head.addWidget(label(f"Pay {money(o['price_after'], cur)}", "off"))
        v.addLayout(head)
        v.addWidget(label(o["description"], wrap=True))
        if o.get("conditions"):
            v.addWidget(label(o["conditions"], "muted", wrap=True))
        if o.get("source_url"):
            src = label(f'<a href="{o["source_url"]}">Offer terms</a>', "muted")
            src.setOpenExternalLinks(True)
            v.addWidget(src)
        return f


# ---------------------------------------------------------------- tiles

class ProductTile(QFrame):
    clicked = Signal(dict)

    def __init__(self, p: dict, loader: ImageLoader, best: bool):
        super().__init__()
        self.p = p
        self.setObjectName("tile")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedWidth(250)
        cur = p.get("currency", "INR")
        v = QVBoxLayout(self); v.setContentsMargins(12, 12, 12, 12); v.setSpacing(6)

        top = QHBoxLayout()
        top.addWidget(label(p["store"], "storeBadge"))
        top.addStretch()
        if best:
            top.addWidget(label("BEST DEAL", "ribbon"))
        v.addLayout(top)
        img_row = QHBoxLayout(); img_row.addStretch()
        img_row.addWidget(image_slot(loader, p.get("image_url"), 170, p["title"]))
        img_row.addStretch()
        v.addLayout(img_row)

        title = label(p["title"], wrap=True)
        title.setMaximumHeight(40)
        title.setStyleSheet("font-weight:600;")
        v.addWidget(title)
        if p.get("rating"):
            r = QHBoxLayout()
            r.addWidget(label(f"{p['rating']:.1f} ★", "rating"))
            if p.get("rating_count"):
                r.addWidget(label(f"({p['rating_count']:,})", "muted"))
            r.addStretch()
            v.addLayout(r)

        pr = QHBoxLayout()
        pr.addWidget(label(money(p.get("price"), cur), "price"))
        if p.get("mrp") and p["mrp"] > (p.get("price") or 0):
            pr.addWidget(label(money(p["mrp"], cur), "mrp"))
        pct = discount_pct(p)
        if pct:
            pr.addWidget(label(f"{pct}% off", "off"))
        pr.addStretch()
        v.addLayout(pr)

        eff = p.get("effective_price")
        mine = best_user_offer(p)
        if eff is not None and eff < (p.get("price") or eff + 1):
            via = f" with {mine['card']}" if mine else " after offers"
            v.addWidget(label(f"{money(eff, cur)}{via}", "yourPrice", wrap=True))
        n = len(p.get("card_offers", [])) + len(p.get("other_offers", []))
        if n:
            v.addWidget(label(f"+{n} offer{'s' if n != 1 else ''} available", "muted"))
        v.addStretch()

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.p)
        super().mouseReleaseEvent(e)


class TileGrid(QWidget):
    """Reflows tiles into as many columns as fit, stretching them to fill the row."""
    MIN_W, GAP = 235, 14

    def __init__(self):
        super().__init__()
        self.grid = QGridLayout(self)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setSpacing(self.GAP)
        self.grid.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.tiles: list[QWidget] = []
        self.cols = 0

    def set_tiles(self, tiles: list[QWidget]) -> None:
        for t in self.tiles:
            t.setParent(None)
            t.deleteLater()
        for t in tiles:
            t.setMinimumWidth(self.MIN_W)
            t.setMaximumWidth(16777215)
        self.tiles = tiles
        self.cols = 0
        self._reflow()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._reflow()

    def _reflow(self) -> None:
        cols = max(1, (self.width() + self.GAP) // (self.MIN_W + self.GAP))
        if cols == self.cols:
            return
        for c in range(max(cols, self.cols)):
            self.grid.setColumnStretch(c, 1 if c < cols else 0)
        self.cols = cols
        for t in self.tiles:
            self.grid.removeWidget(t)
        for i, t in enumerate(self.tiles):
            self.grid.addWidget(t, i // cols, i % cols)


# ---------------------------------------------------------------- main window

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.settings = Settings()
        self.loader = ImageLoader()
        self.result: DealResult | None = None
        self.thread: QThread | None = None
        self.worker: SearchWorker | None = None
        self.last_query = ""

        self.setWindowTitle("DealScout — the best price, on your card")
        self.resize(1320, 860)
        root = QWidget(); root.setObjectName("page")
        self.setCentralWidget(root)
        col = QVBoxLayout(root); col.setContentsMargins(0, 0, 0, 0); col.setSpacing(0)
        col.addWidget(self._header())
        col.addWidget(self._category_bar())
        self.stack = QStackedWidget()
        col.addWidget(self.stack, 1)
        self.home = self._home_page()
        self.loading = self._loading_page()
        self.results = self._results_page()
        for w in (self.home, self.loading, self.results):
            self.stack.addWidget(w)
        self._refresh_cards()

    # ---- header
    def _header(self) -> QWidget:
        h = QFrame(); h.setObjectName("header")
        lay = QHBoxLayout(h); lay.setContentsMargins(22, 12, 22, 12); lay.setSpacing(12)
        brand = QVBoxLayout(); brand.setSpacing(0)
        name = QHBoxLayout(); name.setSpacing(0)
        name.addWidget(label("Deal", "logo")); name.addWidget(label("Scout", "logoAccent"))
        brand.addLayout(name)
        brand.addWidget(label("best price · best card offer", "tagline"))
        lay.addLayout(brand)
        lay.addSpacing(12)

        self.search = QLineEdit(); self.search.setObjectName("searchBox")
        self.search.setPlaceholderText("Describe what you need — e.g. \"lightweight laptop for college, good battery, under ₹60,000\"")
        self.search.returnPressed.connect(self.start_search)
        lay.addWidget(self.search, 1)
        self.budget = QLineEdit(); self.budget.setObjectName("budgetBox")
        self.budget.setPlaceholderText("Max budget (optional)")
        self.budget.setFixedWidth(170)
        self.budget.returnPressed.connect(self.start_search)
        lay.addWidget(self.budget)
        self.search_btn = QPushButton("🔍  Search"); self.search_btn.setObjectName("searchBtn")
        self.search_btn.clicked.connect(self.start_search)
        lay.addWidget(self.search_btn)
        self.cards_btn = QPushButton(); self.cards_btn.setObjectName("headerBtn")
        self.cards_btn.clicked.connect(self.edit_cards)
        lay.addWidget(self.cards_btn)
        gear = QPushButton("⚙  Settings"); gear.setObjectName("headerBtn")
        gear.clicked.connect(self.edit_settings)
        lay.addWidget(gear)
        return h

    def _category_bar(self) -> QWidget:
        bar = QFrame(); bar.setObjectName("catBar")
        lay = QHBoxLayout(bar); lay.setContentsMargins(22, 0, 22, 0); lay.setSpacing(4)
        for name, example in CATEGORIES:
            b = QPushButton(name); b.setObjectName("chip")
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _=False, ex=example: (self.search.setText(ex), self.search.setFocus()))
            lay.addWidget(b)
        lay.addStretch()
        return bar

    # ---- pages
    def _scroll(self, inner: QWidget) -> QScrollArea:
        s = QScrollArea(); s.setWidgetResizable(True); s.setWidget(inner)
        s.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        inner.setObjectName("page")
        return s

    def _home_page(self) -> QWidget:
        inner = QWidget()
        v = QVBoxLayout(inner); v.setContentsMargins(26, 22, 26, 22); v.setSpacing(18)
        hero = QFrame(); hero.setObjectName("hero")
        hv = QVBoxLayout(hero); hv.setContentsMargins(36, 34, 36, 34); hv.setSpacing(10)
        hv.addWidget(label("Tell us what you need.\nWe find the lowest price — and the best deal on your card.",
                           "heroTitle", wrap=True))
        hv.addWidget(label("DealScout searches the major stores live, checks every bank, card, coupon and "
                           "exchange offer it can find, and works out what you would actually pay.",
                           "heroText", wrap=True))
        v.addWidget(hero)

        steps = QHBoxLayout(); steps.setSpacing(14)
        for icon, head, text in [
            ("✍", "1. Describe it", "Write your requirement in plain words — features, use, budget."),
            ("💳", "2. Add your cards", "Pick your bank and card type. We match offers you qualify for."),
            ("🔎", "3. We search live", "Stores, bank offers, coupons, cashback and exchange deals."),
            ("🛒", "4. Buy at the best price", "Open the exact product page with one click."),
        ]:
            f = QFrame(); f.setObjectName("panel")
            fv = QVBoxLayout(f); fv.setContentsMargins(16, 16, 16, 16)
            ic = label(icon); ic.setStyleSheet("font-size:22pt;")
            fv.addWidget(ic)
            fv.addWidget(label(head, "sectionTitle"))
            fv.addWidget(label(text, "muted", wrap=True))
            steps.addWidget(f)
        v.addLayout(steps)

        cards_panel = QFrame(); cards_panel.setObjectName("panel")
        cv = QVBoxLayout(cards_panel); cv.setContentsMargins(18, 16, 18, 16)
        row = QHBoxLayout()
        row.addWidget(label("Your cards", "sectionTitle")); row.addStretch()
        manage = QPushButton("Manage cards"); manage.setObjectName("plainBtn"); manage.clicked.connect(self.edit_cards)
        row.addWidget(manage)
        cv.addLayout(row)
        self.home_cards = QHBoxLayout(); self.home_cards.setSpacing(10)
        cv.addLayout(self.home_cards)
        v.addWidget(cards_panel)
        v.addStretch()
        return self._scroll(inner)

    def _loading_page(self) -> QWidget:
        w = QWidget(); w.setObjectName("page")
        v = QVBoxLayout(w); v.setContentsMargins(0, 60, 0, 0)
        panel = QFrame(); panel.setObjectName("panel"); panel.setFixedWidth(720)
        pv = QVBoxLayout(panel); pv.setContentsMargins(28, 24, 28, 24); pv.setSpacing(12)
        self.loading_title = label("Searching stores…", "sectionTitle", wrap=True)
        pv.addWidget(self.loading_title)
        bar = QProgressBar(); bar.setRange(0, 0); bar.setTextVisible(False); bar.setFixedHeight(6)
        pv.addWidget(bar)
        pv.addWidget(label("Checking live prices, bank offers, coupons and exchange deals. "
                           "This usually takes a minute or two.", "muted", wrap=True))
        self.log = QListWidget(); self.log.setMinimumHeight(280)
        self.log.setStyleSheet("QListWidget { border:none; background:#fafbfc; } QListWidget::item { padding:4px; }")
        pv.addWidget(self.log)
        cancel = QPushButton("Cancel"); cancel.setObjectName("plainBtn"); cancel.clicked.connect(self.cancel_search)
        pv.addWidget(cancel, 0, Qt.AlignmentFlag.AlignRight)
        v.addWidget(panel, 0, Qt.AlignmentFlag.AlignHCenter)
        v.addStretch()
        return w

    def _results_page(self) -> QWidget:
        w = QWidget(); w.setObjectName("page")
        h = QHBoxLayout(w); h.setContentsMargins(18, 16, 18, 16); h.setSpacing(16)

        side = QFrame(); side.setObjectName("panel"); side.setFixedWidth(230)
        sv = QVBoxLayout(side); sv.setContentsMargins(14, 14, 14, 14); sv.setSpacing(8)
        sv.addWidget(label("Filters", "sectionTitle"))
        sv.addWidget(label("Sort by", "muted"))
        self.sort = QComboBox()
        self.sort.addItems(["Your best price", "Listed price: low to high", "Listed price: high to low",
                            "Biggest discount", "Customer rating"])
        self.sort.currentIndexChanged.connect(self.render_tiles)
        sv.addWidget(self.sort)
        self.only_mine = QCheckBox("Offers on my cards only")
        self.only_mine.toggled.connect(self.render_tiles)
        sv.addWidget(self.only_mine)
        self.in_stock = QCheckBox("In stock only")
        self.in_stock.toggled.connect(self.render_tiles)
        sv.addWidget(self.in_stock)
        sv.addSpacing(6)
        sv.addWidget(label("Stores", "muted"))
        self.store_box = QVBoxLayout(); self.store_box.setSpacing(4)
        sv.addLayout(self.store_box)
        sv.addStretch()
        h.addWidget(side)

        inner = QWidget()
        self.results_col = QVBoxLayout(inner)
        self.results_col.setContentsMargins(0, 0, 6, 0); self.results_col.setSpacing(14)
        self.best_holder = QVBoxLayout()
        self.results_col.addLayout(self.best_holder)
        self.summary = label("", wrap=True)
        self.results_col.addWidget(self.summary)
        self.count = label("", "sectionTitle")
        self.results_col.addWidget(self.count)
        self.grid = TileGrid()
        self.results_col.addWidget(self.grid)
        self.tips = label("", wrap=True)
        self.tips.setObjectName("panel"); self.tips.setContentsMargins(14, 12, 14, 12)
        self.results_col.addWidget(self.tips)
        self.sources = label("", "muted", wrap=True)
        self.sources.setOpenExternalLinks(True)
        self.results_col.addWidget(self.sources)
        self.results_col.addStretch()
        h.addWidget(self._scroll(inner), 1)
        self.store_checks: list[QCheckBox] = []
        return w

    # ---- cards / settings
    def _refresh_cards(self) -> None:
        n = len(self.settings.cards)
        self.cards_btn.setText(f"💳  My Cards ({n})")
        while self.home_cards.count():
            item = self.home_cards.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        if not self.settings.cards:
            self.home_cards.addWidget(label("No cards yet — add one to see offers you qualify for.", "muted"))
        for c in self.settings.cards:
            self.home_cards.addWidget(label(f"💳  {c.label()}", "cardChip"))
        self.home_cards.addStretch()

    def edit_cards(self) -> None:
        CardsDialog(self.settings, self).exec()
        self._refresh_cards()

    def edit_settings(self) -> None:
        SettingsDialog(self.settings, self).exec()

    # ---- search flow
    def start_search(self) -> None:
        query = self.search.text().strip()
        if not query or self.thread is not None:
            return
        key = self.settings.effective_api_key()
        if not key:
            QMessageBox.information(self, "API key needed",
                                    "DealScout needs an Anthropic API key to search the web.\n"
                                    "Add it in Settings.")
            self.edit_settings()
            key = self.settings.effective_api_key()
            if not key:
                return
        if not self.settings.cards:
            ask = QMessageBox.question(self, "No cards added",
                                       "You haven't added any cards, so card offers can't be matched to you.\n"
                                       "Add your cards first?")
            if ask == QMessageBox.StandardButton.Yes:
                self.edit_cards()

        self.last_query = query
        self.log.clear()
        self.loading_title.setText(f"Finding the best deal for “{query}”…")
        self.stack.setCurrentWidget(self.loading)
        self.search_btn.setEnabled(False)

        self.thread = QThread(self)
        self.worker = SearchWorker(query, list(self.settings.cards), self.settings.country,
                                   self.budget.text().strip(), self.settings.depth, key)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.progress.connect(self._progress)
        self.worker.done.connect(self._done)
        self.worker.failed.connect(self._failed)
        self.worker.done.connect(self.thread.quit)
        self.worker.failed.connect(self.thread.quit)
        self.thread.finished.connect(self._cleanup)
        self.thread.start()

    def cancel_search(self) -> None:
        if self.worker:
            self.worker.cancelled = True
            self.log.addItem("Cancelling…")

    def _progress(self, msg: str) -> None:
        self.log.addItem(msg)
        self.log.scrollToBottom()

    def _cleanup(self) -> None:
        self.thread.deleteLater()
        self.worker.deleteLater()
        self.thread = self.worker = None
        self.search_btn.setEnabled(True)

    def _failed(self, msg: str) -> None:
        self.stack.setCurrentWidget(self.results if self.result else self.home)
        if msg != "Search cancelled.":
            QMessageBox.warning(self, "Search failed", msg)

    def _done(self, result: DealResult) -> None:
        self.result = result
        self._build_store_filters()
        self._build_best_banner()
        self.summary.setText(result.summary)
        if result.tips:
            self.tips.setText("<b>💡 Buying tips</b><br>" + "<br>".join(f"• {t}" for t in result.tips))
            self.tips.show()
        else:
            self.tips.hide()
        links = [f'<a href="{u}">{(t or u)[:70]}</a>' for t, u in result.sources[:12]]
        self.sources.setText(("<b>Sources checked:</b> " + " · ".join(links)) if links else "")
        self.sort.setCurrentIndex(0)
        self.render_tiles()
        self.stack.setCurrentWidget(self.results)

    def _build_store_filters(self) -> None:
        for cb in self.store_checks:
            cb.setParent(None); cb.deleteLater()
        self.store_checks = []
        for store in sorted({p["store"] for p in self.result.products}):
            cb = QCheckBox(store); cb.setChecked(True)
            cb.toggled.connect(self.render_tiles)
            self.store_box.addWidget(cb)
            self.store_checks.append(cb)

    def _build_best_banner(self) -> None:
        while self.best_holder.count():
            item = self.best_holder.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        p = self.result.products[self.result.best_index]
        cur = p.get("currency", "INR")
        f = QFrame(); f.setObjectName("bestBanner")
        h = QHBoxLayout(f); h.setContentsMargins(18, 16, 18, 16); h.setSpacing(18)
        h.addWidget(image_slot(self.loader, p.get("image_url"), 150, p["title"]))
        v = QVBoxLayout(); v.setSpacing(6)
        top = QHBoxLayout()
        top.addWidget(label("🏆 BEST DEAL FOR YOU", "ribbon")); top.addWidget(label(p["store"], "storeBadge"))
        top.addStretch()
        v.addLayout(top)
        t = label(p["title"], wrap=True); t.setStyleSheet("font-size:14pt; font-weight:700;")
        v.addWidget(t)
        pr = QHBoxLayout()
        eff = p.get("effective_price")
        pr.addWidget(label(money(eff if eff is not None else p.get("price"), cur), "bigPrice"))
        if eff is not None and eff < (p.get("price") or 0):
            pr.addWidget(label(money(p["price"], cur), "mrp"))
        pr.addStretch()
        v.addLayout(pr)
        if p.get("effective_price_note"):
            v.addWidget(label(p["effective_price_note"], "yourPrice", wrap=True))
        v.addWidget(label(self.result.best_reason, "muted", wrap=True))
        btns = QHBoxLayout()
        buy = QPushButton(f"Buy on {p['store']}  →"); buy.setObjectName("buyBtn")
        buy.clicked.connect(lambda: open_url(p["url"]))
        more = QPushButton("View all offers"); more.setObjectName("plainBtn")
        more.clicked.connect(lambda: self.show_product(p))
        btns.addWidget(buy); btns.addWidget(more); btns.addStretch()
        v.addLayout(btns)
        h.addLayout(v, 1)
        self.best_holder.addWidget(f)

    def render_tiles(self) -> None:
        if not self.result:
            return
        stores = {cb.text() for cb in self.store_checks if cb.isChecked()}
        items = [p for p in self.result.products if p["store"] in stores]
        if self.only_mine.isChecked():
            items = [p for p in items if best_user_offer(p)]
        if self.in_stock.isChecked():
            items = [p for p in items if p.get("in_stock") is not False]
        big = float("inf")
        keys = [
            lambda p: p.get("effective_price") if p.get("effective_price") is not None else p.get("price") or big,
            lambda p: p.get("price") or big,
            lambda p: -(p.get("price") or 0),
            lambda p: -(discount_pct(p) or 0),
            lambda p: -(p.get("rating") or 0),
        ]
        items.sort(key=keys[self.sort.currentIndex()])
        best = self.result.products[self.result.best_index]
        tiles = []
        for p in items:
            t = ProductTile(p, self.loader, p is best)
            t.clicked.connect(self.show_product)
            tiles.append(t)
        self.count.setText(f"{len(items)} results for “{self.last_query}”")
        self.grid.set_tiles(tiles)

    def show_product(self, p: dict) -> None:
        ProductDialog(p, self.loader, self).exec()

    def closeEvent(self, e):
        if self.worker:
            self.worker.cancelled = True
        if self.thread:
            self.thread.quit()
            self.thread.wait(3000)
        super().closeEvent(e)


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("DealScout")
    app.setStyleSheet(STYLE)
    f = QFont("Segoe UI", 10)
    app.setFont(f)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
