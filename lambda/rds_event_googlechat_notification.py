import json
import os
import urllib3
from datetime import datetime

def lambda_handler(event, context):
    http = urllib3.PoolManager()
    
    google_chat_webhook_url = os.environ.get('GOOGLE_CHAT_WEBHOOK_URL')
    if not google_chat_webhook_url:
        print('GOOGLE_CHAT_WEBHOOK_URL environment variable is not set')
        return {
            'statusCode': 500,
            'body': json.dumps('GOOGLE_CHAT_WEBHOOK_URL not configured')
        }
    
    try:
        detail = event.get('detail', {})
        event_id = detail.get('EventID', '')
        source_id = detail.get('SourceIdentifier', '')
        event_message = detail.get('Message', '')
        event_time = event.get('time', '')
        
        event_types = {
            'RDS-EVENT-0087': {
                'title': '🔴 RDS Instance Stopped',
                'subtitle': 'Database instance has been stopped',
                'icon': 'https://fonts.gstatic.com/s/i/short-term/release/googlesymbols/stop_circle/default/48px.svg'
            },
            'RDS-EVENT-0088': {
                'title': '🟢 RDS Instance Started',
                'subtitle': 'Database instance has been started',
                'icon': 'https://fonts.gstatic.com/s/i/short-term/release/googlesymbols/play_circle/default/48px.svg'
            }
        }
        
        event_info = event_types.get(event_id, {
            'title': 'ℹ️ RDS Event',
            'subtitle': 'Database event occurred',
            'icon': 'https://fonts.gstatic.com/s/i/short-term/release/googlesymbols/info/default/48px.svg'
        })
        
        if event_time:
            try:
                dt = datetime.fromisoformat(event_time.replace('Z', '+00:00'))
                formatted_time = dt.strftime('%Y-%m-%d %H:%M:%S UTC')
            except:
                formatted_time = event_time
        else:
            formatted_time = 'Unknown'
        
        google_chat_message = {
            'cardsV2': [{
                'card': {
                    'header': {
                        'title': event_info['title'],
                        'subtitle': event_info['subtitle'],
                        'imageUrl': event_info['icon'],
                        'imageType': 'CIRCLE'
                    },
                    'sections': [{
                        'header': 'Event Details',
                        'widgets': [
                            {
                                'decoratedText': {
                                    'topLabel': 'Instance',
                                    'text': source_id,
                                    'startIcon': {
                                        'knownIcon': 'DATABASE'
                                    }
                                }
                            },
                            {
                                'decoratedText': {
                                    'topLabel': 'Event ID',
                                    'text': event_id,
                                    'startIcon': {
                                        'knownIcon': 'BOOKMARK'
                                    }
                                }
                            },
                            {
                                'decoratedText': {
                                    'topLabel': 'Message',
                                    'text': event_message,
                                    'wrapText': True,
                                    'startIcon': {
                                        'knownIcon': 'DESCRIPTION'
                                    }
                                }
                            },
                            {
                                'decoratedText': {
                                    'topLabel': 'Time',
                                    'text': formatted_time,
                                    'startIcon': {
                                        'knownIcon': 'CLOCK'
                                    }
                                }
                            },
                            {
                                'decoratedText': {
                                    'topLabel': 'Region',
                                    'text': 'ap-northeast-2 (Seoul)',
                                    'startIcon': {
                                        'knownIcon': 'MAP_PIN'
                                    }
                                }
                            }
                        ]
                    }]
                }
            }]
        }
        
        response = http.request(
            'POST',
            google_chat_webhook_url,
            body=json.dumps(google_chat_message).encode('utf-8'),
            headers={'Content-Type': 'application/json; charset=UTF-8'}
        )
        
        if response.status == 200:
            return {
                'statusCode': 200,
                'body': json.dumps('Google Chat notification sent successfully')
            }
        else:
            print(f'Google Chat API returned status code: {response.status}')
            print(f'Response body: {response.data}')
            return {
                'statusCode': response.status,
                'body': json.dumps(f'Failed to send Google Chat notification: {response.data}')
            }
            
    except Exception as e:
        print(f'Error: {str(e)}')
        return {
            'statusCode': 500,
            'body': json.dumps(f'Error processing event: {str(e)}')
        }