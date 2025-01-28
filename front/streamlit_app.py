from util.init import Init
from util.aws import AWS
from util.crypt import Crypt
from util.db import DB
import pyupbit
import streamlit as st
import pandas as pd
import plotly.express as px

### 환경변수 로드
env = Init.set_env()

# 데이터 로드 함수
def load_data(conn):
    # conn = get_connection()
    query = "SELECT * FROM trades"
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df

# 초기 투자 금액 계산 함수
def calculate_initial_investment(df):
    initial_krw_balance = df.iloc[0]['krw_balance']
    initial_btc_balance = df.iloc[0]['btc_balance']
    initial_btc_price = df.iloc[0]['btc_krw_price']
    initial_total_investment = initial_krw_balance + (initial_btc_balance * initial_btc_price)
    return initial_total_investment

# 현재 투자 금액 계산 함수
def calculate_current_investment(df):
    current_krw_balance = df.iloc[-1]['krw_balance']
    current_btc_balance = df.iloc[-1]['btc_balance']
    btc_avg_buy_price = df.iloc[-1]['btc_avg_buy_price']
    current_btc_price = pyupbit.get_current_price("KRW-BTC")  # 현재 BTC 가격 가져오기
    btc_purchase_price = current_btc_balance * btc_avg_buy_price
    profit = (current_btc_balance * current_btc_price) - btc_purchase_price
    current_total_investment = current_krw_balance + btc_purchase_price + profit

    return current_total_investment

# 메인 함수
def main():
    st.title('Bitcoin Trades Viewer')

    # AWS Assume Role로 접근
    assume_session = AWS.get_assume_role(env)

    # 암호화 키 호출
    Crypt.init(assume_session, env)

    # 데이터 베이스 연결
    dbUrlParameter = AWS.get_parameter(assume_session, env, 'db/url')
    dbPasswordParameter = AWS.get_parameter(assume_session, env, 'db/password')
    conn = DB.get_db_connection(dbUrlParameter, dbPasswordParameter)

    # 데이터 로드
    df = load_data(conn)

    if df.empty:
        st.warning('No trade data available.')
        return

    # 초기 투자 금액 계산
    initial_investment = calculate_initial_investment(df)
    initial_investment_fstring = f"{initial_investment:,} 원"

    # 현재 투자 금액 계산
    current_investment = calculate_current_investment(df)
    current_investment_fstring = f"{current_investment:,} 원"

    # 수익률 계산
    profit_rate = ((current_investment - initial_investment) / initial_investment) * 100

    # 수익률 표시
    st.header(f'📈 Current Profit Rate: {profit_rate:.2f}%')
    st.write(f"Initial investment: {initial_investment_fstring}")
    st.write(f"Current investment: {current_investment_fstring}")

    # 기본 통계
    st.header('Basic Statistics')
    st.write(f"Total number of trades: {len(df)}")
    st.write(f"First trade date: {df['timestamp'].min()}")
    st.write(f"Last trade date: {df['timestamp'].max()}")

    # 거래 내역 표시
    st.header("Trade History")
    st.dataframe(df)


if __name__ == "__main__":
    main()