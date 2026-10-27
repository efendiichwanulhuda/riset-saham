"""Siapa yang memegang saham: pemegang saham besar dari situs BEI, ditambah data institusi dari Yahoo Finance.

Data BEI berasal dari profil emiten (pemegang saham di atas 5% dan porsi masyarakat), biasanya diperbarui
bulanan. Ini BERBEDA dengan broker summary (broker yang membeli/menjual hari ini).
"""

from __future__ import annotations

import re

import pandas as pd
import requests

from tickers import yahoo_symbol

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                         "Chrome/130.0 Safari/537.36",
           "Accept": "application/json", "Referer": "https://www.idx.co.id/"}

_FOREIGN = re.compile(r"\b(ltd|limited|pte|inc|llc|corp|corporation|fund|holdings? b\.?v|b\.v|gmbh|s\.a|plc|"
                      r"bank of new york|citibank|hsbc|jpmorgan|state street|ubs|dbs|norges|vanguard|blackrock|"
                      r"government of)\b", re.I)
_PUBLIC = re.compile(r"masyarakat|public|publik|lainnya|others", re.I)
_TREASURY = re.compile(r"saham treasuri|treasury", re.I)
_LOCAL_INST = re.compile(r"\b(pt|tbk|koperasi|yayasan|dana pensiun|reksa dana|asuransi|bpjs|negara republik|"
                         r"pemerintah|danantara|taspen|asabri)\b", re.I)


def classify(name: str) -> str:
    """Tebak jenis pemegang dari namanya."""
    if _PUBLIC.search(name):
        return "Masyarakat (publik < 5%)"
    if _TREASURY.search(name):
        return "Saham treasuri (dibeli kembali)"
    if _FOREIGN.search(name):
        return "Institusi asing"
    if _LOCAL_INST.search(name):
        return "Institusi/perusahaan lokal"
    return "Perorangan"


def _num(x) -> float:
    if x is None:
        return float("nan")
    if isinstance(x, (int, float)):
        return float(x)
    s = str(x).replace("%", "").strip()
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".") if s.rfind(",") > s.rfind(".") else s.replace(",", "")
    else:
        s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return float("nan")


def from_idx(code: str) -> pd.DataFrame | None:
    url = f"https://www.idx.co.id/primary/ListedCompany/GetCompanyProfilesDetail?KodeEmiten={code}&language=id-id"
    r = requests.get(url, headers=HEADERS, timeout=20)
    r.raise_for_status()
    rows = r.json().get("PemegangSaham") or []
    # Persentase kadang ditulis sebagai pecahan (0.55) dan kadang sebagai persen (55.0)
    pcts = [p for p in (_num(d.get("Persentase")) for d in rows) if p == p]
    scale = 100 if pcts and sum(pcts) <= 1.5 else 1
    out = []
    for d in rows:
        name = str(d.get("Nama") or "").strip()
        if not name:
            continue
        pct = _num(d.get("Persentase"))
        out.append({"Pemegang": name, "Jenis": classify(name), "Jumlah saham": _num(d.get("Jumlah")),
                    "Persen": pct * scale,
                    "Pengendali": bool(d.get("Pengendali"))})
    return pd.DataFrame(out) if out else None


def from_yahoo(code: str) -> dict:
    """Ringkasan kepemilikan dari Yahoo: % orang dalam, % institusi, dan daftar institusi/reksa dana."""
    import yfinance as yf

    t = yf.Ticker(yahoo_symbol(code))
    out: dict = {}
    try:
        mh = t.major_holders
        if mh is not None and not mh.empty:
            s = mh.iloc[:, 0]
            out["insider"] = float(s.get("insidersPercentHeld", float("nan"))) * 100
            out["institusi"] = float(s.get("institutionsPercentHeld", float("nan"))) * 100
    except Exception:
        pass
    lists = []
    for attr, kind in (("institutional_holders", "Institusi"), ("mutualfund_holders", "Reksa dana")):
        try:
            df = getattr(t, attr)
        except Exception:
            df = None
        if df is None or df.empty:
            continue
        for _, row in df.iterrows():
            pct = row.get("pctHeld", row.get("% Out", float("nan")))
            lists.append({"Pemegang": row.get("Holder"), "Jenis": kind, "Jumlah saham": row.get("Shares"),
                          "Persen": float(pct) * 100 if pct == pct else float("nan"),
                          "Tanggal laporan": pd.to_datetime(row.get("Date Reported")).date()
                          if row.get("Date Reported") is not None else None})
    if lists:
        out["daftar"] = pd.DataFrame(lists)
    return out


