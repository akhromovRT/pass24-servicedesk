from __future__ import annotations

from datetime import datetime, timedelta

import bcrypt
from jose import jwt

from backend.config import settings


def hash_password(password: str) -> str:
    """Хеширует пароль с помощью bcrypt."""
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    """Проверяет совпадение открытого пароля с хешем."""
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def create_access_token(data: dict) -> str:
    """
    Создаёт JWT access-токен.

    В payload добавляется поле ``exp`` с временем истечения,
    определённым в ``settings.access_token_expire_minutes``.
    """
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=settings.access_token_expire_minutes)
    to_encode["exp"] = expire
    return jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)
