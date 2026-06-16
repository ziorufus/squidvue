from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.core.db import get_db
from app.models import User, UserRole
from app.schemas.users import PrivilegedUserCreate


router = APIRouter(prefix='/api/users', tags=['users'])


@router.get('/privileged')
def list_privileged(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    users = db.scalars(select(User).where(User.role == UserRole.PRIVILEGED).order_by(User.email.asc())).all()
    return [{'id': u.id, 'email': u.email, 'name': u.name, 'role': u.role.value} for u in users]


@router.post('/privileged')
def create_privileged(payload: PrivilegedUserCreate, _: User = Depends(require_admin), db: Session = Depends(get_db)):
    existing = db.scalar(select(User).where(User.email == payload.email.lower()))
    if existing:
        existing.role = UserRole.PRIVILEGED
        db.commit()
        return {'id': existing.id, 'email': existing.email, 'name': existing.name, 'role': existing.role.value}

    user = User(google_sub=f'pending:{payload.email.lower()}', email=payload.email.lower(), name=payload.email.lower(), role=UserRole.PRIVILEGED)
    db.add(user)
    db.commit()
    db.refresh(user)
    return {'id': user.id, 'email': user.email, 'name': user.name, 'role': user.role.value}


@router.delete('/privileged/{user_id}')
def delete_privileged(user_id: int, _: User = Depends(require_admin), db: Session = Depends(get_db)):
    user = db.get(User, user_id)
    if not user or user.role != UserRole.PRIVILEGED:
        raise HTTPException(status_code=404, detail='Privileged user not found')
    db.delete(user)
    db.commit()
    return {'ok': True}
