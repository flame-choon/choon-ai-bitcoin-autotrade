import os
import sys

### 환경변수 로드
def set_env():
    env = os.getenv('PYTHON_ENV', sys.argv[1])
    print(f"Current environment: {env}")

    return env