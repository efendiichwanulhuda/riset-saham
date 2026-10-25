"""Ambil berita pasar modal, deteksi kode saham, dan beri skor sentimen."""

from __future__ import annotations

import html
import math
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from urllib.parse import quote_plus

import feedparser
import requests

from tickers import NOT_TICKERS, TICKERS

USER_AGENT = "Mozilla/5.0 (RisetSaham/1.0)"


def google_news(query: str) -> str:
    return f"https://news.google.com/rss/search?q={quote_plus(query)}&hl=id&gl=ID&ceid=ID:id"


# Sumber berita umum. Kalau salah satu tidak bisa diakses, aplikasi tetap jalan
# dengan sumber lain (statusnya terlihat di sidebar).
FEEDS = {
    "Google News: saham": google_news("saham when:2d"),
    "Google News: IHSG": google_news("IHSG saham naik when:2d"),
    "Google News: emiten": google_news("emiten laba dividen when:3d"),
    "CNBC Indonesia Market": "https://www.cnbcindonesia.com/market/rss",
    "Kontan Investasi": "https://investasi.kontan.co.id/rss",
    "Bisnis Market": "https://market.bisnis.com/rss",
    "IDX Channel": "https://www.idxchannel.com/rss",
}

# Kata/frasa dan bobotnya. Positif = cenderung mendorong harga, negatif = sebaliknya.
# Frasa yang lebih panjang dicek lebih dulu supaya "tidak naik" tidak dihitung sebagai "naik".
LEXICON = {
    # positif kuat
    "laba melonjak": 3, "laba naik": 2.5, "laba bersih naik": 2.5, "laba tumbuh": 2.5,
    "rekor laba": 3, "cetak rekor": 2.5, "rekor tertinggi": 2, "all time high": 2,
    "pendapatan naik": 2, "pendapatan tumbuh": 2, "penjualan naik": 2, "kinerja moncer": 2.5,
    "dividen jumbo": 3, "dividen interim": 2, "bagi dividen": 2, "tebar dividen": 2, "dividen": 1,
    "buyback": 2, "pembelian kembali saham": 2, "akuisisi": 1.5, "ekspansi": 1.5,
    "kontrak baru": 2, "raih kontrak": 2, "proyek baru": 1.5, "kerja sama strategis": 1.5,
    "net buy": 2, "asing borong": 2.5, "borong saham": 2, "akumulasi": 1.5, "inflow": 1,
    "target harga naik": 2.5, "rekomendasi beli": 2, "buy on weakness": 1, "upgrade": 2,
    "ara": 2, "auto reject atas": 2, "melesat": 2, "meroket": 2, "melonjak": 2, "terbang": 1.5,
    "menguat": 1, "naik": 0.8, "rebound": 1.5, "bullish": 1.5, "prospek cerah": 2, "positif": 0.8,
    "stock split": 1, "masuk indeks": 1.5, "msci": 0.5, "lq45": 0.3,
    # negatif kuat
    "rugi bersih": -3, "merugi": -2.5, "kerugian": -2, "laba turun": -2.5, "laba anjlok": -3,
    "pendapatan turun": -2, "penjualan turun": -2, "gagal bayar": -3.5, "default": -2.5,
    "pkpu": -3, "pailit": -3.5, "suspensi": -3, "disuspensi": -3, "delisting": -3.5,
    "notasi khusus": -2, "full call auction": -1.5, "unusual market activity": -1, "uma": -1,
    "net sell": -2, "asing lepas": -2.5, "jual saham": -1, "outflow": -1, "aksi jual": -1.5,
    "target harga turun": -2.5, "rekomendasi jual": -2, "downgrade": -2, "arb": -2,
    "auto reject bawah": -2, "anjlok": -2, "ambruk": -2.5, "longsor": -2, "terjun": -2,
    "melemah": -1, "turun": -0.8, "koreksi": -1, "bearish": -1.5, "tekanan": -1,
    "gugatan": -1.5, "kasus": -1, "korupsi": -2.5, "denda": -1.5, "sanksi": -1.5,
    "right issue": -0.5, "dilusi": -1.5, "negatif": -0.8,
}
NEGATORS = ("tidak ", "tak ", "belum ", "gagal ")
_LEXICON_SORTED = sorted(LEXICON.items(), key=lambda kv: -len(kv[0]))

# Kode saham lain (misalnya semua emiten BEI) yang juga dikenali bila ditulis kapital di berita.
KNOWN_CODES: set[str] = set()

CODE_RE = re.compile(r"\b([A-Z]{4})\b")
TAG_RE = re.compile(r"<[^>]+>")


