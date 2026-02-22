# Panduan Deploy AI Trading Agent ke VPS (Ubuntu) 24/7

Untuk memastikan agen AI beroperasi dan memantau pasar tanpa henti (24 jam) meskipun laptop Anda dimatikan, Anda perlu men-_deploy_ (mengunggah dan menjalankan) sistem ini ke sebuah **VPS (Virtual Private Server)** berbasis Linux.

Sistem kita terdiri dari 3 modul terpisah yang harus terus menyala:

1. **AI Trading Engine** (`presentation/cli/main.py` - AI Core: Pengambil keputusan & Eksekutor)
2. **REST API Backend** (`presentation/api/main.py` - Penyedia data Dashboard via FastAPI)
3. **Web Dashboard UI** (`presentation/web/` - Tampilan visual berbasis React/Vite)

Berikut adalah panduan _best practice_ langkah demi langkah untuk melakukan deploy ke server VPS (disarankan menggunakan **Ubuntu 20.04 / 22.04 / 24.04 LTS**).

---

## Langkah 1: Persiapan Server VPS

Masuk (SSH) ke dalam server VPS Anda:

```bash
ssh root@IP_VPS_ANDA
```

Lakukan _update_ sistem dan _install_ pustaka pendukung (Python, Node.js, Nginx, dan Git):

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install python3-pip python3-venv git nginx curl -y

# Install Node.js & npm (Untuk build Dashboard React)
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs
```

---

## Langkah 2: Kloning Repositori & Install Dependencies

Silakan _upload_ folder proyek ini ke VPS Anda (melalui Git, FTP, atau SCP). Asumsikan diletakkan di `/root/ai-trading`.

```bash
cd /root/ai-trading

# 1. Setup Virtual Environment Python
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 2. Jangan lupa buat & isi file .env Anda (Masukkan API Key Indodax)
cp .env.example .env
nano .env # (Lalu isi Kunci API, dan ubah TRADING_MODE=paper jika ingin simulasi)

# 3. Setup Frontend React
cd presentation/web
npm install
npm run build
```

---

## Langkah 3: Menjalankan AI Engine & API Backend via PM2

Karena menjaga skrip tetap hidup itu rumit, kita akan menggunakan **PM2** (_Process Manager_) untuk menahan agar AI bot dan API tetap hidup di _background_ dan otomatis _restart_ jika _error_ atau VPS nge-_reboot_.

### 3.1. Install PM2 Global

Pastikan `npm` sudah terpasang dari langkah 1. Instal PM2 secara global:

```bash
sudo npm install -g pm2
```

### 3.2. Jalankan AI Trading Engine

Kembali ke _root_ proyek, dan berikan Python Path ke PM2 agar sistem mengenali strukturnya:

```bash
cd /root/ai-trading
export PYTHONPATH=$(pwd)
pm2 start presentation/cli/main.py --name "ai-trading-bot" --interpreter ./venv/bin/python
```

### 3.3. Jalankan FastAPI Backend

Lalu kita luncurkan API Server di Port 8000:

```bash
cd /root/ai-trading
export PYTHONPATH=$(pwd)
pm2 start ./venv/bin/uvicorn --name "ai-trading-api" -- presentation.api.main:app --host 127.0.0.1 --port 8000
```

### 3.4. Simpan Konfigurasi dan Setup Auto-Start

Agar kedua service ini otomatis kembali menyala saat server VPS di-_restart_:

```bash
# Simpan layanan yang sedang berjalan saat ini
pm2 save

# Buat script auto-startup
pm2 startup
```

Lalu **_copy-paste_** perintah (`sudo env PATH...`) yang dimunculkan oleh layar VPS Anda setelah menjalankan kode di atas.

Untuk mengecek apakah AI sedang _Trading_ dan tidak ada _Error_:

```bash
pm2 logs ai-trading-bot
pm2 status
```

---

## Langkah 4: Tampilkan Dashboard React ke Publik menggunakan Nginx

Tadi kita telah menjalankan `npm run build` yang menghasilkan web statis di `/root/ai-trading/presentation/web/dist`. Kita akan mendistribusikannya menggunakan Nginx agar bisa diakses dari Web Browser HP atau Laptop.

1. Hapus konfigurasi _default_ nginx:

```bash
sudo rm /etc/nginx/sites-enabled/default
```

2. Buat konfigurasi routing baru:

```bash
sudo nano /etc/nginx/sites-available/aitrading
```

Isi dengan script blok server Nginx berikut:

```nginx
server {
    listen 80;
    server_name _; # Bisa diganti dengan domain bot Anda misal: bot.trading.com

    # Area 1: Frontend React UI (Hasil Build Vite)
    location / {
        root /root/ai-trading/presentation/web/dist;
        index index.html;
        try_files $uri $uri/ /index.html;
    }

    # Area 2: Reverse Proxy untuk FastAPI Backend
    location /api/ {
        proxy_pass http://127.0.0.1:8000/api/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

3. Aktifkan koneksi Nginx:

```bash
sudo ln -s /etc/nginx/sites-available/aitrading /etc/nginx/sites-enabled/
sudo systemctl restart nginx
```

````

3. Aktifkan koneksi Nginx:

```bash
sudo ln -s /etc/nginx/sites-available/aitrading /etc/nginx/sites-enabled/
sudo systemctl restart nginx
````

---

## Selesai! 🎉

Sekarang Anda cukup membuka alamat `http://IP_VPS_ANDA/` di browser web (bahkan dari HP sekalipun) dan Anda akan melihat Dashboard Premium menyala secara real-time.

Bot ini akan 100% otonom (berjalan sendiri di latar belakang VPS) memonitor Orderbook Indodax setiap detiknya dan menyimpan seluruh histori PnL di dalam `trading_agent.db`.

> **Catatan:** Jangan bagikan tautan IP VPS / Domain Anda secara publik kecuali Anda telah mengimplementasikan sistem Authentication (Login) tambahan di langkah berikutnya, karena _dashboard_ tersebut bersifat rahasia (mengandung riwayat _balance/equity_ keuangan Anda).
