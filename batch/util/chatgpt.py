from util.crypt import Crypt
from util.aws import AWS
from util.log import Log
from openai import OpenAI
import json
import re

class ChatGPT:

    def __init__(self, assume_session, env):
        self.assume_session = assume_session
        self.env = env

    # OpenAI 의 API 키 이용하여 초기화
    def init(self):
        self.openAIParameter = AWS.get_parameter(self.assume_session, self.env, 'key/openai')
        return OpenAI(api_key=Crypt.decrypt_env_value(self.openAIParameter))
    
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
    def generate_reflection(self, openAiClient, trades_df, current_market_data):
        performance = ChatGPT.calculate_performance(trades_df)  # 투자 퍼포먼스 계산
        
        # OpenAI API 호출로 AI의 반성 일기 및 개선 사항 생성 요청
        response = openAiClient.chat.completions.create(
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
    
    # AI에 데이터들을 제공하여 투자 판단 결과를 받음
    def generate_trade(self, openAiClient, filtered_balances, orderbook, df_daily_recent, df_hourly_recent, fear_greed_index):
        
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
        
        response = openAiClient.chat.completions.create(
        model="o1-preview",
        messages=[
            {
                "role": "user",
                "content": f"""
                You are an expert in Bitcoin investing. This analysis is performed every 6 hours. Analyze the provided data and datermine whether to buy, sell, or hold at the current moment. 
                Consider the following in your analysis:
                
                - Technical indicators and market data
                - The Fear and Greed Index and its implications
                - Overall market sentiment
                - Recent trading performance 

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
        ])

        return response.choices[0].message.content
    
    # AI 응답 파싱
    def parse_ai_response(self, response_text):    
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
                Log.recordLog(Log.ERROR, "Error", "No JSON found in AI response.")
                return None
        except json.JSONDecodeError as e:
            Log.recordLog(Log.ERROR, "JSON parsing error", f"{e}")
            # ChatGPT.logger.error(f"JSON parsing error: {e}")
            return None        