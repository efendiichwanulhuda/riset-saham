"""Riset otomatis yang sekaligus mengajari cara membacanya.

- fundamental(): untuk mode Investasi. Menjelaskan valuasi, profitabilitas, pertumbuhan, kesehatan keuangan, dan dividen.
- money_flow(): untuk mode Scalping. Menjelaskan VWAP, uang masuk/keluar, indikator volume, likuiditas, dan rencana trading.

Setiap poin berisi: apa itu, cara membacanya, patokan umum, dan arti angka untuk saham ini.
Semua patokan adalah aturan praktis umum, bukan rumus pasti. Bukan rekomendasi investasi.
"""

from __future__ import annotations

import math

import pandas as pd

from analysis import tick_size

GOOD, WARN, BAD, INFO = "✅", "⚠️", "🔴", "ℹ️"


def _item(status, judul, nilai, apa, cara, patokan, saham) -> dict:
    return {"status": status, "judul": judul, "nilai": nilai, "apa": apa, "cara": cara, "patokan": patokan, "saham": saham}


def _num(x) -> float | None:
    if isinstance(x, (int, float)) and not (isinstance(x, float) and math.isnan(x)):
        return float(x)
    return None


def _rp(v: float) -> str:
    a = abs(v)
    if a >= 1e12:
        return f"Rp {v / 1e12:,.2f} triliun"
    if a >= 1e9:
        return f"Rp {v / 1e9:,.1f} miliar"
    return f"Rp {v:,.0f}"


def _quarter(d) -> str:
    return f"Q{(d.month - 1) // 3 + 1} {d.year}"


def _conclude(groups, good_text, mixed_text, bad_text) -> dict:
    items = [it for _, _, its in groups for it in its if it["status"] != INFO]
    good = sum(it["status"] == GOOD for it in items)
    bad = sum(it["status"] == BAD for it in items)
    total = len(items)
    ratio = (good - 0.5 * bad) / total if total else 0
    if total == 0:
        return {"level": "info", "teks": "Data belum cukup untuk menarik kesimpulan.", "good": 0, "total": 0}
    level, teks = ("success", good_text) if ratio >= 0.6 else ("warning", mixed_text) if ratio >= 0.3 else ("error", bad_text)
    return {"level": level, "teks": teks, "good": good, "total": total}


# ---------------------------------------------------------------- Fundamental


def _ttm(series: pd.Series) -> float | None:
    s = series.dropna()
    return float(s.tail(4).sum()) if len(s) >= 4 else None


def _yoy_quarter(q: pd.Series):
    """(nama kuartal, nilai terakhir, nilai setahun lalu) bila tersedia."""
    if q is None or len(q) == 0:
        return None
    last_d, last_v = q.index[-1], float(q.iloc[-1])
    same = q[[d.year == last_d.year - 1 and d.month == last_d.month for d in q.index]]
    prev = float(same.iloc[0]) if len(same) else None
    return _quarter(last_d), last_v, prev


def _growth(now: float, prev: float | None) -> float | None:
    if prev is None or prev == 0:
        return None
    return (now / prev - 1) * 100 * (1 if prev > 0 else -1)


