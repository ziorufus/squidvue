from collections import defaultdict
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
        question_time=payload.question_time_multiple_choice,
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
                max_points=q.max_points or settings.default_max_points,
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
    quiz.question_time = payload.question_time_multiple_choice
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
                max_points=q.max_points or settings.default_max_points,
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


@router.get('/{quiz_id}/detail')
def quiz_detail(quiz_id: int, current_user: User = Depends(require_privileged), db: Session = Depends(get_db)):
    quiz = db.scalar(select(Quiz).options(selectinload(Quiz.questions)).where(Quiz.id == quiz_id))
    if not quiz:
        raise HTTPException(status_code=404, detail='Quiz not found')
    if not can_edit(current_user, quiz):
        raise HTTPException(status_code=403, detail='Not allowed')

    questions = sorted(quiz.questions, key=lambda q: q.position)

    participants = db.execute(
        select(Participant.id, Participant.emoji).where(Participant.quiz_id == quiz_id)
    ).all()
    participant_emojis = {p.id: p.emoji for p in participants}
    all_participant_ids = set(participant_emojis.keys())

    answers_by_question: dict[int, list] = defaultdict(list)
    if questions:
        for ans in db.execute(
            select(Answer.question_id, Answer.participant_id, Answer.value)
            .where(Answer.question_id.in_([q.id for q in questions]))
        ).all():
            if ans.participant_id in participant_emojis:
                answers_by_question[ans.question_id].append((ans.participant_id, ans.value))

    result_questions = []
    for question in questions:
        qanswers = answers_by_question[question.id]
        answered_pids = {pid for pid, _ in qanswers}
        no_answer_emojis = sorted(participant_emojis[pid] for pid in all_participant_ids if pid not in answered_pids)

        if question.question_type == QuestionType.MULTIPLE_CHOICE:
            option_groups: dict[str, list] = defaultdict(list)
            for pid, value in qanswers:
                option_groups[(value or '').upper()].append(participant_emojis[pid])

            choices = []
            for letter in ['A', 'B', 'C', 'D', 'E']:
                text = getattr(question, f'option_{letter.lower()}')
                if text is None:
                    continue
                emojis = sorted(option_groups.get(letter, []))
                choices.append({
                    'option': letter,
                    'text': text,
                    'count': len(emojis),
                    'emojis': emojis,
                    'is_correct': letter == (question.correct_answer or '').upper(),
                })

            if no_answer_emojis:
                choices.append({'option': 'no_answer', 'text': None, 'count': len(no_answer_emojis), 'emojis': no_answer_emojis, 'is_correct': False})

            stats = {'type': 'multiple_choice', 'choices': choices}

        else:
            value_groups: dict[str, list] = defaultdict(list)
            for pid, value in qanswers:
                value_groups[value].append(participant_emojis[pid])

            stats = {
                'type': 'open',
                'answers': sorted(
                    [{'value': val, 'count': len(emojis), 'emojis': sorted(emojis)} for val, emojis in value_groups.items()],
                    key=lambda x: -x['count'],
                ),
            }

        result_questions.append({
            'id': question.id,
            'position': question.position,
            'text': question.text,
            'question_type': question.question_type.value,
            'correct_answer': question.correct_answer,
            'max_points': question.max_points,
            'options': {
                letter: getattr(question, f'option_{letter.lower()}')
                for letter in ['A', 'B', 'C', 'D', 'E']
                if getattr(question, f'option_{letter.lower()}') is not None
            },
            'stats': stats,
        })

    return {
        'quiz': {
            'id': quiz.id,
            'code': quiz.code,
            'title': quiz.title,
            'status': quiz.status.value,
            'started_at': quiz.started_at.isoformat() if quiz.started_at else None,
            'stopped_at': quiz.stopped_at.isoformat() if quiz.stopped_at else None,
        },
        'participants_count': len(participant_emojis),
        'questions': result_questions,
    }


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
