from news import detect_tickers, parse_feed, score_sentiment

RSS = b"""<?xml version="1.0"?><rss><channel>
<item><title>Laba BBCA melonjak, asing borong saham - Kontan</title><link>https://x/1</link>
<pubDate>Sat, 25 Oct 2026 01:00:00 GMT</pubDate></item>
<item><title>IHSG ditutup melemah, saham Aneka Tambang anjlok - CNBC Indonesia</title><link>https://x/2</link>
<pubDate>Sat, 25 Oct 2026 02:00:00 GMT</pubDate></item>
</channel></rss>"""


def test_detect_code_and_alias():
    assert detect_tickers("Saham BBCA dan Telkom naik, IHSG menguat") == ["BBCA", "TLKM"]
    assert detect_tickers("IHSG dan BUMN") == []
    assert "ANTM" in detect_tickers("Antam catat penjualan emas")


def test_sentiment_direction_and_negation():
    assert score_sentiment("Laba bersih naik dan dividen jumbo")[0] > 3
    assert score_sentiment("Perusahaan rugi bersih, saham disuspensi")[0] < -3
    assert score_sentiment("Harga saham tidak naik")[0] < 0


def test_parse_google_style_feed():
    arts = parse_feed(RSS, "Google News: saham")
    assert arts[0].source == "Kontan" and arts[0].tickers == ["BBCA"] and arts[0].sentiment > 0
    assert arts[1].tickers == ["ANTM"] and arts[1].sentiment < 0


def test_ticks_and_auto_reject():
    from analysis import auto_reject, tick_size, to_tick
    assert tick_size(150) == 1 and tick_size(1500) == 5 and tick_size(9000) == 25
    assert to_tick(1503) == 1505
    ara, arb = auto_reject(1000)
    assert ara == 1250 and arb == 750


def test_levels_on_sample_history():
    import demo
    from analysis import accumulation, key_levels, volume_profile
    df = demo.history(["BBCA"])["BBCA"]
    vp = volume_profile(df)
    lv = key_levels(df, vp)
    assert abs(vp["persen"].sum() - 100) < 1e-6
    assert lv["stop"] < lv["harga"] < lv["t1"] <= lv["t2"]
    assert accumulation(df)["verdict"] in {"Akumulasi", "Distribusi", "Netral"}


def test_speculative_risk_flags_small_illiquid_stock():
    import demo
    import prices
    from analysis import speculative_risk
    df = demo.history(["DOOH"])["DOOH"]
    level, flags = speculative_risk(df, prices.indicators(df), market_cap=1.5e11)
    assert level in {"Sedang", "Tinggi"} and any("Kapitalisasi kecil" in f for f in flags)


def test_any_listed_code_detected_in_news():
    import news
    news.KNOWN_CODES.add("DOOH")
    assert news.detect_tickers("Saham DOOH melonjak hari ini") == ["DOOH"]
