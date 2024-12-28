import util.init as init
import util.aws as aws
import util.crypt as crypt
import util.db as db
import util.selenium as sn
import pyupbit
from openai import OpenAI
import pandas as pd
import json
import ta
from ta.utils import dropna
import requests
import logging
import time
from pydantic import BaseModel
from datetime import datetime, timedelta
from selenium.common.exceptions import WebDriverException


class TradingDecision(BaseModel):
    decision: str
    percentage: int
    reason: str

### 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 환경변수 로드
env = init.set_env()

# AWS Assume Role로 접근
assume_session = aws.get_assume_role()

### AWS Parameter Store에 접근하여 암호화 키 가져오기
upbitAccessParameter = aws.get_parameter(assume_session, env, 'key/upbit-access')
upbitSecretParameter = aws.get_parameter(assume_session, env, 'key/upbit-secret')
openAIParameter = aws.get_parameter(assume_session, env, 'key/openai')

### 암호화 키 호출
crypt.init(assume_session, env)

# 데이터베이스 초기화
db.init_db(assume_session, env)

### TA 라이브러리를 이용하여 df 데이터에 보조지표 추가
### 추가한 보조 지표 : 볼린저 밴드, RSI, MACD, 이동평균선 
def add_indicators(df):
    # 볼린저 밴드
    indicator_bb = ta.volatility.BollingerBands(close=df['close'], window=20, window_dev=2)
    df['bb_bbm'] = indicator_bb.bollinger_mavg()
    df['bb_bbh'] = indicator_bb.bollinger_hband()
    df['bb_bbl'] = indicator_bb.bollinger_lband()

    # RSI
    df['rsi'] = ta.momentum.RSIIndicator(close=df['close'], window=14).rsi()

    # MACD
    macd = ta.trend.MACD(close=df['close'])
    df['macd'] = macd.macd()
    df['macd_signal'] = macd.macd_signal()
    df['macd_diff'] = macd.macd_diff()
    
    # 이동평균선
    df['sma_20'] = ta.trend.SMAIndicator(close=df['close'], window=20).sma_indicator()
    df['ema_12'] = ta.trend.EMAIndicator(close=df['close'], window=12).ema_indicator()
    
    return df

### 공포 탐욕 지수 API 호출
def get_fear_and_greed_index():
    url = "https://api.alternative.me/fng/"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        return data['data'][0]
    else:
        print(f"Failed to fetch Fear and Greed Index. Status code: {response.status_code}")
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

def get_recent_trades(conn, days=7):
    c = conn.cursor()
    seven_days_ago = (datetime.now() - timedelta(days=days)).isoformat()
    c.execute("SELECT * FROM trades WHERE timestamp > %s ORDER BY timestamp DESC", (seven_days_ago,))
    columns = [column[0] for column in c.description]
    return pd.DataFrame.from_records(data=c.fetchall(), columns=columns)

def calculate_performance(trades_df):
    if trades_df.empty:
        return 0
    
    initial_balance = trades_df.iloc[-1]['krw_balance'] + trades_df.iloc[-1]['btc_balance'] * trades_df.iloc[-1]['btc_krw_price']
    final_balance = trades_df.iloc[0]['krw_balance'] + trades_df.iloc[0]['btc_balance'] * trades_df.iloc[0]['btc_krw_price']
    
    return (final_balance - initial_balance) / initial_balance * 100

