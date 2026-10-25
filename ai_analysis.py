"""Analisis saham dengan Claude: menggabungkan berita, teknikal, dan fundamental jadi satu laporan."""

from __future__ import annotations

import os
from collections.abc import Iterator

import anthropic

MODEL = "claude-opus-5-5"

SYSTEM = """Kamu analis riset saham Bursa Efek Indonesia yang menulis untuk investor ritel pemula dalam Bahasa Indonesia sehari-hari.
Tugasmu menilai apakah sebuah saham layak dibeli untuk trading/swing beberapa hari sampai beberapa minggu, berdasarkan data yang diberikan
dan pencarian web untuk berita, laporan keuangan, aksi korporasi, dan foreign flow/broker summary terbaru bila ada yang dipublikasikan media.
Jujur dan seimbang: sebut risiko sama seriusnya dengan peluang. Jangan menjanjikan kenaikan harga. Jika data kurang, katakan.
Sebut sumber (nama media + tanggal) untuk fakta dari pencarian web. Angka harga dalam Rupiah dan bulatkan ke fraksi harga BEI.
Data order book real-time tidak tersedia; pakai peta volume per harga sebagai pendekatan dan jangan mengarang data bid/offer.
Gunakan kalimat pendek, poin-poin, tabel, dan emoji penanda (✅ ⚠️ 🛑 🎯) supaya mudah dibaca. Jelaskan istilah teknis dalam kurung.
Lakukan pencarian dulu, lalu tulis laporan langsung tanpa kalimat pengantar.

Format laporan (Markdown), persis urutannya:
#### 📌 Intinya
Satu baris: label tebal **MENARIK**, **PANTAU**, atau **HINDARI** + keyakinan (rendah/sedang/tinggi). Lalu 3 poin alasan terpenting.
#### 🎯 Rencana trading
Tabel kolom: Langkah | Harga | Keterangan. Baris: Area beli, Stop loss, Target 1, Target 2, Rasio untung/rugi.
Tambahkan 1-2 kalimat kapan sebaiknya masuk (misalnya tunggu koreksi ke support atau tembus resistance dengan volume).
#### 📰 Berita & katalis
Poin-poin berita terpenting (tanggal, sumber) dan dampaknya ke harga. Sebut katalis yang akan datang (RUPS, dividen, rilis laporan keuangan).
#### 📈 Teknikal
Tabel kolom: Indikator | Nilai | Artinya. Lalu ringkasan tren dalam 2 kalimat.
#### 📊 Peta volume & bandarmologi
Jelaskan zona volume besar (support/resistance), apakah ada akumulasi atau distribusi, dan info foreign flow/broker dari berita bila ada.
Akhiri dengan apa yang harus dicek di order book Stockbit (level bid/offer spesifik yang perlu diperhatikan).
#### 🏢 Fundamental & valuasi
Tabel kolom: Indikator | Nilai | Penilaian. Lalu kesimpulan valuasi dibanding rata-rata sektor bila kamu tahu.
#### ⚠️ Risiko utama
3-5 poin.
#### 🔀 Skenario
Tabel kolom: Skenario | Pemicu | Harga tujuan. Baris: Naik, Sideways, Turun.
"""


def has_key() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


def _fmt(value) -> str:
    if isinstance(value, float):
        return f"{value:,.4g}"
    return str(value)


def build_prompt(code: str, name: str, sector: str, ind: dict | None, lv: dict | None, acc: dict | None,
                 vp, fund: dict, articles: list, scores: dict, keystats_notes: list[str] = ()) -> str:
    lines = [f"Saham: {code} ({name}), sektor {sector}.", ""]
    lines.append(f"Skor aplikasi: gabungan {scores['total']:+.2f}, berita {scores['news']:+.2f}, "
                 f"teknikal {scores['tech']:+.2f} (skala -5 s.d. +5).")
    if ind:
        lines += ["", "Data teknikal:",
                  f"- Harga terakhir Rp {ind['harga']:,.0f} per {ind['tanggal']}",
                  f"- Perubahan: 1 hari {ind['chg_1d']:+.1f}%, 5 hari {ind['chg_5d']:+.1f}%, 1 bulan {ind['chg_1m']:+.1f}%",
                  f"- Harga vs MA20: {ind['vs_ma20']:+.1f}%, MA20 {'di atas' if ind['ma20_gt_ma50'] else 'di bawah'} MA50",
                  f"- RSI14: {ind['rsi14']:.0f}, volume hari terakhir {ind['vol_ratio']:.1f}x rata-rata 20 hari"]
    if lv:
        lines += ["", "Level hasil hitungan aplikasi:",
                  f"- Support Rp {lv['support']:,.0f}, resistance Rp {lv['resistance']:,.0f}, ATR Rp {lv['atr']:,.0f}",
                  f"- Area beli Rp {lv['entry_low']:,.0f}–{lv['entry_high']:,.0f}, stop loss Rp {lv['stop']:,.0f}, "
                  f"target 1 Rp {lv['t1']:,.0f}, target 2 Rp {lv['t2']:,.0f}, rasio untung/rugi ke T1 {lv['rr1']:.1f}x"]
    if acc:
        lines += ["", f"Akumulasi/distribusi {acc['days']} hari: {acc['verdict']}; hari naik bervolume besar {acc['acc_days']}, "
                      f"hari turun bervolume besar {acc['dist_days']}; MFI {acc['mfi']:.0f}; "
                      f"OBV {'naik' if acc['obv_trend'] > 0 else 'turun'}; A/D {'naik' if acc['ad_trend'] > 0 else 'turun'}."]
    if vp is not None:
        top = vp.sort_values("volume", ascending=False).head(4)
        lines += ["", "Zona volume terbesar 60 hari (pengganti order book):"]
        lines += [f"- {row.rentang}: {row.persen:.0f}% volume" for row in top.itertuples()]
    if fund:
        lines += ["", "Fundamental (Yahoo Finance; ROE/margin/pertumbuhan dalam desimal, dividen yield dan utang/ekuitas dalam persen):"]
        lines += [f"- {k}: {_fmt(v)}" for k, v in fund.items()]
    if keystats_notes:
        lines += ["", "Catatan tambahan (kinerja kuartalan & risiko):"] + [f"- {n}" for n in keystats_notes]
    if articles:
        lines += ["", "Berita yang ditemukan aplikasi (skor sentimen kamus kata):"]
        for a in articles[:15]:
            lines.append(f"- [{a.published:%d %b %Y}] {a.title} ({a.source}, skor {a.sentiment:+.1f})")
    lines += ["", f"Cari juga berita, laporan keuangan, dan foreign flow terbaru {code} di web, lalu tulis laporannya."]
    return "\n".join(lines)


