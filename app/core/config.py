from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "privacy-agent"
    app_env: str = "local"
    database_url: str = "postgresql+psycopg://privacy:privacy@postgres:5432/privacy_agent"
    gmail_oauth_client_secrets_file: str = "secrets/google_oauth_client.json"
    gmail_oauth_token_file: str = "secrets/gmail_token.json"
    gmail_oauth_send_token_file: str = "secrets/gmail_send_token.json"
    gmail_discovery_max_results_per_query: int = 50
    controller_resolver_max_pages: int = 20
    openclaw_enabled: bool = False
    openclaw_model: str = ""
    openclaw_max_input_chars: int = 12000
    alberto_bridge_token: str = ""
    privacy_user_full_name: str = ""
    privacy_user_preferred_email: str = ""
    privacy_user_optional_phone: str = ""
    privacy_user_country: str = ""
    privacy_user_preferred_language: str = "en"
    gdpr_default_deadline_days: int = 30
    privacy_data_root: str = "data/cases"
    privacy_max_upload_bytes: int = 50_000_000
    privacy_max_zip_uncompressed_bytes: int = 100_000_000
    privacy_max_zip_members: int = 500
    privacy_api_token: str = ""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
