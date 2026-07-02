from typing import Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # App
    PROJECT_NAME: str = "Supply Chain Agent"
    API_V1_STR: str = "/api"

    # Auth
    SECRET_KEY: str = "your-secret-key-should-be-complex-and-stored-in-env"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24

    # Database
    DATABASE_URL: str = "postgresql+pg8000://postgres:123456@localhost:5432/supply_chain_agent"
    PO_HISTORY_SYNC_START_DATE: str = "2025-01-01T00:00:00"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_CACHE_TTL: int = 86400

    # MinIO / S3 compatible storage
    MINIO_ENDPOINT: Optional[str] = None
    MINIO_ACCESS_KEY: Optional[str] = None
    MINIO_SECRET_KEY: Optional[str] = None
    MINIO_BUCKET: str = "supply-chain-agent"
    MINIO_SECURE: bool = False
    MINIO_REGION: Optional[str] = None
    MINIO_PUBLIC_BASE_URL: Optional[str] = None

    # Centralized config paths
    CONFIG_DIR: str = "config"
    KINGDEE_CONFIG_PATH: Optional[str] = None

    # LLM
    LLM_PROVIDER: str = "openai"
    LLM_API_KEY: Optional[str] = None
    LLM_BASE_URL: Optional[str] = None
    LLM_MODEL: str = "gpt-3.5-turbo"

    # Procurement Agent LLM
    PROCUREMENT_AGENT_LLM_PROVIDER: str = "deepseek"
    PROCUREMENT_AGENT_LLM_API_KEY: Optional[str] = None
    PROCUREMENT_AGENT_LLM_BASE_URL: Optional[str] = None
    PROCUREMENT_AGENT_LLM_MODEL: str = "deepseek-v4-flash"

    # Admin Init
    ADMIN_USERNAME: Optional[str] = None
    ADMIN_PASSWORD: Optional[str] = None

    # WeChat Official Account
    WECHAT_APP_ID: Optional[str] = None
    WECHAT_APP_SECRET: Optional[str] = None
    WECHAT_TOKEN: str = "supply_chain_agent_wechat_token"
    WECHAT_VERIFY_URL: Optional[str] = None
    WECHAT_OAUTH_REDIRECT_URL: Optional[str] = None
    WECHAT_OAUTH_FRONTEND_URL: Optional[str] = None
    WECHAT_MENU_URL_VERSION: Optional[str] = None
    WECHAT_TEMPLATE_DEFAULT_URL: Optional[str] = None
    WECHAT_TEMPLATE_ONBOARDING_RESULT_ID: Optional[str] = None
    WECHAT_TEMPLATE_NEW_INQUIRY_ID: Optional[str] = None
    WECHAT_TEMPLATE_WARNING_ID: Optional[str] = None
    WECHAT_TEMPLATE_INQUIRY_RESULT_ID: Optional[str] = None
    WECHAT_TEMPLATE_QUOTE_DEADLINE_REMINDER_ID: Optional[str] = None
    WECHAT_TEMPLATE_CONTRACT_CONFIRM_ID: Optional[str] = None
    WECHAT_TEMPLATE_MEMBER_REVIEW_ID: Optional[str] = None
    WECHAT_SUBSCRIBE_WELCOME_MESSAGE: str = "\u6b22\u8fce\u5173\u6ce8\u4f9b\u5e94\u94fe\u534f\u540c\u5e73\u53f0\u3002"

    class Config:
        env_file = ".env"
        extra = "allow"


settings = Settings()
