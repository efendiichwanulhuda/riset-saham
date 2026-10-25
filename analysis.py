"""Analisis detail dari data harian: level harga, peta volume, akumulasi/distribusi, dan checklist.

Catatan: order book (antrian bid/offer) dan broker summary BEI tidak tersedia gratis.
Peta volume per harga di sini adalah pendekatannya: di harga mana transaksi paling banyak terjadi.
"""

from __future__ import annotations

import math

import pandas as pd

# Batas auto reject BEI (persen dari harga penutupan sebelumnya) per rentang harga.
# Aturan ini pernah berubah; cek pengumuman BEI terbaru dan sesuaikan bila perlu.
ARA_TIERS = [(200, 0.35), (5000, 0.25), (math.inf, 0.20)]
ARB_TIERS = [(200, 0.35), (5000, 0.25), (math.inf, 0.20)]
MIN_PRICE = 50


def tick_size(price: float) -> int:
    """Fraksi harga BEI."""
    if price < 200:
        return 1
    if price < 500:
        return 2
    if price < 2000:
        return 5
    if price < 5000:
        return 10
    return 25


def to_tick(price: float, mode: str = "nearest") -> float:
    t = tick_size(price)
    f = {"down": math.floor, "up": math.ceil}.get(mode, round)
    return float(f(price / t) * t)


def _tier(price: float, tiers) -> float:
    return next(pct for limit, pct in tiers if price <= limit)


def auto_reject(prev_close: float) -> tuple[float, float]:
    """Perkiraan harga ARA dan ARB untuk hari bursa berikutnya."""
    ara = to_tick(prev_close * (1 + _tier(prev_close, ARA_TIERS)), "down")
    arb = max(MIN_PRICE, to_tick(prev_close * (1 - _tier(prev_close, ARB_TIERS)), "up"))
    return ara, arb


def atr(df: pd.DataFrame, period: int = 14) -> float:
    prev = df["Close"].shift()
    tr = pd.concat([df["High"] - df["Low"], (df["High"] - prev).abs(), (df["Low"] - prev).abs()], axis=1).max(axis=1)
    return float(tr.tail(period).mean())


def volume_profile(df: pd.DataFrame, days: int = 60, bins: int = 12) -> pd.DataFrame:
    """Total volume per rentang harga dalam `days` hari terakhir."""
    recent = df.tail(days)
    typical = (recent["High"] + recent["Low"] + recent["Close"]) / 3
    lo, hi = float(recent["Low"].min()), float(recent["High"].max())
    if hi <= lo:
        hi = lo + 1
    edges = [lo + (hi - lo) * i / bins for i in range(bins + 1)]
    cats = pd.cut(typical, edges, include_lowest=True, labels=False)
    vol = recent["Volume"].groupby(cats).sum().reindex(range(bins), fill_value=0)
    out = pd.DataFrame({
        "dari": [edges[i] for i in range(bins)],
        "sampai": [edges[i + 1] for i in range(bins)],
        "volume": vol.values.astype(float),
    })
    out["tengah"] = (out["dari"] + out["sampai"]) / 2
    total = out["volume"].sum() or 1
    out["persen"] = out["volume"] / total * 100
    out["rentang"] = [f"Rp {to_tick(a):,.0f} – {to_tick(b):,.0f}" for a, b in zip(out["dari"], out["sampai"])]
    return out


def money_flow(df: pd.DataFrame, period: int = 14) -> float:
    """Money Flow Index: RSI yang memperhitungkan volume (0–100)."""
    tp = (df["High"] + df["Low"] + df["Close"]) / 3
    mf = tp * df["Volume"]
    up = mf.where(tp > tp.shift(), 0).tail(period).sum()
    down = mf.where(tp < tp.shift(), 0).tail(period).sum()
    return 100.0 if down == 0 else float(100 - 100 / (1 + up / down))


