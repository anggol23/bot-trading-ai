# 🌊 Project Leviathan - AI Crypto Trading Agent

**AI Trading Agent** otonom tingkat lanjut yang dikhususkan untuk memindai aktivitas _Smart Money_ (Whales) di bursa Kripto menggunakan Volume Profile Parabolik dan _Sentiment Analysis_ NLP. Proyek ini dibangun dengan prinsip _Clean Architecture_ dan berjalan sepenuhnya secara _Asynchronous_ untuk memindai ratusan pasar dalam hitungan milidetik.

## ✨ Fitur Utama (Phase 0 - 4 Lengkap)

1.  **Omni-Scanner Asynchronous**: Memindai seluruh _pair_ di Indodax secara serentak (konkuren). Mampu mengabaikan koin berlikuiditas rendah secara otomatis (contoh: k Volume 24 Jam di bawah $50.000 USD).
2.  **Anti-Spoofing & Z-Score Tracker**: Tidak akan tertipu oleh _"Buy Wall"_ palsu di orderbook. Dynamic Z-Score hanya merespon transaksi _Whale_ asli yang memakan likuiditas di atas ambang batas standar deviasi historis.
3.  **Trade Management (Pyramiding & Exhaustion)**:
    - **Scale-In**: AI dapat membuka posisi hingga 3 lapis untuk aset yang sedang _profit_ (dengan resiko yang dibagi dua setiap masuk lapis baru).
    - **Volume Exhaustion Trailing**: Mampu menahan aset tanpa batas Take-Profit statis, lalu **Force Close** seketika saat terdeteksi _Whales_ mulai melakukan distribusi (jual massal).
4.  **Macro Sentiment Veto (NLP)**: Mengambil berita kripto secara _real-time_ lewat API dan menganalisis polanya menggunakan `vaderSentiment`. Jika terpantau sentimen fundamental sangat buruk (krisis, hack), AI akan melakukan _Veto_ (HOLD) pada sinyal teknikal apapun untuk mencegah kerugian _black swan_.

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
# Mode Trading: "paper" (Uji Coba Uang Palsu) atau "live" (Pakai Uang Asli Indodax)
TRADING_MODE="paper"

# Kunci API Indodax (Hanya wajib diisi jika TRADING_MODE="live")
INDODAX_API_KEY="kunci_api_indodax_anda"
INDODAX_SECRET="kunci_rahasia_indodax_anda"

# Kunci NLP News (Opsional, tapi penting untuk VETO)
# Daftar gratis di: https://cryptopanic.com/developers/api/
CRYPTOPANIC_API_KEY="kunci_cryptopanic_anda"

# Pengaturan Resiko Dasar (Dalam format desimal, 0.02 = 2%)
RISK_PER_TRADE=0.02
TRADING_PAIRS="BTC/IDR,ETH/IDR,SOL/IDR,XRP/IDR"
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
