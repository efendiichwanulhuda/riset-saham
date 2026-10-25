"""Daftar saham IDX yang dipantau, beserta nama/alias untuk mendeteksi saham di berita.

Tambahkan saham lain dengan format: "KODE": ("Nama perusahaan", "Sektor", [alias, ...]).
Alias ditulis huruf kecil; dicocokkan sebagai kata utuh di judul/ringkasan berita.
"""

TICKERS = {
    # Perbankan
    "BBCA": ("Bank Central Asia", "Perbankan", ["bank central asia", "bca"]),
    "BBRI": ("Bank Rakyat Indonesia", "Perbankan", ["bank rakyat indonesia", "bri"]),
    "BMRI": ("Bank Mandiri", "Perbankan", ["bank mandiri"]),
    "BBNI": ("Bank Negara Indonesia", "Perbankan", ["bank negara indonesia", "bni"]),
    "BRIS": ("Bank Syariah Indonesia", "Perbankan", ["bank syariah indonesia", "bsi"]),
    "BBTN": ("Bank Tabungan Negara", "Perbankan", ["bank tabungan negara", "btn"]),
    "ARTO": ("Bank Jago", "Perbankan", ["bank jago"]),
    "BNGA": ("Bank CIMB Niaga", "Perbankan", ["cimb niaga"]),
    "BDMN": ("Bank Danamon", "Perbankan", ["bank danamon"]),
    "PNBN": ("Bank Panin", "Perbankan", ["bank panin"]),
    # Telekomunikasi & teknologi
    "TLKM": ("Telkom Indonesia", "Telekomunikasi", ["telkom indonesia", "telkom"]),
    "ISAT": ("Indosat Ooredoo Hutchison", "Telekomunikasi", ["indosat"]),
    "EXCL": ("XLSmart Telecom Sejahtera", "Telekomunikasi", ["xl axiata", "xlsmart"]),
    "TOWR": ("Sarana Menara Nusantara", "Telekomunikasi", ["sarana menara nusantara", "protelindo"]),
    "MTEL": ("Dayamitra Telekomunikasi", "Telekomunikasi", ["mitratel", "dayamitra"]),
    "GOTO": ("GoTo Gojek Tokopedia", "Teknologi", ["goto", "gojek", "tokopedia"]),
    "BUKA": ("Bukalapak", "Teknologi", ["bukalapak"]),
    "EMTK": ("Elang Mahkota Teknologi", "Teknologi", ["elang mahkota teknologi", "emtek"]),
    "DCII": ("DCI Indonesia", "Teknologi", ["dci indonesia"]),
    # Konsumer
    "UNVR": ("Unilever Indonesia", "Konsumer", ["unilever indonesia", "unilever"]),
    "ICBP": ("Indofood CBP Sukses Makmur", "Konsumer", ["indofood cbp"]),
    "INDF": ("Indofood Sukses Makmur", "Konsumer", ["indofood"]),
    "MYOR": ("Mayora Indah", "Konsumer", ["mayora"]),
    "GGRM": ("Gudang Garam", "Konsumer", ["gudang garam"]),
    "HMSP": ("HM Sampoerna", "Konsumer", ["sampoerna"]),
    "KLBF": ("Kalbe Farma", "Kesehatan", ["kalbe farma", "kalbe"]),
    "SIDO": ("Industri Jamu dan Farmasi Sido Muncul", "Kesehatan", ["sido muncul"]),
    "CPIN": ("Charoen Pokphand Indonesia", "Konsumer", ["charoen pokphand"]),
    "JPFA": ("Japfa Comfeed Indonesia", "Konsumer", ["japfa"]),
    "AMRT": ("Sumber Alfaria Trijaya", "Ritel", ["alfamart", "sumber alfaria"]),
    "MIDI": ("Midi Utama Indonesia", "Ritel", ["alfamidi"]),
    "ACES": ("Aspirasi Hidup Indonesia", "Ritel", ["ace hardware", "aspirasi hidup"]),
    "MAPI": ("Mitra Adiperkasa", "Ritel", ["mitra adiperkasa"]),
    "ERAA": ("Erajaya Swasembada", "Ritel", ["erajaya"]),
    "MIKA": ("Mitra Keluarga Karyasehat", "Kesehatan", ["mitra keluarga"]),
    "HEAL": ("Medikaloka Hermina", "Kesehatan", ["hermina"]),
    # Otomotif & industri
    "ASII": ("Astra International", "Industri", ["astra international", "astra"]),
    "UNTR": ("United Tractors", "Industri", ["united tractors"]),
    "AUTO": ("Astra Otoparts", "Industri", ["astra otoparts"]),
    # Energi & tambang
    "ADRO": ("Alamtri Resources Indonesia", "Energi", ["adaro", "alamtri resources"]),
    "AADI": ("Adaro Andalan Indonesia", "Energi", ["adaro andalan"]),
    "PTBA": ("Bukit Asam", "Energi", ["bukit asam"]),
    "ITMG": ("Indo Tambangraya Megah", "Energi", ["indo tambangraya"]),
    "BUMI": ("Bumi Resources", "Energi", ["bumi resources"]),
    "HRUM": ("Harum Energy", "Energi", ["harum energy"]),
    "INDY": ("Indika Energy", "Energi", ["indika energy", "indika"]),
    "MEDC": ("Medco Energi Internasional", "Energi", ["medco"]),
    "PGAS": ("Perusahaan Gas Negara", "Energi", ["perusahaan gas negara", "pgn"]),
    "AKRA": ("AKR Corporindo", "Energi", ["akr corporindo"]),
    "PGEO": ("Pertamina Geothermal Energy", "Energi", ["pertamina geothermal"]),
    "ADMR": ("Adaro Minerals Indonesia", "Tambang", ["adaro minerals", "alamtri minerals"]),
    "ANTM": ("Aneka Tambang", "Tambang", ["aneka tambang", "antam"]),
    "INCO": ("Vale Indonesia", "Tambang", ["vale indonesia"]),
    "MDKA": ("Merdeka Copper Gold", "Tambang", ["merdeka copper gold", "merdeka copper"]),
    "MBMA": ("Merdeka Battery Materials", "Tambang", ["merdeka battery"]),
    "NCKL": ("Trimegah Bangun Persada", "Tambang", ["trimegah bangun persada", "harita nickel"]),
    "TINS": ("Timah", "Tambang", ["pt timah"]),
    "AMMN": ("Amman Mineral Internasional", "Tambang", ["amman mineral"]),
    "BRMS": ("Bumi Resources Minerals", "Tambang", ["bumi resources minerals"]),
    "PSAB": ("J Resources Asia Pasifik", "Tambang", ["j resources"]),
    "EMAS": ("Merdeka Gold Resources", "Tambang", ["merdeka gold"]),
    # Petrokimia & dasar
    "TPIA": ("Chandra Asri Pacific", "Petrokimia", ["chandra asri"]),
    "BRPT": ("Barito Pacific", "Petrokimia", ["barito pacific"]),
    "CUAN": ("Petrindo Jaya Kreasi", "Energi", ["petrindo"]),
    "BREN": ("Barito Renewables Energy", "Energi", ["barito renewables"]),
    "INKP": ("Indah Kiat Pulp & Paper", "Bahan Dasar", ["indah kiat"]),
    "TKIM": ("Pabrik Kertas Tjiwi Kimia", "Bahan Dasar", ["tjiwi kimia"]),
    "SMGR": ("Semen Indonesia", "Bahan Dasar", ["semen indonesia"]),
    "INTP": ("Indocement Tunggal Prakarsa", "Bahan Dasar", ["indocement"]),
    # Properti & konstruksi
    "BSDE": ("Bumi Serpong Damai", "Properti", ["bumi serpong damai", "sinar mas land"]),
    "CTRA": ("Ciputra Development", "Properti", ["ciputra"]),
    "PWON": ("Pakuwon Jati", "Properti", ["pakuwon"]),
    "SMRA": ("Summarecon Agung", "Properti", ["summarecon"]),
    "PANI": ("Pantai Indah Kapuk Dua", "Properti", ["pik 2", "pantai indah kapuk dua"]),
    "JSMR": ("Jasa Marga", "Infrastruktur", ["jasa marga"]),
    "WIKA": ("Wijaya Karya", "Konstruksi", ["wijaya karya"]),
    "PTPP": ("PP (Persero)", "Konstruksi", ["pp persero", "pembangunan perumahan"]),
    # Agribisnis
    "AALI": ("Astra Agro Lestari", "Agribisnis", ["astra agro"]),
    "LSIP": ("PP London Sumatra", "Agribisnis", ["london sumatra", "lonsum"]),
    "DSNG": ("Dharma Satya Nusantara", "Agribisnis", ["dharma satya"]),
    "TAPG": ("Triputra Agro Persada", "Agribisnis", ["triputra agro"]),
    # Media & lainnya
    "SCMA": ("Surya Citra Media", "Media", ["surya citra media", "sctv"]),
    "MNCN": ("Media Nusantara Citra", "Media", ["media nusantara citra"]),
    "SRTG": ("Saratoga Investama Sedaya", "Investasi", ["saratoga"]),
    "ESSA": ("ESSA Industries Indonesia", "Petrokimia", ["essa industries"]),
    "RAJA": ("Rukun Raharja", "Energi", ["rukun raharja"]),
    "RATU": ("Raharja Energi Cepu", "Energi", ["raharja energi cepu"]),
    "DSSA": ("Dian Swastatika Sentosa", "Energi", ["dian swastatika"]),
}

# Kata kapital 4 huruf yang sering muncul di berita tapi bukan kode saham di daftar
# (dipakai supaya tidak salah deteksi bila daftar diperluas).
NOT_TICKERS = {"IHSG", "BUMN", "IPO", "OJK", "LQ45", "IDX", "BEI", "KSEI", "RUPS", "MSCI", "FTSE", "USD"}


def yahoo_symbol(code: str) -> str:
    """Kode Yahoo Finance untuk saham IDX, misalnya BBCA -> BBCA.JK."""
    return f"{code}.JK"
