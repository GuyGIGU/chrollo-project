import sqlite3

def run_migration():
    conn = sqlite3.connect('trading_journal.db')
    cursor = conn.cursor()
    try:
        cursor.execute("ALTER TABLE trade_logs ADD COLUMN target_r FLOAT DEFAULT 3.0;")
        print("Successfully added target_r column.")
    except Exception as e:
        print("Error/Already Exists:", e)
    
    conn.commit()
    conn.close()

if __name__ == '__main__':
    run_migration()
