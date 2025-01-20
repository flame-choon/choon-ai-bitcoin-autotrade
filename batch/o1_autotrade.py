from util.init import Init
from util.crypt import Crypt
from util.aws import AWS
from util.db import DB
from util.chatgpt import ChatGPT
from util.log import Log
import pyupbit
import time
import ta
from ta.utils import dropna
import requests
import schedule

### 로깅 설정
logger = Log()

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
        logger.recordLog(Log.ERROR, " Error fetching Fear and Greed Index", f"{e}")
        return None

### 자동 트레이드 메서드
def ai_trading(env):

    # AWS Assume Role로 접근
    assume_session = AWS.get_assume_role(env)

    ### AWS Parameter Store에 접근하여 암호화 키 가져오기
    upbitAccessParameter = AWS.get_parameter(assume_session, env, 'key/upbit-access')
    upbitSecretParameter = AWS.get_parameter(assume_session, env, 'key/upbit-secret')
    
    ### 암호화 키 호출
    Crypt.init(assume_session, env)

    # 데이터베이스 초기화
    DB.init_db(assume_session, env)

    # 데이터 베이스 연결
    dbUrlParameter = AWS.get_parameter(assume_session, env, 'db/url')
    dbPasswordParameter = AWS.get_parameter(assume_session, env, 'db/password')
    conn = DB.get_db_connection(dbUrlParameter, dbPasswordParameter)

    # Upbit 객체 생성
    accessKey = Crypt.decrypt_env_value(upbitAccessParameter)
    secretKey = Crypt.decrypt_env_value(upbitSecretParameter)
    upbit = pyupbit.Upbit(accessKey, secretKey)

    # OpenAI 초기화
    openAi = ChatGPT(assume_session, env)
    openAiClient = openAi.init()
    if not openAiClient.api_key:
        logger.recordLog(Log.ERROR, "Error", "OpenAI API key is missing or invalid.")
        return None
    
    # 1. 차트 데이터 조회 및 보조지표 추가
    # 30일 일봉 데이터
    df_daily = pyupbit.get_ohlcv("KRW-BTC", interval="day", count=30)
    df_daily = dropna(df_daily)     
    df_daily = add_indicators(df_daily)
    
    # 7일 시간봉 데이터
    df_hourly = pyupbit.get_ohlcv("KRW-BTC", interval="minute60", count=168) 
    df_hourly = dropna(df_hourly)
    df_hourly = add_indicators(df_hourly)

    # 최근 데이터만 사용하도록 설정 (메모리 절약)
    df_daily_recent = df_daily.tail(30)
    df_hourly_recent = df_hourly.tail(24)

    # 2. 공포 탐욕 지수 가져오기
    fear_greed_index = get_fear_and_greed_index()

    # 3. 현재 투자 상태 조회 (KRW, BTC 만 조회)
    all_balances = upbit.get_balances()
    filtered_balances = [balance for balance in all_balances if balance['currency'] in ['BTC','KRW']]
    
    # 4. KRW-BTC 오더북 (호가 데이터) 조회
    orderbook = pyupbit.get_orderbook("KRW-BTC")

    # 5. 최근 거래 내역 가져오기
    recent_trades = DB.get_recent_trades(conn)

    # 현재 시장 데이터 수집 (기존 코드에서 가져온 데이터 사용)
    current_market_data = {
        "fear_greed_index": fear_greed_index,
        "orderbook": orderbook,
        "daily_ohlcv": df_daily.to_dict(),
        "hourly_ohlcv": df_hourly.to_dict()
    }

    # 반성 및 개선 내용 생성
    # reflection = ''
    reflection = openAi.generate_reflection(openAiClient, recent_trades, current_market_data)
    
    # AI에 투자 판단 요청
    response_text = openAi.generate_trade(openAiClient, filtered_balances, orderbook, df_daily_recent, df_hourly_recent, fear_greed_index, reflection)

    # AI의 응답내용 파싱
    parsed_response = openAi.parse_ai_response(response_text)
    if not parsed_response:
        logger.recordLog(Log.ERROR, "Error", "Failed to parse AI response")
        return 

    decision = parsed_response.get('decision')
    percentage = parsed_response.get('percentage')
    reason = parsed_response.get('reason')

    if not decision or reason is None:
        logger.recordLog(Log.ERROR, "Error", "Incomplete data in AI response.")
        return
    
    # logger.info(f"AI Decision: {decision.upper()}")
    # logger.info(f"percentage: {percentage}")
    # logger.info(f"Decision Reason: {reason}")

    order_executed = False

    if decision == "buy":
        my_krw = upbit.get_balance("KRW")
        if my_krw is None:
            logger.recordLog(Log.ERROR, "Error", "Failed to retrieve KRW balance.")
            return
        buy_amount = my_krw * (percentage / 100) * 0.9995
        if buy_amount > 5000:
            logger.recordLog(Log.INFO, "Buy Order Executed", f"{percentage}% of available KRW")
            try:                
                order = upbit.buy_market_order("KRW-BTC", buy_amount)
                if order:
                    logger.recordLog(Log.INFO, "Buy order executed successfullly", f"{order}")
                    order_executed = True
                else:
                    logger.recordLog(Log.ERROR, "Error", "Buy order failed.")
            except Exception as e:
                logger.recordLog(Log.ERROR, "Error executing buy order", f"{e}")
        else:
            logger.recordLog(Log.WARNING, "Buy Order Failed", "Insufficient KRW (less than 5000 KRW)")
    elif decision == "sell":
        my_btc = upbit.get_balance("KRW-BTC")
        if my_btc is None:
            logger.ERROR(Log.ERROR, "Error", "Failed to retrieve BTC balance.")
            return
        sell_amount = my_btc * (percentage / 100)
        current_price = pyupbit.get_current_price("KRW-BTC")
        if sell_amount * current_price > 5000:
            logger.recordLog(Log.INFO, "Sell Order Executed", f"{percentage}% of held BTC")
            try:
                order = upbit.sell_market_order("KRW-BTC", sell_amount)
                if order:
                    order_executed = True
                else:
                    logger.recordLog(Log.ERROR, "Error", "Sell order failed.")
            except Exception as e:
                logger.recordLog(Log.ERROR, "Error executing sell order", f"{e}")
        else:
            logger.recordLog(Log.WARNING, "Sell Order Failed", "Insufficient BTC (less than 5000 KRW worth)")
    elif decision == "hold":
        logger.recordLog(Log.INFO, "INFO", "### Hold Position ###")
    else:
        logger.recordLog(Log.ERROR, "ERROR", "Invalid decision received from AI.")
    
    # 거래 실행 여부와 관계없이 현재 잔고 조회
    # time.sleep(2) # API 호출 제한을 고려하여 잠시 대기
    balances = upbit.get_balances()
    btc_balance = next((float(balance['balance']) for balance in balances if balance['currency'] == 'BTC'), 0)
    krw_balance = next((float(balance['balance']) for balance in balances if balance['currency'] == 'KRW'), 0)
    btc_avg_buy_price = next((float(balance['avg_buy_price']) for balance in balances if balance['currency'] == 'BTC'), 0)
    current_btc_price = pyupbit.get_current_price("KRW-BTC")

    # 거래 정보 로깅
    DB.log_trade(conn, decision, percentage if order_executed else 0, reason, 
              btc_balance, krw_balance, btc_avg_buy_price, current_btc_price, reflection)

    conn.close()

# ai_trading(env)

# 주기를 12시간 마다 인것을 고려
# schedule.every().day.at("05:00").do(ai_trading, env)    # Trigger at 14:00 (KST)
schedule.every().day.at("11:00").do(ai_trading, env)    # Trigger at 20:00 (KST)
# schedule.every().day.at("17:00").do(ai_trading, env)    # Trigger at 02:00 (KST)
schedule.every().day.at("23:00").do(ai_trading, env)    # Trigger at 08:00 (KST)

while 1:
    schedule.run_pending()
    time.sleep(1)