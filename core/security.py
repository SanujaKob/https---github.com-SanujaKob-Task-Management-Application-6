# core/security.py
from datetime import datetime, timezone, timedelta
from typing import Any, Dict
import os

from jose import jwt
from passlib.context import CryptContext

# ---- Config ----
SECRET_KEY = os.getenv("ABACUS_SECRET_KEY", "change-this-in-production-please")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ABACUS_ACCESS_TOKEN_MINUTES", "60"))

# ---- Password hashing ----
_pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return _pwd.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    return _pwd.hash(password)

# ---- JWT ----
def create_access_token(subject: str, extra_claims: Dict[str, Any] | None = None) -> str:
    now = datetime.now(timezone.utc)
    exp = now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    claims: Dict[str, Any] = {
        "sub": subject,
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
    }
    if extra_claims:
        claims.update(extra_claims)
    return jwt.encode(claims, SECRET_KEY, algorithm=ALGORITHM)