def load(code: str) -> tuple[pd.DataFrame | None, dict, str]:
    """Kembalikan (pemegang saham besar BEI, data Yahoo, status sumber)."""
    major, status = None, []
    try:
        major = from_idx(code)
        status.append("BEI: OK" if major is not None else "BEI: data kosong")
    except Exception as exc:
        status.append(f"BEI: gagal ({type(exc).__name__})")
    try:
        yahoo = from_yahoo(code)
    except Exception as exc:
        yahoo = {}
        status.append(f"Yahoo: gagal ({type(exc).__name__})")
    return major, yahoo, " · ".join(status)


def summarize(major: pd.DataFrame | None) -> dict:
    """Hitung porsi pengendali, asing, publik (free float), dan konsentrasi kepemilikan."""
    if major is None or major.empty:
        return {}
    df = major.dropna(subset=["Persen"])
    by_type = df.groupby("Jenis")["Persen"].sum().sort_values(ascending=False)
    public = float(by_type.get("Masyarakat (publik < 5%)", float("nan")))
    holders = df[~df["Jenis"].str.startswith(("Masyarakat", "Saham treasuri"))].sort_values("Persen", ascending=False)
    top = holders.iloc[0] if not holders.empty else None
    return {"by_type": by_type, "free_float": public,
            "top_name": top["Pemegang"] if top is not None else None,
            "top_pct": float(top["Persen"]) if top is not None else float("nan"),
            "top3_pct": float(holders["Persen"].head(3).sum()),
            "foreign_pct": float(by_type.get("Institusi asing", 0.0))}


def checks(s: dict) -> list[tuple[str, str]]:
    """Bacaan sederhana dari struktur pemegang saham."""
    if not s:
        return []
    out = []
    ff, top = s["free_float"], s["top_pct"]
    if top == top:
        if top >= 50:
            out.append(("✅", f"Ada pengendali kuat ({s['top_name']}, {top:.1f}%). Arah perusahaan jelas, tapi keputusan "
                              "besar (right issue, jual saham) ada di tangan satu pihak."))
        elif top < 20:
            out.append(("⚠️", f"Kepemilikan tersebar, pemegang terbesar hanya {top:.1f}%. Tidak ada pengendali dominan."))
    if ff == ff:
        if ff < 10:
            out.append(("🔥", f"Saham publik (free float) hanya {ff:.1f}%. Barang di pasar sedikit sehingga harga mudah "
                              "digerakkan pihak besar (rawan digoreng) dan bisa terkena aturan free float minimum BEI."))
        elif ff < 20:
            out.append(("⚠️", f"Free float {ff:.1f}%, tergolong kecil. Pergerakan harga bisa liar."))
        else:
            out.append(("✅", f"Free float {ff:.1f}%, cukup besar sehingga harga lebih sulit dimainkan."))
    if s["foreign_pct"] >= 10:
        out.append(("✅", f"Institusi asing memegang {s['foreign_pct']:.1f}% (di atas 5% masing-masing)."))
    return out


HOLDER_GUIDE = """
**Cara cek siapa yang memegang saham lebih detail:**
1. **Stockbit** > buka saham > tab **Profile** > **Shareholders**: daftar pemegang di atas 5% dan perubahannya tiap bulan.
2. **idx.co.id** > Perusahaan Tercatat > Profil Perusahaan > ketik kode > bagian **Pemegang Saham**.
3. **KSEI** (ksei.co.id) menerbitkan laporan bulanan pemegang saham di atas 5% untuk semua emiten. Bandingkan bulan ini
   dengan bulan lalu: kalau pemegang besar menambah porsi, itu tanda akumulasi jangka panjang.
4. **Keterbukaan Informasi** di idx.co.id: direksi, komisaris, dan pemegang di atas 5% wajib lapor setiap membeli/menjual.
   Direksi yang membeli saham perusahaannya sendiri sering dianggap sinyal positif.

**Bedanya dengan broker summary:** pemegang saham = siapa pemiliknya (data bulanan). Broker summary = lewat broker
mana saham dibeli dan dijual hari ini (data harian, cocok untuk scalping/trading).
"""
