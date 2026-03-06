# 🌊 Project Leviathan - AI Crypto Trading Agent

**AI Trading Agent** otonom tingkat lanjut yang dikhususkan untuk memindai aktivitas _Smart Money_ (Whales) di bursa Kripto menggunakan Volume Profile Parabolik dan _Sentiment Analysis_ NLP. Proyek ini dibangun dengan prinsip _Clean Architecture_ dan berjalan sepenuhnya secara _Asynchronous_ untuk memindai ratusan pasar dalam hitungan milidetik.

## ✨ Fitur Utama (Phase 0 - 5 Lengkap)

1.  **Omni-Scanner Asynchronous**: Memindai seluruh _pair_ di Indodax secara serentak (konkuren). Mampu mengabaikan koin berlikuiditas rendah secara otomatis (contoh: Volume 24 Jam di bawah $50.000 USD).
2.  **Anti-Spoofing & Z-Score Tracker**: Tidak akan tertipu oleh _"Buy Wall"_ palsu di orderbook. Dynamic Z-Score hanya merespon transaksi _Whale_ asli yang memakan likuiditas di atas ambang batas standar deviasi historis.
3.  **Whale Confidence Profiling (LLM Logic)**: Setiap penemuan _Volume Spike_ akan divalidasi dengan skor "Whale Confidence" (1-10) beserta penjelasan logis fundamental/teknikal dalam Bahasa Indonesia mengapa posisi tersebut berpotensi menguntungkan.
4.  **Trade Management (Pyramiding & Exhaustion)**:
    - **Scale-In**: AI dapat membuka posisi hingga 3 lapis untuk aset yang sedang _profit_ (dengan resiko yang dibagi dua setiap masuk lapis baru).
    - **Volume Exhaustion Trailing**: Mampu menahan aset tanpa batas Take-Profit statis, lalu **Force Close** seketika saat terdeteksi _Whales_ mulai melakukan distribusi (jual massal).
5.  **Dynamic Risk Punishment & Target Force**: AI bertindak adaptif terhadap performa hariannya:
    - **Target Force**: Jika target profit harian (misal: 1%) belum tercapai, AI akan memberikan ruang _Stop Loss_ ekstra sebesar 25% agar posisi tidak mudah tersapu _whipsaw_ pasar yang bergejolak.
    - **Drawdown Punishment**: Jika AI menyentuh batas kerugian harian (misal: rugi > 2%), alokasi modal otomatis dipotong separuh (50%) untuk melindungi ekuitas dari manuver balas dendam (_Revenge Trading_).
6.  **Macro Sentiment Veto (NLP)**: Mengambil berita kripto secara _real-time_ lewat API dan menganalisis polanya menggunakan `vaderSentiment`. Jika terpantau sentimen fundamental sangat buruk (krisis, hack), AI akan melakukan _Veto_ (HOLD) pada sinyal teknikal apapun untuk mencegah kerugian _black swan_.
7.  **Interactive React Web Dashboard**: Menyajikan antarmuka visual _real-time_ atas kinerja bot. Fitur lengkap mulai dari _Equity Curve_ dengan filter rentang waktu (Hari Ini, 7 Hari, 30 Hari, Semua), Riwayat Transaksi tertutup, Live Volume Feed penemuan Paus, hingga pantauan target harian dan _Unrealized PNL_.

---

## 🚀 Panduan Instalasi & Menjalankan Bot

Ikuti langkah-langkah di bawah ini untuk menjalankan AI Trading Bot di PC / Server lokal Anda.

### Persiapan Sistem (Prerequisites)

- **OS**: Linux / MacOS / Windows (Direkomendasikan menggunakan WSL).
- **Python**: Versi `3.10` atau lebih baru.
- Pemahaman dasar tentang Terminal / _Command Line_.

### 1. Kloning dan Buka Folder Proyek

Buka terminal Anda dan pastikan berada di dalam folder proyek ini:

```bash
cd /path/to/PROJECT LIAR/AI TRADING
```

### 2. Membuat Virtual Environment (Sangat Direkomendasikan)

Virtual Environment (`venv`) berfungsi agar pustaka Python bot ini tidak bentrok dengan aplikasi Python lain di komputer Anda.

```bash
# Membuat environment bernama "venv"
python -m venv venv

# Mengaktifkan environment (Linux/MacOS)
source venv/bin/activate

# Mengaktifkan environment (Windows)
# venv\Scripts\activate
```

_(Catatan: Jika sudah aktif, nama `(venv)` akan muncul di awal baris terminal)_.

### 3. Mengunduh Pustaka (Dependencies)

Install seluruh pustaka (library) yang dibutuhkan dari file `requirements.txt`:

```bash
pip install -r requirements.txt
```

### 4. Konfigurasi Variabel Lingkungan (`.env`)

Agent membutuhkan beberapa kata sandi dan API Key agar dapat berkomunikasi dengan pasar dan baca berita.

1. Duplikasi nama file `.env.example` (jika ada) dan ubah namanya menjadi tepat `.env`.
2. Buka file `.env` dan isi data-data krusial:

