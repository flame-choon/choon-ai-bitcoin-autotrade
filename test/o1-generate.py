import pyupbit
import ta
from ta.utils import dropna
from cryptography.fernet import Fernet
from openai import OpenAI
import requests
import json
import boto3

def get_parameter(session, env, keyPath):
    ssm_client = session.client('ssm')
    parameter = ssm_client.get_parameter(Name=f'/{env}/{keyPath}', WithDecryption=True)
    
    return parameter['Parameter']['Value']

def decrypt_env_value(encrypted_value):
    return fernet.decrypt(encrypted_value).decode()

### 공포 탐욕 지수 API 호출
def get_fear_and_greed_index():
    url = "https://api.alternative.me/fng/"
    try:
        response = requests.get(url, timeout=10, verify=False)
        response.raise_for_status()
        data = response.json()
        return data['data'][0]
    except requests.exceptions.RequestsException as e:
        print(" Error fetching Fear and Greed Index", f"{e}")
        return None

def add_indicators(df):
    # 볼린저 밴드 추가
    # windows 값 만큼의 데이터가 있어야 산출이 가능
    indicator_bb = ta.volatility.BollingerBands(close=df['close'], window=5, window_dev=2)
    df['bb_bbm'] = indicator_bb.bollinger_mavg()
    df['bb_bbh'] = indicator_bb.bollinger_hband()
    df['bb_bbl'] = indicator_bb.bollinger_lband()

    # RSI (Relative Strength Index) 추가
    # 최소 14일치의 데이터가 있어야 조회 가능
    df['rsi'] = ta.momentum.RSIIndicator(close=df['close'], window=14).rsi()

    # 이동평균선 (단기, 장기)
    # window 값 만큼의 데이터가 있어야 산출이 가능
    df['sma_5'] = ta.trend.SMAIndicator(close=df['close'], window=5).sma_indicator()
    df['ema_7'] = ta.trend.EMAIndicator(close=df['close'], window=7).ema_indicator()

    return df

# AI에 데이터들을 제공하여 투자 판단 결과를 받음
def generate_trade(filtered_balances, orderbook, df_daily_recent, df_hourly_recent, fear_greed_index):
        
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
        
        # response = openAiClient.chat.completions.create(
        # model="o1-preview",
        messages=[
            {
                "role": "user",
                "content": f"""
                You are an expert in Bitcoin investing. This analysis is performed every 12 hours. Analyze the provided data and datermine whether to buy, sell, or hold at the current moment. 
                Consider the following in your analysis:
                
                - Technical indicators and market data
                - The Fear and Greed Index and its implications
                - Overall market sentiment

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
                    Daily OHLCV with indicators (recent 30 days): {df_daily_recent.to_json()}
                    Hourly OHLCV with indicators (recent 168 hours): {df_hourly_recent.to_json()}
                    Fear and Greed Index: {json.dumps(fear_greed_index)}
                """
            }
        ]
        # )

        return messages

        # return response.choices[0].message.content

def o1_generate(env):

    AWS_DEFAULT_REGION = "ap-northeast-2"

    boto3_session = boto3.Session(profile_name='choon')

    sts_client = boto3_session.client('sts')
    assume_role_client = sts_client.assume_role(
        RoleArn="arn:aws:iam::879780444466:role/choon-assume-role",
        RoleSessionName="choon-session"
    )

    assume_session = boto3.Session(
        aws_access_key_id=assume_role_client['Credentials']['AccessKeyId'],
        aws_secret_access_key=assume_role_client['Credentials']['SecretAccessKey'],
        aws_session_token=assume_role_client['Credentials']['SessionToken'],
        region_name=AWS_DEFAULT_REGION
    )

    ### AWS Parameter Store에 접근하여 암호화 키 가져오기
    upbitAccessParameter = get_parameter(assume_session, env, 'key/upbit-access')
    upbitSecretParameter = get_parameter(assume_session, env, 'key/upbit-secret')
    
    ### 암호화 키 호출
    fernetParameter = get_parameter(assume_session, env, 'key/fernet')

    global fernet
    fernet = Fernet(fernetParameter.encode())

    # Upbit 객체 생성
    accessKey = decrypt_env_value(upbitAccessParameter)
    secretKey = decrypt_env_value(upbitSecretParameter)
    upbit = pyupbit.Upbit(accessKey, secretKey)

    # OpenAI 초기화
    openAIParameter = get_parameter(assume_session, env, 'key/openai')
    # print(openAIParameter)

    # openAi = OpenAI(api_key=decrypt_env_value(openAIParameter))
    # openAiClient = openAi.init()
    # if not openAiClient.api_key:
    #     print("Error", "OpenAI API key is missing or invalid.")
    #     return None
    
    # 1. 차트 데이터 조회 및 보조지표 추가
    # 30일 일봉 데이터
    df_daily = pyupbit.get_ohlcv("KRW-BTC", interval="day", count=44)  ## RSI 데이터 제공으로 인해 14일 추가하여 호출
    df_daily = add_indicators(df_daily)
    df_daily = dropna(df_daily)     
    df_daily.rename(columns={'value': 'value_krw'}, inplace=True)

    print(df_daily.head())

    # 7일 시간봉 데이터
    df_hourly = pyupbit.get_ohlcv("KRW-BTC", interval="minute60", count=168) ## RSI 데이터 제공으로 인해 14시간 추가하여 호출
    df_hourly = add_indicators(df_hourly)
    df_hourly = dropna(df_hourly)

    # 2. 공포 탐욕 지수 가져오기
    fear_greed_index = get_fear_and_greed_index()

    # 3. 현재 투자 상태 조회 (KRW, BTC 만 조회)
    all_balances = upbit.get_balances()
    filtered_balances = [balance for balance in all_balances if balance['currency'] in ['BTC','KRW']]
    
    # 4. KRW-BTC 오더북 (호가 데이터) 조회
    orderbook = pyupbit.get_orderbook("KRW-BTC")

    messages = generate_trade(filtered_balances, orderbook, df_daily, df_hourly, fear_greed_index)

    # print(messages)

    return ""

o1_generate('local')