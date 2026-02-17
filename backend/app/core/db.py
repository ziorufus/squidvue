from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker

from app.core.config import settings


connect_args = {'check_same_thread': False} if settings.database_url.startswith('sqlite') else {}
engine = create_engine(settings.database_url, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def ensure_runtime_schema() -> None:
    if not settings.database_url.startswith('sqlite'):
        return

    with engine.begin() as conn:
        users_info = conn.execute(text("PRAGMA table_info('users')")).mappings().all()
        columns = {row['name'] for row in users_info}

        if 'emoji' not in columns:
            conn.execute(text('ALTER TABLE users ADD COLUMN emoji VARCHAR(32)'))

        conn.execute(
            text('CREATE UNIQUE INDEX IF NOT EXISTS ix_users_emoji_unique ON users (emoji) WHERE emoji IS NOT NULL')
        )