def stream_analysis(prompt: str) -> Iterator[str]:
    """Hasilkan potongan teks laporan secara bertahap (untuk ditampilkan langsung)."""
    client = anthropic.Anthropic()
    with client.beta.messages.stream(
        model=MODEL,
        max_tokens=16000,
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        output_config={"effort": "medium"},
        system=SYSTEM,
        tools=[{"type": "web_search_20260209", "name": "web_search", "max_uses": 6,
                "user_location": {"type": "approximate", "country": "ID"}}],
        messages=[{"role": "user", "content": prompt}],
    ) as stream:
        yield from stream.text_stream
        final = stream.get_final_message()
    if final.stop_reason == "refusal":
        yield "\n\n_Analisis tidak bisa diselesaikan untuk permintaan ini._"
    elif final.stop_reason == "max_tokens":
        yield "\n\n_Laporan terpotong karena terlalu panjang._"


BROKER_SYSTEM = """Kamu analis bandarmologi saham Bursa Efek Indonesia yang menjelaskan dengan bahasa sederhana untuk pemula.
Kamu menerima screenshot dan/atau teks broker summary (biasanya dari Stockbit) untuk satu saham.
Baca angkanya dengan teliti. Kalau ada angka yang tidak terbaca jelas, katakan, jangan menebak.
Jangan menjanjikan kenaikan harga. Gunakan tabel, poin pendek, dan emoji penanda (✅ ⚠️ 🔥).

Format laporan (Markdown):
#### 📌 Intinya
Satu baris: **AKUMULASI**, **DISTRIBUSI**, atau **NETRAL/TIDAK JELAS** + keyakinan, lalu 3 poin alasan.
#### 🟢 Pembeli terbesar
Tabel: Broker | Nama & jenis | Lot/nilai beli | Rata-rata harga beli | Catatan.
#### 🔴 Penjual terbesar
Tabel yang sama untuk penjual.
#### 🔍 Bacaan bandarmologi
Apakah pembelian terkonsentrasi di sedikit broker (tanda bandar) atau tersebar (ritel), broker asing vs lokal vs ritel,
posisi harga sekarang dibanding rata-rata harga beli pembeli besar (di bawah = pembeli besar masih rugi, cenderung dijaga;
jauh di atas = rawan ambil untung), dan apakah broker ritel (YP, PD, XC, XL, dll.) dominan sebagai pembeli (sering tanda
ritel sedang "nyangkut") atau penjual.
#### 🎯 Yang perlu dipantau
Level harga penting (rata-rata harga bandar), broker yang perlu diikuti beberapa hari ke depan, dan tanda bahaya.
"""


def stream_broker_analysis(code: str, images: list[tuple[bytes, str]], text: str, context: str) -> Iterator[str]:
    """Analisis broker summary dari screenshot (PNG/JPEG) dan/atau teks tempelan."""
    import base64

    from brokers import BROKERS

    dictionary = "\n".join(f"- {k}: {v[0]} ({v[1]}, {v[2]})" for k, v in BROKERS.items())
    content: list[dict] = []
    for data, mime in images:
        content.append({"type": "image", "source": {"type": "base64", "media_type": mime,
                                                    "data": base64.b64encode(data).decode()}})
    content.append({"type": "text", "text": (
        f"Saham: {code}.\n\nKonteks dari aplikasi:\n{context}\n\n"
        f"Kamus kode broker (bisa tidak lengkap):\n{dictionary}\n\n"
        + (f"Teks broker summary yang ditempel pengguna:\n{text}\n\n" if text.strip() else "")
        + "Analisis broker summary di atas.")})
    client = anthropic.Anthropic()
    with client.beta.messages.stream(
        model=MODEL,
        max_tokens=16000,
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        output_config={"effort": "medium"},
        system=BROKER_SYSTEM,
        messages=[{"role": "user", "content": content}],
    ) as stream:
        yield from stream.text_stream
        final = stream.get_final_message()
    if final.stop_reason == "refusal":
        yield "\n\n_Analisis tidak bisa diselesaikan untuk permintaan ini._"