def _slope_pct(series: pd.Series, days: int = 20) -> float:
    s = series.tail(days)
    base = s.abs().mean() or 1
    return float((s.iloc[-1] - s.iloc[0]) / base * 100)


def accumulation(df: pd.DataFrame, days: int = 20) -> dict:
    close, vol = df["Close"], df["Volume"]
    direction = close.diff().apply(lambda x: 1 if x > 0 else -1 if x < 0 else 0)
    obv = (direction * vol).cumsum()
    rng = (df["High"] - df["Low"]).replace(0, float("nan"))
    clv = (((close - df["Low"]) - (df["High"] - close)) / rng).fillna(0)
    ad = (clv * vol).cumsum()
    avg = vol.rolling(20).mean()
    recent = df.tail(days).index
    big = vol.loc[recent] > avg.loc[recent]
    acc_days = int(((direction.loc[recent] > 0) & big).sum())
    dist_days = int(((direction.loc[recent] < 0) & big).sum())
    obv_trend, ad_trend = _slope_pct(obv, days), _slope_pct(ad, days)
    mfi = money_flow(df)
    score = (obv_trend > 0) + (ad_trend > 0) + (acc_days > dist_days) + (mfi > 50)
    verdict = "Akumulasi" if score >= 3 else "Distribusi" if score <= 1 else "Netral"
    return {"obv_trend": obv_trend, "ad_trend": ad_trend, "acc_days": acc_days, "dist_days": dist_days,
            "mfi": mfi, "verdict": verdict, "days": days}


def pivots(df: pd.DataFrame) -> dict:
    h, l, c = float(df["High"].iloc[-1]), float(df["Low"].iloc[-1]), float(df["Close"].iloc[-1])
    p = (h + l + c) / 3
    return {"R2": to_tick(p + (h - l)), "R1": to_tick(2 * p - l), "Pivot": to_tick(p),
            "S1": to_tick(2 * p - h), "S2": to_tick(p - (h - l))}


def key_levels(df: pd.DataFrame, vp: pd.DataFrame) -> dict:
    """Area beli, stop loss, dan target berdasarkan support/resistance, peta volume, dan ATR."""
    price = float(df["Close"].iloc[-1])
    a = atr(df)
    low20, high20 = float(df["Low"].tail(20).min()), float(df["High"].tail(20).max())
    below = vp[vp["sampai"] <= price]
    above = vp[vp["dari"] >= price]
    vol_support = float(below.loc[below["volume"].idxmax(), "tengah"]) if not below.empty else low20
    vol_resist = float(above.loc[above["volume"].idxmax(), "tengah"]) if not above.empty else high20
    support = max(low20, vol_support) if vol_support < price else low20
    resistance = min(high20, vol_resist) if vol_resist > price else high20
    stop = to_tick(min(support, price - a) - 0.5 * a, "down")
    entry_low = to_tick(max(support, price - a), "down")
    t1 = to_tick(max(resistance, price + 1.5 * a), "up")
    t2 = to_tick(max(float(df["High"].tail(120).max()), price + 3 * a), "up")
    risk = price - stop
    return {
        "harga": price, "atr": a, "support": to_tick(support), "resistance": to_tick(resistance),
        "entry_low": entry_low, "entry_high": to_tick(price),
        "stop": stop, "t1": t1, "t2": t2,
        "risk_pct": risk / price * 100, "t1_pct": (t1 / price - 1) * 100, "t2_pct": (t2 / price - 1) * 100,
        "rr1": (t1 - price) / risk if risk > 0 else float("nan"),
    }


def _ok(cond: bool | None, good: str, bad: str, neutral: str | None = None) -> tuple[str, str]:
    if cond is None:
        return "⚪", neutral or bad
    return ("✅", good) if cond else ("⚠️", bad)


