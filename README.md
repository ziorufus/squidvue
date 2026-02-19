# Quiz Platform (Vue + FastAPI + WebSockets)

This repository contains a full-stack real-time quiz platform with:

- `frontend/`: Vue 3 + Vite + Bootstrap
- `backend/`: FastAPI + SQLite + Google OAuth2 + WebSockets

## Project Structure

- `backend/app/main.py`: FastAPI application, REST routes, websocket endpoint
- `backend/app/services/runtime.py`: quiz timer engine, scoring, rankings, live broadcasts
- `frontend/src/pages/AdminPage.vue`: admin + privileged quiz management UI
- `frontend/src/pages/QuizPlayerPage.vue`: student mobile UI
- `frontend/src/pages/QuestionScreenPage.vue`: question projector/screen UI

## Environment Variables

Backend (`backend/.env` from `backend/.env.example`):

- `ADMIN_EMAIL`
- `DEFAULT_QUESTION_TIME_MULTIPLE_CHOICE` (fallback: `DEFAULT_QUESTION_TIME`)
- `DEFAULT_QUESTION_TIME_OPEN` (fallback: `DEFAULT_QUESTION_TIME`)
- `DEFAULT_COUNTDOWN_TIME`
- `DEFAULT_MAX_POINTS`
- `ALLOWED_EMOJIS` (space-separated list of allowed emojis, globally assigned to users)
- `GOOGLE_CLIENT_ID`
- `GOOGLE_CLIENT_SECRET`
- `SECRET_KEY`
- `BASE_URL`
- `DATABASE_URL`
- `REDIS_URL` (optional; enables cross-worker pub/sub and runtime leader lock)
- `ACCESS_TOKEN_EXPIRE_MINUTES`

Frontend (`frontend/.env` from `frontend/.env.example`):

- `VITE_API_BASE`
- `VITE_GOOGLE_CLIENT_ID`

## Run Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

## Run Frontend

```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```

## Main Routes

- Frontend home/login: `http://localhost:5173/`
- Student: `http://localhost:5173/quiz/CODE`
- Question screen: `http://localhost:5173/questions/CODE`
- Global ranking screen: `http://localhost:5173/ranking`
- Admin panel: `http://localhost:5173/admin`

## Notes

- Students are expected on mobile/tablet; on `md` and larger screens, answer controls are hidden.
- Emoji assignment is global and persistent per user across all quizzes.
- Stopping a running quiz resets quiz results.
- Finished quizzes require reset before they can run again.
