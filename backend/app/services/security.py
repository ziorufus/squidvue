from datetime import datetime, timedelta, timezone

from google.auth.transport import requests
from google.oauth2 import id_token
from jose import jwt

from app.core.config import settings


ALGORITHM = 'HS256'


def verify_google_token(credential: str) -> dict:
    info = id_token.verify_oauth2_token(credential, requests.Request(), settings.google_client_id)
    return {
        'sub': info.get('sub', ''),
        'email': info.get('email', '').lower(),
        'name': info.get('name', info.get('email', 'Unknown')),
    }


def create_access_token(payload: dict) -> str:
    now = datetime.now(timezone.utc)
    data = payload.copy()
    data['exp'] = now + timedelta(minutes=settings.access_token_expire_minutes)
    data['iat'] = now
    return jwt.encode(data, settings.secret_key, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict:
    return jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