def checklist(ind: dict, acc: dict, lv: dict, fund: dict) -> list[tuple[str, str]]:
    items = [
        _ok(ind["vs_ma20"] > 0, f"Harga di atas MA20 ({ind['vs_ma20']:+.1f}%), tren jangka pendek naik",
            f"Harga di bawah MA20 ({ind['vs_ma20']:+.1f}%), tren jangka pendek lemah"),
        _ok(ind["ma20_gt_ma50"], "MA20 di atas MA50, tren menengah naik", "MA20 di bawah MA50, tren menengah turun"),
        _ok(45 <= ind["rsi14"] <= 70, f"RSI {ind['rsi14']:.0f}, momentum sehat",
            f"RSI {ind['rsi14']:.0f}, " + ("jenuh beli, rawan koreksi" if ind["rsi14"] > 70 else "momentum lemah")),
        _ok(acc["verdict"] == "Akumulasi", f"Pola volume menunjukkan akumulasi ({acc['acc_days']} hari naik bervolume besar vs {acc['dist_days']} hari turun)",
            f"Pola volume: {acc['verdict'].lower()} ({acc['acc_days']} hari naik bervolume besar vs {acc['dist_days']} hari turun)"),
        _ok(acc["mfi"] > 50, f"Money Flow {acc['mfi']:.0f}, uang cenderung masuk", f"Money Flow {acc['mfi']:.0f}, uang cenderung keluar"),
        _ok(lv["rr1"] >= 1.5 if lv["rr1"] == lv["rr1"] else None,
            f"Rasio untung/rugi ke target 1 = {lv['rr1']:.1f}x (layak)",
            f"Rasio untung/rugi ke target 1 = {lv['rr1']:.1f}x (kurang menarik, idealnya ≥1.5x)"),
    ]
    pe, pbv, roe = fund.get("PER"), fund.get("PBV"), fund.get("ROE")
    if pe is not None:
        items.append(_ok(0 < pe <= 15, f"PER {pe:.1f}x, valuasi relatif murah/wajar", f"PER {pe:.1f}x, valuasi relatif mahal atau laba negatif"))
    if pbv is not None:
        items.append(_ok(pbv <= 3, f"PBV {pbv:.1f}x, tidak terlalu mahal terhadap aset", f"PBV {pbv:.1f}x, mahal terhadap nilai buku"))
    if roe is not None:
        items.append(_ok(roe >= 0.12, f"ROE {roe * 100:.0f}%, perusahaan efisien menghasilkan laba", f"ROE {roe * 100:.0f}%, profitabilitas rendah"))
    return items


def interpret_fundamental(label: str, value) -> str:
    if not isinstance(value, (int, float)):
        return ""
    rules = {
        "PER": lambda v: "laba negatif" if v <= 0 else "murah" if v < 10 else "wajar" if v <= 20 else "mahal",
        "PBV": lambda v: "di bawah nilai buku" if v < 1 else "wajar" if v <= 3 else "mahal",
        "ROE": lambda v: "sangat baik" if v >= 0.2 else "baik" if v >= 0.12 else "rendah",
        "Margin laba bersih": lambda v: "tinggi" if v >= 0.15 else "sedang" if v >= 0.05 else "tipis",
        "Pertumbuhan pendapatan (YoY)": lambda v: "tumbuh" if v > 0 else "turun",
        "Pertumbuhan laba (YoY)": lambda v: "tumbuh" if v > 0 else "turun",
        "Utang/ekuitas": lambda v: "rendah" if v < 50 else "sedang" if v <= 150 else "tinggi",
        "Dividen yield": lambda v: "tinggi" if v >= 5 else "sedang" if v >= 2 else "kecil",
    }
    return rules[label](value) if label in rules else ""


def format_fundamental(label: str, value) -> str:
    if not isinstance(value, (int, float)):
        return str(value)
    if label in {"ROE", "Margin laba bersih", "Pertumbuhan pendapatan (YoY)", "Pertumbuhan laba (YoY)"}:
        return f"{value * 100:.1f}%"
    if label == "Dividen yield":
        return f"{value:.2f}%"
    if label == "Kapitalisasi pasar":
        return f"Rp {value / 1e12:,.1f} triliun"
    if label in {"PER", "PBV"}:
        return f"{value:.1f}x"
    if label.startswith("Harga"):
        return f"Rp {value:,.0f}"
    return f"{value:,.1f}"


