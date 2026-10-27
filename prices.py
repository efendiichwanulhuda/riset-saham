"""Data harga dari Yahoo Finance dan indikator teknikal sederhana."""

from __future__ import annotations

import pandas as pd
import yfinance as yf

from tickers import yahoo_symbol


def download_history(codes: list[str], period: str = "6mo") -> dict[str, pd.DataFrame]:
    """Riwayat harga harian per kode saham. Saham yang gagal diunduh dilewati."""
    if not codes:
        return {}
    symbols = [yahoo_symbol(c) for c in codes]
    raw = yf.download(symbols, period=period, interval="1d", group_by="ticker",
                      auto_adjust=False, progress=False, threads=True)
    out = {}
    for code, sym in zip(codes, symbols):
        try:
            df = raw[sym] if isinstance(raw.columns, pd.MultiIndex) else raw
            df = df.dropna(subset=["Close"])
            if len(df) >= 2:
                out[code] = df
        except KeyError:
            continue
    return out


def intraday(code: str, interval: str = "5m", period: str = "5d") -> pd.DataFrame | None:
    """Data harga per 5 menit beberapa hari terakhir (tertunda sekitar 15 menit)."""
    df = yf.download(yahoo_symbol(code), period=period, interval=interval, auto_adjust=False, progress=False)
    if df is None or df.empty:
        return None
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df.dropna(subset=["Close"])


def rsi(close: pd.Series, period: int = 14) -> float:
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / period, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / period, adjust=False).mean()
    rs = gain / loss.replace(0, float("nan"))
    value = 100 - 100 / (1 + rs)
    return float(value.iloc[-1]) if pd.notna(value.iloc[-1]) else 100.0


def indicators(df: pd.DataFrame) -> dict:
    close, vol = df["Close"], df["Volume"]
    last = float(close.iloc[-1])

    def pct(n: int) -> float:
        return (last / float(close.iloc[-1 - n]) - 1) * 100 if len(close) > n else float("nan")

    ma20 = float(close.tail(20).mean())
    ma50 = float(close.tail(50).mean())
    avg_vol20 = float(vol.tail(21).iloc[:-1].mean()) if len(vol) > 1 else float("nan")
    return {
        "harga": last,
        "chg_1d": pct(1),
        "chg_5d": pct(5),
        "chg_1m": pct(21),
        "vs_ma20": (last / ma20 - 1) * 100,
        "ma20_gt_ma50": ma20 > ma50,
        "vol_ratio": float(vol.iloc[-1]) / avg_vol20 if avg_vol20 else float("nan"),
        "rsi14": rsi(close),
        "tanggal": df.index[-1].date(),
    }


def technical_score(ind: dict) -> float:
    """Skor momentum -5..+5: tren di atas MA20, MA20>MA50, volume naik, RSI tidak jenuh beli."""
    s = 0.0
    s += max(-2.0, min(2.0, ind["vs_ma20"] / 3))
    s += 1.0 if ind["ma20_gt_ma50"] else -1.0
    vr = ind["vol_ratio"]
    if vr == vr and vr > 1.5:  # vr == vr -> bukan NaN
        s += 1.0 if ind["chg_1d"] >= 0 else -1.0
    r = ind["rsi14"]
    if r > 75:
        s -= 1.5  # sudah naik terlalu tinggi, rawan koreksi
    elif r < 30:
        s += 0.5  # jenuh jual, peluang pantulan
    elif 50 <= r <= 70:
        s += 1.0
    return max(-5.0, min(5.0, s))


FUNDAMENTAL_FIELDS = {
    "marketCap": "Kapitalisasi pasar",
    "trailingPE": "PER",
    "priceToBook": "PBV",
    "returnOnEquity": "ROE",
    "profitMargins": "Margin laba bersih",
    "revenueGrowth": "Pertumbuhan pendapatan (YoY)",
    "earningsGrowth": "Pertumbuhan laba (YoY)",
    "debtToEquity": "Utang/ekuitas",
    "dividendYield": "Dividen yield",
    "fiftyTwoWeekHigh": "Harga tertinggi 52 minggu",
    "fiftyTwoWeekLow": "Harga terendah 52 minggu",
}


def fundamentals(code: str) -> dict:
    """Data fundamental ringkas dari Yahoo Finance. Kosong bila tidak tersedia."""
    try:
        info = yf.Ticker(yahoo_symbol(code)).info or {}
    except Exception:
        return {}
    return {label: info[key] for key, label in FUNDAMENTAL_FIELDS.items() if info.get(key) is not None}



KEYSTAT_ROWS = {
    "Laba bersih": ["Net Income", "Net Income Common Stockholders"],
    "EPS": ["Diluted EPS", "Basic EPS"],
    "Pendapatan": ["Total Revenue", "Operating Revenue"],
}


def _pick(stmt: pd.DataFrame, names: list[str]) -> pd.Series:
    for n in names:
        if stmt is not None and n in stmt.index:
            return stmt.loc[n].dropna()
    return pd.Series(dtype=float)


def keystats(code: str) -> dict[str, dict[str, pd.Series]]:
    """Laporan laba rugi per kuartal dan per tahun dari Yahoo Finance.

    Hasil: {"Laba bersih": {"kuartal": Series, "tahunan": Series}, ...}, index berupa tanggal akhir periode.
    """
    try:
        t = yf.Ticker(yahoo_symbol(code))
        q, a = t.quarterly_income_stmt, t.income_stmt
    except Exception:
        return {}
    out = {}
    for label, names in KEYSTAT_ROWS.items():
        qs, ys = _pick(q, names), _pick(a, names)
        if len(qs) or len(ys):
            out[label] = {"kuartal": qs.sort_index(), "tahunan": ys.sort_index()}
    return out