def fundamental(code: str, sector: str, fund: dict, ks: dict, price: float | None) -> dict:
    fund = fund or {}
    ks = ks or {}
    is_bank = any(w in (sector or "").lower() for w in ("bank", "perbankan", "keuangan", "financial"))
    pe, pbv = _num(fund.get("PER")), _num(fund.get("PBV"))
    roe, margin = _num(fund.get("ROE")), _num(fund.get("Margin laba bersih"))
    rev_g, earn_g = _num(fund.get("Pertumbuhan pendapatan (YoY)")), _num(fund.get("Pertumbuhan laba (YoY)"))
    der, dy = _num(fund.get("Utang/ekuitas")), _num(fund.get("Dividen yield"))
    mcap = _num(fund.get("Kapitalisasi pasar"))
    hi52, lo52 = _num(fund.get("Harga tertinggi 52 minggu")), _num(fund.get("Harga terendah 52 minggu"))

    rev_q = ks.get("Pendapatan", {}).get("kuartal", pd.Series(dtype=float))
    ni_q = ks.get("Laba bersih", {}).get("kuartal", pd.Series(dtype=float))
    eps_q = ks.get("EPS", {}).get("kuartal", pd.Series(dtype=float))
    eps_ttm = _ttm(eps_q)
    if eps_ttm is None and pe and price and pe > 0:
        eps_ttm = price / pe
    if pe is None and eps_ttm and price and eps_ttm > 0:
        pe = price / eps_ttm
    bvps = price / pbv if price and pbv and pbv > 0 else None

    # 1. Valuasi
    val = []
    if mcap:
        size = "big cap (besar)" if mcap >= 10e12 else "mid cap (menengah)" if mcap >= 1e12 else "small cap (kecil)"
        val.append(_item(
            INFO if mcap >= 1e12 else WARN, "Kapitalisasi pasar", _rp(mcap),
            "Harga seluruh perusahaan di bursa: harga saham x jumlah saham beredar. Ini ukuran besar-kecilnya perusahaan.",
            "Makin besar, biasanya makin stabil dan likuid (mudah dijual), tapi pertumbuhannya cenderung lebih pelan. "
            "Saham kecil bisa naik cepat, tapi juga turun cepat dan lebih mudah digerakkan bandar.",
            "Big cap ≥ Rp 10 triliun · mid cap Rp 1–10 triliun · small cap < Rp 1 triliun.",
            f"{code} termasuk **{size}**." + (" Hati-hati: saham kecil lebih rawan digoreng." if mcap < 1e12 else "")))
    if pe is not None:
        if pe <= 0:
            s, txt = BAD, "PER negatif artinya perusahaan sedang **rugi**, jadi tidak bisa dinilai pakai PER."
        elif pe < 10:
            s, txt = GOOD, f"PER {pe:.1f}x tergolong **murah**: modalmu kembali dari laba dalam ±{pe:.0f} tahun (kalau laba stabil). Cek kenapa murah, jangan-jangan labanya akan turun."
        elif pe <= 20:
            s, txt = GOOD, f"PER {pe:.1f}x tergolong **wajar**."
        else:
            s, txt = WARN, f"PER {pe:.1f}x tergolong **mahal**. Masih bisa masuk akal kalau labanya tumbuh cepat (lihat bagian pertumbuhan)."
        val.append(_item(
            s, "PER (Price to Earnings Ratio)", f"{pe:.1f}x",
            "Harga saham dibagi laba per saham (EPS) setahun. Artinya: kamu membayar berapa kali laba tahunan untuk tiap lembar saham.",
            "Makin kecil makin murah. Bandingkan dengan saham lain di sektor yang sama dan dengan PER saham ini di masa lalu, "
            "karena tiap sektor punya 'harga normal' berbeda (bank dan konsumer biasanya lebih mahal daripada batu bara).",
            "< 10x murah · 10–20x wajar · > 20x mahal · negatif = rugi.", txt))
        if pe > 0:
            ey = 100 / pe
            val.append(_item(
                GOOD if ey >= 8 else WARN if ey < 5 else INFO, "Earnings yield (kebalikan PER)", f"{ey:.1f}% per tahun",
                "Laba per saham dibagi harga (1 / PER). Anggap seperti 'bunga' yang dihasilkan perusahaan untuk setiap rupiah yang kamu tanam.",
                "Bandingkan dengan bunga deposito atau obligasi pemerintah (SBN) sekitar 6%. Kalau earnings yield jauh di bawah itu, "
                "kamu bergantung pada pertumbuhan laba agar investasimu sepadan.",
                "> 8% menarik · 5–8% sedang · < 5% mahal kecuali labanya tumbuh cepat.",
                f"Setiap Rp 100 yang kamu bayar untuk {code}, perusahaan menghasilkan laba sekitar Rp {ey:.1f} per tahun."))
    if pbv is not None:
        s = GOOD if pbv < 1 else GOOD if pbv <= 3 else WARN
        bank_note = " Untuk bank, PBV adalah ukuran valuasi utama; bank besar dengan ROE tinggi wajar dihargai PBV 2–5x." if is_bank else ""
        val.append(_item(
            s, "PBV (Price to Book Value)", f"{pbv:.2f}x",
            "Harga saham dibagi nilai buku (aset dikurangi utang) per saham. Artinya: berapa kali lipat dari 'modal bersih' perusahaan yang kamu bayar.",
            "PBV di bawah 1x berarti harga saham lebih murah dari modal bersihnya, bisa jadi peluang atau tanda pasar meragukan kualitas asetnya. "
            "PBV tinggi wajar kalau ROE juga tinggi (perusahaan pintar memutar modal)." + bank_note,
            "< 1x di bawah nilai buku · 1–3x wajar · > 3x mahal (kecuali ROE tinggi).",
            f"Nilai buku {code} sekitar Rp {bvps:,.0f} per saham, harga sekarang {pbv:.2f}x dari itu." if bvps else f"PBV {pbv:.2f}x."))
    if eps_ttm and eps_ttm > 0 and bvps and price:
        graham = math.sqrt(22.5 * eps_ttm * bvps)
        diff = (price / graham - 1) * 100
        val.append(_item(
            GOOD if diff <= 0 else WARN if diff > 50 else INFO, "Perkiraan harga wajar (Graham number)", f"Rp {graham:,.0f}",
            "Rumus klasik Benjamin Graham (guru Warren Buffett): √(22,5 × EPS × nilai buku per saham). Angka 22,5 berasal dari batas "
            "PER 15x dikali PBV 1,5x yang dianggap wajar untuk saham defensif.",
            "Kalau harga di bawah angka ini, saham tergolong murah menurut ukuran konservatif. Rumus ini cocok untuk perusahaan stabil, "
            "kurang cocok untuk saham pertumbuhan tinggi (teknologi) yang memang selalu terlihat 'mahal'.",
            "Harga < Graham number = ada margin of safety (ruang aman).",
            f"Dengan EPS 12 bulan Rp {eps_ttm:,.1f} dan nilai buku Rp {bvps:,.0f}, harga wajar kasar {code} sekitar Rp {graham:,.0f}. "
            f"Harga sekarang Rp {price:,.0f} ({diff:+.0f}% dari harga wajar)."))
    if hi52 and lo52 and price and hi52 > lo52:
        pos = (price - lo52) / (hi52 - lo52) * 100
        val.append(_item(
            INFO, "Posisi harga dalam setahun", f"{pos:.0f}% dari rentang",
            "Letak harga sekarang di antara harga terendah dan tertinggi 52 minggu terakhir (0% = di titik terendah, 100% = di puncak).",
            "Investor nilai suka membeli saat posisi rendah asalkan fundamentalnya masih bagus. Posisi tinggi bukan berarti jelek, "
            "tapi ruang naiknya perlu dibenarkan oleh kenaikan laba.",
            "Bukan patokan baik/buruk, dipakai untuk konteks.",
            f"Rentang setahun Rp {lo52:,.0f} – {hi52:,.0f}. Harga {code} sekarang {(price / hi52 - 1) * 100:+.0f}% dari puncak dan "
            f"{(price / lo52 - 1) * 100:+.0f}% dari titik terendah."))

    # 2. Profitabilitas
    prof = []
    if roe is not None:
        s = GOOD if roe >= 0.12 else BAD if roe < 0 else WARN
        prof.append(_item(
            s, "ROE (Return on Equity)", f"{roe * 100:.1f}%",
            "Laba bersih setahun dibagi modal pemegang saham. Artinya: dari setiap Rp 100 modal pemilik, perusahaan menghasilkan laba berapa.",
            "Ini ukuran paling penting untuk melihat 'perusahaan pintar cari uang atau tidak'. ROE tinggi yang stabil bertahun-tahun "
            "adalah ciri perusahaan berkualitas. Hati-hati kalau ROE tinggi karena utang besar (cek Utang/ekuitas).",
            "≥ 20% sangat baik · 12–20% baik · < 12% rendah · negatif = rugi.",
            f"Setiap Rp 100 modal pemilik {code} menghasilkan laba sekitar Rp {roe * 100:.1f} per tahun."
            + (" Ini **sangat baik**." if roe >= 0.2 else " Ini **baik**." if roe >= 0.12 else " Ini **di bawah standar**.")))
    if margin is not None:
        s = GOOD if margin >= 0.1 else BAD if margin < 0 else WARN
        prof.append(_item(
            s, "Margin laba bersih (NPM)", f"{margin * 100:.1f}%",
            "Laba bersih dibagi pendapatan. Artinya: dari setiap Rp 100 penjualan, berapa yang tersisa jadi laba setelah semua biaya dan pajak.",
            "Margin tinggi menandakan perusahaan punya 'kekuatan harga' atau efisien. Bandingkan dengan sesama sektor: ritel dan "
            "distributor wajar bermargin tipis (2–5%), sedangkan bank, rokok, atau telko bisa 15–30%.",
            "≥ 15% tinggi · 5–15% sedang · < 5% tipis · negatif = rugi.",
            f"Dari setiap Rp 100 penjualan {code}, sekitar Rp {margin * 100:.1f} menjadi laba bersih."))
    if len(rev_q) >= 4 and len(ni_q) >= 4:
        common = rev_q.index.intersection(ni_q.index)
        m = (ni_q.loc[common] / rev_q.loc[common].replace(0, float("nan"))).dropna() * 100
        if len(m) >= 4:
            recent, before = m.tail(2).mean(), m.iloc[:-2].tail(4).mean()
            trend = "membaik" if recent > before + 1 else "memburuk" if recent < before - 1 else "stabil"
            prof.append(_item(
                GOOD if trend != "memburuk" else WARN, "Tren margin per kuartal", trend,
                "Perubahan margin laba bersih dari kuartal ke kuartal.",
                "Margin yang naik berarti biaya terkendali atau harga jual naik. Margin yang terus turun sering jadi tanda awal masalah "
                "(persaingan ketat, bahan baku mahal) sebelum terlihat di laba.",
                "Naik atau stabil = baik · turun terus = waspada.",
                "Margin per kuartal: " + " → ".join(f"{_quarter(d)} {v:.1f}%" for d, v in m.tail(6).items()) + "."))

    # 3. Pertumbuhan
    grow = []
    for label, series, alt in (("Pendapatan", rev_q, rev_g), ("Laba bersih", ni_q, earn_g)):
        yq = _yoy_quarter(series)
        g = _growth(yq[1], yq[2]) if yq else None
        if g is None and alt is not None:
            g = alt * 100
        if g is None:
            continue
        what = ("Kenaikan penjualan dibanding periode yang sama tahun lalu (year on year/YoY)." if label == "Pendapatan"
                else "Kenaikan laba bersih dibanding periode yang sama tahun lalu (YoY).")
        cara = ("Dibandingkan dengan kuartal yang sama tahun lalu, bukan kuartal sebelumnya, supaya pengaruh musim (misalnya Lebaran) hilang. "
                + ("Pendapatan adalah 'bahan bakar' laba: laba bisa naik sesaat karena hemat biaya, tapi pertumbuhan jangka panjang butuh penjualan naik."
                   if label == "Pendapatan" else
                   "Laba yang tumbuh adalah alasan utama harga saham naik dalam jangka panjang. Cek juga apakah kenaikannya dari bisnis inti "
                   "atau dari keuntungan sekali saja (misalnya jual aset)."))
        s = GOOD if g >= 10 else INFO if g >= 0 else WARN if g > -20 else BAD
        detail = (f"{label} {yq[0]} {_rp(yq[1])} vs {_rp(yq[2])} setahun lalu, " if yq and yq[2] is not None else "")
        grow.append(_item(
            s, f"Pertumbuhan {label.lower()} (YoY)", f"{g:+.0f}%", what, cara,
            "≥ 10% bagus · 0–10% pelan · negatif = menyusut.", f"{detail}berubah **{g:+.0f}%**."))
    if len(ni_q) >= 4:
        last8 = ni_q.tail(8)
        losses = int((last8 < 0).sum())
        grow.append(_item(
            GOOD if losses == 0 else BAD if losses >= len(last8) / 2 else WARN, "Konsistensi laba", f"{losses} kuartal rugi dari {len(last8)}",
            "Berapa kali perusahaan rugi dalam beberapa kuartal terakhir.",
            "Investor jangka panjang lebih suka perusahaan yang untung terus-menerus, karena labanya mudah diperkirakan. "
            "Laba naik-turun tajam membuat valuasi (PER) sulit dipercaya.",
            "0 kuartal rugi = konsisten · sering rugi = spekulatif.",
            f"Laba bersih {code} per kuartal: " + " · ".join(f"{_quarter(d)} {_rp(v)}" for d, v in last8.tail(4).items()) + "."))
    ni_ttm, ni_y = _ttm(ni_q), ks.get("Laba bersih", {}).get("tahunan", pd.Series(dtype=float))
    if ni_ttm is not None and len(ni_y):
        prev_y = float(ni_y.iloc[-1])
        g = _growth(ni_ttm, prev_y)
        if g is not None:
            grow.append(_item(
                GOOD if g > 0 else WARN, "Laba 12 bulan terakhir (TTM) vs tahun buku terakhir", f"{g:+.0f}%",
                "TTM (trailing twelve months) = jumlah laba 4 kuartal terakhir. Ini gambaran laba setahun yang paling baru.",
                "Kalau TTM lebih besar dari laba tahun buku terakhir, berarti tahun ini berjalan lebih baik daripada tahun lalu.",
                "Positif = tahun berjalan lebih baik.",
                f"Laba TTM {_rp(ni_ttm)} vs laba tahun {ni_y.index[-1].year} {_rp(prev_y)}."))

    # 4. Kesehatan keuangan
    health = []
    if der is not None:
        ratio = der / 100
        if is_bank:
            s, txt = INFO, (f"Utang/ekuitas {ratio:.2f}x. Untuk bank angka ini **wajar tinggi** karena dana nasabah dihitung sebagai utang. "
                            "Untuk bank, lebih tepat cek CAR (permodalan, idealnya > 15%) dan NPL (kredit macet, idealnya < 3%) di laporan keuangan.")
        elif ratio < 0.5:
            s, txt = GOOD, f"Utang hanya {ratio:.2f}x modal: **sangat aman**, perusahaan tidak bergantung pada pinjaman."
        elif ratio <= 1.5:
            s, txt = INFO, f"Utang {ratio:.2f}x modal: **masih wajar**. Pastikan laba operasi cukup untuk bayar bunga."
        else:
            s, txt = WARN, f"Utang {ratio:.2f}x modal: **tinggi**. Saat bunga naik atau penjualan turun, perusahaan bisa tertekan."
        health.append(_item(
            s, "Utang terhadap ekuitas (DER)", f"{ratio:.2f}x",
            "Total utang berbunga dibagi modal sendiri. Artinya: untuk setiap Rp 1 modal pemilik, perusahaan meminjam berapa.",
            "Utang mempercepat pertumbuhan kalau bisnis lancar, tapi jadi beban berat saat bisnis lesu. Sektor properti dan "
            "infrastruktur wajar berutang lebih besar; sektor teknologi dan konsumer idealnya rendah.",
            "< 0,5x aman · 0,5–1,5x wajar · > 1,5x tinggi (kecuali bank/lembaga keuangan).", txt))

    # 5. Dividen
    div = []
    if dy is not None:
        payout = dy * pe / 100 if pe and pe > 0 else None
        div.append(_item(
            GOOD if dy >= 4 else INFO if dy >= 1 else WARN, "Dividen yield", f"{dy:.2f}% per tahun",
            "Dividen setahun dibagi harga saham. Ini 'uang tunai' yang dibagikan perusahaan ke pemegang saham.",
            "Cocok untuk investor yang ingin pemasukan rutin. Yield sangat tinggi (> 10%) kadang jebakan: bisa karena harga sahamnya "
            "anjlok atau dividennya hanya sekali.",
            "≥ 5% tinggi · 2–5% sedang · < 2% kecil.",
            f"Kalau membeli Rp 10 juta saham {code}, perkiraan dividen sekitar Rp {dy / 100 * 10_000_000:,.0f} per tahun (sebelum pajak 10%)."))
        if payout is not None:
            div.append(_item(
                GOOD if 20 <= payout <= 80 else WARN, "Payout ratio (perkiraan)", f"{payout:.0f}% dari laba",
                "Persen laba yang dibagikan sebagai dividen (dihitung kasar: dividen yield × PER).",
                "Payout sedang berarti perusahaan berbagi sambil tetap menyimpan laba untuk berkembang. Payout di atas 100% berarti "
                "membagi lebih dari labanya, sulit dipertahankan.",
                "30–70% sehat · > 100% tidak berkelanjutan · rendah bisa berarti laba dipakai untuk ekspansi.",
                f"{code} membagikan sekitar {payout:.0f}% labanya sebagai dividen."))

    groups = [(t, i, its) for t, i, its in (
        ("💰 Valuasi: mahal atau murah?", "Mengukur harga saham dibandingkan laba dan aset perusahaan.", val),
        ("🏭 Profitabilitas: pintar cari untung?", "Mengukur seberapa efisien perusahaan mengubah modal dan penjualan menjadi laba.", prof),
        ("📈 Pertumbuhan: makin besar atau mengecil?", "Mengukur apakah penjualan dan laba terus bertambah.", grow),
        ("🛡️ Kesehatan keuangan: aman dari utang?", "Mengukur risiko perusahaan kesulitan membayar kewajiban.", health),
        ("🎁 Dividen: bagi hasil ke pemegang saham", "Mengukur uang tunai yang dibagikan ke investor.", div),
    ) if its]

    concl = _conclude(groups,
                      f"Secara fundamental {code} terlihat **sehat dan menarik** untuk dipelajari lebih lanjut sebagai investasi.",
                      f"Fundamental {code} **campuran**: ada sisi kuat dan sisi lemah. Pahami poin ⚠️ sebelum membeli.",
                      f"Fundamental {code} **lemah** saat ini. Cocoknya dipantau dulu sampai kinerjanya membaik.")
    lessons = [
        "Jangan menilai dari satu angka. Saham murah (PER rendah) belum tentu bagus kalau labanya turun.",
        "Kombinasi favorit investor: **ROE tinggi + laba tumbuh + utang rendah + valuasi wajar**.",
        "Selalu bandingkan dengan saham sejenis di sektor yang sama, bukan dengan semua saham.",
        "Baca laporan keuangan lengkap (idx.co.id > Laporan Keuangan) untuk cek **arus kas operasi**: laba yang bagus seharusnya juga menghasilkan kas.",
        "Fundamental bergerak lambat. Cek ulang tiap rilis laporan kuartalan (akhir April, Juli, Oktober, dan Maret untuk laporan tahunan).",
    ]
    return {"judul": f"Riset fundamental {code}", "kesimpulan": concl, "groups": groups, "pelajaran": lessons,
            "kosong": not groups}


