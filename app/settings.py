from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    archies_transcripts_api_url: str
    proxy_username: str
    proxy_password: str
    youtube_api_key: str
    groq_api_key: str
    supabase_url: str
    supabase_service_role_key: str
    supabase_jwt_secret: str

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=False
    )


settings = AppSettings()
