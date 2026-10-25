"""Riset Saham: berita + sentimen + momentum harga saham IDX.

Jalankan:  streamlit run app.py
"""

from __future__ import annotations

import os
from collections import defaultdict

import altair as alt
import pandas as pd
import streamlit as st

import ai_analysis
import analysis
import news
import prices
import universe
from brokers import BROKERS
from tickers import TICKERS

DEMO = os.environ.get("RISET_DEMO") == "1"

st.set_page_config(page_title="Riset Saham", page_icon="📈", layout="wide")


def secret(name: str) -> str | None:
    """Ambil rahasia dari Streamlit Secrets (saat online) atau variabel lingkungan (saat di komputer)."""
    try:
        if name in st.secrets:
            return str(st.secrets[name])
    except Exception:
        pass
    return os.environ.get(name)


if secret("ANTHROPIC_API_KEY"):
    os.environ["ANTHROPIC_API_KEY"] = secret("ANTHROPIC_API_KEY")

# Kunci sederhana supaya aplikasi online (dan API key di dalamnya) tidak dipakai orang lain.
APP_PASSWORD = secret("APP_PASSWORD")
if APP_PASSWORD and not st.session_state.get("unlocked"):
    st.title("📈 Riset Saham")
    pw = st.text_input("Kata sandi", type="password")
    if pw == APP_PASSWORD:
        st.session_state["unlocked"] = True
        st.rerun()
    elif pw:
        st.error("Kata sandi salah.")
    st.stop()

DISCLAIMER = (
    "⚠️ **Bukan rekomendasi investasi.** Skor di aplikasi ini dihitung otomatis dari kata-kata "
    "di berita dan pergerakan harga, dan bisa salah. Berita positif tidak menjamin harga naik. "
    "Selalu cek laporan keuangan, valuasi, dan atur risikomu sendiri sebelum membeli."
)


@st.cache_data(ttl=900, show_spinner="Mengambil berita terbaru...")
def load_news(extra: tuple[str, ...]):
    if DEMO:
        import demo
        return demo.articles(), {"Data contoh": "OK"}
    return news.fetch_all(list(extra))


@st.cache_data(ttl=6 * 3600, show_spinner=False)
def load_fundamentals(code: str):
    return {} if DEMO else prices.fundamentals(code)


@st.cache_data(ttl=6 * 3600, show_spinner=False)
def load_keystats(code: str):
    if DEMO:
        import demo
        return demo.keystats(code)
    return prices.keystats(code)


@st.cache_data(ttl=900, show_spinner="Mengambil data harga semua saham...")
def load_prices(codes: tuple[str, ...]):
    if DEMO:
        import demo
        return demo.history(list(codes))
    return prices.download_history(list(codes))


def label(score: float) -> str:
    if score >= 2.5:
        return "🟢 Sangat positif"
    if score >= 1:
        return "🟢 Positif"
    if score > -1:
        return "⚪ Netral"
    if score > -2.5:
        return "🔴 Negatif"
    return "🔴 Sangat negatif"


def fmt_pct(x: float) -> str:
    return "-" if x != x else f"{x:+.1f}%"


@st.cache_data(ttl=24 * 3600, show_spinner="Mengambil daftar semua saham BEI...")
def load_universe():
    if DEMO:
        import demo
        return demo.universe(), "data contoh"
    return universe.load()


uni, uni_source = load_universe()
UNI = {r.Kode: (r.Perusahaan, r.Sektor, r.Kapitalisasi) for r in uni.itertuples()}
for _code, (_name, _sector, _) in TICKERS.items():
    UNI.setdefault(_code, (_name, _sector, None))
news.KNOWN_CODES.update(UNI)


def name_of(code: str) -> str:
    return str(UNI.get(code, (code,))[0] or code)


def sector_of(code: str) -> str:
    return str(UNI.get(code, (code, "-"))[1] or "-")


def mcap_of(code: str) -> float | None:
    v = UNI.get(code, (None, None, None))[2]
    return float(v) if v is not None and v == v else None


# ---------- Sidebar ----------
with st.sidebar:
    st.title("📈 Riset Saham")
    st.caption("Berita & sentimen saham Bursa Efek Indonesia")
    if st.button("🔄 Muat ulang data", width="stretch"):
        st.cache_data.clear()
    watch_raw = st.text_input("Pantau saham tertentu (pisahkan koma)", placeholder="BBCA, ANTM, GOTO")
    watch = tuple(c.strip().upper() for c in watch_raw.split(",") if c.strip().upper() in UNI)
    w_news = st.slider("Bobot berita vs teknikal", 0.0, 1.0, 0.6, 0.1,
                       help="1.0 = hanya berita, 0.0 = hanya pergerakan harga")
    min_news = st.number_input("Minimal jumlah berita", 1, 10, 1)
    only_positive = st.checkbox("Tampilkan hanya skor positif", value=False)

