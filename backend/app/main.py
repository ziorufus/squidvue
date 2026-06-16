from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api import auth, public, quizzes, users
from app.core.config import settings
from app.core.db import SessionLocal, ensure_runtime_schema, initialize_schema
from app.models import Question, Quiz, User, UserRole
from app.services.runtime import QuizRuntime
from app.services.security import decode_access_token


runtime = QuizRuntime(SessionLocal, settings.redis_url)


@asynccontextmanager
async def lifespan(app: FastAPI):
    initialize_schema()
    ensure_runtime_schema()
    app.state.runtime = runtime
    await runtime.start()
    yield
    await runtime.stop()


app = FastAPI(title='Quiz Platform', lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.base_url, 'http://localhost:5173', 'http://127.0.0.1:5173'],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(quizzes.router)
app.include_router(public.router)


@app.get('/health')
def health():
    return {'ok': True}


def _load_quiz_fresh(db, code: str):
    stmt = (
        select(Quiz)
        .options(selectinload(Quiz.questions))
        .where(Quiz.code == code)
        .execution_options(populate_existing=True)
    )
    return db.scalar(stmt)


def _resolve_user(token: str | None):
    if not token:
        return None
    try:
        payload = decode_access_token(token)
        user_id = int(payload.get('user_id'))
    except (JWTError, ValueError, TypeError):
        return None

    db = SessionLocal()
    try:
        return db.get(User, user_id)
    finally:
        db.close()


@app.websocket('/ws/quiz/{code}/{channel}')
async def quiz_socket(websocket: WebSocket, code: str, channel: str):
    token = websocket.query_params.get('token')
    user = _resolve_user(token)

    code = code.upper()
    if channel not in {'student', 'admin', 'screen'}:
        await websocket.close(code=1008)
        return

    if channel in {'admin', 'screen'} and (not user or user.role not in {UserRole.ADMIN, UserRole.PRIVILEGED}):
        await websocket.close(code=1008)
        return

    room = f'quiz:{code}:{channel}'
    await runtime.ws.connect(room, websocket)

    db = SessionLocal()
    try:
        quiz = _load_quiz_fresh(db, code)
        if not quiz:
            await websocket.send_json({'type': 'error', 'message': 'Quiz not found'})
            await websocket.close(code=1008)
            return

        participant = None
        if channel == 'student':
            if not user:
                await websocket.send_json({'type': 'error', 'message': 'Auth required'})
                await websocket.close(code=1008)
                return
            try:
                participant = runtime.ensure_participant(db, quiz, user)
            except (ValueError, RuntimeError) as exc:
                await websocket.send_json({'type': 'error', 'message': str(exc)})
                await websocket.close(code=1008)
                return
            db.commit()

        await runtime.broadcast_quiz_state(db, quiz)

        while True:
            msg = await websocket.receive_json()
            action = msg.get('action')

            db.expire_all()
            quiz = _load_quiz_fresh(db, code)
            if not quiz:
                await websocket.send_json({'type': 'error', 'message': 'Quiz not found'})
                continue
            quiz.questions.sort(key=lambda q: q.position)

            if action == 'submit_answer' and participant:
                qid = int(msg.get('question_id'))
                value = str(msg.get('value', ''))
                question = db.get(Question, qid)
                if not question or question.quiz_id != quiz.id:
                    await websocket.send_json({'type': 'answer_ack', 'accepted': False, 'reason': 'Invalid question'})
                    continue
                result = runtime.submit_answer(db, quiz, participant, question, value)
                db.commit()
                await websocket.send_json({'type': 'answer_ack', **result})
                await runtime.broadcast_quiz_state(db, quiz, include_stats=False)

            elif action == 'save_open_draft' and participant:
                qid = int(msg.get('question_id'))
                value = str(msg.get('value', ''))
                question = db.get(Question, qid)
                if question and question.quiz_id == quiz.id:
                    runtime.upsert_open_draft(db, participant.id, qid, value)
                    db.commit()
            elif action == 'ping':
                await websocket.send_json({'type': 'pong'})

    except WebSocketDisconnect:
        runtime.ws.disconnect(room, websocket)
    finally:
        db.close()
