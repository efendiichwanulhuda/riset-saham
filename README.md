# Riset Saham (MVP)

Aplikasi web untuk memantau berita saham Bursa Efek Indonesia. Aplikasi ini mengambil berita terbaru, mendeteksi kode saham yang dibahas, memberi skor sentimen, lalu menggabungkannya dengan momentum harga dari Yahoo Finance menjadi satu peringkat.

> ⚠️ **Bukan rekomendasi investasi.** Skor dihitung otomatis dan bisa salah. Selalu baca beritanya, cek fundamental, dan atur risikomu sendiri.

## Cara menjalankan (Windows / Mac / Linux)

1. Pasang Python 3.10 atau lebih baru dari https://www.python.org/downloads/ (di Windows centang **Add Python to PATH**).
2. Buka Terminal / Command Prompt di folder ini, lalu jalankan:
   ```
   pip install -r requirements.txt
   streamlit run app.py
   ```
3. Browser akan terbuka otomatis di http://localhost:8501.

Mau lihat tampilannya dengan data contoh (tanpa internet)?
Mac/Linux: `RISET_DEMO=1 streamlit run app.py` · Windows: `set RISET_DEMO=1` lalu `streamlit run app.py`.

## Mengaktifkan Analisis AI (opsional)

Tombol **Buat analisis lengkap** di halaman detail saham memakai Claude untuk membaca data harga, fundamental, berita, dan mencari berita terbaru di web, lalu menulis laporan: kesimpulan (MENARIK / PANTAU / HINDARI), katalis, teknikal, fundamental, risiko, dan skenario.

1. Buat akun di https://console.anthropic.com, isi saldo (kartu kredit), lalu buat API key di menu **API Keys**.
2. Sebelum menjalankan aplikasi, masukkan key-nya:
   - Mac/Linux: `export ANTHROPIC_API_KEY=sk-ant-...`
   - Windows: `set ANTHROPIC_API_KEY=sk-ant-...`
3. Jalankan `streamlit run app.py` seperti biasa.

Biaya per analisis kira-kira beberapa ratus sampai sekitar dua ribu rupiah, tergantung panjang laporan dan jumlah pencarian web. Jangan bagikan API key ke siapa pun.

## Fitur

- **🚀 Rekomendasi Naik**: kandidat saham yang lolos semua kriteria (skor gabungan minimal +1.5, berita positif, tren tidak turun, RSI belum di atas 75, tidak ada berita sangat negatif dalam 2 hari). Tiap saham menampilkan alasan, berita utama, dan tombol **Buka di Stockbit** untuk langsung cek dan beli di Stockbit.
- **🧮 Screener**: pilih cakupan **Saham likuid** (±90) atau **Semua saham BEI** (±950 emiten, termasuk saham kecil yang jarang dibahas). Strategi siap pakai: Breakout volume, Akumulasi diam-diam, Pullback di tren naik, Rebound oversold, dan **🔥 Saham kecil sedang ramai**. Setiap saham diberi label **Risiko gorengan** (Rendah/Sedang/Tinggi).
- **Peringkat**: saham yang paling banyak diberitakan positif, lengkap dengan skor berita, skor teknikal, harga, perubahan 1 dan 5 hari, RSI, dan lonjakan volume.
- **Detail saham**: bisa memilih atau mengetik kode saham BEI apa pun (misalnya DOOH). Kalau sahamnya spekulatif, muncul kotak **Risiko saham gorengan** beserta alasannya. Isi laporannya:
  1. Ringkasan cepat dengan checklist ✅/⚠️
  2. Level harga penting: area beli, stop loss, target 1 dan 2, rasio untung/rugi, perkiraan ARA/ARB, fraksi harga, pivot
  3. Grafik harga dengan MA20/MA50 dan garis level
  4. Peta volume per harga (pengganti order book): zona harga dengan transaksi terbanyak
  5. Akumulasi atau distribusi (OBV, A/D line, Money Flow Index, hari bervolume besar) dan tekanan beli vs jual 10 hari (pengganti trade book)
  6. **Broker summary (bandarmologi)**: upload screenshot broker summary dari Stockbit (atau tempel teksnya), lalu AI membaca broker pembeli/penjual terbesar (AK, ZP, YP, dll.), rata-rata harga beli, dan tanda akumulasi bandar. Dilengkapi kamus kode broker dan panduan cek order book, trade book, dan foreign flow
  7. Fundamental: Keystats per kuartal (pendapatan, laba bersih, EPS, Tahunan, TTM, pertumbuhan YoY) dan rasio dengan penilaian (murah/wajar/mahal)
  8. Analisis AI lengkap
  9. Semua berita terkait
