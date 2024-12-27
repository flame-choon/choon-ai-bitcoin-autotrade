import boto3

### AWS Assume 권한 획득
def get_assume_role():
    boto3_session = boto3.Session(profile_name='choon')
    sts_client = boto3_session.client('sts')
    assume_role_client = sts_client.assume_role(
        RoleArn="arn:aws:iam::879780444466:role/choon-assume-role",
        RoleSessionName="choon-session"
    )

    assume_session = boto3.Session(
        aws_access_key_id=assume_role_client['Credentials']['AccessKeyId'],
        aws_secret_access_key=assume_role_client['Credentials']['SecretAccessKey'],
        aws_session_token=assume_role_client['Credentials']['SessionToken']
    )

    return assume_session

### AWS Parameter Store에 저장
def get_parameter(session, env, keyPath):
    ssm_client = session.client('ssm')
    parameter = ssm_client.get_parameter(Name=f'/{env}/{keyPath}', WithDecryption=True)
    
    return parameter['Parameter']['Value']