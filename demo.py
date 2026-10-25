"""Data contoh untuk mencoba tampilan aplikasi tanpa internet (RISET_DEMO=1). BUKAN data asli."""

from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd

from news import Article, detect_tickers, score_sentiment

_SAMPLES = [
    ("[CONTOH] Laba bersih BBRI naik 12%, bank siap tebar dividen interim", 3),
    ("[CONTOH] Asing borong saham ANTM saat harga emas cetak rekor", 5),
    ("[CONTOH] GOTO masih merugi, tapi rugi bersih menyusut", 8),
    ("[CONTOH] Telkom raih kontrak baru pusat data", 12),
    ("[CONTOH] Saham BUMI disuspensi setelah lonjakan tidak wajar", 20),
    ("[CONTOH] Bank Central Asia catat pendapatan tumbuh, analis naikkan target harga naik", 26),
    ("[CONTOH] Adaro ekspansi ke bisnis hijau, saham ADRO menguat", 30),
    ("[CONTOH] Pendapatan UNVR turun, saham melemah", 40),
]


def articles():
    now = datetime.now(timezone.utc)
    out = []
    for title, hours in _SAMPLES:
        a = Article(title=title, link="https://example.com", source="Data contoh",
                    published=now - timedelta(hours=hours))
        a.tickers = detect_tickers(title)
        a.sentiment, a.hits = score_sentiment(title)
        out.append(a)
    return out


def history(codes):
    out = {}
    idx = pd.bdate_range(end=datetime.now().date(), periods=120)
    for i, code in enumerate(codes):
        rng = np.random.default_rng(i)
        small = code in SMALL_CAPS
        close = (120 if small else 1000) * np.exp(np.cumsum(rng.normal(0.003 if small else 0.001, 0.06 if small else 0.02, len(idx))))
        out[code] = pd.DataFrame({"Close": close, "High": close * (1 + rng.uniform(0, 0.02, len(idx))),
                                  "Low": close * (1 - rng.uniform(0, 0.02, len(idx))),
                                  "Volume": rng.integers(1e6, 5e6, len(idx))}, index=idx)
        if small:
            out[code].iloc[-1, out[code].columns.get_loc("Volume")] = 4e7
    return out


def keystats(code):
    rng = np.random.default_rng(len(code) + ord(code[0]))
    qidx = pd.to_datetime([f"{y}-{m:02d}-{d}" for y in (2023, 2024, 2025)
                           for m, d in ((3, 31), (6, 30), (9, 30), (12, 31))] + ["2026-03-31", "2026-06-30"])
    rev = pd.Series(rng.uniform(800, 1200, len(qidx)) * 1e9, index=qidx).cumsum() / 4
    ni = rev * rng.uniform(-0.05, 0.2, len(qidx))
    eps = ni / 1e10
    out = {}
    for label, q in (("Pendapatan", rev), ("Laba bersih", ni), ("EPS", eps)):
        annual = q.groupby(q.index.year).sum()
        annual = annual[annual.index < 2026]
        annual.index = pd.to_datetime([f"{y}-12-31" for y in annual.index])
        out[label] = {"kuartal": q, "tahunan": annual}
    return out


SMALL_CAPS = {"DOOH": "Era Media Informasi", "BAPA": "Bekasi Asri Pemula", "FUTR": "Lini Imaji Kreasi Ekosistem",
              "BABY": "Multitrend Indo", "KAQI": "Jantra Grupa Indonesia"}


def universe():
    from universe import builtin
    df = builtin()
    extra = pd.DataFrame([{"Kode": k, "Perusahaan": f"[CONTOH] {v}", "Sektor": "Lainnya", "Harga": None,
                           "Kapitalisasi": 1.5e11} for k, v in SMALL_CAPS.items()])
    return pd.concat([df, extra], ignore_index=True)
