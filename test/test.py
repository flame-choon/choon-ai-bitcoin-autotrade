import boto3

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

ssm_client = assume_session.client('ssm')
parameter = ssm_client.get_parameter(Name='/local/key/fernet', WithDecryption=True)

print(parameter['Parameter']['Value'])

# def load_env():

#     env = os.getenv('PYTHON_ENV', sys.argv[1])

#     env_file = f'.env.{env}'

#     load_dotenv(dotenv_path=env_file)

#     print(f"Current environment: {env}")

# load_env()

# database_url = os.getenv('DATABASE_URL')
# print(f"Database URL: {database_url}")

# ### youtube-transcript-api 테스트

# from youtube_transcript_api import YouTubeTranscriptApi

# def get_combined_transcript(video_id):
#     transcript = YouTubeTranscriptApi.get_transcript(video_id)

#     # 모든 텍스트를 하나의 문자열로 결합
#     combined_text = ' '.join(entry['text'] for entry in transcript)

#     return combined_text

# print(get_combined_transcript("TWINrTppUl4"))


### selenum 테스트

# from selenium import webdriver
# from selenium.webdriver.chrome.service import Service
# from selenium.webdriver.chrome.options import Options
# from webdriver_manager.chrome import ChromeDriverManager
# from selenium.webdriver.support.ui import WebDriverWait
# from selenium.webdriver.common.by import By
# from selenium.webdriver.common.actions.wheel_input import ScrollOrigin
# from selenium.webdriver import ActionChains
# from selenium.webdriver.support import expected_conditions as EC
# from selenium.common.exceptions import TimeoutException, ElementClickInterceptedException
# import time
# import logging

# # 로깅 설정
# logging.basicConfig(level=logging.INFO)
# logger = logging.getLogger(__name__)

# def setup_chrome_options():
#     chrome_options = Options()
#     chrome_options.add_argument("--start-maximized")
#     chrome_options.add_argument("--headless")  # 디버깅을 위해 헤드리스 모드 비활성화
#     chrome_options.add_argument("--disable-gpu")
#     chrome_options.add_argument("--no-sandbox")
#     chrome_options.add_argument("--disable-dev-shm-usage")
#     chrome_options.add_experimental_option('excludeSwitches', ['enable-logging'])
#     return chrome_options

# def create_driver():
#     logger.info("ChromeDriver 설정 중...")
#     service = Service(ChromeDriverManager().install())
#     driver = webdriver.Chrome(service=service, options=setup_chrome_options())
#     return driver

# def click_element_by_xpath(driver, xpath, element_name, wait_time=10):
#     try:
#         element = WebDriverWait(driver, wait_time).until(
#             EC.element_to_be_clickable((By.XPATH, xpath))
#         )
#         element.click()
#         logger.info(f"{element_name} 클릭 완료")
#         time.sleep(2)  # 클릭 후 잠시 대기
#     except TimeoutException:
#         logger.error(f"{element_name} 요소를 찾는 데 시간이 초과되었습니다.")
#     except ElementClickInterceptedException:
#         logger.error(f"{element_name} 요소를 클릭할 수 없습니다. 다른 요소에 가려져 있을 수 있습니다.")
#     except Exception as e:
#         logger.error(f"{element_name} 클릭 중 오류 발생: {e}")


# def perform_chart_actions(driver):
#     # 시간 메뉴 클릭
#     click_element_by_xpath(
#         driver,
#         "/html/body/div[1]/div[2]/div[3]/span/div/div/div[1]/div/div/cq-menu[1]/span",
#         "시간 메뉴"
#     )
    
#     # 일 옵션 선택
#     click_element_by_xpath(
#         driver,
#         "/html/body/div[1]/div[2]/div[3]/span/div/div/div[1]/div/div/cq-menu[1]/cq-menu-dropdown/cq-item[10]",
#         "일 옵션"
#     )
    
#     # 지표 메뉴 클릭
#     click_element_by_xpath(
#         driver,
#         "/html/body/div[1]/div[2]/div[3]/span/div/div/div[1]/div/div/cq-menu[3]/span",
#         "지표 메뉴"
#     )

#     # 볼린저 밴드 옵션 선택
#     click_element_by_xpath(
#         driver,
#         "/html/body/div[1]/div[2]/div[3]/span/div/div/div[1]/div/div/cq-menu[3]/cq-menu-dropdown/cq-scroll/cq-studies/cq-studies-content/cq-item[15]",
#         "볼린저 밴드 옵션"
#     )

#     # 지표 메뉴 클릭
#     click_element_by_xpath(
#         driver,
#         "/html/body/div[1]/div[2]/div[3]/span/div/div/div[1]/div/div/cq-menu[3]/span",
#         "지표 메뉴"
#     )

#     # 지표 메뉴 스크롤 이동
#     element = driver.find_element(By.XPATH, "/html/body/div[1]/div[2]/div[3]/span/div/div/div[1]/div/div/cq-menu[3]/cq-menu-dropdown/cq-scroll/div[2]")
#     scroll_origin = ScrollOrigin.from_element(element)
#     ActionChains(driver)\
#         .scroll_from_origin(scroll_origin, 0, 700)\
#         .perform()
    
#     # 일목균형표 옵션 선택
#     click_element_by_xpath(
#         driver,
#         "/html/body/div[1]/div[2]/div[3]/span/div/div/div[1]/div/div/cq-menu[3]/cq-menu-dropdown/cq-scroll/cq-studies/cq-studies-content/cq-item[44]",
#         "일목균형표 옵션"
#     )


# def capture_full_page_screenshot(driver, filename):
#     # logger.info(f"{url} 로딩 중...")
#     # driver.get(url)
    
#     # 페이지 로딩을 위한 대기 시간
#     logger.info("페이지 로딩 대기 중...")
#     time.sleep(10)  # 페이지 로딩을 위해 10초 대기
    
#     logger.info("전체 페이지 스크린샷 촬영 중...")
#     driver.save_screenshot(filename)
#     logger.info(f"스크린샷이 성공적으로 저장되었습니다: {filename}")

# def main():
#     driver = None
#     try:
#         driver = create_driver()
#         driver.get("https://upbit.com/full_chart?code=CRIX.UPBIT.KRW-BTC")
#         perform_chart_actions(driver)
#         capture_full_page_screenshot(
#             driver, 
#             "upbit_btc_full_chart.png"
#         )
#     except Exception as e:
#         logger.error(f"오류 발생: {e}")
#     finally:
#         if driver:
#             driver.quit()

# if __name__ == "__main__":
#     main()