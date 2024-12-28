from cryptography.fernet import Fernet
import util.aws as aws

### 암호화 라이브러리 (Fernet) 초기화 
def init(assume_session, env):
    fernetParameter = aws.get_parameter(assume_session, env, 'key/fernet')

    global fernet
    fernet = Fernet(fernetParameter.encode())
    
## 복호화
def decrypt_env_value(encrypted_value):
    return fernet.decrypt(encrypted_value).decode()
