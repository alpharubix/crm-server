from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str
    JWT_SECRET_KEY: str
    MONGODB_URI: str
    APP_PASSWORD: str
    DEV: str
    FIVE_POINT_CREDIT_BACKEND_URL: str
    TELECRM_URL: str
    TELECRM_TOKEN: str

    # Meta WhatsApp Cloud API Configuration
    META_GRAPH_VERSION: str = "v26.0"
    WHATSAPP_PHONE_NUMBER_ID: str = ""
    WHATSAPP_BUSINESS_ACCOUNT_ID: str = ""
    WHATSAPP_ACCESS_TOKEN: str = ""
    META_APP_SECRET: str = ""
    WEBHOOK_VERIFY_TOKEN: str = ""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()  # type: ignore
