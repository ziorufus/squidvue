from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', extra='ignore')

    admin_email: str
    default_question_time_multiple_choice: int = Field(
        default=20,
        validation_alias=AliasChoices('DEFAULT_QUESTION_TIME_MULTIPLE_CHOICE', 'DEFAULT_QUESTION_TIME'),
    )
    default_question_time_open: int = Field(
        default=20,
        validation_alias=AliasChoices('DEFAULT_QUESTION_TIME_OPEN', 'DEFAULT_QUESTION_TIME'),
    )
    default_countdown_time: int = 5
    default_max_points: int = 1
    allowed_emojis: str = '😀 😎 🤓 🐼 🍀 🚀 🔥 🦊 🎯 ⚡ 🐙 🧠 🐧 🐯 🦄 🦉 🐬 🐢 🦋 🐝'
    google_client_id: str
    google_client_secret: str
    secret_key: str
    base_url: str = 'http://localhost:5173'
    database_url: str = 'sqlite:///./quiz.db'
    redis_url: str | None = None
    access_token_expire_minutes: int = 720


settings = Settings()
