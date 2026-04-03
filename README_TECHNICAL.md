# 🤖 Indodax Autonomous AI Trading Agent - Documentation

Dokumentasi ini merangkum arsitektur, algoritma, dan sistem strategi yang digunakan dalam proyek **Indodax Autonomous AI Trading Agent**.

---

## 🏗️ 1. Arsitektur Sistem (Hybrid AI Model)

Proyek ini menggunakan pendekatan **"Hybrid AI"**, yang menggabungkan kecepatan algoritma teknis dengan kemampuan kognitif LLM (_Large Language Model_).

### A. Core Pipeline

1.  **Ingestion Layer**: Mengambil data OHLCV (candlestick), Orderbook, dan Trade History secara _real-time_ via CCXT (Indodax).
2.  **Analysis Layer**: Menghasilkan sinyal dari berbagai dimensi (Teknikal, Volume Whale, Sentimen).
3.  **Strategic Audit Layer**: Gemini AI Strategist memvalidasi sinyal teknis untuk mencegah _fake signal_.
4.  **Risk Engine**: Menghitung ukuran posisi dan batas risiko sebelum eksekusi.
5.  **Execution Layer**: Mengirim order ke bursa dan mengelola posisi terbuka secara asinkron.

---

## 📊 2. Algoritma Utama

### A. Whale Flow & Volume Anomaly (Sinyal Utama)

Bot ini tidak hanya melihat harga, tapi melihat "Uang".

- **Z-Score Detection**: Mendeteksi trade tunggal yang ukurannya >3x standar deviasi rata-rata volume historis.
- **Net Inflow/Outflow**: Menghitung apakah volume besar tersebut adalah tekanan beli (_Accumulation_) atau jual (_Distribution_).
- **Orderbook Wall Analysis**: Mencari "tembok" raksasa pada antrian beli/jual yang sering dipasang oleh bandar untuk mengarahkan harga.

### B. Dynamic Market Regime Detection

Bot menyesuaikan perilaku berdasarkan "cuaca" pasar:

- **CHOPPY**: Pasar sampingan/tenang. Konfigurasi diperketat untuk menghindari _whipsaw_.
- **VOLATILE**: Ayunan harga besar. _Stop Loss_ diperlebar dan _Take Profit_ dipercepat.
- **TRENDING (BULL/BEAR)**: Tren kuat. Bot menjadi lebih agresif dan membiarkan profit tumbuh lebih lama.

### C. Gemini LLM Strategist (Strategic Veto)

Setiap sinyal teknikal dengan keyakinan >70% akan dikirim ke **Gemini 1.5 Flash**.

- **Prompt Engineering**: Gemini menerima data indikator, anomali volume, dan berita terbaru.
- **Decision**: Gemini memberikan status `APPROVE`, `REJECT`, atau `WAIT` berdasarkan logika makro.

---

## 🛡️ 3. Sistem Proteksi Modal & Optimasi

### A. Market Correlation Filter (BTC Veto)

- **Logika**: Bitcoin adalah kompas utama. Jika BTC terdeteksi dalam tren `TRENDING_BEAR` (jatuh tajam), bot otomatis membatalkan sinyal `BUY` di koin apapun.
- **Fungsi**: Mencegah kerugian massal saat terjadi _market crash_.

### B. Trailing Take Profit (TTP)

- **Activation**: Aktif saat posisi mencapai profit >2%.
- **Tracking**: Bot mencatat harga tertinggi yang pernah dicapai selama trade terbuka.
- **Callback**: Jika harga turun 1% dari titik tertinggi, bot langsung jual (_close position_).
- **Hasil**: Mengubah target 2% menjadi potensi 10%, 20%, atau lebih selama tren masih naik.

### C. Daily Discipline & Elite Mode

- **Discipline Mode**: Aktif jika target harian belum tercapai. Bot tetap mengejar peluang, tetapi tidak menurunkan standar entry. Tidak ada _confidence boost_, tidak ada _re-entry_ agresif, dan sinyal tanpa konfirmasi multi-timeframe tetap dibatalkan.
- **Elite Mode**: Aktif jika target harian tercapai. Bot menjadi sangat selektif (hanya mengambil sinyal A+) dan memotong eksposur modal sebesar 50% untuk menjaga profit yang sudah didapat.
- **Loss Streak Cooldown**: Jika terjadi beberapa loss beruntun pada hari yang sama, bot menghentikan entry baru sementara untuk mencegah _revenge trading_.

### D. Drawdown Punishment (Risk Halving)

- **Drawdown Limit**: Jika bot mengalami kerugian harian yang menyiasati batas _drawdown_ tertentu (contoh: loss >2%), sistem akan menghukum bot secara otomatis.
- **Punishment Action**: Alokasi _Buying Power_ dipotong menjadi setengah (1/2) untuk sisa hari tersebut demi mencegah keruntuhan ekuitas akibat _Revenge Trading_.

---

## 📦 4. Infrastruktur Data

- **Database**: SQLite dengan mode **WAL (Write-Ahead Logging)** untuk memungkinkan pembacaan dan penulisan asinkron tanpa _lock error_.
- **Concurrency**: Menggunakan `asyncio` untuk memantau puluhan koin secara paralel.
- **Logging**: Sistem log berlapis (`trading_agent.log`) yang memisahkan aktifitas teknis, eksekusi trade, dan pesan error.

---

## 📝 5. Filosofi Trading

_"Cut losses early, let profits run, and follow the smart money (Whales)."_

Bot ini didesain untuk menjadi sangat defensif di pasar yang buruk dan sangat oportunis di pasar yang kuat. Penggunaan LLM memastikan bot tidak hanya bertindak berdasarkan rumus matematika, tapi juga memahami sentimen pasar global.