if DEMO:
    st.warning("Mode DEMO: semua berita dan harga di bawah adalah DATA CONTOH, bukan data pasar asli.")
st.info(DISCLAIMER)

articles, status = load_news(tuple(f"saham {c}" for c in watch))
agg = news.aggregate_by_ticker(articles)
for c in watch:
    agg.setdefault(c, {"count": 0, "positive": 0, "negative": 0, "news_score": 0.0, "articles": []})

news_codes = {c for c, d in agg.items() if d["count"] >= min_news or c in watch}
mentioned = len(agg)
history = load_prices(tuple(sorted(TICKERS)))
agg = defaultdict(lambda: {"count": 0, "positive": 0, "negative": 0, "news_score": 0.0, "articles": []}, agg)
codes = tuple(sorted(set(history) | news_codes))

with st.sidebar:
    with st.expander("Status sumber berita"):
        for name, s in status.items():
            st.write(f"{'✅' if s.startswith('OK') else '❌'} {name}: {s}")
    st.caption(f"{len(articles)} berita unik, {mentioned} saham disebut. Daftar saham: {len(uni)} emiten "
               f"(sumber: {uni_source}).")

# ---------- Peringkat ----------
def safe_indicators(df):
    try:
        return prices.indicators(df) if df is not None and len(df) >= 2 else None
    except Exception:
        return None


def build_row(code: str, hist) -> dict:
    d = agg[code]
    news_score = max(-5.0, min(5.0, d["news_score"]))
    ind = safe_indicators(hist)
    inds[code] = ind
    tech = prices.technical_score(ind) if ind else 0.0
    total = w_news * news_score + (1 - w_news) * tech if ind else news_score
    return {
        "Kode": code, "Perusahaan": name_of(code), "Sektor": sector_of(code),
        "Skor": round(total, 2), "Sinyal": label(total),
        "Skor berita": round(news_score, 2), "Skor teknikal": round(tech, 2) if ind else None,
        "Berita (+/-)": f"{d['count']} ({d['positive']}/{d['negative']})",
        "Harga": ind["harga"] if ind else None,
        "1 hari": fmt_pct(ind["chg_1d"]) if ind else "-",
        "5 hari": fmt_pct(ind["chg_5d"]) if ind else "-",
        "RSI": round(ind["rsi14"]) if ind else None,
        "Volume vs rata2": f"{ind['vol_ratio']:.1f}x" if ind and ind["vol_ratio"] == ind["vol_ratio"] else "-",
    }


inds = {}
rows = [build_row(code, history.get(code)) for code in codes]
table_all = pd.DataFrame(rows)
if not table_all.empty:
    table_all = table_all.sort_values("Skor", ascending=False)
# Peringkat & rekomendasi hanya untuk saham yang diberitakan; screener & detail memakai semua saham.
table = table_all[table_all["Kode"].isin(news_codes)] if not table_all.empty else table_all
if only_positive and not table.empty:
    table = table[table["Skor"] > 0]

def stockbit_url(code: str) -> str:
    return f"https://stockbit.com/symbol/{code}"


def is_candidate(r) -> bool:
    """Kriteria Rekomendasi Naik: skor kuat, berita positif, tren tidak turun, belum jenuh beli,
    dan tidak ada berita sangat negatif (misalnya suspensi atau gagal bayar) dalam 2 hari terakhir."""
    code = r["Kode"]
    ind = inds.get(code)
    if r["Skor"] < 1.5 or r["Skor berita"] <= 0:
        return False
    if ind and (prices.technical_score(ind) < 0 or ind["rsi14"] > 75):
        return False
    return not any(a.sentiment <= -2.5 and a.age_hours <= 48 for a in agg[code]["articles"])


def reasons(r) -> list[str]:
    code = r["Kode"]
    d, ind = agg[code], inds.get(code)
    out = [f"{d['positive']} dari {d['count']} berita bernada positif"]
    if ind:
        if ind["vs_ma20"] > 0:
            out.append(f"Harga {ind['vs_ma20']:+.1f}% di atas rata-rata 20 hari (tren naik)")
        if ind["ma20_gt_ma50"]:
            out.append("MA20 di atas MA50 (tren menengah naik)")
        if ind["vol_ratio"] == ind["vol_ratio"] and ind["vol_ratio"] > 1.5:
            out.append(f"Volume {ind['vol_ratio']:.1f}x rata-rata, ada minat beli")
        out.append(f"RSI {ind['rsi14']:.0f}: " + ("masih ada ruang naik" if ind["rsi14"] <= 70 else "mendekati jenuh beli, hati-hati"))
    else:
        out.append("Data harga tidak tersedia, cek grafik di Stockbit")
    return out