ORDERBOOK_GUIDE = """
Buka saham ini di Stockbit, lalu cek hal berikut sebelum membeli:

1. **Order book (bid/offer)**: kalau antrian **bid** (beli) jauh lebih tebal daripada **offer** (jual) di beberapa level di bawah harga sekarang, ada penopang harga. Offer yang sangat tebal tepat di atas harga berarti ada "tembok" yang harus ditembus.
2. **Bandingkan dengan peta volume** di atas: level bid tebal yang sama dengan zona volume besar adalah support yang lebih kuat.
3. **Broker summary**: lihat apakah broker pembeli terbesar (net buy) konsisten selama beberapa hari. Pembelian besar oleh sedikit broker sering jadi tanda akumulasi.
4. **Foreign flow**: net buy asing beberapa hari berturut-turut biasanya mendukung kenaikan saham berkapitalisasi besar.
5. **Running trade**: transaksi besar yang terus "HAKA" (langsung membeli di harga offer) menandakan pembeli agresif.
6. **Trade book**: lihat lot yang terjadi di tiap harga. Kalau transaksi di harga offer (HAKA, pembeli agresif) lebih banyak daripada di harga bid (HAKI, penjual agresif), pembeli sedang menguasai. Bandingkan dengan tabel tekanan beli/jual di atas.
7. **Jangan kejar harga** yang sudah dekat ARA atau jauh di atas area beli; pasang antrian di area beli dan siapkan stop loss.
"""


def keystats_table(data: dict[str, pd.Series], years: int = 3) -> pd.DataFrame:
    """Tabel ala Keystats Stockbit: baris Q1–Q4, Tahunan, TTM; kolom tahun terbaru di kiri."""
    q, a = data["kuartal"], data["tahunan"]
    yrs = sorted({d.year for d in q.index} | {d.year for d in a.index}, reverse=True)[:years]
    table = pd.DataFrame(index=["Q1", "Q2", "Q3", "Q4", "Tahunan", "TTM"], columns=yrs, dtype=float)
    for d, v in q.items():
        if d.year in yrs:
            table.loc[f"Q{(d.month - 1) // 3 + 1}", d.year] = v
    for y in yrs:
        annual = a[[d.year == y for d in a.index]]
        if len(annual):
            table.loc["Tahunan", y] = annual.iloc[-1]
        quarters = q[[d.year == y for d in q.index]]
        if len(quarters):
            last = quarters.index.max()
            prev = q[q.index <= last].tail(4)
            if len(prev) == 4:
                table.loc["TTM", y] = prev.sum()
    return table


def keystats_checks(data: dict[str, dict[str, pd.Series]]) -> list[tuple[str, str]]:
    """Pertumbuhan YoY kuartal terakhir dan tren laba, dalam bahasa sederhana."""
    items = []
    for label in ("Pendapatan", "Laba bersih", "EPS"):
        if label not in data:
            continue
        q = data[label]["kuartal"]
        if len(q) == 0:
            continue
        last_d, last_v = q.index[-1], q.iloc[-1]
        q_name = f"Q{(last_d.month - 1) // 3 + 1} {last_d.year}"
        same = q[[d.year == last_d.year - 1 and d.month == last_d.month for d in q.index]]
        if len(same) and same.iloc[0] != 0:
            prev = same.iloc[0]
            if prev < 0 <= last_v:
                items.append(("✅", f"{label} {q_name} berbalik positif dari negatif setahun lalu (turnaround)"))
            elif last_v < 0 <= prev:
                items.append(("⚠️", f"{label} {q_name} berbalik negatif (rugi) dari positif setahun lalu"))
            else:
                g = (last_v / prev - 1) * 100 * (1 if prev > 0 else -1)
                items.append(("✅" if g > 0 else "⚠️", f"{label} {q_name} {g:+.0f}% dibanding kuartal yang sama tahun lalu"))
        elif last_v < 0:
            items.append(("⚠️", f"{label} {q_name} negatif (rugi)"))
    return items


