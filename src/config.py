from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    database_url: str
    JWT_SECRET_KEY: str
    MONGODB_URI:str
    model_config = SettingsConfigDict(env_file=".env")


settings = Settings()  # type: ignore