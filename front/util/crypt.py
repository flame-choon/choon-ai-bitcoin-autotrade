from cryptography.fernet import Fernet
from util.aws import AWS

class Crypt:
    ### 암호화 라이브러리 (Fernet) 초기화 
    def init(assume_session, env):
        fernetParameter = AWS.get_parameter(assume_session, env, 'key/fernet')

        global fernet
        fernet = Fernet(fernetParameter.encode())
        
    ## 복호화
    def decrypt_env_value(encrypted_value):
        return fernet.decrypt(encrypted_value).decode()