tab_reco, tab_screen, tab_rank, tab_detail, tab_news, tab_help = st.tabs(
    ["🚀 Rekomendasi Naik", "🧮 Screener", "🏆 Peringkat", "🔍 Detail saham", "📰 Semua berita", "❓ Cara membaca skor"])

with tab_reco:
    st.subheader("Kandidat saham berpotensi naik")
    st.caption("Disaring otomatis: skor gabungan minimal +1.5, berita positif, tren harga tidak turun, RSI belum di atas 75, "
               "dan tidak ada berita sangat negatif dalam 2 hari terakhir. Ini daftar kandidat untuk diriset, bukan perintah beli.")
    reco = table[table.apply(is_candidate, axis=1)] if not table.empty else table
    if reco.empty:
        st.info("Hari ini belum ada saham yang memenuhi semua kriteria. Lihat tab Peringkat untuk daftar lengkapnya.")
    for _, r in reco.head(10).iterrows():
        code = r["Kode"]
        ind = inds.get(code)
        with st.container(border=True):
            left, right = st.columns([3, 1])
            with left:
                st.markdown(f"### {code} · {r['Perusahaan']}")
                st.caption(f"{r['Sektor']} · {r['Sinyal']} · skor {r['Skor']:+.2f}")
                st.markdown("\n".join(f"- {x}" for x in reasons(r)))
                top_news = sorted(agg[code]["articles"], key=lambda a: a.sentiment, reverse=True)[:2]
                for a in top_news:
                    st.markdown(f"📰 [{a.title}]({a.link}) · <small>{a.source}</small>", unsafe_allow_html=True)
            with right:
                if ind:
                    st.metric("Harga", f"Rp {ind['harga']:,.0f}", f"{fmt_pct(ind['chg_1d'])} hari ini")
                st.link_button("Buka di Stockbit", stockbit_url(code), type="primary", width="stretch")
                st.caption("Analisis AI lengkap ada di tab Detail saham.")

with tab_screen:
    st.subheader("Screening saham")
    scope = st.radio("Cakupan", [f"Saham likuid ({len(history)})", f"Semua saham BEI ({len(uni)})"], horizontal=True,
                     help="Semua saham BEI termasuk saham kecil yang jarang dibahas. Pengambilan datanya lebih lama (1–2 menit), "
                          "lalu disimpan 1 jam.")
    s_hist = load_prices(tuple(sorted(uni["Kode"]))) if scope.startswith("Semua") else history
    st.caption(f"Menyaring {len(s_hist)} saham memakai data harga harian, termasuk yang tidak sedang diberitakan.")
    preset = st.radio("Strategi", list(analysis.PRESETS), horizontal=True)
    st.info(analysis.PRESETS[preset])
    f1, f2, f3, f4 = st.columns(4)
    sectors = sorted({sector_of(c) for c in s_hist})
    pick_sectors = f1.multiselect("Sektor", sectors, placeholder="Semua sektor")
    price_rng = f2.slider("Harga (Rp)", 1, 15000, (1, 15000), step=1)
    rsi_rng = f3.slider("RSI", 0, 100, (0, 100))
    min_value = f4.number_input("Nilai transaksi min (Rp miliar/hari)", 0.0, 1000.0, 0.5, 0.5,
                                help="Saham dengan nilai transaksi kecil sulit dibeli/dijual (kurang likuid).")
    only_up = st.checkbox("Hanya tren naik (MA20 di atas MA50)")
    srows = []
    for c, df in s_hist.items():
        ind = inds.get(c) or safe_indicators(df)
        if ind and len(df) >= 30:
            try:
                srows.append(analysis.screen_row(c, df, ind, mcap_of(c)))
            except Exception:
                continue
    screen = pd.DataFrame(srows)
    if not screen.empty:
        screen["Perusahaan"] = screen["Kode"].map(name_of)
        screen["Sektor"] = screen["Kode"].map(sector_of)
        screen["Berita"] = screen["Kode"].map(lambda c: label(max(-5.0, min(5.0, agg[c]["news_score"]))) if agg[c]["count"] else "-")
        screen = analysis.apply_preset(screen, preset)
        if pick_sectors:
            screen = screen[screen["Sektor"].isin(pick_sectors)]
        screen = screen[screen["Harga"].between(*price_rng) & screen["RSI"].between(*rsi_rng)
                        & (screen["Nilai transaksi (Rp M/hari)"] >= min_value)]
        if only_up:
            screen = screen[screen["Tren naik"]]
    if screen.empty:
        st.warning("Tidak ada saham yang lolos. Coba longgarkan filter atau pilih strategi lain.")
    else:
        screen = screen.sort_values("Volume x", ascending=False)
        st.write(f"**{len(screen)} saham lolos.** Pilih kodenya di tab Detail saham untuk analisis lengkap.")
        if (screen["Risiko gorengan"] == "🔥 Tinggi").any():
            st.warning("Ada saham berisiko gorengan tinggi di daftar ini (likuiditas tipis, sangat volatil, atau sering "
                       "mendekati ARA). Bisa naik cepat, tapi juga bisa ARB berhari-hari atau disuspensi.")
        cols = ["Kode", "Perusahaan", "Sektor", "Harga", "1 hari %", "5 hari %", "1 bulan %", "RSI", "vs MA20 %",
                "Volume x", "Nilai transaksi (Rp M/hari)", "Kapitalisasi (Rp T)", "Risiko gorengan", "Akumulasi", "MFI",
                "Berita"]
        show = screen[cols].copy()
        show["Stockbit"] = show["Kode"].map(stockbit_url)
        st.dataframe(show, hide_index=True, width="stretch", column_config={
            "Harga": st.column_config.NumberColumn(format="Rp %d"),
            **{c: st.column_config.NumberColumn(format="%+.1f%%") for c in ["1 hari %", "5 hari %", "1 bulan %", "vs MA20 %"]},
            "RSI": st.column_config.NumberColumn(format="%.0f"), "MFI": st.column_config.NumberColumn(format="%.0f"),
            "Volume x": st.column_config.NumberColumn(format="%.1fx"),
            "Nilai transaksi (Rp M/hari)": st.column_config.NumberColumn(format="%.1f"),
            "Kapitalisasi (Rp T)": st.column_config.NumberColumn(format="%.2f"),
            "Stockbit": st.column_config.LinkColumn(display_text="Buka"),
        })

