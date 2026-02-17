import random

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import User


def allowed_emojis() -> list[str]:
    return [x for x in settings.allowed_emojis.split() if x.strip()]


def ensure_user_emoji(db: Session, user: User) -> str:
    if user.emoji:
        return user.emoji

    pool = allowed_emojis()
    if not pool:
        raise ValueError('ALLOWED_EMOJIS is empty')

    max_attempts = len(pool) + 3
    for _ in range(max_attempts):
        used = set(db.scalars(select(User.emoji).where(User.emoji.is_not(None))).all())
        available = [emoji for emoji in pool if emoji not in used]
        if not available:
            raise ValueError('No available emojis left in ALLOWED_EMOJIS')

        candidate = random.choice(available)
        try:
            with db.begin_nested():
                user.emoji = candidate
                db.flush()
                return candidate
        except IntegrityError:
            db.expire_all()
            continue

    raise RuntimeError('Could not assign a unique emoji, please retry')