def trade_pressure(df: pd.DataFrame, days: int = 10) -> pd.DataFrame:
    """Perkiraan tekanan beli vs jual harian dari posisi harga penutupan dalam rentang hari itu.

    Tutup di dekat harga tertinggi = pembeli dominan; dekat terendah = penjual dominan.
    Ini BUKAN trade book asli (yang mencatat setiap transaksi HAKA/HAKI per harga).
    """
    recent = df.tail(days + 1)
    rng = (recent["High"] - recent["Low"]).replace(0, float("nan"))
    buy = ((recent["Close"] - recent["Low"]) / rng).fillna(0.5).clip(0, 1)
    out = pd.DataFrame({
        "Tanggal": recent.index.date,
        "Harga": recent["Close"].values,
        "Perubahan %": recent["Close"].pct_change().values * 100,
        "Volume (lot)": (recent["Volume"] / 100).values,
        "Nilai (Rp miliar)": (recent["Close"] * recent["Volume"] / 1e9).values,
        "Beli %": buy.values * 100,
    }).tail(days)
    out["Jual %"] = 100 - out["Beli %"]
    out["Dominan"] = out["Beli %"].apply(lambda b: "🟢 Pembeli" if b >= 60 else "🔴 Penjual" if b <= 40 else "⚪ Seimbang")
    return out


# ---------- Screener ----------

PRESETS = {
    "Semua saham (pakai filter sendiri)": "Tampilkan semua saham yang lolos filter di samping.",
    "🚀 Breakout volume": "Harga ditutup di level tertinggi 20 hari dengan volume minimal 2x rata-rata. Tanda awal tren naik baru.",
    "🕵️ Akumulasi diam-diam": "Harga relatif datar sebulan (±7%) tapi pola volume menunjukkan akumulasi. Sering terjadi sebelum harga bergerak.",
    "📉➡️📈 Pullback di tren naik": "Tren menengah naik (MA20 > MA50), harga turun mendekati MA20, RSI 40–55. Kesempatan beli saat koreksi.",
    "🔄 Rebound oversold": "RSI di bawah 35 dan hari ini harga naik. Potensi pantulan setelah turun dalam (risiko lebih tinggi).",
    "🔥 Saham kecil sedang ramai": "Harga di bawah Rp500 atau kapitalisasi di bawah Rp2 triliun, volume hari ini minimal 3x rata-rata, "
                                  "dan harga naik. Sering jadi incaran 'gorengan': potensi naik cepat, risiko turun juga sangat besar.",
}


def screen_row(code: str, df: pd.DataFrame, ind: dict, market_cap: float | None = None) -> dict:
    acc = accumulation(df)
    risk, _ = speculative_risk(df, ind, market_cap)
    prior_high = float(df["High"].iloc[-21:-1].max()) if len(df) > 21 else float("nan")
    value20 = float((df["Close"] * df["Volume"]).tail(20).mean())
    return {
        "Kode": code, "Harga": ind["harga"], "1 hari %": ind["chg_1d"], "5 hari %": ind["chg_5d"],
        "1 bulan %": ind["chg_1m"], "RSI": ind["rsi14"], "vs MA20 %": ind["vs_ma20"],
        "Tren naik": ind["ma20_gt_ma50"], "Volume x": ind["vol_ratio"],
        "Nilai transaksi (Rp M/hari)": value20 / 1e9, "Akumulasi": acc["verdict"], "MFI": acc["mfi"],
        "Kapitalisasi (Rp T)": market_cap / 1e12 if market_cap else float("nan"),
        "Risiko gorengan": {"Tinggi": "🔥 Tinggi", "Sedang": "⚠️ Sedang", "Rendah": "✅ Rendah"}[risk],
        "_breakout": ind["harga"] >= prior_high and ind["vol_ratio"] >= 2,
    }


