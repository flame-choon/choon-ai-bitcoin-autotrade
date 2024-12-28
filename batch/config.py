from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    APP_TITLE: str = "Choon Autotrade Batch"
    APP_DESCRIPTION: str = "This is a project for batch processing in Choon Autotrade."
    APP_VERSION: str = "1.0.0"
    HOST: str = "0.0.0.0"
    PORT: int = 8090

settings = Settings()