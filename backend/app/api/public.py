from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_user
from app.core.db import get_db
from app.models import Answer, Participant, Quiz, User


router = APIRouter(prefix='/api/public', tags=['public'])


@router.get('/quiz/{code}')
def quiz_public_info(code: str, request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    quiz = db.scalar(select(Quiz).options(selectinload(Quiz.questions)).where(Quiz.code == code.upper()))
    if not quiz:
        raise HTTPException(status_code=404, detail='Quiz not found')

    runtime = request.app.state.runtime
    try:
        participant = runtime.ensure_participant(db, quiz, user)
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    db.commit()

    quiz.questions.sort(key=lambda q: q.position)
    state = runtime.compute_state(quiz)

    total_score = db.scalar(select(func.sum(Answer.score)).where(Answer.participant_id == participant.id))

    return {
        'quiz': {
            'id': quiz.id,
            'code': quiz.code,
            'title': quiz.title,
            'status': quiz.status.value,
            'question_time': quiz.question_time,
            'countdown_time': quiz.countdown_time,
            'total_questions': len(quiz.questions),
        },
        'participant': {
            'id': participant.id,
            'emoji': participant.emoji,
            'score': float(total_score or 0),
        },
        'state': {
            'phase': state.phase,
            'remaining_seconds': state.remaining_seconds,
            'question_index': state.question_index,
        },
    }


@router.get('/quiz/{code}/ranking')
def ranking(code: str, request: Request, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    quiz = db.scalar(select(Quiz).where(Quiz.code == code.upper()))
    if not quiz:
        raise HTTPException(status_code=404, detail='Quiz not found')
    runtime = request.app.state.runtime
    return {
        'quiz': runtime.ranking_for_quiz(db, quiz.id),
        'global': runtime.global_ranking(db),
    }


@router.get('/ranking/global')
def global_ranking(request: Request, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    runtime = request.app.state.runtime
    return {
        'global': runtime.global_ranking(db),
    }
