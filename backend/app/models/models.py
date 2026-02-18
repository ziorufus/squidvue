from datetime import datetime
from enum import Enum

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum as SqlEnum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


class UserRole(str, Enum):
    ADMIN = 'admin'
    PRIVILEGED = 'privileged'
    STUDENT = 'student'


class QuizStatus(str, Enum):
    DRAFT = 'draft'
    READY = 'ready'
    RUNNING = 'running'
    FINISHED = 'finished'


class QuestionType(str, Enum):
    MULTIPLE_CHOICE = 'multiple_choice'
    OPEN = 'open'


class User(Base):
    __tablename__ = 'users'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    google_sub: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    emoji: Mapped[str | None] = mapped_column(String(32), unique=True, nullable=True, index=True)
    role: Mapped[UserRole] = mapped_column(SqlEnum(UserRole), nullable=False, default=UserRole.STUDENT)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class Quiz(Base):
    __tablename__ = 'quizzes'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(5), unique=True, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    # Legacy column kept for backward-compatible writes on existing databases.
    question_time: Mapped[int] = mapped_column(Integer, nullable=False, default=20)
    question_time_multiple_choice: Mapped[int] = mapped_column(Integer, nullable=False)
    question_time_open: Mapped[int] = mapped_column(Integer, nullable=False)
    countdown_time: Mapped[int] = mapped_column(Integer, nullable=False)
    emoji_pool: Mapped[str] = mapped_column(Text, default='')
    status: Mapped[QuizStatus] = mapped_column(SqlEnum(QuizStatus), default=QuizStatus.DRAFT, nullable=False)
    owner_id: Mapped[int] = mapped_column(ForeignKey('users.id'), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    stopped_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    owner = relationship('User')
    questions = relationship('Question', back_populates='quiz', cascade='all, delete-orphan')


class Question(Base):
    __tablename__ = 'questions'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    quiz_id: Mapped[int] = mapped_column(ForeignKey('quizzes.id', ondelete='CASCADE'), nullable=False, index=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    question_type: Mapped[QuestionType] = mapped_column(SqlEnum(QuestionType), nullable=False)
    option_a: Mapped[str | None] = mapped_column(Text, nullable=True)
    option_b: Mapped[str | None] = mapped_column(Text, nullable=True)
    option_c: Mapped[str | None] = mapped_column(Text, nullable=True)
    option_d: Mapped[str | None] = mapped_column(Text, nullable=True)
    option_e: Mapped[str | None] = mapped_column(Text, nullable=True)
    correct_answer: Mapped[str] = mapped_column(Text, nullable=False)
    max_points: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    quiz = relationship('Quiz', back_populates='questions')


class Participant(Base):
    __tablename__ = 'participants'
    __table_args__ = (
        UniqueConstraint('quiz_id', 'user_id', name='uq_participant_quiz_user'),
        UniqueConstraint('quiz_id', 'emoji', name='uq_participant_quiz_emoji'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    quiz_id: Mapped[int] = mapped_column(ForeignKey('quizzes.id', ondelete='CASCADE'), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    emoji: Mapped[str] = mapped_column(String(32), nullable=False)
    joined_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class Answer(Base):
    __tablename__ = 'answers'
    __table_args__ = (UniqueConstraint('participant_id', 'question_id', name='uq_answer_participant_question'),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    participant_id: Mapped[int] = mapped_column(ForeignKey('participants.id', ondelete='CASCADE'), nullable=False, index=True)
    question_id: Mapped[int] = mapped_column(ForeignKey('questions.id', ondelete='CASCADE'), nullable=False, index=True)
    value: Mapped[str] = mapped_column(Text, default='')
    is_correct: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    response_seconds: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    score: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    submitted_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class OpenDraft(Base):
    __tablename__ = 'open_drafts'
    __table_args__ = (UniqueConstraint('participant_id', 'question_id', name='uq_draft_participant_question'),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    participant_id: Mapped[int] = mapped_column(ForeignKey('participants.id', ondelete='CASCADE'), nullable=False, index=True)
    question_id: Mapped[int] = mapped_column(ForeignKey('questions.id', ondelete='CASCADE'), nullable=False, index=True)
    value: Mapped[str] = mapped_column(Text, default='')
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