with tab_rank:
    st.subheader("Saham yang paling banyak diberitakan positif")
    if table.empty:
        st.warning("Belum ada saham yang terdeteksi di berita. Coba muat ulang, atau cek status sumber berita di sidebar.")
    else:
        top = table.head(3)
        cols = st.columns(len(top))
        for col, (_, r) in zip(cols, top.iterrows()):
            col.metric(f"{r['Kode']} · {r['Perusahaan']}", f"{r['Skor']:+.2f}", r["Sinyal"], delta_color="off")
        st.dataframe(table, hide_index=True, width="stretch",
                     column_config={"Harga": st.column_config.NumberColumn(format="Rp %d"),
                                    "Skor": st.column_config.ProgressColumn(min_value=-5, max_value=5, format="%.2f")})

with tab_detail:
    ranked = list(table_all["Kode"]) if not table_all.empty else []
    options = ranked + sorted(set(UNI) - set(ranked))
    if not options:
        st.write("Belum ada saham untuk ditampilkan.")
    else:
        code = st.selectbox("Pilih saham", options,
                            format_func=lambda c: f"{c} · {name_of(c)}",
                            help="Ketik kode atau nama untuk mencari di antara semua saham BEI.")
        name, sector = name_of(code), sector_of(code)
        hist = history.get(code)
        if hist is None:
            hist = load_prices((code,)).get(code)
        r = build_row(code, hist)
        fund = load_fundamentals(code)
        ind = inds[code]
        if hist is not None and len(hist) >= 30:
            vp = analysis.volume_profile(hist)
            lv = analysis.key_levels(hist, vp)
            acc = analysis.accumulation(hist)
            piv = analysis.pivots(hist)
            ara, arb = analysis.auto_reject(lv["harga"])
            checks = analysis.checklist(ind, acc, lv, fund)
        else:
            vp = lv = acc = piv = None
            checks = []

        head_l, head_r = st.columns([3, 1])
        head_l.markdown(f"## {code} · {name}")
        head_l.caption(f"{sector} · sinyal aplikasi: {r['Sinyal']} (skor {r['Skor']:+.2f})")
        head_r.link_button("📲 Buka di Stockbit", stockbit_url(code), type="primary", width="stretch")

        if ind:
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Harga terakhir", f"Rp {ind['harga']:,.0f}", f"{fmt_pct(ind['chg_1d'])} hari ini")
            c2.metric("5 hari / 1 bulan", fmt_pct(ind["chg_5d"]), f"{fmt_pct(ind['chg_1m'])} sebulan", delta_color="off")
            c3.metric("Skor berita", f"{r['Skor berita']:+.2f}", r["Berita (+/-)"] + " berita", delta_color="off")
            c4.metric("Akumulasi?", acc["verdict"] if acc else "-",
                      f"Money Flow {acc['mfi']:.0f}" if acc else None, delta_color="off")

        risk_level, risk_flags = analysis.speculative_risk(hist, ind, mcap_of(code)) if ind and hist is not None and len(hist) >= 20 else ("Rendah", [])
        if risk_level != "Rendah":
            box = st.error if risk_level == "Tinggi" else st.warning
            box(f"**{'🔥' if risk_level == 'Tinggi' else '⚠️'} Risiko saham gorengan: {risk_level}**\n\n"
                + "\n".join(f"- {f}" for f in risk_flags))
            with st.expander("Tips kalau mau ikut saham spekulatif"):
                st.markdown(analysis.GORENGAN_GUIDE)

        # 1. Ringkasan
        st.markdown("### 1️⃣ Ringkasan cepat")
        if checks:
            good = sum(1 for s, _ in checks if s == "✅")
            ratio = good / len(checks)
            msg = f"{good} dari {len(checks)} poin mendukung kenaikan."
            if ratio >= 0.7:
                st.success(f"**Kondisi mendukung kenaikan.** {msg}")
            elif ratio >= 0.4:
                st.warning(f"**Kondisi campuran, perlu hati-hati.** {msg}")
            else:
                st.error(f"**Kondisi belum mendukung.** {msg}")
            for status, text in checks:
                st.markdown(f"{status} {text}")
        else:
            st.caption("Data harga belum cukup untuk analisis detail.")

        if lv:
            # 2. Level harga
            st.markdown("### 2️⃣ Level harga penting")
            st.caption("Dihitung dari support/resistance, zona volume terbesar, dan rata-rata gerak harian (ATR). "
                       "Sudah dibulatkan ke fraksi harga BEI.")
            levels = pd.DataFrame([
                ["🎯 Target 2", f"Rp {lv['t2']:,.0f}", f"{lv['t2_pct']:+.1f}%", "Target lanjutan bila tren kuat"],
                ["🎯 Target 1", f"Rp {lv['t1']:,.0f}", f"{lv['t1_pct']:+.1f}%", "Resistance terdekat, area ambil untung pertama"],
                ["🟢 Area beli", f"Rp {lv['entry_low']:,.0f} – {lv['entry_high']:,.0f}", "",
                 "Antri beli di rentang ini, hindari mengejar harga"],
                ["🛡️ Support", f"Rp {lv['support']:,.0f}", f"{(lv['support'] / lv['harga'] - 1) * 100:+.1f}%", "Level penahan turun"],
                ["🛑 Stop loss", f"Rp {lv['stop']:,.0f}", f"{-lv['risk_pct']:+.1f}%", "Jual bila tutup di bawah level ini"],
            ], columns=["Level", "Harga", "Dari harga kini", "Artinya"])
            st.table(levels.set_index("Level"))
            k1, k2, k3, k4 = st.columns(4)
            k1.metric("Untung/rugi ke T1", f"{lv['rr1']:.1f}x" if lv["rr1"] == lv["rr1"] else "-",
                      "layak" if lv["rr1"] >= 1.5 else "kurang", delta_color="normal" if lv["rr1"] >= 1.5 else "inverse")
            k2.metric("Gerak harian rata2 (ATR)", f"Rp {lv['atr']:,.0f}", f"{lv['atr'] / lv['harga'] * 100:.1f}% per hari", delta_color="off")
            k3.metric("Perkiraan ARA besok", f"Rp {ara:,.0f}")
            k4.metric("Perkiraan ARB besok", f"Rp {arb:,.0f}")
            st.caption(f"Fraksi harga saat ini Rp {analysis.tick_size(lv['harga'])}. Pivot hari ini: "
                       + " · ".join(f"{k} Rp {v:,.0f}" for k, v in piv.items())
                       + ". Batas ARA/ARB adalah perkiraan, cek aturan BEI terbaru.")

            # 3. Grafik
            st.markdown("### 3️⃣ Grafik harga & level")
            df = hist[["Close"]].rename(columns={"Close": "Harga"})
            df["MA20"] = df["Harga"].rolling(20).mean()
            df["MA50"] = df["Harga"].rolling(50).mean()
            long = df.reset_index(names="Tanggal").melt("Tanggal", var_name="Garis", value_name="Rp").dropna()
            lines = pd.DataFrame({"Rp": [lv["t1"], lv["stop"], lv["support"]],
                                  "Level": ["Target 1", "Stop loss", "Support"]})
            price_chart = alt.Chart(long).mark_line().encode(
                x="Tanggal:T", y=alt.Y("Rp:Q", scale=alt.Scale(zero=False)), color="Garis:N",
                tooltip=["Tanggal:T", "Garis:N", alt.Tooltip("Rp:Q", format=",.0f")])
            rules = alt.Chart(lines).mark_rule(strokeDash=[6, 4]).encode(
                y="Rp:Q", color=alt.Color("Level:N", scale=alt.Scale(
                    domain=["Target 1", "Stop loss", "Support"], range=["#2e7d32", "#c62828", "#f9a825"])),
                tooltip=["Level:N", alt.Tooltip("Rp:Q", format=",.0f")])
            st.altair_chart((price_chart + rules).resolve_scale(color="independent").properties(height=320), width="stretch")

            # 4. Peta volume
            st.markdown("### 4️⃣ Peta volume per harga (pengganti order book)")
            st.caption("Di rentang harga mana transaksi paling banyak terjadi selama 60 hari terakhir. Batang panjang = "
                       "banyak pembeli dan penjual pernah bertemu di sana, biasanya jadi support (di bawah harga) "
                       "atau resistance (di atas harga). Batang merah = posisi harga sekarang.")
            vp_show = vp.copy()
            vp_show["Posisi"] = vp_show.apply(
                lambda x: "Harga sekarang" if x["dari"] <= lv["harga"] <= x["sampai"]
                else "Di bawah harga (calon support)" if x["sampai"] < lv["harga"] else "Di atas harga (calon resistance)", axis=1)
            st.altair_chart(
                alt.Chart(vp_show).mark_bar().encode(
                    y=alt.Y("rentang:N", sort=alt.EncodingSortField("dari", order="descending"), title=None,
                            axis=alt.Axis(labelOverlap=False, labelLimit=0)),
                    x=alt.X("persen:Q", title="% dari total volume"),
                    color=alt.Color("Posisi:N", scale=alt.Scale(
                        domain=["Di atas harga (calon resistance)", "Harga sekarang", "Di bawah harga (calon support)"],
                        range=["#90a4ae", "#e53935", "#43a047"]), legend=alt.Legend(orient="top", title=None, labelLimit=0, columns=1)),
                    tooltip=["rentang:N", alt.Tooltip("persen:Q", format=".1f"), alt.Tooltip("volume:Q", format=",.0f")],
                ).properties(height=alt.Step(28)), width="stretch")
            st.info("Order book asli (antrian bid/offer), broker summary, dan foreign flow tidak tersedia gratis. "
                    "Cek langsung di Stockbit dengan panduan di bagian 6.")

            # 5. Akumulasi
            st.markdown("### 5️⃣ Akumulasi atau distribusi?")
            a1, a2, a3, a4 = st.columns(4)
            a1.metric("Kesimpulan", acc["verdict"])
            a2.metric("Hari naik bervolume besar", acc["acc_days"], f"vs {acc['dist_days']} hari turun", delta_color="off")
            a3.metric("Money Flow Index", f"{acc['mfi']:.0f}",
                      "uang masuk" if acc["mfi"] > 50 else "uang keluar",
                      delta_color="normal" if acc["mfi"] > 50 else "inverse")
            a4.metric("Tren OBV / A/D", f"{'naik' if acc['obv_trend'] > 0 else 'turun'} / "
                      f"{'naik' if acc['ad_trend'] > 0 else 'turun'}")
            with st.expander("Apa artinya?"):
                st.markdown("""
- **Akumulasi**: harga naik disertai volume besar lebih sering daripada harga turun bervolume besar. Tanda ada pihak yang mengumpulkan saham.
- **Distribusi**: kebalikannya, tanda ada pihak yang melepas saham.
- **Money Flow Index (MFI)**: seperti RSI tapi memperhitungkan volume. Di atas 50 berarti uang cenderung masuk; di atas 80 sudah terlalu panas.
- **OBV dan A/D line**: akumulasi volume berdasarkan arah harga. Kalau harga datar tapi OBV naik, sering jadi tanda akumulasi diam-diam.
""")

            st.markdown("#### Tekanan beli vs jual 10 hari terakhir (pengganti trade book)")
            st.caption("Perkiraan dari posisi harga penutupan dalam rentang harian: tutup dekat harga tertinggi berarti "
                       "pembeli lebih agresif (mirip banyak HAKA), dekat terendah berarti penjual lebih agresif (HAKI). "
                       "Trade book asli per transaksi ada di Stockbit.")
            tp = analysis.trade_pressure(hist)
            bars = tp.melt(id_vars=["Tanggal"], value_vars=["Beli %", "Jual %"], var_name="Pihak", value_name="Persen")
            st.altair_chart(alt.Chart(bars).mark_bar().encode(
                x=alt.X("Tanggal:O", timeUnit="monthdate", title=None),
                y=alt.Y("Persen:Q", stack="normalize", axis=alt.Axis(format="%"), title=None),
                color=alt.Color("Pihak:N", scale=alt.Scale(domain=["Beli %", "Jual %"], range=["#43a047", "#e53935"]),
                                legend=alt.Legend(orient="top", title=None)),
                tooltip=["Tanggal:T", "Pihak:N", alt.Tooltip("Persen:Q", format=".0f")]).properties(height=220),
                width="stretch")
            st.dataframe(tp.iloc[::-1], hide_index=True, width="stretch", column_config={
                "Harga": st.column_config.NumberColumn(format="Rp %d"),
                "Perubahan %": st.column_config.NumberColumn(format="%+.1f%%"),
                "Volume (lot)": st.column_config.NumberColumn(format="%,.0f"),
                "Nilai (Rp miliar)": st.column_config.NumberColumn(format="%.1f"),
                "Beli %": st.column_config.NumberColumn(format="%.0f%%"),
                "Jual %": st.column_config.NumberColumn(format="%.0f%%"),
            })

        # 6. Broker summary & order book
        st.markdown("### 6️⃣ Broker summary (bandarmologi) & order book")
        st.caption("Data broker summary (broker mana yang membeli/menjual, misalnya AK, ZP, YP) tidak tersedia gratis, "
                   "jadi ambil dari Stockbit: buka saham ini > Broker Summary > screenshot, lalu upload di sini. "
                   "AI akan membaca dan menganalisisnya.")
        with st.container(border=True):
            shots = st.file_uploader("Screenshot broker summary (boleh lebih dari satu)", type=["png", "jpg", "jpeg", "webp"],
                                     accept_multiple_files=True, key=f"bs_{code}")
            pasted = st.text_area("Atau tempel teks broker summary di sini", key=f"bst_{code}", height=100,
                                  placeholder="Contoh: AK beli 12.500 lot avg 230; YP jual 8.000 lot avg 228; ...")
            broker_key = f"broker_{code}"
            if not ai_analysis.has_key():
                st.caption("Isi ANTHROPIC_API_KEY untuk mengaktifkan analisis broker summary (lihat README).")
            elif st.button("🔍 Analisis broker summary", disabled=not (shots or pasted.strip()), key=f"bsb_{code}"):
                images = [(f.getvalue(), f.type or "image/png") for f in shots or []]
                context = (f"Harga terakhir Rp {ind['harga']:,.0f}, perubahan 1 hari {ind['chg_1d']:+.1f}%, "
                           f"1 bulan {ind['chg_1m']:+.1f}%. " if ind else "") + (
                           f"Pola volume 20 hari: {acc['verdict']}. Risiko gorengan: {risk_level}." if acc else "")
                with st.spinner("AI sedang membaca broker summary..."):
                    try:
                        st.session_state[broker_key] = st.write_stream(
                            ai_analysis.stream_broker_analysis(code, images, pasted, context))
                    except Exception as exc:
                        st.error(f"Analisis gagal: {exc}")
                st.caption("Dibuat oleh AI dari gambar yang kamu upload dan bisa salah baca. Cek ulang angkanya.")
            elif broker_key in st.session_state:
                st.markdown(st.session_state[broker_key])
                st.caption("Dibuat oleh AI dari gambar yang kamu upload dan bisa salah baca. Cek ulang angkanya.")
            st.link_button(f"📲 Buka {code} di Stockbit", stockbit_url(code))
        with st.expander("📖 Kamus kode broker (AK, ZP, YP, dll.)"):
            st.dataframe(pd.DataFrame([{"Kode": k, "Nama": v[0], "Jenis": v[1], "Pengguna utama": v[2]}
                                       for k, v in BROKERS.items()]), hide_index=True, width="stretch")
            st.caption("Broker asing/institusi yang terus membeli sering dianggap tanda akumulasi 'uang besar'. Broker ritel "
                       "(YP, PD, XC, XL) yang dominan membeli sering berarti investor ritel yang sedang masuk. Nama broker bisa "
                       "berubah karena merger; cek daftar anggota bursa di idx.co.id.")
        with st.expander("📋 Cara cek order book, trade book & foreign flow di Stockbit"):
            st.markdown(analysis.ORDERBOOK_GUIDE)

        # 7. Fundamental
        st.markdown("### 7️⃣ Fundamental")
        ks = load_keystats(code)
        if ks:
            st.markdown("#### Keystats: kinerja per kuartal")
            for status, text in analysis.keystats_checks(ks):
                st.markdown(f"{status} {text}")
            metric = st.segmented_control("Data", list(ks), default=next(iter(ks)), key=f"ks_{code}") or next(iter(ks))
            kt = analysis.keystats_table(ks[metric])
            scale, unit = (1, "Rp per saham") if metric == "EPS" else (1e9, "Rp miliar")
            vals = kt.astype(float) / scale
            text = vals.map(lambda v: "-" if pd.isna(v) else f"{v:,.2f}")
            st.dataframe(text.style.apply(
                lambda col: ["color: #c62828" if pd.notna(v) and v < 0 else "" for v in vals[col.name]]),
                width="stretch")
            st.caption(f"Satuan: {unit}. TTM = total 4 kuartal terakhir sampai kuartal terakhir tahun itu. "
                       "Angka merah = rugi. Sumber Yahoo Finance; kuartal lama kadang tidak tersedia, cek juga Keystats di Stockbit.")
            st.markdown("#### Rasio")
        if fund:
            ft = pd.DataFrame([{"Indikator": k, "Nilai": analysis.format_fundamental(k, v),
                                "Penilaian": analysis.interpret_fundamental(k, v)} for k, v in fund.items()])
            st.table(ft.set_index("Indikator"))
            st.caption("Sumber Yahoo Finance. Bandingkan dengan saham lain di sektor yang sama.")
        else:
            st.caption("Data fundamental tidak tersedia.")

        # 8. Analisis AI
        st.markdown("### 8️⃣ Analisis AI lengkap")
        report_key = f"ai_{code}"
        if not ai_analysis.has_key():
            st.caption("Isi ANTHROPIC_API_KEY untuk mengaktifkan analisis AI (lihat README).")
        elif st.button(f"🤖 Buat analisis lengkap {code}", type="primary"):
            prompt = ai_analysis.build_prompt(
                code, name, sector, ind, lv, acc, vp, fund, agg[code]["articles"],
                {"total": r["Skor"], "news": r["Skor berita"],
                 "tech": r["Skor teknikal"] if pd.notna(r["Skor teknikal"]) else 0.0},
                [t for _, t in analysis.keystats_checks(load_keystats(code))]
                + [f"Risiko gorengan {risk_level}: {f}" for f in risk_flags])
            with st.container(border=True):
                with st.spinner("AI sedang membaca berita, laporan keuangan, dan grafik... (sekitar 1–2 menit)"):
                    try:
                        st.session_state[report_key] = st.write_stream(ai_analysis.stream_analysis(prompt))
                    except Exception as exc:
                        st.error(f"Analisis gagal: {exc}")
                st.caption("Dibuat oleh AI dan bisa keliru. Bukan rekomendasi investasi.")
        elif report_key in st.session_state:
            with st.container(border=True):
                st.markdown(st.session_state[report_key])
                st.caption("Dibuat oleh AI dan bisa keliru. Bukan rekomendasi investasi.")

        # 9. Berita
        st.markdown(f"### 9️⃣ Berita terkait ({agg[code]['count']})")
        for a in sorted(agg[code]["articles"], key=lambda a: a.published, reverse=True):
            with st.container(border=True):
                st.markdown(f"{label(a.sentiment)} **[{a.title}]({a.link})**  \n<small>{a.source} · "
                            f"{a.published.astimezone().strftime('%d %b %Y %H:%M')} · skor {a.sentiment:+.1f}</small>",
                            unsafe_allow_html=True)
                if a.summary:
                    st.write(a.summary)
                if a.hits:
                    st.caption("Kata kunci: " + ", ".join(a.hits))
        st.link_button("Cari berita lain tentang " + code,
                       f"https://news.google.com/search?q={code}%20saham&hl=id&gl=ID&ceid=ID:id")

