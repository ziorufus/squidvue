from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker

from app.core.config import settings


connect_args = {'check_same_thread': False} if settings.database_url.startswith('sqlite') else {}
engine = create_engine(
    settings.database_url,
    connect_args=connect_args,
    pool_size=4,
    max_overflow=4,
    pool_timeout=30,
    pool_pre_ping=True,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def initialize_schema() -> None:
    """Create tables/types safely across multi-worker startup."""
    if engine.dialect.name == 'postgresql':
        # Serialize DDL across workers/processes to avoid enum type creation races.
        with engine.begin() as conn:
            conn.execute(text('SELECT pg_advisory_lock(88442211)'))
            try:
                Base.metadata.create_all(bind=conn)
            finally:
                conn.execute(text('SELECT pg_advisory_unlock(88442211)'))
        return

    Base.metadata.create_all(bind=engine)


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

        quizzes_info = conn.execute(text("PRAGMA table_info('quizzes')")).mappings().all()
        quiz_columns = {row['name'] for row in quizzes_info}

        if 'question_time_multiple_choice' not in quiz_columns:
            conn.execute(
                text(
                    f'ALTER TABLE quizzes ADD COLUMN question_time_multiple_choice INTEGER NOT NULL DEFAULT {settings.default_question_time_multiple_choice}'
                )
            )
        if 'question_time_open' not in quiz_columns:
            conn.execute(
                text(
                    f'ALTER TABLE quizzes ADD COLUMN question_time_open INTEGER NOT NULL DEFAULT {settings.default_question_time_open}'
                )
            )

        if 'question_time' in quiz_columns:
            conn.execute(
                text(
                    'UPDATE quizzes SET question_time_multiple_choice = question_time '
                    'WHERE question_time_multiple_choice IS NULL OR question_time_multiple_choice <= 0'
                )
            )
            conn.execute(
                text(
                    'UPDATE quizzes SET question_time_open = question_time '
                    'WHERE question_time_open IS NULL OR question_time_open <= 0'
                )
            )
