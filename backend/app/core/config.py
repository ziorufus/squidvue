from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', extra='ignore')

    admin_email: str
    default_question_time: int = 20
    default_countdown_time: int = 5
    default_max_points: int = 1
    allowed_emojis: str = '😀 😎 🤓 🐼 🍀 🚀 🔥 🦊 🎯 ⚡ 🐙 🧠 🐧 🐯 🦄 🦉 🐬 🐢 🦋 🐝'
    google_client_id: str
    google_client_secret: str
    secret_key: str
    base_url: str = 'http://localhost:5173'
    database_url: str = 'sqlite:///./quiz.db'
    access_token_expire_minutes: int = 720


settings = Settings()
