from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.models import User, UserRole
from app.services.security import decode_access_token


bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Missing credentials')
    try:
        payload = decode_access_token(credentials.credentials)
        user_id = int(payload.get('user_id'))
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Invalid token')
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='User not found')
    return user


def require_privileged(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role not in {UserRole.ADMIN, UserRole.PRIVILEGED}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Not authorized')
    return current_user


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Admin required')
    return current_user
