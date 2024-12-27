import mysql.connector
import mysql
import aws
import crypt

### SQLite DB 연결
def get_db_connection(dbUrlParameter, dbPasswordParameter):
    return mysql.connector.connect(
        host=crypt.decrypt_env_value(dbUrlParameter),
        user="application",
        password=crypt.decrypt_env_value(dbPasswordParameter),
        database="bitcoin_trades"
    )

### DB 초기화
def init_db(assume_session, env):
    dbUrlParameter = aws.get_parameter(assume_session, env, 'db/url')
    dbPasswordParameter = aws.get_parameter(assume_session, env, 'db/password')

    conn = get_db_connection(dbUrlParameter, dbPasswordParameter)
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
