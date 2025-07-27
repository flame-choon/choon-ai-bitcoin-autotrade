import boto3
import json

def lambda_handler(event, context):
    try:
        rds_client = boto3.client('rds', region_name='ap-northeast-2')
        
        db_instance_arn = 'arn:aws:rds:ap-northeast-2:879780444466:db:choon-autotrade-db'
        db_instance_identifier = db_instance_arn.split(':')[-1]
        
        response = rds_client.describe_db_instances(DBInstanceIdentifier=db_instance_identifier)
        db_instance = response['DBInstances'][0]
        current_status = db_instance['DBInstanceStatus']
        
        if current_status == 'stopped':
            start_response = rds_client.start_db_instance(DBInstanceIdentifier=db_instance_identifier)
            
            return {
                'statusCode': 200,
                'body': json.dumps({
                    'message': f'RDS instance {db_instance_identifier} is being started',
                    'db_instance_status': start_response['DBInstance']['DBInstanceStatus']
                })
            }
        else:
            return {
                'statusCode': 200,
                'body': json.dumps({
                    'message': f'RDS instance {db_instance_identifier} is not in stopped state',
                    'current_status': current_status
                })
            }
            
    except Exception as e:
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e),
                'message': 'Failed to start RDS instance'
            })
        }