```env
# ===== Main Setup =====
# Mode Trading: "paper" (Uji Coba Uang Palsu) atau "live" (Pakai Uang Asli Indodax)
TRADING_MODE="paper"

# Kunci API Indodax (Hanya wajib diisi jika TRADING_MODE="live")
INDODAX_API_KEY="kunci_api_indodax_anda"
INDODAX_SECRET="kunci_rahasia_indodax_anda"

# ===== Trading & Risk Configuration =====
TRADING_PAIRS="BTC/IDR,ETH/IDR,SOL/IDR,ADA/IDR,DOGE/IDR"
TIMEFRAME="15m"                           # Timeframe indikator (15m, 1h, 4h, dll)
ANALYSIS_INTERVAL_MINUTES=5               # Interval siklus pemindaian pasar

RISK_PER_TRADE=0.02                       # Risiko per perdagangan (0.02 = 2% modal)
MAX_OPEN_POSITIONS=3                      # Maksimal order paralel
DAILY_DRAWDOWN_LIMIT=0.05                 # Batas kerugian mati harian (5%)
PUNISHMENT_DRAWDOWN_PCT=0.02              # Batas kerugian hingga modal AI dipotong setengah
DAILY_TARGET_PROFIT=0.01                  # Target profit harian (1%)
STOP_LOSS_ATR_MULTIPLIER=2.0              # Jarak rentang Stop Loss dari volatilitas

# ===== Trailing Take Profit =====
TRAILING_TP_ACTIVATION=0.015              # Trailing nyala jika profit tembus 1.5%
TRAILING_TP_CALLBACK=0.01                 # Harga turun 1% = ambil profit

# ===== Volume Tracker & NLP =====
VOLUME_ANOMALY_MULTIPLIER=3.0             # Syarat paus: Volume 3x rata-rata
VOLUME_ANOMALY_MIN_USD_VALUE=5000         # Filter minimal US$ 5000 per transaksi paus
CRYPTOPANIC_API_KEY="kunci_cryptopanic"   # Akses API sentimen berita Fundamental

# ===== AI LLM Strategist (Gemini) =====
ENABLE_LLM_AUDIT=true                     # Aktifkan validasi akal sehat oleh LLM
GEMINI_API_KEY="kunci_gemini_anda"
GEMINI_MODEL="gemini-1.5-flash"

# ===== Notifikasi & Logging =====
ENABLE_TELEGRAM=false
TELEGRAM_BOT_TOKEN="token_bot_anda"
TELEGRAM_CHAT_ID="id_chat_anda"
LOG_LEVEL="INFO"
```

_(Catatan: Biarkan mode tetap `"paper"` untuk menguji algoritma)_.

### 5. Menjalankan AI Agent

Pastikan `venv` Anda sudah aktif. Kemudian, jalankan aplikasi _Orchestrator_ utama. Karena menggunakan struktur modular, Anda harus menambahkan proyek ke Python path terlebih dahulu:

```bash
# Export struktur folder agar terbaca oleh Python
export PYTHONPATH=$(pwd)

# Menyalakan AI Otonom
python presentation/cli/main.py
```

Jika berhasil, Anda akan melihat _Dashboard CLI_ yang akan menyajikan siklus Scan, Technical Analysis, Volume Tracking, Sentiment News, dan Status Portofolio setiap 60 menit sekali (bisa diubah di `.env`).

---

## 🛠️ Menjalankan Unit Tests (Pengujian Skrip)

Untuk memastikan bahwa AI Anda tidak ada _bug_ di sistem inti perhitungan resiko dan volume, Anda dapat menjalankan otomatisasi _testing_ yang telah disediakan:

```bash
# Export path terlebih dahulu jika belum
export PYTHONPATH=$(pwd)

# Jalankan pustaka pytest
pytest tests/
```

Tunggu beberapa detik, jika muncul bar merah atau pesan `FAILED`, hubungi _developer_. Jika hijau / `PASSED`, sistem 100% stabil.

---

## 🖥️ Menjalankan Web Dashboard (UI)

Selain Command Line (CLI), proyek ini juga menyediakan antarmuka Web Dashboard menggunakan **React + Vite** untuk Frontend dan **FastAPI** untuk Backend.

### 1. Menjalankan Backend API (FastAPI)

Buka tab terminal **BARU**, aktifkan virtual environment, dan jalankan server API:

```bash
# Aktifkan venv
source venv/bin/activate

# Export path project
export PYTHONPATH=$(pwd)

# Jalankan server API (akan jalan di port 8000)
uvicorn presentation.api.main:app --reload
```

### 2. Menjalankan Frontend Web (React/Vite)

Buka tab terminal **BARU** lainnya, lalu masuk ke folder web dan jalankan Node.js server:

```bash
# Pindah ke direktori web
cd presentation/web

# Install package Node.js (Hanya perlu dilakukan sekali)
npm install

# Jalankan server frontend
npm run dev
```

Buka tautan yang muncul (biasanya `http://localhost:5173`) di browser web Anda (Chrome/Firefox) untuk melihat grafik langsung dan posisi _trading_ AI Anda!
