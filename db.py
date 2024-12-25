import sqlite3

def init_db():
    conn = sqlite3.connect('bitcoin_trades.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS trades
              (id INTEGER PRIMARY KEY AUTOINCREMENT,
              timestamp TEXT,
              decision TEXT,
              percentage INTEGER,
              reason TEXT,
              btc_balance REAL,
              krw_balance REAL,
              btc_avg_buy_price REAL,
              btc_krw_price REAL)''')
    conn.commit()
    return conn



# 데이터베이스 초기화
init_db()