# ---------------------------------------------------------------- Money flow


FEE_BUY, FEE_SELL = 0.15, 0.25  # persen, perkiraan umum broker online (jual sudah termasuk pajak 0,1%)


def money_flow(code: str, daily: tuple | None, intra: tuple | None, acc: dict | None, ind: dict | None,
               lv: dict | None, pressure: pd.DataFrame | None = None) -> dict:
    sm = daily[1] if daily else None
    bars, hourly, isum = intra if intra else (None, None, None)
    today, multi, volume, liquid, plan = [], [], [], [], []

    # 1. Hari ini
    if isum:
        above = isum["vs_vwap"] > 0
        today.append(_item(
            GOOD if above else WARN, "Harga vs VWAP", f"{isum['vs_vwap']:+.1f}% (VWAP Rp {isum['vwap']:,.0f})",
            "VWAP (Volume Weighted Average Price) = harga rata-rata semua transaksi hari ini, ditimbang volumenya. "
            "Bayangkan ini sebagai 'harga modal rata-rata' semua orang yang beli hari ini.",
            "Harga di atas VWAP: rata-rata pembeli hari ini sedang untung, jadi mereka cenderung menahan, pembeli memegang kendali. "
            "Harga di bawah VWAP: pembeli hari ini rata-rata rugi, mereka cenderung jual saat harga naik sedikit (tekanan jual). "
            "Scalper sering beli saat harga turun menyentuh VWAP dari atas lalu memantul.",
            "Di atas VWAP = kuat · menempel VWAP (±0,5%) = penentuan · di bawah VWAP = lemah.",
            f"Harga terakhir {code} Rp {isum['harga']:,.0f}, " + ("**di atas** VWAP, pembeli masih menang." if above
                                                               else "**di bawah** VWAP, penjual masih menekan.")))
        net = isum["net"]
        today.append(_item(
            GOOD if net > 0 else WARN, "Uang bersih hari bursa terakhir", f"Rp {net:+,.2f} miliar",
            "Uang masuk (transaksi saat harga naik) dikurangi uang keluar (transaksi saat harga turun), dihitung tiap 5 menit lalu dijumlahkan.",
            "Positif berarti lebih banyak uang yang 'mendorong' harga naik daripada yang menjatuhkan. Yang penting adalah arah dan "
            "konsistensinya, bukan besar angkanya saja; bandingkan dengan nilai transaksi rata-rata harian.",
            "Positif dan makin besar = akumulasi intraday · negatif = distribusi intraday.",
            f"Pada {isum['tanggal'].strftime('%d %b %Y')}, uang bersih {code} **{'masuk' if net > 0 else 'keluar'}** Rp {abs(net):,.2f} miliar."
            + (f" Itu sekitar {abs(net) / sm['value_avg'] * 100:.0f}% dari rata-rata nilai transaksi harian." if sm and sm["value_avg"] > 0 else "")))
        if hourly is not None and len(hourly):
            pos = int((hourly["Bersih (Rp M)"] > 0).sum())
            last = float(hourly["Bersih (Rp M)"].iloc[-1])
            today.append(_item(
                GOOD if pos >= len(hourly) / 2 and last > 0 else WARN if last < 0 else INFO, "Pola uang per jam",
                f"{pos} dari {len(hourly)} jam positif",
                "Uang bersih dipecah per jam perdagangan.",
                "Uang yang masuk merata sepanjang hari lebih sehat daripada hanya melonjak di satu jam. Perhatikan **jam terakhir**: "
                "uang masuk di akhir sesi sering berarti pemain besar berani menyimpan saham untuk besok.",
                "Mayoritas jam positif + jam terakhir positif = tren intraday sehat.",
                "Per jam (Rp miliar): " + " · ".join(f"{j} {v:+.2f}" for j, v in
                                                     zip(hourly["Jam"], hourly["Bersih (Rp M)"])) + "."))
        rng = isum["high"] - isum["low"]
        if rng > 0:
            posd = (isum["harga"] - isum["low"]) / rng * 100
            today.append(_item(
                GOOD if posd >= 60 else WARN if posd <= 40 else INFO, "Posisi harga dalam rentang hari ini", f"{posd:.0f}%",
                "Letak harga terakhir di antara harga terendah (0%) dan tertinggi (100%) hari ini.",
                "Tutup dekat harga tertinggi = pembeli agresif sampai akhir (banyak HAKA, beli di harga offer). Tutup dekat terendah = "
                "penjual agresif (banyak HAKI, jual di harga bid).",
                "> 60% pembeli dominan · 40–60% seimbang · < 40% penjual dominan.",
                f"Rentang hari ini Rp {isum['low']:,.0f} – {isum['high']:,.0f}, harga terakhir Rp {isum['harga']:,.0f}."))

    # 2. Beberapa hari terakhir
    if sm:
        multi.append(_item(
            GOOD if sm["net_5d"] > 0 else WARN, "Uang bersih 5 hari", f"Rp {sm['net_5d']:+,.1f} miliar",
            "Jumlah uang bersih harian selama seminggu bursa terakhir. Uang harian diperkirakan dari posisi harga penutupan dalam rentang hari itu.",
            "Melihat siapa yang menang dalam seminggu: pembeli atau penjual. Untuk scalping, ikuti arah uang yang dominan "
            "(lebih mudah 'berenang searah arus').",
            "Positif = arus beli · negatif = arus jual.",
            f"Dalam 5 hari, {sm['in_pct_5d']:.0f}% nilai transaksi {code} tergolong uang masuk."))
        multi.append(_item(
            GOOD if sm["net_20d"] > 0 else WARN, "Uang bersih 20 hari (sebulan)", f"Rp {sm['net_20d']:+,.1f} miliar",
            "Jumlah uang bersih selama sekitar satu bulan bursa.",
            "Memberi gambaran tren besar. Kalau 5 hari positif tapi 20 hari negatif, bisa jadi hanya pantulan sementara di tren turun.",
            "Searah dengan 5 hari = tren kuat · berlawanan = hati-hati.",
            f"Arah 5 hari {'masuk' if sm['net_5d'] > 0 else 'keluar'}, arah 20 hari {'masuk' if sm['net_20d'] > 0 else 'keluar'}"
            + (": **searah**." if (sm["net_5d"] > 0) == (sm["net_20d"] > 0) else ": **berlawanan**, tren belum jelas.")))
        st_ = sm["streak"]
        multi.append(_item(
            GOOD if st_ >= 3 else WARN if st_ <= -3 else INFO, "Hari berturut-turut", f"{abs(st_)} hari {'masuk' if st_ > 0 else 'keluar'}",
            "Berapa hari terakhir uang bersih bergerak ke arah yang sama tanpa putus.",
            "Uang masuk beberapa hari berturut-turut sering menandakan ada pihak yang sedang mengumpulkan (akumulasi). "
            "Sebaliknya, uang keluar beruntun berarti ada yang terus melepas.",
            "≥ 3 hari masuk = akumulasi · ≥ 3 hari keluar = distribusi.",
            f"Uang {code} sudah {abs(st_)} hari berturut-turut {'masuk' if st_ > 0 else 'keluar'}."))
        multi.append(_item(
            GOOD if sm["big_in"] > sm["big_out"] else WARN if sm["big_out"] > sm["big_in"] else INFO,
            "Hari 'uang besar'", f"{sm['big_in']} masuk / {sm['big_out']} keluar",
            "Hari ketika nilai transaksi lebih dari 2x rata-rata 20 hari. Biasanya ada pemain besar (institusi, bandar) yang bertransaksi.",
            "Arah uang besar lebih penting daripada hari-hari biasa. Uang besar masuk saat harga baru menembus resistance adalah "
            "sinyal kuat; uang besar keluar saat harga di puncak sering tanda distribusi.",
            "Lebih banyak masuk = pemain besar membeli.",
            f"Dalam 20 hari terakhir ada {sm['big_in'] + sm['big_out']} hari uang besar di {code}."))

    # 3. Indikator volume
    if acc:
        mfi = acc["mfi"]
        volume.append(_item(
            BAD if mfi >= 80 else GOOD if mfi > 50 else WARN if mfi > 20 else INFO, "Money Flow Index (MFI 14 hari)", f"{mfi:.0f}",
            "Indikator 0–100 seperti RSI, tapi memperhitungkan volume. Mengukur kuatnya uang yang masuk dibanding keluar selama 14 hari.",
            "Di atas 50 uang cenderung masuk. Di atas 80 sudah terlalu panas (overbought), rawan aksi ambil untung. "
            "Di bawah 20 sudah terlalu dingin (oversold), kadang jadi peluang pantulan.",
            "< 20 oversold · 20–50 lemah · 50–80 sehat · > 80 overbought.",
            f"MFI {code} {mfi:.0f}: " + ("terlalu panas, jangan kejar harga." if mfi >= 80 else "uang masuk dengan sehat." if mfi > 50
                                         else "uang cenderung keluar." if mfi > 20 else "sudah jenuh jual, tunggu tanda pantulan.")))
        volume.append(_item(
            GOOD if acc["obv_trend"] > 0 else WARN, "OBV (On Balance Volume)", "naik" if acc["obv_trend"] > 0 else "turun",
            "Volume dijumlahkan terus: ditambah saat harga naik, dikurangi saat harga turun.",
            "Yang dilihat arahnya. OBV naik saat harga datar sering berarti akumulasi diam-diam (harga akan menyusul naik). "
            "OBV turun saat harga naik = kenaikan tidak didukung volume (divergensi negatif).",
            "Searah harga = tren sehat · berlawanan = waspada pembalikan.",
            f"OBV {code} {'naik' if acc['obv_trend'] > 0 else 'turun'} dalam {acc['days']} hari terakhir."))
        volume.append(_item(
            GOOD if acc["ad_trend"] > 0 else WARN, "A/D line (Accumulation/Distribution)", "naik" if acc["ad_trend"] > 0 else "turun",
            "Mirip OBV, tapi memperhitungkan posisi harga penutupan dalam rentang hari itu (tutup di atas = akumulasi).",
            "Lebih halus daripada OBV karena hari naik tipis dengan tutup di bawah tetap dihitung sebagai distribusi.",
            "Naik = akumulasi · turun = distribusi.",
            f"A/D {code} {'naik' if acc['ad_trend'] > 0 else 'turun'}."))
        volume.append(_item(
            GOOD if acc["acc_days"] > acc["dist_days"] else WARN, "Hari akumulasi vs distribusi",
            f"{acc['acc_days']} vs {acc['dist_days']}",
            "Hari naik bervolume di atas rata-rata (akumulasi) dibanding hari turun bervolume di atas rata-rata (distribusi).",
            "Volume besar menunjukkan keyakinan. Kalau hari naik lebih sering bervolume besar, berarti pembeli lebih yakin daripada penjual.",
            "Akumulasi > distribusi = baik.",
            f"Kesimpulan pola volume {code}: **{acc['verdict']}**."))
    if ind and _num(ind.get("vol_ratio")) is not None:
        vr = ind["vol_ratio"]
        volume.append(_item(
            GOOD if vr >= 1.5 else INFO if vr >= 0.7 else WARN, "Volume hari ini vs rata-rata", f"{vr:.1f}x",
            "Volume transaksi hari terakhir dibagi rata-rata 20 hari.",
            "Scalping butuh saham yang 'hidup'. Lonjakan volume disertai harga naik = minat beli baru. Lonjakan volume dengan harga turun = panik jual.",
            "≥ 2x sangat aktif · 1–2x normal-aktif · < 0,7x sepi.",
            f"Volume {code} hari ini {vr:.1f}x rata-rata, harga {ind.get('chg_1d', 0):+.1f}%."))
    if pressure is not None and len(pressure):
        avg_buy = float(pressure["Beli %"].mean())
        dom = int((pressure["Beli %"] >= 60).sum())
        volume.append(_item(
            GOOD if avg_buy >= 55 else WARN if avg_buy <= 45 else INFO, "Tekanan beli 10 hari", f"{avg_buy:.0f}% beli",
            "Perkiraan porsi pembeli agresif dari posisi harga penutupan tiap hari (pengganti trade book).",
            "Seperti menghitung HAKA vs HAKI secara kasar. Untuk angka asli per transaksi, buka Trade Book di Stockbit.",
            "> 55% pembeli dominan · 45–55% seimbang · < 45% penjual dominan.",
            f"Dalam 10 hari, {dom} hari didominasi pembeli."))

    # 4. Likuiditas & biaya
    if sm:
        va = sm["value_avg"]
        liquid.append(_item(
            GOOD if va >= 10 else WARN if va >= 1 else BAD, "Likuiditas (nilai transaksi rata-rata)", f"Rp {va:,.1f} miliar/hari",
            "Rata-rata uang yang berpindah tangan per hari di saham ini.",
            "Ini syarat pertama scalping: kamu harus bisa keluar kapan saja. Di saham sepi, antrian beli (bid) tipis, sehingga saat "
            "mau jual harganya harus diturunkan beberapa tick.",
            "≥ Rp 10 M/hari likuid · Rp 1–10 M cukup (pakai lot kecil) · < Rp 1 M berbahaya untuk scalping.",
            f"Sebagai patokan, jangan pakai posisi lebih dari ±1% nilai transaksi harian, yaitu sekitar Rp {va * 0.01 * 1000:,.0f} juta untuk {code}."))
    if lv:
        tick = tick_size(lv["harga"])
        tick_pct = tick / lv["harga"] * 100
        fee = FEE_BUY + FEE_SELL
        need = math.ceil(fee / tick_pct) if tick_pct else 0
        atr_ticks = lv["atr"] / tick
        liquid.append(_item(
            GOOD if need <= 2 else WARN if need <= 4 else BAD, "Biaya per transaksi dalam tick", f"impas setelah naik {need} tick",
            "Tick adalah kenaikan harga terkecil (fraksi harga BEI). Fee beli + jual di broker online sekitar "
            f"{FEE_BUY:.2f}% + {FEE_SELL:.2f}% = {fee:.2f}%.",
            "Scalper mengambil untung kecil (beberapa tick), jadi fee bisa memakan semua untung. Hitung dulu harga harus naik berapa tick "
            "baru kamu impas.",
            "Impas ≤ 2 tick nyaman · 3–4 tick butuh gerakan lebih besar · > 4 tick kurang cocok untuk scalping.",
            f"Di harga Rp {lv['harga']:,.0f}, 1 tick = Rp {tick} ({tick_pct:.2f}%). Kamu baru untung setelah naik **{need} tick** "
            f"(Rp {lv['harga'] + need * tick:,.0f}). Cek fee brokermu sendiri."))
        liquid.append(_item(
            GOOD if atr_ticks >= need * 3 else WARN, "Ruang gerak harian (ATR)", f"Rp {lv['atr']:,.0f} ≈ {atr_ticks:.0f} tick",
            "ATR (Average True Range) = rata-rata jarak harga tertinggi dan terendah per hari selama 14 hari.",
            "Menunjukkan seberapa jauh harga biasa bergerak sehari. Gerak terlalu kecil = susah dapat untung setelah fee. "
            "Gerak terlalu besar = stop loss harus lebar.",
            "Idealnya ATR minimal 3x jumlah tick impas.",
            f"{code} biasanya bergerak {lv['atr'] / lv['harga'] * 100:.1f}% per hari, cukup untuk "
            f"{max(int(atr_ticks // max(need, 1)), 0)}x target impas."))

    # 5. Rencana
    if lv:
        entry = isum["vwap"] if isum and isum["vs_vwap"] > 0 else lv["support"]
        tick = tick_size(lv["harga"])
        plan.append(_item(
            INFO, "Contoh rencana scalping (latihan)", f"beli ±Rp {entry:,.0f}",
            "Rencana sederhana berbasis level money flow. Tulis rencana SEBELUM masuk agar tidak terbawa emosi.",
            "1) Tunggu harga mendekati area beli, jangan kejar harga yang sudah lari. 2) Pasang stop loss sebelum beli. "
            "3) Ambil untung bertahap. 4) Kalau harga turun menembus VWAP dengan uang keluar besar, keluar.",
            "Rasio untung : rugi minimal 1,5 : 1.",
            f"Area beli sekitar **Rp {entry:,.0f}** ({'VWAP' if isum and isum['vs_vwap'] > 0 else 'support'}) · stop loss "
            f"**Rp {max(entry - 2 * tick, lv['stop']):,.0f}** (±2 tick di bawah) · target cepat **Rp {entry + 4 * tick:,.0f}**, "
            f"target lanjut **Rp {lv['t1']:,.0f}** (resistance). Ini hanya contoh latihan, bukan rekomendasi."))

    groups = [(t, i, its) for t, i, its in (
        ("⏱️ Hari ini: siapa yang menang?", "Dihitung dari data per 5 menit hari bursa terakhir (tertunda ±15 menit dari Yahoo).", today),
        ("📅 Beberapa hari terakhir: arah arus uang", "Dihitung dari data harian 20 hari terakhir.", multi),
        ("📊 Indikator volume: kuatnya dorongan", "Indikator teknikal klasik yang membaca volume.", volume),
        ("💧 Likuiditas & biaya: bisa keluar cepat?", "Syarat wajib sebelum scalping.", liquid),
        ("📝 Rencana trading", "Menggabungkan semua poin di atas jadi rencana konkret.", plan),
    ) if its]
    concl = _conclude(groups,
                      f"Money flow {code} **mendukung**: uang cenderung masuk dan sahamnya cukup aktif. Cari entry di dekat VWAP/support.",
                      f"Money flow {code} **campuran**. Kalau mau scalping, pakai lot kecil dan disiplin stop loss.",
                      f"Money flow {code} **belum mendukung**: uang cenderung keluar atau saham kurang likuid. Lebih aman menunggu.")
    lessons = [
        "Scalping = berenang searah arus. Ikuti arah uang besar, jangan melawan.",
        "**VWAP** adalah garis kendali: di atasnya pembeli menang, di bawahnya penjual menang.",
        "Harga naik tapi uang bersih negatif = kenaikan semu. Harga datar tapi OBV naik = akumulasi diam-diam.",
        "Selalu hitung **tick impas** setelah fee, dan pastikan likuiditas cukup untuk keluar cepat.",
        "Data di sini perkiraan dari harga dan volume. Konfirmasi dengan **broker summary, trade book, dan order book** live di Stockbit.",
    ]
    return {"judul": f"Riset money flow {code}", "kesimpulan": concl, "groups": groups, "pelajaran": lessons,
            "kosong": not groups}


