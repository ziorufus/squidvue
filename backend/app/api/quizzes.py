from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import delete, select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_user, require_privileged
from app.core.config import settings
from app.core.db import get_db
from app.models import Answer, OpenDraft, Participant, Question, QuestionType, Quiz, QuizStatus, User, UserRole
from app.schemas.quizzes import QuizIn
from app.services.codegen import generate_code


router = APIRouter(prefix='/api/quizzes', tags=['quizzes'])


def can_edit(user: User, quiz: Quiz) -> bool:
    return user.role == UserRole.ADMIN or quiz.owner_id == user.id


@router.get('')
def list_quizzes(current_user: User = Depends(require_privileged), db: Session = Depends(get_db)):
    stmt = select(Quiz).options(selectinload(Quiz.questions)).order_by(Quiz.created_at.desc())
    if current_user.role != UserRole.ADMIN:
        stmt = stmt.where(Quiz.owner_id == current_user.id)
    quizzes = db.scalars(stmt).all()
    return [
        {
            'id': q.id,
            'code': q.code,
            'title': q.title,
            'question_time_multiple_choice': q.question_time_multiple_choice,
            'question_time_open': q.question_time_open,
            'countdown_time': q.countdown_time,
            'status': q.status.value,
            'question_count': len(q.questions),
        }
        for q in quizzes
    ]


@router.get('/defaults')
def defaults(_: User = Depends(require_privileged)):
    return {
        'default_question_time_multiple_choice': settings.default_question_time_multiple_choice,
        'default_question_time_open': settings.default_question_time_open,
        'default_countdown_time': settings.default_countdown_time,
        'default_max_points': settings.default_max_points,
    }