@dataclass
class Article:
    title: str
    link: str
    source: str
    published: datetime
    summary: str = ""
    tickers: list[str] = field(default_factory=list)
    sentiment: float = 0.0
    hits: list[str] = field(default_factory=list)

    @property
    def age_hours(self) -> float:
        return max(0.0, (datetime.now(timezone.utc) - self.published).total_seconds() / 3600)


def clean(text: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(TAG_RE.sub(" ", text or ""))).strip()


def detect_tickers(text: str) -> list[str]:
    """Cari kode saham (huruf kapital) dan nama perusahaan di teks."""
    found = []
    for code in CODE_RE.findall(text):
        if (code in TICKERS or code in KNOWN_CODES) and code not in NOT_TICKERS and code not in found:
            found.append(code)
    lower = " " + text.lower() + " "
    for code, (_, _, aliases) in TICKERS.items():
        if code in found:
            continue
        for alias in aliases:
            if re.search(rf"(?<![a-z0-9]){re.escape(alias)}(?![a-z0-9])", lower):
                found.append(code)
                break
    return found


def score_sentiment(text: str) -> tuple[float, list[str]]:
    """Skor sentimen berbasis kamus kata; hasilnya dibatasi antara -5 dan +5."""
    lower = " " + text.lower() + " "
    used = [False] * len(lower)
    total, hits = 0.0, []
    for phrase, weight in _LEXICON_SORTED:
        for m in re.finditer(rf"(?<![a-z0-9]){re.escape(phrase)}(?![a-z0-9])", lower):
            s, e = m.span()
            if any(used[s:e]):
                continue
            for i in range(s, e):
                used[i] = True
            w = weight
            if any(lower[max(0, s - len(n)):s] == n for n in NEGATORS):
                w = -w * 0.7
            total += w
            hits.append(f"{phrase} ({w:+.1f})")
    return max(-5.0, min(5.0, total)), hits


def _published(entry) -> datetime:
    t = entry.get("published_parsed") or entry.get("updated_parsed")
    if t:
        return datetime.fromtimestamp(time.mktime(t), tz=timezone.utc)
    return datetime.now(timezone.utc)


def parse_feed(raw: bytes | str, source: str) -> list[Article]:
    feed = feedparser.parse(raw)
    out = []
    for e in feed.entries:
        title = clean(e.get("title", ""))
        if not title:
            continue
        src = source
        # Judul Google News berformat "Judul - Nama Media"
        if source.startswith("Google News") and " - " in title:
            title, src = title.rsplit(" - ", 1)
        summary = clean(e.get("summary", ""))
        if summary.startswith(title[:40]):
            summary = ""  # ringkasan Google News hanya mengulang judul
        art = Article(title=title, link=e.get("link", ""), source=src,
                      published=_published(e), summary=summary[:400])
        text = f"{art.title}. {art.summary}"
        art.tickers = detect_tickers(text)
        art.sentiment, art.hits = score_sentiment(text)
        out.append(art)
    return out


def fetch_feed(url: str, source: str, timeout: float = 12) -> list[Article]:
    r = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=timeout)
    r.raise_for_status()
    return parse_feed(r.content, source)


def fetch_all(extra_queries: list[str] | None = None) -> tuple[list[Article], dict[str, str]]:
    """Ambil semua sumber. Mengembalikan (artikel unik, status per sumber)."""
    feeds = dict(FEEDS)
    for q in extra_queries or []:
        feeds[f"Google News: {q}"] = google_news(f"{q} when:7d")
    articles, status = [], {}
    for name, url in feeds.items():
        try:
            items = fetch_feed(url, name)
            articles.extend(items)
            status[name] = f"OK ({len(items)} berita)"
        except Exception as exc:  # sumber gagal tidak boleh menghentikan aplikasi
            status[name] = f"Gagal: {type(exc).__name__}"
    seen, unique = set(), []
    for a in sorted(articles, key=lambda a: a.published, reverse=True):
        key = re.sub(r"\W+", "", a.title.lower())[:80]
        if key not in seen:
            seen.add(key)
            unique.append(a)
    return unique, status


def recency_weight(age_hours: float, half_life_hours: float = 24) -> float:
    """Berita makin lama makin kecil bobotnya (setengahnya tiap 24 jam)."""
    return math.pow(0.5, age_hours / half_life_hours)


def aggregate_by_ticker(articles: list[Article]) -> dict[str, dict]:
    """Ringkasan per saham: jumlah berita, skor berita tertimbang waktu, daftar berita."""
    agg: dict[str, dict] = {}
    for a in articles:
        for code in a.tickers:
            d = agg.setdefault(code, {"count": 0, "positive": 0, "negative": 0,
                                      "news_score": 0.0, "articles": []})
            d["count"] += 1
            d["positive"] += a.sentiment > 0
            d["negative"] += a.sentiment < 0
            d["news_score"] += a.sentiment * recency_weight(a.age_hours)
            d["articles"].append(a)
    return agg
