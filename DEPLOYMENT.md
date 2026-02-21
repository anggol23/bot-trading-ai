# Panduan Deploy AI Trading Agent ke VPS (Ubuntu) 24/7

Untuk memastikan agen AI beroperasi dan memantau pasar tanpa henti (24 jam) meskipun laptop Anda dimatikan, Anda perlu men-_deploy_ (mengunggah dan menjalankan) sistem ini ke sebuah **VPS (Virtual Private Server)** berbasis Linux.

Sistem kita terdiri dari 3 bagian utama yang harus terus menyala:

1. **AI Trading Engine** (`main.py` - Pengambil keputusan & Eksekutor)
2. **REST API Backend** (`web/server/main.py` - Penyedia data Dashboard)
3. **Web Dashboard UI** (`web/client/` - Tampilan visual berbasis React)

Berikut adalah panduan _best practice_ langkah demi langkah untuk melakukan deploy ke server VPS (disarankan menggunakan **Ubuntu 20.04 / 22.04 LTS**).

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
nano .env # (Lalu copas isi dari .env lokal Anda, ubah TRADING_MODE=paper jika masih ingin simulasi)

# 3. Setup Frontend React
cd web/client
npm install
npm run build
```

---

## Langkah 3: Menjalankan AI Engine & API Backend via PM2

Karena Anda memfavoritkan `pm2` untuk _process manager_, kita akan menggunakannya untuk menahan agar _bot_ dan API tetap hidup di _background_ dan akan otomatis _restart_ jika _error_ atau server _reboot_.

### 3.1. Install PM2 Global

Pastikan `npm` sudah terpasang dari langkah 1. Instal PM2 secara global:

```bash
sudo npm install -g pm2
```

### 3.2. Jalankan AI Trading Engine

Pastikan Anda berada di _root_ proyek:

```bash
cd /root/ai-trading
pm2 start main.py --name "ai-trading-bot" --interpreter ./venv/bin/python
```

### 3.3. Jalankan FastAPI Backend

Bergeser ke folder backend, lalu luncurkan melalui Uvicorn menggunakan _interpreter_ virtual environment:

```bash
cd /root/ai-trading/web/server
pm2 start ../../venv/bin/python --name "ai-trading-api" -- -m uvicorn main:app --host 127.0.0.1 --port 8000
```

### 3.4. Simpan Konfigurasi dan Setup Auto-Start

Agar kedua service ini otomatis kembali menyala saat server VPS di-_restart_:

```bash
# Simpan layanan yang sedang berjalan saat ini
pm2 save

# Buat script auto-startup
pm2 startup
```

Lalu _copy-paste_ perintah yang dimunculkan oleh layar VPS Anda setelah menjalankan kode di atas.

Untuk mengecek _log_ sistem apabila ada error atau sekadar melihat status _Running_:

```bash
pm2 logs
pm2 status
```

---

## Langkah 4: Tampilkan Dashboard React ke Publik menggunakan Nginx

Tadi kita telah menjalankan `npm run build` yang menghasilkan folder statis `/root/ai-trading/web/client/dist`. Kita akan mendistribusikannya menggunakan Nginx agar bisa diakses dari IP atau Domain VPS Anda.

1. Hapus konfigurasi _default_ nginx:

```bash
sudo rm /etc/nginx/sites-enabled/default
```

2. Buat konfigurasi routing baru:

```bash
sudo nano /etc/nginx/sites-available/aitrading
```

Isi dengan:

```nginx
server {
    listen 80;
    server_name _; # Bisa diganti domain Anda misal: bot.domain.com

    # Area 1: Frontend React UI
    location / {
        root /root/ai-trading/web/client/dist;
        index index.html index.htm;
        try_files $uri $uri/ /index.html;
    }

    # Area 2: Proxy API Request ke FastAPI Backend
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

---

## Selesai! 🎉

Sekarang Anda cukup membuka alamat `http://IP_VPS_ANDA/` di browser web (bahkan dari HP sekalipun) dan Anda akan melihat Dashboard Premium menyala secara real-time.

Bot ini akan 100% otonom (berjalan sendiri di latar belakang VPS) memonitor Orderbook Indodax setiap detiknya dan menyimpan seluruh histori PnL di dalam `trading_agent.db`.

> **Catatan:** Jangan bagikan tautan IP VPS / Domain Anda secara publik kecuali Anda telah mengimplementasikan sistem Authentication (Login) tambahan di langkah berikutnya, karena _dashboard_ tersebut bersifat rahasia (mengandung riwayat _balance/equity_ keuangan Anda).
