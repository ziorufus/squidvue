import asyncio
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import math
import logging

from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.models import Answer, OpenDraft, Participant, Question, QuestionType, Quiz, QuizStatus, User
from app.services.emoji import ensure_user_emoji
from app.ws.manager import WebSocketManager

logger = logging.getLogger('quiz.submit')


@dataclass
class RuntimeState:
    status: str
    question_index: int | None
    phase: str
    remaining_seconds: int
    total_questions: int


class QuizRuntime:
    def __init__(self, session_factory: sessionmaker) -> None:
        self.session_factory = session_factory
        self.ws = WebSocketManager()
        self.locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
        self.last_phase: dict[str, tuple[str, int | None]] = {}
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        if not self._task:
            self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            self._task = None

    async def _loop(self) -> None:
        while True:
            await self.tick_all()
            await asyncio.sleep(1)

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    def _question_time(self, quiz: Quiz, question: Question) -> int:
        if question.question_type == QuestionType.MULTIPLE_CHOICE:
            return quiz.question_time_multiple_choice
        return quiz.question_time_open

    def _question_window(self, quiz: Quiz, question_index: int) -> tuple[float, float, int] | None:
        offset = 0.0
        for idx, question in enumerate(quiz.questions):
            question_time = self._question_time(quiz, question)
            question_start = offset + quiz.countdown_time
            question_end = question_start + question_time
            if idx == question_index:
                return question_start, question_end, question_time
            offset = question_end
        return None

    def compute_state(self, quiz: Quiz) -> RuntimeState:
        total_questions = len(quiz.questions)
        if total_questions == 0:
            return RuntimeState(status=quiz.status.value, question_index=None, phase='idle', remaining_seconds=0, total_questions=0)

        if quiz.status != QuizStatus.RUNNING or not quiz.started_at:
            phase = 'finished' if quiz.status == QuizStatus.FINISHED else 'idle'
            return RuntimeState(status=quiz.status.value, question_index=None, phase=phase, remaining_seconds=0, total_questions=total_questions)

        started_at = quiz.started_at.replace(tzinfo=timezone.utc) if quiz.started_at.tzinfo is None else quiz.started_at
        elapsed = max(0.0, (self._now() - started_at).total_seconds())
        offset = 0.0
        for idx, question in enumerate(quiz.questions):
            question_time = self._question_time(quiz, question)
            countdown_end = offset + quiz.countdown_time
            question_end = countdown_end + question_time
            if elapsed < countdown_end:
                remaining = max(1, int(math.ceil(countdown_end - elapsed)))
                return RuntimeState(status='running', question_index=idx, phase='countdown', remaining_seconds=remaining, total_questions=total_questions)
            if elapsed < question_end:
                remaining = max(1, int(math.ceil(question_end - elapsed)))
                return RuntimeState(status='running', question_index=idx, phase='question', remaining_seconds=remaining, total_questions=total_questions)
            offset = question_end

        return RuntimeState(status='finished', question_index=None, phase='finished', remaining_seconds=0, total_questions=total_questions)

    async def tick_all(self) -> None:
        db: Session = self.session_factory()
        try:
            quizzes = db.scalars(select(Quiz).where(Quiz.status == QuizStatus.RUNNING)).all()
            for quiz in quizzes:
                quiz.questions.sort(key=lambda q: q.position)
                state = self.compute_state(quiz)
                key = quiz.code
                prev = self.last_phase.get(key)
                curr = (state.phase, state.question_index)

                if prev and prev[0] == 'question' and curr[0] != 'question' and prev[1] is not None:
                    prev_question = quiz.questions[prev[1]]
                    self._finalize_open_drafts(db, quiz, prev_question)
                    db.commit()

                if state.phase == 'finished':
                    quiz.status = QuizStatus.FINISHED
                    quiz.stopped_at = datetime.utcnow()
                    self._finalize_all_missing_answers(db, quiz)
                    db.commit()

                self.last_phase[key] = curr
                await self.broadcast_quiz_state(db, quiz)
        finally:
            db.close()

    def _finalize_open_drafts(self, db: Session, quiz: Quiz, question: Question) -> None:
        if question.question_type != QuestionType.OPEN:
            return

        participants = db.scalars(select(Participant).where(Participant.quiz_id == quiz.id)).all()
        for participant in participants:
            already = db.scalar(
                select(Answer).where(Answer.participant_id == participant.id, Answer.question_id == question.id)
            )
            if already:
                continue
            draft = db.scalar(
                select(OpenDraft).where(OpenDraft.participant_id == participant.id, OpenDraft.question_id == question.id)
            )
            value = draft.value if draft else ''
            is_correct = value.strip().lower() == question.correct_answer.strip().lower()
            max_time = self._question_time(quiz, question)
            score = self._score(question.max_points, max_time, max_time) if is_correct else 0.0
            db.add(
                Answer(
                    participant_id=participant.id,
                    question_id=question.id,
                    value=value,
                    is_correct=is_correct,
                    response_seconds=max_time,
                    score=score,
                )
            )

    def _finalize_all_missing_answers(self, db: Session, quiz: Quiz) -> None:
        participants = db.scalars(select(Participant).where(Participant.quiz_id == quiz.id)).all()
        quiz.questions.sort(key=lambda q: q.position)

        for participant in participants:
            for question in quiz.questions:
                already = db.scalar(
                    select(Answer).where(Answer.participant_id == participant.id, Answer.question_id == question.id)
                )
                if already:
                    continue
                max_time = self._question_time(quiz, question)
                db.add(
                    Answer(
                        participant_id=participant.id,
                        question_id=question.id,
                        value='',
                        is_correct=False,
                        response_seconds=max_time,
                        score=0,
                    )
                )

    def _score(self, max_points: int, max_time: int, time_taken: float) -> float:
        if time_taken > max_time:
            return 0.0
        return float(max_points + max_points * (max_time - time_taken) / max_time)

    async def broadcast_quiz_state(self, db: Session, quiz: Quiz) -> None:
        quiz.questions.sort(key=lambda q: q.position)
        state = self.compute_state(quiz)
        question_payload = None
        if state.question_index is not None and state.question_index < len(quiz.questions):
            q = quiz.questions[state.question_index]
            question_payload = {
                'id': q.id,
                'position': q.position,
                'text': q.text,
                'question_type': q.question_type.value,
                'options': {
                    'A': q.option_a,
                    'B': q.option_b,
                    'C': q.option_c,
                    'D': q.option_d,
                    'E': q.option_e,
                },
            }

        stats = self.quiz_stats(db, quiz.id)
        payload = {
            'type': 'state',
            'quiz_code': quiz.code,
            'status': state.status,
            'phase': state.phase,
            'remaining_seconds': state.remaining_seconds,
            'question_index': state.question_index,
            'total_questions': state.total_questions,
            'question': question_payload,
            'stats': stats,
        }
        await self.ws.broadcast(f'quiz:{quiz.code}:student', payload)
        await self.ws.broadcast(f'quiz:{quiz.code}:admin', payload)
        await self.ws.broadcast(f'quiz:{quiz.code}:screen', payload)

    def quiz_stats(self, db: Session, quiz_id: int) -> dict:
        total_participants = db.scalar(select(func.count()).select_from(Participant).where(Participant.quiz_id == quiz_id)) or 0
        correct_answers = db.scalar(
            select(func.count()).select_from(Answer).join(Participant, Participant.id == Answer.participant_id).where(Participant.quiz_id == quiz_id, Answer.is_correct.is_(True))
        ) or 0
        avg_correct_seconds = db.scalar(
            select(func.avg(Answer.response_seconds)).join(Participant, Participant.id == Answer.participant_id).where(Participant.quiz_id == quiz_id, Answer.is_correct.is_(True))
        )
        return {
            'participants': int(total_participants),
            'correct_answers': int(correct_answers),
            'avg_correct_seconds': round(float(avg_correct_seconds), 2) if avg_correct_seconds is not None else None,
        }

    def ranking_for_quiz(self, db: Session, quiz_id: int) -> list[dict]:
        rows = db.execute(
            select(User.emoji, func.sum(Answer.score).label('score'))
            .select_from(Participant)
            .join(User, User.id == Participant.user_id)
            .join(Answer, Answer.participant_id == Participant.id)
            .where(Participant.quiz_id == quiz_id)
            .where(User.emoji.is_not(None))
            .group_by(User.emoji)
            .order_by(func.sum(Answer.score).desc())
        ).all()
        return [{'emoji': row[0], 'score': float(row[1] or 0)} for row in rows]

    def global_ranking(self, db: Session) -> list[dict]:
        rows = db.execute(
            select(User.emoji, func.sum(Answer.score).label('score'))
            .select_from(Participant)
            .join(User, User.id == Participant.user_id)
            .join(Answer, Answer.participant_id == Participant.id)
            .where(User.emoji.is_not(None))
            .group_by(User.emoji)
            .order_by(func.sum(Answer.score).desc())
        ).all()
        return [{'emoji': row[0], 'score': float(row[1] or 0)} for row in rows]

    def upsert_open_draft(self, db: Session, participant_id: int, question_id: int, value: str) -> None:
        draft = db.scalar(select(OpenDraft).where(OpenDraft.participant_id == participant_id, OpenDraft.question_id == question_id))
        if not draft:
            draft = OpenDraft(participant_id=participant_id, question_id=question_id, value=value)
            db.add(draft)
        else:
            draft.value = value
            draft.updated_at = datetime.utcnow()

    def submit_answer(
        self,
        db: Session,
        quiz: Quiz,
        participant: Participant,
        question: Question,
        value: str,
    ) -> dict:
        log_ctx = {
            'quiz_code': quiz.code,
            'participant_id': participant.id,
            'submitted_question_id': question.id,
        }
        if quiz.status != QuizStatus.RUNNING or not quiz.started_at:
            logger.warning('answer_rejected_not_running %s', {**log_ctx, 'quiz_status': quiz.status.value})
            return {'accepted': False, 'reason': 'Question is not open'}

        quiz.questions.sort(key=lambda q: q.position)
        try:
            question_index = next(i for i, q in enumerate(quiz.questions) if q.id == question.id)
        except StopIteration:
            logger.warning('answer_rejected_invalid_question %s', log_ctx)
            return {'accepted': False, 'reason': 'Invalid question'}

        existing = db.scalar(
            select(Answer).where(Answer.participant_id == participant.id, Answer.question_id == question.id)
        )
        if existing:
            logger.info('answer_rejected_duplicate %s', log_ctx)
            return {'accepted': False, 'reason': 'Already answered'}

        # Prefer the runtime state as source of truth for "question is open".
        state = self.compute_state(quiz)
        if state.phase == 'question' and state.question_index is not None:
            current_question = quiz.questions[state.question_index]
            if current_question.id == question.id:
                started_at = quiz.started_at.replace(tzinfo=timezone.utc) if quiz.started_at and quiz.started_at.tzinfo is None else quiz.started_at
                window = self._question_window(quiz, state.question_index)
                if not window:
                    return {'accepted': False, 'reason': 'Question is not open'}
                question_start_offset, _question_end_offset, max_time = window
                question_start = started_at + timedelta(seconds=question_start_offset)
                now = self._now()
                response_seconds = max(0.0, min(max_time, (now - question_start).total_seconds()))
                logger.info(
                    'answer_accept_runtime_state %s',
                    {
                        **log_ctx,
                        'state_phase': state.phase,
                        'state_question_index': state.question_index,
                        'state_question_id': current_question.id,
                        'response_seconds': round(response_seconds, 3),
                    },
                )
                return self._store_answer(db, quiz, participant, question, value, response_seconds)

        started_at = quiz.started_at.replace(tzinfo=timezone.utc) if quiz.started_at and quiz.started_at.tzinfo is None else quiz.started_at
        window = self._question_window(quiz, question_index)
        if not window:
            logger.warning('answer_rejected_invalid_question_index %s', {**log_ctx, 'question_index': question_index})
            return {'accepted': False, 'reason': 'Invalid question'}
        question_start_offset, question_end_offset, max_time = window
        question_start = started_at + timedelta(seconds=question_start_offset)
        question_end = started_at + timedelta(seconds=question_end_offset)
        now = self._now()

        # Small tolerance to absorb transport/scheduling latency at boundary.
        grace_seconds = 0.75
        if now < question_start:
            logger.warning(
                'answer_rejected_before_open %s',
                {
                    **log_ctx,
                    'state_phase': state.phase,
                    'state_question_index': state.question_index,
                    'question_index': question_index,
                    'now': now.isoformat(),
                    'question_start': question_start.isoformat(),
                },
            )
            return {'accepted': False, 'reason': 'Question is not open'}
        if now > question_end + timedelta(seconds=grace_seconds):
            logger.warning(
                'answer_rejected_after_close %s',
                {
                    **log_ctx,
                    'state_phase': state.phase,
                    'state_question_index': state.question_index,
                    'question_index': question_index,
                    'now': now.isoformat(),
                    'question_end': question_end.isoformat(),
                    'grace_seconds': grace_seconds,
                },
            )
            return {'accepted': False, 'reason': 'Question is not open'}

        effective_now = min(now, question_end)
        response_seconds = max(0.0, min(max_time, (effective_now - question_start).total_seconds()))
        logger.info(
            'answer_accept_time_window %s',
            {
                **log_ctx,
                'question_index': question_index,
                'response_seconds': round(response_seconds, 3),
            },
        )
        return self._store_answer(db, quiz, participant, question, value, response_seconds)

    def _store_answer(
        self,
        db: Session,
        quiz: Quiz,
        participant: Participant,
        question: Question,
        value: str,
        response_seconds: float,
    ) -> dict:

        cleaned = value.strip()
        if question.question_type == QuestionType.MULTIPLE_CHOICE:
            normalized = cleaned.upper()
            is_correct = normalized == question.correct_answer.strip().upper()
            stored_value = normalized
        else:
            normalized = cleaned.lower()
            is_correct = normalized == question.correct_answer.strip().lower()
            stored_value = cleaned

        max_time = self._question_time(quiz, question)
        score = self._score(question.max_points, max_time, response_seconds) if is_correct else 0.0
        db.add(
            Answer(
                participant_id=participant.id,
                question_id=question.id,
                value=stored_value,
                is_correct=is_correct,
                response_seconds=response_seconds,
                score=score,
            )
        )
        return {'accepted': True, 'is_correct': is_correct, 'score': score, 'response_seconds': response_seconds}

    def ensure_participant(self, db: Session, quiz: Quiz, user: User) -> Participant:
        emoji = ensure_user_emoji(db, user)
        existing = db.scalar(select(Participant).where(Participant.quiz_id == quiz.id, Participant.user_id == user.id))
        if existing:
            if existing.emoji != emoji:
                existing.emoji = emoji
                db.flush()
            return existing

        participant = Participant(quiz_id=quiz.id, user_id=user.id, emoji=emoji)
        db.add(participant)
        db.flush()
        return participant
