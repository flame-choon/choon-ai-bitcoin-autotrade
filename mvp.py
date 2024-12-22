import os
from dotenv import load_dotenv
import pyupbit
from openai import OpenAI
import json

# .env 파일에 저장되어 있는 환경변수 정보를 불러옴
load_dotenv()

# 1. 업비트 차트 데이터 가져오기 (30일 일봉)
df = pyupbit.get_ohlcv("KRW-BTC", count = 30, interval = "day") 
# o (open)  : 시가 첫 번째 거래 가격
# h (high)  : 고가, 최고 거래 가격
# l (low)   : 저가, 최저 거래 가격
# c (close) : 종가, 마지막 거래 가격
# v (volume): 거래량, 거래된 수량
# v (value) : 거래금액, 거래된 총 금액


# 2. AI에게 데이터 제공하고 판단 받기
aiClient = OpenAI()

response = aiClient.chat.completions.create(
  model="gpt-4o",
  messages=[
    {
      "role": "system",
      "content": [
        {
          "type": "text",
          "text": "You are an expert in Bitcoin investing. Tell me whether to buy, sell, or hold at the moment based on the chart data provided. response in json format.\n\nResponse Example:\n{\"decision:\"buy\", \"reason\": \"some technical reason\"}\n{\"decision:\"sell\", \"reason\": \"some technical reason\"}\n{\"decision:\"hold\", \"reason\": \"some technical reason\"}"
        }
      ]
    },
    {
      "role": "user",
      "content": [
        {
          "type": "text",
          "text": df.to_json()
        }
      ]
    }
  ],
  response_format={
    "type": "json_object"
  }
)

result = response.choices[0].message.content

# 3. AI의 판단에 따라 실제로 자동매매 진행하기
result = json.loads(result)

accessKey = os.getenv("UPBIT_ACCESS_KEY")
secretKey = os.getenv("UPBIT_SECRET_KEY")
upbit = pyupbit.Upbit(accessKey, secretKey)

if result["decision"] == "buy":
    # 매수
    print(upbit.buy_market_order("KRW-BTC", upbit.get_balance("KRW")))
    print(result["reason"])
elif result["decision"] == "sell":
    # 매도
    print(upbit.sell_market_order("KRW-BTC", upbit.get_balance("KRW-BTC")))
elif result["decision"] == "hold":
    # 지나감
    print(result["reason"])