import sqlite3

def migrate():
    conn = sqlite3.connect("trading_agent.db")
    cursor = conn.cursor()
    
    # Check if reasoning exists
    cursor.execute("PRAGMA table_info(trades)")
    columns = [row[1] for row in cursor.fetchall()]
    
    if "reasoning" not in columns:
        cursor.execute("ALTER TABLE trades ADD COLUMN reasoning TEXT")
        print("Added 'reasoning' column to 'trades' table.")
        
    if "max_drawdown" not in columns:
        cursor.execute("ALTER TABLE trades ADD COLUMN max_drawdown REAL DEFAULT 0.0")
        print("Added 'max_drawdown' column to 'trades' table.")
        
    conn.commit()
    conn.close()
    print("Migration complete.")

if __name__ == "__main__":
    migrate()