- **Analisis AI** (opsional): laporan lengkap per saham, lihat bagian di atas.
- **Semua berita**: daftar berita terbaru dengan kode saham yang terdeteksi.
- **Pantau saham tertentu**: ketik kode (misalnya `BBCA, ANTM`) di sidebar untuk mencari berita khusus saham itu.
- Data disimpan sementara 15 menit; tekan **Muat ulang data** untuk mengambil yang terbaru.

## Daftar semua saham BEI

Aplikasi mengambil daftar semua emiten dari Yahoo Finance, atau dari situs BEI kalau Yahoo gagal. Supaya paling lengkap dan akurat, kamu juga bisa mengunduh daftar resminya: buka idx.co.id > Data Pasar > Data Saham > Daftar Saham, klik unduh, lalu simpan filenya di folder aplikasi dengan nama `daftar_saham.xlsx`. Sumber yang dipakai terlihat di sidebar.

## Sumber data

- Berita: Google News (RSS), CNBC Indonesia, Kontan, Bisnis, IDX Channel. Sumber yang gagal dilewati, dan statusnya terlihat di sidebar.
- Harga: Yahoo Finance (kode `.JK`), tertunda sekitar 10–15 menit dari harga real-time.

## Mengubah isi

- `tickers.py`: daftar saham likuid (sekitar 90) beserta alias nama untuk deteksi berita.
- `universe.py`: pengambil daftar semua saham BEI.
- `brokers.py`: kamus kode broker.
- `news.py`: daftar sumber berita (`FEEDS`) dan kamus kata sentimen (`LEXICON`).
- `analysis.py`: level harga, peta volume, akumulasi/distribusi, checklist, aturan fraksi dan ARA/ARB.
- `prices.py`: rumus skor teknikal dan data fundamental.
- `ai_analysis.py`: instruksi dan format laporan Analisis AI.
- `test_news.py`: tes otomatis (`python -m pytest test_news.py`).

## Keterbatasan

Order book real-time, broker summary, dan foreign flow BEI tidak tersedia gratis, jadi aplikasi memakai peta volume dan indikator akumulasi sebagai pendekatan, dan broker summary dianalisis dari screenshot Stockbit yang kamu upload. Status UMA, notasi khusus, dan suspensi hanya terdeteksi bila muncul di berita, jadi cek juga pengumuman BEI. Mode "Semua saham BEI" butuh 1–2 menit untuk mengambil data harga pertama kali. Batas ARA/ARB adalah perkiraan (atur di `analysis.py` bila aturan BEI berubah).

Skor berita memakai kamus kata, jadi tidak memahami konteks. Contohnya, "rugi bersih menyusut" tetap dihitung negatif. Perusahaan dengan nama mirip juga bisa salah terdeteksi.

## Memasang online (Streamlit Community Cloud, gratis)

1. Simpan kode ini di repository GitHub.
2. Buka https://share.streamlit.io, masuk dengan akun GitHub, klik **Create app**, pilih repository, branch `main`, dan file `app.py`.
3. Buka **Advanced settings > Secrets**, lalu isi (contohnya ada di `.streamlit/secrets.toml.example`):
   ```
   APP_PASSWORD = "kata-sandi-pilihanmu"
   ANTHROPIC_API_KEY = "sk-ant-..."
   ```
   `APP_PASSWORD` mengunci aplikasi supaya orang lain yang tahu link-nya tidak bisa memakai API key-mu.
4. Klik **Deploy**. Setelah 2–5 menit aplikasi bisa dibuka dari HP lewat link `https://<nama>.streamlit.app`.
