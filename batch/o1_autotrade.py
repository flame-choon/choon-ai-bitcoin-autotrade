from util.init import Init
from util.crypt import Crypt
from util.aws import AWS
import util.db as db
import pyupbit
import schedule
import re
from openai import OpenAI
import pandas as pd
import json
import ta
from ta.utils import dropna
import requests
import logging
import time
from datetime import datetime, timedelta

### 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 환경변수 로드
env = Init.set_env()

### TA 라이브러리를 이용하여 df 데이터에 보조지표 추가
### 추가한 보조 지표 : 볼린저 밴드, RSI, MACD, 이동평균선 
def add_indicators(df):
    # 볼린저 밴드 추가
    indicator_bb = ta.volatility.BollingerBands(close=df['close'], window=20, window_dev=2)
    df['bb_bbm'] = indicator_bb.bollinger_mavg()
    df['bb_bbh'] = indicator_bb.bollinger_hband()
    df['bb_bbl'] = indicator_bb.bollinger_lband()

    # RSI (Relative Strength Index) 추가
    df['rsi'] = ta.momentum.RSIIndicator(close=df['close'], window=14).rsi()

    # 이동평균선 (단기, 장기)
    df['sma_20'] = ta.trend.SMAIndicator(close=df['close'], window=20).sma_indicator()
    df['ema_12'] = ta.trend.EMAIndicator(close=df['close'], window=12).ema_indicator()

    # # MACD (Moving Average Convergence Divergence) 추가
    # macd = ta.trend.MACD(close=df['close'])
    # df['macd'] = macd.macd()
    # df['macd_signal'] = macd.macd_signal()
    # df['macd_diff'] = macd.macd_diff()

    #  # Stochastic Oscillator 추가
    # stoch = ta.momentum.StochasticOscillator(
    #     high=df['high'], low=df['low'], close=df['close'], window=14, smooth_window=3)
    # df['stoch_k'] = stoch.stoch()
    # df['stoch_d'] = stoch.stoch_signal()
    
    return df

### 공포 탐욕 지수 API 호출
def get_fear_and_greed_index():
    url = "https://api.alternative.me/fng/"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        return data['data'][0]
    except requests.exceptions.RequestsException as e:
        logger.error(f"Error fetching Fear and Greed Index: {e}")
        return None

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

# 최근 투자 기록을 기반으로 퍼포먼스 계산 (초기 잔고 대비 최종 잔고)
def calculate_performance(trades_df):
    if trades_df.empty:
        return 0 # 기록이 없을 경우 0%로 설정
    
    # 초기 잔고 계산 (KRW + BTC * 현재 가격)
    initial_balance = trades_df.iloc[-1]['krw_balance'] + trades_df.iloc[-1]['btc_balance'] * trades_df.iloc[-1]['btc_krw_price']
    # 최종 잔고 계산
    final_balance = trades_df.iloc[0]['krw_balance'] + trades_df.iloc[0]['btc_balance'] * trades_df.iloc[0]['btc_krw_price']
    return (final_balance - initial_balance) / initial_balance * 100

# AI 모델을 사용하여 최근 투자 기록과 시장 데이터를 기반으로 분석 및 반성을 생성하는 함수
def generate_reflection(trades_df, current_market_data, openAIParameter):
    performance = calculate_performance(trades_df)  # 투자 퍼포먼스 계산
    
    client = OpenAI(
        api_key=Crypt.decrypt_env_value(openAIParameter)
    )
    if not client.api_key:
        logger.error("OpenAI API key is missing or invalid.")
        return None
        
    # OpenAI API 호출로 AI의 반성 일기 및 개선 사항 생성 요청
    response = client.chat.completions.create(
        model="gpt-4o-2024-11-20",
        messages=[
            {
                "role": "system",
                "content": "You are an AI trading assistant tasked with analyzing recent trading performance and current market conditions to generate insights and improvements for future trading decisions."
            },
            {
                "role": "user",
                "content": f"""
                Recent trading data:
                {trades_df.to_json(orient='records')}
                
                Current market data:
                {current_market_data}
                
                Overall performance in the last 7 days: {performance:.2f}%
                
                Please analyze this data and provide:
                1. A brief reflection on the recent trading decisions
                2. Insights on what worked well and what didn't
                3. Suggestions for improvement in future trading decisions
                4. Any patterns or trends you notice in the market data
                
                Limit your response to 250 words or less.
                """
            }
        ]
    )
    
    return response.choices[0].message.content