def generate_reflection(trades_df, current_market_data):
    performance = calculate_performance(trades_df)
    
    client = OpenAI(
        api_key=crypt.decrypt_env_value(openAIParameter)
    )
    response = client.chat.completions.create(
        model="gpt-4o",
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
    # Upbit 객체 생성
    accessKey = crypt.decrypt_env_value(upbitAccessParameter)
    secretKey = crypt.decrypt_env_value(upbitSecretParameter)
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
    df_daily = pyupbit.get_ohlcv("KRW-BTC", interval="day", count=30)
    # NaN 값 제거
    df_daily = dropna(df_daily)     
    df_daily = add_indicators(df_daily)
    
    # 24시간 시간봉 데이터
    df_hourly = pyupbit.get_ohlcv("KRW-BTC", interval="minute60", count=24)
    # NaN 값 제거
    df_hourly = dropna(df_hourly)
    df_hourly = add_indicators(df_hourly)

    # print(df_daily)
    # print(df_hourly)

    # 4. 공포 탐욕 지수 가져오기
    fear_greed_index = get_fear_and_greed_index()

    # 5. Selenum으로 Upbit KRW-BTC 차트 캡쳐 (1일봉, 볼린저밴드, 일목균형표 추가)
    driver = None
    try:
        driver = sn.create_driver()
        driver.get("https://upbit.com/full_chart?code=CRIX.UPBIT.KRW-BTC")
        logger.info("Upbit KRW-BTC 페이지 로드 완료")
        time.sleep(10) # 네트워크 환경 고려하여 페이지 로딩 대기 시간
        logger.info("차트 작업 시작")
        sn.perform_chart_actions(driver)
        logger.info("차트 작업 완료")
        chart_image, saved_file_path = sn.capture_and_encode_screenshot(driver)
        logger.info(f"스크린 샷 캡쳐 완료. 저장된 파일 경로: {saved_file_path}")
    except WebDriverException as e:
        logger.error(f"WebDriver 오류 발생 : {e}")
        chart_image, saved_file_path = None, None
    except Exception as e:
        logger.error(f"차트 캡쳐 중 오류 발생: {e}")
        chart_image, saved_file_path = None, None
    finally:
        if driver:
            driver.quit()

    # AI에게 데이터 제공하고 판단 받기
    client = OpenAI(
        api_key=crypt.decrypt_env_value(openAIParameter)
    )

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "system",
                "content": """You are an expert in Bitcoin investing. Analyze the provided data including technical indicators, market data, recent news headlines, the Fear and Greed Index, YouTube video transcript, and the chart image. Tell me whether to buy, sell, or hold at the moment. Consider the following in your analysis:
                - Technical indicators and market data
                - Recent news headlines and their potential impact on Bitcoin price
                - The Fear and Greed Index and its implications
                - Overall market sentiment
                - The patterns and trends visible in the chart image
                
                Respond with:
                1. A decision (buy, sell, or hold)
                2. If the decision is 'buy', provide a percentage (1-100) of available KRW to use for buying.
                If the decision is 'sell', provide a percentage (1-100) of held BTC to sell.
                If the decision is 'hold', set the percentage to 0.
                3. A reason for your decision
                
                Ensure that the percentage is an integer between 1 and 100 for buy/sell decisions, and exactly 0 for hold decisions.
                Your percentage should reflect the strength of your conviction in the decision based on the analyzed data."""
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": f"""Current investment status: {json.dumps(filtered_balances)}
                                Orderbook: {json.dumps(orderbook)}
                                Daily OHLCV with indicators (30 days): {df_daily.to_json()}
                                Hourly OHLCV with indicators (24 hours): {df_hourly.to_json()}
                                Fear and Greed Index: {json.dumps(fear_greed_index)}"""
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{chart_image}"
                        }                        
                    }
                ]
            }
        ],
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "trading_decision",
                "strict": True,
                "schema": {
                    "type": "object",
                    "properties": {
                        "decision": {"type": "string", "enum": ["buy","sell","hold"]},
                        "percentage": {"type": "integer"},
                        "reason": {"type": "string"}
                    },
                    "required": ["decision", "percentage", "reason"],
                    "additionalProperties": False
                }
            }
        },
        max_tokens=4095
    )

    # AI의 판단에 따라 실제로 자동매매 진행하기
    # pydantic 메서드 이용
    result = TradingDecision.model_validate_json(response.choices[0].message.content)

    # 데이터 베이스 연결
    dbUrlParameter = aws.get_parameter(assume_session, env, 'db/url')
    dbPasswordParameter = aws.get_parameter(assume_session, env, 'db/password')
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

    # 반성 및 개선 내용 생성
    reflection = generate_reflection(recent_trades, current_market_data)

    print("### AI Decision: ", {result.decision.upper()}, "###")
    print(f"### Reason: {result.reason} ###")

    order_executed = False

    if result.decision == "buy":
        my_krw = upbit.get_balance("KRW")
        buy_amount = my_krw * (result.percentage / 100) * 0.9995
        if buy_amount > 5000:
            print("### Buy Order Executed ###")
            order = upbit.buy_market_order("KRW-BTC", buy_amount)
            if order:
                order_executed = True
            print(order)
        else:
            print("### Buy Order Failed: Insufficient KRW (less than 5000 KRW) ###")
    elif result.decision == "sell":
        my_btc = upbit.get_balance("KRW-BTC")
        sell_amount = my_btc * (result.percentage / 100)
        current_price = pyupbit.get_orderbook(ticker="KRW-BTC")['orderbook_units'][0]["ask_price"]
        if sell_amount * current_price > 5000:
            print("### Sell Order Executed ###")
            order = upbit.sell_market_order("KRW-BTC", sell_amount)
            if order:
                order_executed = True
            print(order)
        else:
            print("### Sell Order Failed: Insufficient BTC (less than 5000 KRW worth) ###")
    elif result.decision == "hold":
        print("### Hold Position ###")
    
    # 거래 실행 여부와 관계없이 현재 잔고 조회
    time.sleep(1) # API 호출 제한을 고려하여 잠시 대기
    balances = upbit.get_balances()
    btc_balance = next((float(balance['balance']) for balance in balances if balance['currency'] == 'BTC'), 0)
    krw_balance = next((float(balance['balance']) for balance in balances if balance['currency'] == 'KRW'), 0)
    btc_avg_buy_price = next((float(balance['avg_buy_price']) for balance in balances if balance['currency'] == 'BTC'), 0)
    current_btc_price = pyupbit.get_current_price("KRW-BTC")

    # 거래 정보 로깅
    log_trade(conn, result.decision, result.percentage if order_executed else 0, result.reason, 
              btc_balance, krw_balance, btc_avg_buy_price, current_btc_price, reflection)

    conn.close()

ai_trading()