def apply_preset(df: pd.DataFrame, preset: str) -> pd.DataFrame:
    if preset.endswith("Breakout volume"):
        return df[df["_breakout"]]
    if preset.endswith("Akumulasi diam-diam"):
        return df[(df["1 bulan %"].abs() <= 7) & (df["Akumulasi"] == "Akumulasi")]
    if preset.endswith("Pullback di tren naik"):
        return df[df["Tren naik"] & df["vs MA20 %"].between(-4, 1) & df["RSI"].between(40, 55)]
    if preset.endswith("Saham kecil sedang ramai"):
        small = (df["Harga"] < 500) | (df["Kapitalisasi (Rp T)"] < 2)
        return df[small & (df["Volume x"] >= 3) & (df["1 hari %"] > 0)]
    if preset.endswith("Rebound oversold"):
        return df[(df["RSI"] < 35) & (df["1 hari %"] > 0)]
    return df


# ---------- Risiko saham gorengan ----------

def speculative_risk(df: pd.DataFrame, ind: dict, market_cap: float | None = None) -> tuple[str, list[str]]:
    """Nilai risiko 'gorengan' (Rendah/Sedang/Tinggi) beserta alasannya."""
    flags = []
    price = ind["harga"]
    value20 = float((df["Close"] * df["Volume"]).tail(20).mean())
    atr_pct = atr(df) / price * 100 if price else 0
    no_trade = int((df["Volume"].tail(20) == 0).sum())
    big_up = int((df["Close"].pct_change().tail(10) >= 0.15).sum())
    if price < 200:
        flags.append(f"Harga Rp {price:,.0f} (di bawah Rp200), mudah digerakkan")
    if market_cap and market_cap < 1e12:
        flags.append(f"Kapitalisasi kecil (Rp {market_cap / 1e9:,.0f} miliar)")
    if value20 < 1e9:
        flags.append(f"Nilai transaksi rata-rata hanya Rp {value20 / 1e6:,.0f} juta/hari, sulit keluar saat panik")
    if no_trade >= 3:
        flags.append(f"{no_trade} hari tanpa transaksi dalam 20 hari terakhir")
    if atr_pct > 7:
        flags.append(f"Gerak harian rata-rata {atr_pct:.1f}%, sangat volatil")
    if ind["chg_1m"] == ind["chg_1m"] and abs(ind["chg_1m"]) > 50:
        flags.append(f"Harga bergerak {ind['chg_1m']:+.0f}% dalam sebulan")
    if big_up >= 2:
        flags.append(f"{big_up} kali naik ≥15% dalam 10 hari (mendekati ARA), rawan UMA/suspensi")
    if ind["vol_ratio"] == ind["vol_ratio"] and ind["vol_ratio"] > 5:
        flags.append(f"Volume melonjak {ind['vol_ratio']:.0f}x rata-rata")
    level = "Tinggi" if len(flags) >= 3 else "Sedang" if flags else "Rendah"
    return level, flags


GORENGAN_GUIDE = """
**Kalau mau ikut saham spekulatif ("gorengan"):**
- Pakai uang yang siap hilang, idealnya sebagian kecil saja dari modal.
- Pasang **stop loss** dan disiplin. Saham seperti ini bisa ARB beberapa hari berturut-turut.
- Cek **broker summary**: apakah pembelinya terkumpul di satu-dua broker (tanda bandar) dan berapa harga rata-rata mereka.
- Waspadai **UMA, notasi khusus, dan suspensi** di pengumuman BEI. Kalau disuspensi, uang bisa tertahan lama.
- Jangan masuk saat harga sudah ARA beberapa kali; risiko jadi "pembeli terakhir" makin besar.
"""