### 자동 트레이드 메서드
def ai_trading():

    # AWS Assume Role로 접근
    assume_session = AWS.get_assume_role()

    ### AWS Parameter Store에 접근하여 암호화 키 가져오기
    upbitAccessParameter = AWS.get_parameter(assume_session, env, 'key/upbit-access')
    upbitSecretParameter = AWS.get_parameter(assume_session, env, 'key/upbit-secret')
    openAIParameter = AWS.get_parameter(assume_session, env, 'key/openai')

    ### 암호화 키 호출
    Crypt.init(assume_session, env)

    # 데이터베이스 초기화
    db.init_db(assume_session, env)

    # Upbit 객체 생성
    accessKey = Crypt.decrypt_env_value(upbitAccessParameter)
    secretKey = Crypt.decrypt_env_value(upbitSecretParameter)
    upbit = pyupbit.Upbit(accessKey, secretKey)

    # 1. 현재 투자 상태 조회 (KRW, BTC 만 조회)
    all_balances = upbit.get_balances()
    filtered_balances = [balance for balance in all_balances if balance['currency'] in ['BTC','KRW']]
    # print(json.dumps(filtered_balances))

    # 2. KRW-BTC 오더북 (호가 데이터) 조회
    orderbook = pyupbit.get_orderbook("KRW-BTC")
    # print(json.dumps(orderbook))

    # 3. 차트 데이터 조회 및 보조지표 추가
    # 30일 일봉 데이터
    df_daily = pyupbit.get_ohlcv("KRW-BTC", interval="day", count=180)
    df_daily = dropna(df_daily)     
    df_daily = add_indicators(df_daily)
    
    # 24시간 시간봉 데이터
    df_hourly = pyupbit.get_ohlcv("KRW-BTC", interval="minute60", count=168) # 7 days
    df_hourly = dropna(df_hourly)
    df_hourly = add_indicators(df_hourly)

    # 최근 데이터만 사용하도록 설정 (메모리 절약)
    df_daily_recent = df_daily.tail(30)
    df_hourly_recent = df_hourly.tail(24)

    # 4. 공포 탐욕 지수 가져오기
    fear_greed_index = get_fear_and_greed_index()

    # AI에게 데이터 제공하고 판단 받기
    client = OpenAI(
        api_key=Crypt.decrypt_env_value(openAIParameter)
    )
    if not client.api_key:
        logger.error("OpenAI API key is missing or invalid.")
        return None

    # 데이터 베이스 연결
    dbUrlParameter = AWS.get_parameter(assume_session, env, 'db/url')
    dbPasswordParameter = AWS.get_parameter(assume_session, env, 'db/password')
    conn = db.get_db_connection(dbUrlParameter, dbPasswordParameter)

    # 최근 거래 내역 가져오기
    recent_trades = get_recent_trades(conn)

    # 현재 시장 데이터 수집 (기존 코드에서 가져온 데이터 사용)
    current_market_data = {
        "fear_greed_index": fear_greed_index,
        "orderbook": orderbook,
        "daily_ohlcv": df_daily.to_dict(),
        "hourly_ohlcv": df_hourly.to_dict()
    }

    # # 반성 및 개선 내용 생성
    reflection = generate_reflection(recent_trades, current_market_data, openAIParameter)

    # logger.info(reflection)

    # AI 모델에 반성 내용 제공
    # Few-shot prompting으로 JSON 예시 추가
    examples = """
        Example Response 1:
        {
        "decision": "buy",
        "percentage": 50,
        "reason": "Based on the current market indicators and positive news, it's a good opportunity to invest."

        }

        Example Response 2:
        {
        "decision": "sell",
        "percentage": 30,
        "reason": "Due to negative trends in the market and high fear index, it is advisable to reduce holdings."

        }

        Example Response 3:
        {
        "decision": "hold",
        "percentage": 0,
        "reason": "Market indicators are neutral; it's best to wait for a clearer signal."

        }
        """

    response = client.chat.completions.create(
        model="o1-preview",
        messages=[
            {
                "role": "user",
                "content": f"""
                You are an expert in Bitcoin investing. This analysis is performed every 12 hours. Analyze the provided data and datermine whether to buy, sell, or hold at the current moment. 
                Consider the following in your analysis:
                
                - Technical indicators and market data
                - The Fear and Greed Index and its implications
                - Overall market sentiment
                - Recent trading performance and reflection

                Recent trading reflection:
                {reflection}

                Based on your analysis, make a decision and provide your reasoning.

                Please provide your response in the following JSON format: {examples}
                
                Ensure that the percentage is an integer between 1 and 100 for buy/sell decisions, and exactly 0 for hold decisions.
                Your percentage should reflect the strength of your conviction in the decision based on the analyzed data."""
            },
            {
                "role": "user",
                "content": f"""
                    Current investment status: {json.dumps(filtered_balances)}
                    Orderbook: {json.dumps(orderbook)}
                    Daily OHLCV with indicators (recent 60 days): {df_daily_recent.to_json()}
                    Hourly OHLCV with indicators (recent 48 hours): {df_hourly_recent.to_json()}
                    Fear and Greed Index: {json.dumps(fear_greed_index)}
                """
            }
        ]
    )

    response_text = response.choices[0].message.content

    # AI 응답 파싱
    def parse_ai_response(response_text):    
        try:
            # Extract JSON part from the response
            json_match = re.search(r'\{.*?\}', response_text, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
                # Parse JSON
                parsed_json = json.loads(json_str)
                decision = parsed_json.get('decision')
                percentage = parsed_json.get('percentage')
                reason = parsed_json.get('reason')
                return {'decision': decision, 'percentage': percentage, 'reason': reason}
            else:
                logger.error("No JSON found in AI response.")
                return None
        except json.JSONDecodeError as e:
            logger.error(f"JSON parsing error: {e}")
            return None        
    
    parsed_response = parse_ai_response(response_text)
    if not parsed_response:
        logger.error("Failed to parse AI response")
        return 

    decision = parsed_response.get('decision')
    percentage = parsed_response.get('percentage')
    reason = parsed_response.get('reason')

    if not decision or reason is None:
        logger.error("Incomplete data in AI response.")
        return
    
    logger.info(f"AI Decision: {decision.upper()}")
    logger.info(f"percentage: {percentage}")
    logger.info(f"Decision Reason: {reason}")

    order_executed = False

    if decision == "buy":
        my_krw = upbit.get_balance("KRW")
        if my_krw is None:
            logger.error("Failed to retrieve KRW balance.")
            return
        buy_amount = my_krw * (percentage / 100) * 0.9995
        if buy_amount > 5000:
            logger.info(f"### Buy Order Executed: {percentage}% of available KRW ###")
            try:                
                order = upbit.buy_market_order("KRW-BTC", buy_amount)
                if order:
                    logger.info(f"Buy order executed successfullly: {order}")
                    order_executed = True
                else:
                    logger.error("Buy order failed.")
            except Exception as e:
                logger.error(f"Error executing buy order: {e}")
        else:
            logger.warning("### Buy Order Failed: Insufficient KRW (less than 5000 KRW) ###")
    elif decision == "sell":
        my_btc = upbit.get_balance("KRW-BTC")
        if my_btc is None:
            logger.error("Failed to retrieve BTC balance.")
            return
        sell_amount = my_btc * (percentage / 100)
        current_price = pyupbit.get_current_price("KRW-BTC")
        if sell_amount * current_price > 5000:
            logger.info(f"Sell Order Executed: {percentage}% of held BTC")
            try:
                order = upbit.sell_market_order("KRW-BTC", sell_amount)
                if order:
                    order_executed = True
                else:
                    logger.error("Sell order failed.")
            except Exception as e:
                logger.error(f"Error executing sell order: {e}")
        else:
            logger.warning("### Sell Order Failed: Insufficient BTC (less than 5000 KRW worth) ###")
    elif decision == "hold":
        logger.info("### Hold Position ###")
    else:
        logger.error("Invalid decision received from AI.")
    
    # 거래 실행 여부와 관계없이 현재 잔고 조회
    time.sleep(2) # API 호출 제한을 고려하여 잠시 대기
    balances = upbit.get_balances()
    btc_balance = next((float(balance['balance']) for balance in balances if balance['currency'] == 'BTC'), 0)
    krw_balance = next((float(balance['balance']) for balance in balances if balance['currency'] == 'KRW'), 0)
    btc_avg_buy_price = next((float(balance['avg_buy_price']) for balance in balances if balance['currency'] == 'BTC'), 0)
    current_btc_price = pyupbit.get_current_price("KRW-BTC")

    # 거래 정보 로깅
    log_trade(conn, decision, percentage if order_executed else 0, reason, 
              btc_balance, krw_balance, btc_avg_buy_price, current_btc_price, reflection)

    conn.close()

# ai_trading()

schedule.every().day.at("05:00").do(ai_trading)
schedule.every().day.at("11:00").do(ai_trading)
schedule.every().day.at("17:00").do(ai_trading)
schedule.every().day.at("23:00").do(ai_trading)

while 1:
    schedule.run_pending()
    time.sleep(1)