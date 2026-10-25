"""Kamus kode broker (anggota bursa) yang sering muncul di broker summary.

Nama broker bisa berubah karena merger/akuisisi; cek daftar anggota bursa terbaru di idx.co.id.
Jenis: "Asing" = sekuritas milik/afiliasi asing (sering dipakai investor institusi asing),
"Lokal" = sekuritas dalam negeri. Catatan "ritel" = banyak dipakai investor perorangan.
"""

BROKERS = {
    "AK": ("UBS Sekuritas Indonesia", "Asing", "institusi"),
    "BK": ("J.P. Morgan Sekuritas Indonesia", "Asing", "institusi"),
    "ZP": ("Maybank Sekuritas Indonesia", "Asing", "institusi"),
    "KZ": ("CLSA Sekuritas Indonesia", "Asing", "institusi"),
    "RX": ("Macquarie Sekuritas Indonesia", "Asing", "institusi"),
    "CG": ("Citigroup Sekuritas Indonesia", "Asing", "institusi"),
    "GW": ("HSBC Sekuritas Indonesia", "Asing", "institusi"),
    "YU": ("CGS International Sekuritas Indonesia", "Asing", "institusi & ritel"),
    "AI": ("UOB Kay Hian Sekuritas", "Asing", "institusi & ritel"),
    "DR": ("RHB Sekuritas Indonesia", "Asing", "institusi & ritel"),
    "KK": ("Phillip Sekuritas Indonesia", "Asing", "ritel"),
    "FS": ("Yuanta Sekuritas Indonesia", "Asing", "institusi & ritel"),
    "BQ": ("Korea Investment & Sekuritas Indonesia", "Asing", "institusi & ritel"),
    "XA": ("NH Korindo Sekuritas Indonesia", "Asing", "ritel"),
    "AG": ("Kiwoom Sekuritas Indonesia", "Asing", "ritel"),
    "YP": ("Mirae Asset Sekuritas Indonesia", "Asing", "ritel (sangat banyak)"),
    "PD": ("Indo Premier Sekuritas", "Lokal", "ritel (sangat banyak)"),
    "XC": ("Ajaib Sekuritas Asia", "Lokal", "ritel (sangat banyak)"),
    "XL": ("Stockbit Sekuritas Digital", "Lokal", "ritel (sangat banyak)"),
    "CC": ("Mandiri Sekuritas", "Lokal", "institusi & ritel"),
    "NI": ("BNI Sekuritas", "Lokal", "institusi & ritel"),
    "OD": ("BRI Danareksa Sekuritas", "Lokal", "institusi & ritel"),
    "SQ": ("BCA Sekuritas", "Lokal", "institusi & ritel"),
    "DX": ("Bahana Sekuritas", "Lokal", "institusi"),
    "LG": ("Trimegah Sekuritas Indonesia", "Lokal", "institusi & ritel"),
    "EP": ("MNC Sekuritas", "Lokal", "ritel"),
    "AZ": ("Sucor Sekuritas", "Lokal", "institusi & ritel"),
    "DH": ("Sinarmas Sekuritas", "Lokal", "institusi & ritel"),
    "IF": ("Samuel Sekuritas Indonesia", "Lokal", "institusi & ritel"),
    "GR": ("Panin Sekuritas", "Lokal", "ritel"),
    "KI": ("Ciptadana Sekuritas Asia", "Lokal", "institusi"),
    "HP": ("Henan Putihrai Sekuritas", "Lokal", "ritel"),
    "MG": ("Semesta Indovest Sekuritas", "Lokal", "ritel"),
    "CP": ("KB Valbury Sekuritas Indonesia", "Asing", "ritel"),
}


def describe(code: str) -> str:
    name, kind, note = BROKERS.get(code.upper(), ("tidak ada di kamus", "?", ""))
    return f"{code.upper()} = {name} ({kind}, {note})" if note else f"{code.upper()} = {name}"
