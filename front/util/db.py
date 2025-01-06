from util.crypt import Crypt 
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