# ---------------------------------------------------------------- Pemegang saham

_ROLES = {
    "Pengendali": (
        "Pemegang pengendali: pihak yang menentukan arah perusahaan (memilih direksi, menyetujui aksi korporasi). "
        "Biasanya grup usaha atau keluarga pendiri.",
        "Pengendali paling bisa menggerakkan harga lewat **aksi korporasi**: tender offer atau buyback (biasanya harga naik), "
        "right issue, private placement, atau menjual sebagian saham (biasanya harga tertekan). Kalau pengendali menambah "
        "kepemilikan, itu tanda dia yakin dengan masa depan perusahaannya.",
        "Pantau Keterbukaan Informasi BEI: pengendali wajib lapor setiap membeli/menjual. Hati-hati kalau porsinya turun terus."),
    "Institusi asing": (
        "Dana investasi, bank kustodian, atau perusahaan dari luar negeri. Sering mewakili manajer investasi besar.",
        "Mereka membeli/menjual dalam jumlah sangat besar, jadi arus **foreign flow** sering menentukan tren harga saham besar. "
        "Keputusan mereka dipengaruhi kurs rupiah, suku bunga, dan masuk-keluarnya saham dari indeks global (MSCI, FTSE).",
        "Cek foreign flow (net buy/sell asing) di Stockbit. Asing net buy berhari-hari = akumulasi."),
    "Institusi/perusahaan lokal": (
        "Perusahaan, dana pensiun, asuransi, BPJS, atau badan negara (misalnya Danantara) dari dalam negeri.",
        "Institusi seperti dana pensiun dan asuransi umumnya investor jangka panjang yang menahan harga agar stabil. "
        "Kalau berbentuk PT, bisa jadi masih satu grup dengan pengendali (perusahaan afiliasi).",
        "Cek apakah PT ini terafiliasi dengan pengendali (lihat laporan tahunan bagian struktur grup)."),
    "Perorangan": (
        "Individu yang memegang di atas 5%. Sering disebut 'investor kakap', bisa pendiri, keluarga pemilik, atau investor besar.",
        "Satu orang dengan porsi besar bisa menggerakkan harga, apalagi kalau free float kecil. Pembelian atau penjualannya wajib "
        "dilaporkan, dan pasar sering ikut bereaksi. Kadang nama perorangan dipakai sebagai nominee (atas nama pihak lain).",
        "Cari nama orang ini di berita dan Keterbukaan Informasi: apakah dia sering masuk saham lain lalu harganya naik tajam?"),
    "Saham treasuri (dibeli kembali)": (
        "Saham milik perusahaan sendiri hasil buyback.",
        "Buyback mengurangi barang di pasar dan menunjukkan perusahaan menganggap harganya murah. Tapi saham ini bisa dijual lagi nanti.",
        "Cek kapan program buyback berakhir dan apakah saham treasuri akan dijual kembali."),
    "Masyarakat (publik < 5%)": (
        "Semua investor yang masing-masing memegang di bawah 5%, termasuk investor ritel seperti kita. Ini disebut free float.",
        "Inilah 'barang' yang benar-benar diperdagangkan setiap hari. Makin kecil free float, makin mudah harga digerakkan "
        "oleh sedikit pihak (naik atau turun tajam).",
        "Free float < 10% rawan digoreng dan bisa terkena aturan free float minimum BEI."),
}


