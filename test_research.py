import analysis
import demo
import research


def _run(code):
    hist = demo.history([code])[code]
    vp = analysis.volume_profile(hist)
    lv = analysis.key_levels(hist, vp)
    acc = analysis.accumulation(hist)
    daily = analysis.money_flow_daily(hist)
    intra = analysis.intraday_flow(demo.intraday(code))
    ind = {"harga": lv["harga"], "vol_ratio": 1.8, "chg_1d": 1.2}
    f = research.fundamental(code, "Perbankan", demo.fundamentals(code), demo.keystats(code), lv["harga"])
    m = research.money_flow(code, daily, intra, acc, ind, lv, analysis.trade_pressure(hist))
    return f, m


def test_research_has_every_part_and_exports():
    for code in ("BBRI", "DOOH"):
        for res in _run(code):
            assert not res["kosong"] and res["groups"]
            for _, _, items in res["groups"]:
                for it in items:
                    assert all(it[k] for k in ("status", "judul", "nilai", "apa", "cara", "patokan", "saham"))
            md = research.to_markdown(res)
            assert md.startswith("# Riset") and "Pelajaran kunci" in md


def test_research_handles_missing_data():
    f = research.fundamental("XXXX", "", {}, {}, None)
    m = research.money_flow("XXXX", None, None, None, None, None)
    assert f["kosong"] and m["kosong"]
    assert f["kesimpulan"]["total"] == 0
