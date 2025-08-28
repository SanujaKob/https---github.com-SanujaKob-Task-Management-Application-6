# routers/auth.py
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlmodel import Session, select
from sqlalchemy import or_
from jose import jwt, JWTError

from data.database import get_session as get_db
from models.users import User
from core.security import verify_password, create_access_token, SECRET_KEY, ALGORITHM

router = APIRouter(prefix="/auth", tags=["auth"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

def get_user_by_identifier(db: Session, ident: str) -> User | None:
    stmt = select(User).where(or_(User.username == ident, User.email == ident))
    return db.exec(stmt).first()

def authenticate_user(db: Session, ident: str, password: str) -> User | None:
    user = get_user_by_identifier(db, ident)
    if not user:
        return None
    if not user.password_hash:               # <-- use password_hash
        return None
    try:
        if not verify_password(password, user.password_hash):
            return None
    except Exception:
        # unknown/invalid hash format -> treat as bad creds
        return None
    return user

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    cred_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        sub: str | None = payload.get("sub")
        if sub is None:
            raise cred_exc
    except JWTError:
        raise cred_exc

    user = get_user_by_identifier(db, sub)
    if user is None:
        raise cred_exc
    return user

CurrentUser = get_current_user

@router.post("/login")
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = authenticate_user(db, form.username, form.password)
    if not user:
        raise HTTPException(status_code=400, detail="Incorrect username/email or password")
    token = create_access_token(subject=user.username, extra_claims={"uid": user.id})
    return {"access_token": token, "token_type": "bearer"}