with tab_news:
    st.subheader(f"{len(articles)} berita terbaru")
    q = st.text_input("Cari di judul", "")
    shown = [a for a in articles if q.lower() in a.title.lower()][:150]
    for a in shown:
        tags = " ".join(f"`{t}`" for t in a.tickers)
        st.markdown(f"{label(a.sentiment)} **[{a.title}]({a.link})** {tags}  \n"
                    f"<small>{a.source} · {a.published.astimezone().strftime('%d %b %H:%M')}</small>",
                    unsafe_allow_html=True)

with tab_help:
    st.markdown("""
**Skor berita (-5 s.d. +5)**: setiap berita diberi nilai dari kata kunci, misalnya *laba melonjak* (+3),
*dividen jumbo* (+3), *asing borong* (+2.5), *rugi bersih* (-3), *suspensi* (-3), *gagal bayar* (-3.5).
Berita baru bobotnya penuh, lalu berkurang setengah setiap 24 jam. Skor semua berita sebuah saham dijumlah.

**Skor teknikal (-5 s.d. +5)**: harga di atas rata-rata 20 hari (MA20) menambah skor, MA20 di atas MA50
(tren naik) +1, volume melonjak saat harga naik +1, RSI 50–70 +1, RSI di atas 75 (sudah terlalu tinggi) -1.5.

**Skor gabungan** = bobot berita × skor berita + (1 − bobot) × skor teknikal. Atur bobotnya di sidebar.

**Keterbatasan**: kamus kata tidak memahami konteks (misalnya sarkasme atau berita yang membahas beberapa
saham sekaligus), dan nama perusahaan bisa salah terdeteksi. Selalu baca beritanya langsung.
""")
    st.info(DISCLAIMER)
