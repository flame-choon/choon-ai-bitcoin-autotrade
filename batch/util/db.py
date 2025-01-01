from util.crypt import Crypt
from util.aws import AWS
from datetime import datetime, timedelta
import mysql.connector
import mysql
import pandas as pd


class DB:
    ### SQLite DB 연결
    def get_db_connection(dbUrlParameter, dbPasswordParameter):
        
        return mysql.connector.connect(
            host=Crypt.decrypt_env_value(dbUrlParameter),
            user="application",
            password=Crypt.decrypt_env_value(dbPasswordParameter),
            database="bitcoin_trades"
        )

    ### DB 초기화
    def init_db(assume_session, env):
        dbUrlParameter = AWS.get_parameter(assume_session, env, 'db/url')
        dbPasswordParameter = AWS.get_parameter(assume_session, env, 'db/password')

        conn = DB.get_db_connection(dbUrlParameter, dbPasswordParameter)
        c = conn.cursor()
        c.execute('''
                    CREATE TABLE IF NOT EXISTS trades (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        timestamp VARCHAR(255),
                        decision VARCHAR(10),
                        percentage INT,
                        reason TEXT,
                        btc_balance DECIMAL(18,8),
                        krw_balance DECIMAL(18,2),
                        btc_avg_buy_price DECIMAL(18,2),
                        btc_krw_price DECIMAL(18,2),
                        reflection TEXT
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                ''')
        conn.commit()

    ### DB에 거래 정보 로깅 
    def log_trade(conn, decision, percentage, reason, btc_balance, krw_balance, btc_avg_buy_price, btc_krw_price, reflection=''):
        c = conn.cursor()
        timestamp = datetime.now().isoformat()
        c.execute("""INSERT INTO trades 
                    (timestamp, decision, percentage, reason, btc_balance, krw_balance, btc_avg_buy_price, btc_krw_price, reflection) 
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (timestamp, decision, percentage, reason, btc_balance, krw_balance, btc_avg_buy_price, btc_krw_price, reflection))
        conn.commit()

    # 최근 투자 기록 조회
    def get_recent_trades(conn, days=7):
        c = conn.cursor()
        seven_days_ago = (datetime.now() - timedelta(days=days)).isoformat()
        c.execute("SELECT * FROM trades WHERE timestamp > %s ORDER BY timestamp DESC", (seven_days_ago,))
        columns = [column[0] for column in c.description]
        return pd.DataFrame.from_records(data=c.fetchall(), columns=columns)