def holders(code: str, major: pd.DataFrame | None, summary: dict, price: float | None, yahoo: dict | None = None) -> dict:
    yahoo = yahoo or {}
    people, struct = [], []
    if major is not None and not major.empty:
        df = major.dropna(subset=["Persen"]).sort_values("Persen", ascending=False)
        for _, r in df.iterrows():
            kind = r["Jenis"]
            role = "Pengendali" if r.get("Pengendali") or (r["Persen"] >= 50 and not kind.startswith(("Masyarakat", "Saham treasuri"))) else kind
            apa, cara, pantau = _ROLES.get(role, _ROLES["Perorangan"])
            shares = _num(r.get("Jumlah saham"))
            worth = f" Nilainya sekitar **{_rp(shares * price)}** di harga sekarang." if shares and price else ""
            lot = f" ({shares / 100:,.0f} lot)" if shares else ""
            if role == "Masyarakat (publik < 5%)":
                status = GOOD if r["Persen"] >= 20 else WARN if r["Persen"] >= 10 else BAD
                teks = f"Hanya {r['Persen']:.1f}% saham {code}{lot} yang beredar bebas di pasar.{worth}"
            else:
                status = INFO
                power = ("sangat besar: menentukan hampir semua keputusan" if r["Persen"] >= 50 else
                         "besar: suaranya berpengaruh di RUPS" if r["Persen"] >= 20 else "terasa bila dia membeli/menjual")
                teks = (f"{r['Pemegang']} memegang **{r['Persen']:.2f}%** saham {code}{lot}.{worth} "
                        f"Pengaruhnya {power}.")
                ff = summary.get("free_float", float("nan")) if summary else float("nan")
                if ff == ff and ff > 0 and r["Persen"] > ff:
                    teks += f" Porsinya lebih besar dari seluruh saham publik ({ff:.1f}%), jadi kalau dia menjual, pasar sulit menyerapnya."
            people.append(_item(status, r["Pemegang"], f"{r['Persen']:.2f}% · {role}", apa, cara, pantau, teks))
    if summary:
        top3 = summary["top3_pct"]
        struct.append(_item(
            WARN if top3 >= 80 else INFO, "Konsentrasi 3 pemegang teratas", f"{top3:.1f}%",
            "Total porsi tiga pemegang terbesar (di luar publik).",
            "Makin terkonsentrasi, makin sedikit pihak yang bisa menentukan harga. Bagus kalau mereka terus menambah, "
            "berbahaya kalau mereka mulai melepas.",
            "> 80% sangat terkonsentrasi · 50–80% ada pengendali jelas · < 50% tersebar.",
            f"Tiga pemegang terbesar {code} menguasai {top3:.1f}% saham."))
        if summary["foreign_pct"] > 0:
            struct.append(_item(
                GOOD, "Porsi institusi asing besar (> 5%)", f"{summary['foreign_pct']:.1f}%",
                "Total porsi institusi asing yang masing-masing memegang di atas 5%.",
                "Asing besar biasanya melakukan riset mendalam sebelum masuk, jadi kehadirannya sering dianggap tanda kepercayaan.",
                "Pantau foreign flow harian untuk melihat apakah mereka menambah atau mengurangi.",
                f"Institusi asing tercatat memegang {summary['foreign_pct']:.1f}% saham {code}."))
    ins = _num(yahoo.get("insider"))
    if ins is not None:
        struct.append(_item(
            INFO, "Orang dalam (insider) menurut Yahoo", f"{ins:.1f}%",
            "Porsi saham yang dipegang pengendali, direksi, dan komisaris.",
            "Insider yang membeli saham perusahaannya sendiri sering dianggap sinyal positif, karena merekalah yang paling tahu kondisi perusahaan.",
            "Pantau laporan transaksi direksi/komisaris di Keterbukaan Informasi BEI.",
            f"Insider {code} memegang sekitar {ins:.1f}%."))
    groups = [(t, i, its) for t, i, its in (
        ("👥 Siapa saja pemegangnya dan kenapa penting", "Data dari BEI (pemegang di atas 5% dan publik). Jenis pemegang ditebak dari nama.", people),
        ("🧩 Struktur kepemilikan", "Gambaran besar siapa yang menguasai saham ini.", struct),
    ) if its]
    return {"judul": f"Riset pemegang saham {code}",
            "kesimpulan": _conclude(groups, f"Struktur pemegang saham {code} **sehat**.",
                                    f"Struktur pemegang saham {code} **perlu dicermati**: ada pihak besar yang bisa menggerakkan harga.",
                                    f"Struktur pemegang saham {code} **berisiko**: saham terkonsentrasi dan barang di pasar sedikit."),
            "groups": groups, "kosong": not groups,
            "pelajaran": [
                "Daftar ini dari BEI dan hanya mencatat pemegang **di atas 5%**. Pihak di bawah 5% tidak terlihat namanya.",
                "Yang paling penting bukan siapa pemegangnya, tapi **perubahan porsinya**: bandingkan laporan KSEI/BEI tiap bulan.",
                "Pengendali menambah + free float kecil = harga cenderung mudah naik. Pengendali menjual = waspada.",
                "Untuk melihat siapa yang membeli/menjual **hari ini**, pakai broker summary dan foreign flow, bukan daftar pemegang.",
                "Kepemilikan besar tidak menjamin harga naik. Gabungkan dengan fundamental dan money flow.",
            ]}


# ---------------------------------------------------------------- Ekspor


def to_markdown(res: dict) -> str:
    c = res["kesimpulan"]
    out = [f"# {res['judul']}", "", f"**Kesimpulan:** {c['teks']} ({c['good']} dari {c['total']} poin positif)", ""]
    for title, intro, items in res["groups"]:
        out += [f"## {title}", f"_{intro}_", ""]
        for it in items:
            out += [f"### {it['status']} {it['judul']}: {it['nilai']}",
                    f"- **Apa ini?** {it['apa']}", f"- **Cara membaca:** {it['cara']}",
                    f"- **Patokan umum:** {it['patokan']}", f"- **Artinya untuk saham ini:** {it['saham']}", ""]
    out += ["## 📌 Pelajaran kunci"] + [f"- {x}" for x in res["pelajaran"]]
    out += ["", "_Dibuat otomatis dari data Yahoo Finance. Patokan adalah aturan praktis umum. Bukan rekomendasi investasi._"]
    return "\n".join(out)