@router.get('/code/{code}')
def get_quiz_by_code(code: str, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    quiz = db.scalar(select(Quiz).options(selectinload(Quiz.questions)).where(Quiz.code == code.upper()))
    if not quiz:
        raise HTTPException(status_code=404, detail='Quiz not found')
    quiz.questions.sort(key=lambda q: q.position)
    return {
        'id': quiz.id,
        'code': quiz.code,
        'title': quiz.title,
        'question_time_multiple_choice': quiz.question_time_multiple_choice,
        'question_time_open': quiz.question_time_open,
        'countdown_time': quiz.countdown_time,
        'status': quiz.status.value,
        'questions': [
            {
                'id': x.id,
                'position': x.position,
                'text': x.text,
                'question_type': x.question_type.value,
                'option_a': x.option_a,
                'option_b': x.option_b,
                'option_c': x.option_c,
                'option_d': x.option_d,
                'option_e': x.option_e,
                'correct_answer': x.correct_answer,
                'max_points': x.max_points,
            }
            for x in quiz.questions
        ],
    }


@router.post('')
def create_quiz(payload: QuizIn, current_user: User = Depends(require_privileged), db: Session = Depends(get_db)):
    if not payload.questions:
        raise HTTPException(status_code=400, detail='At least one question is required')

    code = generate_code()
    while db.scalar(select(Quiz).where(Quiz.code == code)):
        code = generate_code()

    quiz = Quiz(
        code=code,
        title=payload.title,
        question_time_multiple_choice=payload.question_time_multiple_choice,
        question_time_open=payload.question_time_open,
        countdown_time=payload.countdown_time,
        emoji_pool='',
        status=QuizStatus.READY,
        owner_id=current_user.id,
    )
    db.add(quiz)
    db.flush()

    for q in payload.questions:
        db.add(
            Question(
                quiz_id=quiz.id,
                position=q.position,
                text=q.text,
                question_type=QuestionType(q.question_type),
                option_a=q.option_a,
                option_b=q.option_b,
                option_c=q.option_c,
                option_d=q.option_d,
                option_e=q.option_e,
                correct_answer=q.correct_answer,
                max_points=q.max_points,
            )
        )

    db.commit()
    db.refresh(quiz)
    return {'id': quiz.id, 'code': quiz.code, 'status': quiz.status.value}


@router.put('/{quiz_id}')
def update_quiz(quiz_id: int, payload: QuizIn, current_user: User = Depends(require_privileged), db: Session = Depends(get_db)):
    quiz = db.scalar(select(Quiz).options(selectinload(Quiz.questions)).where(Quiz.id == quiz_id))
    if not quiz:
        raise HTTPException(status_code=404, detail='Quiz not found')
    if not can_edit(current_user, quiz):
        raise HTTPException(status_code=403, detail='Not allowed')
    if quiz.status == QuizStatus.RUNNING:
        raise HTTPException(status_code=400, detail='Cannot edit a running quiz')

    quiz.title = payload.title
    quiz.question_time_multiple_choice = payload.question_time_multiple_choice
    quiz.question_time_open = payload.question_time_open
    quiz.countdown_time = payload.countdown_time
    quiz.emoji_pool = ''
    quiz.status = QuizStatus.READY

    db.execute(delete(Question).where(Question.quiz_id == quiz.id))
    for q in payload.questions:
        db.add(
            Question(
                quiz_id=quiz.id,
                position=q.position,
                text=q.text,
                question_type=QuestionType(q.question_type),
                option_a=q.option_a,
                option_b=q.option_b,
                option_c=q.option_c,
                option_d=q.option_d,
                option_e=q.option_e,
                correct_answer=q.correct_answer,
                max_points=q.max_points,
            )
        )

    db.commit()
    return {'ok': True}


@router.delete('/{quiz_id}')
def delete_quiz(quiz_id: int, current_user: User = Depends(require_privileged), db: Session = Depends(get_db)):
    quiz = db.get(Quiz, quiz_id)
    if not quiz:
        raise HTTPException(status_code=404, detail='Quiz not found')
    if not can_edit(current_user, quiz):
        raise HTTPException(status_code=403, detail='Not allowed')
    db.delete(quiz)
    db.commit()
    return {'ok': True}


@router.post('/{quiz_id}/start')
async def start_quiz(quiz_id: int, request: Request, current_user: User = Depends(require_privileged), db: Session = Depends(get_db)):
    quiz = db.scalar(select(Quiz).options(selectinload(Quiz.questions)).where(Quiz.id == quiz_id))
    if not quiz:
        raise HTTPException(status_code=404, detail='Quiz not found')
    if not can_edit(current_user, quiz):
        raise HTTPException(status_code=403, detail='Not allowed')
    if quiz.status == QuizStatus.FINISHED:
        raise HTTPException(status_code=400, detail='Finished quiz must be reset before running again')
    if quiz.status == QuizStatus.RUNNING:
        return {'ok': True, 'status': quiz.status.value}

    quiz.status = QuizStatus.RUNNING
    quiz.started_at = datetime.utcnow()
    quiz.stopped_at = None
    db.commit()

    runtime = request.app.state.runtime
    await runtime.broadcast_quiz_state(db, quiz)
    return {'ok': True, 'status': quiz.status.value}


@router.post('/{quiz_id}/stop')
async def stop_quiz(quiz_id: int, request: Request, current_user: User = Depends(require_privileged), db: Session = Depends(get_db)):
    quiz = db.scalar(select(Quiz).options(selectinload(Quiz.questions)).where(Quiz.id == quiz_id))
    if not quiz:
        raise HTTPException(status_code=404, detail='Quiz not found')
    if not can_edit(current_user, quiz):
        raise HTTPException(status_code=403, detail='Not allowed')

    quiz.status = QuizStatus.READY
    quiz.started_at = None
    quiz.stopped_at = datetime.utcnow()

    participant_ids = db.scalars(select(Participant.id).where(Participant.quiz_id == quiz.id)).all()
    if participant_ids:
        db.execute(delete(Answer).where(Answer.participant_id.in_(participant_ids)))
        db.execute(delete(OpenDraft).where(OpenDraft.participant_id.in_(participant_ids)))
    db.execute(delete(Participant).where(Participant.quiz_id == quiz.id))
    db.commit()

    runtime = request.app.state.runtime
    await runtime.broadcast_quiz_state(db, quiz)
    return {'ok': True, 'status': quiz.status.value}


@router.post('/{quiz_id}/reset')
async def reset_quiz(quiz_id: int, request: Request, current_user: User = Depends(require_privileged), db: Session = Depends(get_db)):
    quiz = db.get(Quiz, quiz_id)
    if not quiz:
        raise HTTPException(status_code=404, detail='Quiz not found')
    if not can_edit(current_user, quiz):
        raise HTTPException(status_code=403, detail='Not allowed')

    participant_ids = db.scalars(select(Participant.id).where(Participant.quiz_id == quiz.id)).all()
    if participant_ids:
        db.execute(delete(Answer).where(Answer.participant_id.in_(participant_ids)))
        db.execute(delete(OpenDraft).where(OpenDraft.participant_id.in_(participant_ids)))
    db.execute(delete(Participant).where(Participant.quiz_id == quiz.id))

    quiz.status = QuizStatus.READY
    quiz.started_at = None
    quiz.stopped_at = None
    db.commit()

    runtime = request.app.state.runtime
    await runtime.broadcast_quiz_state(db, quiz)
    return {'ok': True}
