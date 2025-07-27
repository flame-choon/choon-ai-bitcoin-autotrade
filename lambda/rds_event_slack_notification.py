import json
import os
import urllib3
from datetime import datetime

def lambda_handler(event, context):
    http = urllib3.PoolManager()
    
    slack_webhook_url = os.environ.get('SLACK_WEBHOOK_URL')
    if not slack_webhook_url:
        print('SLACK_WEBHOOK_URL environment variable is not set')
        return {
            'statusCode': 500,
            'body': json.dumps('SLACK_WEBHOOK_URL not configured')
        }
    
    try:
        detail = event.get('detail', {})
        event_id = detail.get('EventID', '')
        source_id = detail.get('SourceIdentifier', '')
        event_message = detail.get('Message', '')
        event_time = event.get('time', '')
        
        event_types = {
            'RDS-EVENT-0087': {
                'title': 'RDS Instance Stopped',
                'color': '#FF6B6B',
                'emoji': ':red_circle:'
            },
            'RDS-EVENT-0088': {
                'title': 'RDS Instance Started',
                'color': '#4ECDC4',
                'emoji': ':green_circle:'
            }
        }
        
        event_info = event_types.get(event_id, {
            'title': 'RDS Event',
            'color': '#36a64f',
            'emoji': ':information_source:'
        })
        
        if event_time:
            try:
                dt = datetime.fromisoformat(event_time.replace('Z', '+00:00'))
                formatted_time = dt.strftime('%Y-%m-%d %H:%M:%S UTC')
            except:
                formatted_time = event_time
        else:
            formatted_time = 'Unknown'
        
        slack_message = {
            'text': f"{event_info['emoji']} {event_info['title']}",
            'attachments': [{
                'color': event_info['color'],
                'title': event_info['title'],
                'fields': [
                    {
                        'title': 'Instance',
                        'value': source_id,
                        'short': True
                    },
                    {
                        'title': 'Event ID',
                        'value': event_id,
                        'short': True
                    },
                    {
                        'title': 'Message',
                        'value': event_message,
                        'short': False
                    },
                    {
                        'title': 'Time',
                        'value': formatted_time,
                        'short': True
                    },
                    {
                        'title': 'Region',
                        'value': 'ap-northeast-2',
                        'short': True
                    }
                ],
                'footer': 'AWS RDS Event',
                'ts': int(datetime.now().timestamp())
            }]
        }
        
        response = http.request(
            'POST',
            slack_webhook_url,
            body=json.dumps(slack_message).encode('utf-8'),
            headers={'Content-Type': 'application/json'}
        )
        
        if response.status == 200:
            return {
                'statusCode': 200,
                'body': json.dumps('Slack notification sent successfully')
            }
        else:
            print(f'Slack API returned status code: {response.status}')
            return {
                'statusCode': response.status,
                'body': json.dumps(f'Failed to send Slack notification: {response.data}')
            }
            
    except Exception as e:
        print(f'Error: {str(e)}')
        return {
            'statusCode': 500,
            'body': json.dumps(f'Error processing event: {str(e)}')
        }