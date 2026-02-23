import sqlite3
import os

def reset_database():
    db_path = "trading_agent.db"
    
    if not os.path.exists(db_path):
        print(f"❌ Database '{db_path}' tidak ditemukan.")
        return

    print(f"🔄 Memulai proses reset database '{db_path}'...")
    
    try:
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        
        # Eksekusi penghapusan seluruh tabel data operasional
        queries = [
            "DELETE FROM trades;",
            "DELETE FROM portfolio_snapshots;",
            "DELETE FROM volume_anomalies;",
            "DELETE FROM signals;",
            "DELETE FROM candles;"
        ]
        
        for q in queries:
            c.execute(q)
            
        conn.commit()
        
        # Mengeksekusi VACUUM secara terpisah di luar transaksi
        conn.isolation_level = None
        c.execute("VACUUM;")
        conn.isolation_level = "" # kembalikan ke default
        conn.close()
        
        print("✅ Berhasil! Seluruh riwayat trading, sinyal, dan candlestick telah dibersihkan.")
        print("💡 Silakan jalankan ulang bot Anda menggunakan: pm2 restart ai-trading-bot")
        
    except Exception as e:
        print(f"❌ Terjadi kesalahan saat mereset database: {e}")

if __name__ == "__main__":
    confirm = input("⚠️ PERINGATAN: Ini akan menghapus seluruh data simulasi bot. Lanjutkan? (y/n): ")
    if confirm.lower() == 'y':
        reset_database()
    else:
        print("Dibatalkan.")
