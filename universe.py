"""Daftar semua saham BEI (sekitar 950 emiten), dari beberapa sumber cadangan.

Urutan sumber:
1. File `daftar_saham.xlsx` / `daftar_saham.csv` di folder ini (unduh dari idx.co.id > Data Pasar > Data Saham > Daftar Saham)
2. Screener Yahoo Finance (bursa JKT)
3. API daftar emiten di situs BEI
4. Daftar bawaan di tickers.py (sekitar 90 saham likuid)
"""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd
import requests

from tickers import TICKERS

HERE = Path(__file__).parent
CODE_RE = re.compile(r"^[A-Z]{4}$")
COLUMNS = ["Kode", "Perusahaan", "Sektor", "Harga", "Kapitalisasi"]


def _clean(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["Kode"] = df["Kode"].astype(str).str.strip().str.upper()
    df = df[df["Kode"].str.match(CODE_RE)].drop_duplicates("Kode")
    for col in COLUMNS:
        if col not in df:
            df[col] = None
    df["Sektor"] = df["Sektor"].fillna("-")
    return df[COLUMNS].reset_index(drop=True)


def from_file() -> pd.DataFrame | None:
    for name in ("daftar_saham.xlsx", "daftar_saham.xls", "daftar_saham.csv"):
        path = HERE / name
        if not path.exists():
            continue
        raw = pd.read_csv(path) if path.suffix == ".csv" else pd.read_excel(path)
        cols = {c: str(c).strip().lower() for c in raw.columns}
        kode = next((c for c, l in cols.items() if l in {"kode", "kode saham", "code", "kodeemiten"}), None)
        nama = next((c for c, l in cols.items() if "nama" in l or l == "name"), None)
        sektor = next((c for c, l in cols.items() if "sektor" in l or "sector" in l), None)
        if kode is None:
            continue
        df = pd.DataFrame({"Kode": raw[kode], "Perusahaan": raw[nama] if nama else None,
                           "Sektor": raw[sektor] if sektor else None})
        return _clean(df)
    return None


def from_yahoo() -> pd.DataFrame | None:
    import yfinance as yf
    from yfinance import EquityQuery

    query = EquityQuery("eq", ["exchange", "JKT"])
    rows, offset = [], 0
    while offset < 2000:
        res = yf.screen(query, offset=offset, size=250, sortField="intradaymarketcap", sortAsc=False)
        quotes = res.get("quotes", []) if isinstance(res, dict) else []
        for q in quotes:
            sym = str(q.get("symbol", ""))
            if not sym.endswith(".JK"):
                continue
            rows.append({"Kode": sym[:-3], "Perusahaan": q.get("longName") or q.get("shortName"),
                         "Sektor": q.get("sector"), "Harga": q.get("regularMarketPrice"),
                         "Kapitalisasi": q.get("marketCap")})
        if len(quotes) < 250:
            break
        offset += 250
    return _clean(pd.DataFrame(rows)) if len(rows) > 200 else None


def from_idx() -> pd.DataFrame | None:
    url = "https://www.idx.co.id/primary/ListedCompany/GetCompanyProfiles?start=0&length=9999"
    r = requests.get(url, headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"}, timeout=20)
    r.raise_for_status()
    data = r.json().get("data", [])
    df = pd.DataFrame([{"Kode": d.get("KodeEmiten"), "Perusahaan": d.get("NamaEmiten"),
                        "Sektor": d.get("Sektor")} for d in data])
    return _clean(df) if len(df) > 200 else None


def builtin() -> pd.DataFrame:
    return _clean(pd.DataFrame([{"Kode": k, "Perusahaan": v[0], "Sektor": v[1]} for k, v in TICKERS.items()]))


def load() -> tuple[pd.DataFrame, str]:
    """Kembalikan (daftar saham, nama sumber)."""
    for name, fn in (("file daftar_saham", from_file), ("Yahoo Finance", from_yahoo), ("situs BEI", from_idx)):
        try:
            df = fn()
        except Exception:
            df = None
        if df is not None and len(df):
            # Lengkapi nama/sektor dari daftar bawaan bila sumber tidak menyediakannya
            for i, row in df.iterrows():
                if row["Kode"] in TICKERS:
                    if not row["Perusahaan"]:
                        df.at[i, "Perusahaan"] = TICKERS[row["Kode"]][0]
                    if row["Sektor"] in (None, "-"):
                        df.at[i, "Sektor"] = TICKERS[row["Kode"]][1]
            df["Perusahaan"] = df["Perusahaan"].fillna(df["Kode"])
            return df, name
    return builtin(), "daftar bawaan (90 saham)"
