import os
from datetime import timedelta

SECRET_KEY = os.getenv("ABACUS_SECRET_KEY", "change-this-in-production-please")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ABACUS_ACCESS_TOKEN_MINUTES", "60"))

def access_token_delta() -> timedelta:
    return timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
