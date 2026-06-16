from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.db import get_db
from app.models import User, UserRole
from app.schemas.auth import AuthToken, GoogleLoginRequest
from app.services.emoji import ensure_user_emoji
from app.services.security import create_access_token, verify_google_token


router = APIRouter(prefix='/api/auth', tags=['auth'])


@router.post('/google', response_model=AuthToken)
def login_google(payload: GoogleLoginRequest, db: Session = Depends(get_db)):
    info = verify_google_token(payload.credential)
    if not info.get('email'):
        raise HTTPException(status_code=400, detail='Google token did not return email')

    user = db.scalar(select(User).where(User.google_sub == info['sub']))
    if not user:
        role = UserRole.STUDENT
        if info['email'].lower() == settings.admin_email.lower():
            role = UserRole.ADMIN
        existing_privileged = db.scalar(
            select(User).where(User.email == info['email'].lower(), User.role == UserRole.PRIVILEGED)
        )
        if existing_privileged:
            existing_privileged.google_sub = info['sub']
            existing_privileged.name = info['name']
            user = existing_privileged
        else:
            user = User(google_sub=info['sub'], email=info['email'].lower(), name=info['name'], role=role)
            db.add(user)
        db.commit()
        db.refresh(user)
    else:
        user.email = info['email'].lower()
        user.name = info['name']
        if user.email == settings.admin_email.lower():
            user.role = UserRole.ADMIN
        db.commit()

    try:
        ensure_user_emoji(db, user)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    db.commit()
    db.refresh(user)

    token = create_access_token({'user_id': user.id, 'role': user.role.value})
    return AuthToken(access_token=token, role=user.role.value, email=user.email, name=user.name)


@router.get('/me')
def me(current_user: User = Depends(get_current_user)):
    return {'id': current_user.id, 'email': current_user.email, 'name': current_user.name, 'role': current_user.role.value}
