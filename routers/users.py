# routers/users.py

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from data.database import get_session
from models.users import User, UserCreate, UserRead, UserUpdate, Role

# ✅ use the dependency function directly
from routers.auth import get_current_user
from core.security import get_password_hash, verify_password

router = APIRouter(prefix="/users", tags=["users"])

# ---------------------------
# Helpers
# ---------------------------
def to_user_read(u: User) -> UserRead:
    return UserRead.model_validate(u)

def coerce_role(value: Optional[object]) -> Optional[Role]:
    if value is None:
        return None
    if isinstance(value, Role):
        return value
    # accept str/int -> Role, otherwise raise
    return Role(value)

# ---------------------------
# CRUD Endpoints
# ---------------------------
@router.post("", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def create_user(payload: UserCreate, session: Session = Depends(get_session)):
    # Uniqueness checks
    if session.exec(select(User).where(User.username == payload.username)).first():
        raise HTTPException(status_code=400, detail="Username already exists")
    if session.exec(select(User).where(User.email == payload.email)).first():
        raise HTTPException(status_code=400, detail="Email already exists")

    user = User(
        username=payload.username,
        email=payload.email,
        full_name=payload.full_name,
        role=coerce_role(getattr(payload, "role", None)),
        # ✅ hash password into the correct column name used by your model
        # Change to password_hash if and only if your model column is named that way.
        hashed_password=get_password_hash(payload.password),
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return to_user_read(user)

@router.get("", response_model=List[UserRead])
def list_users(session: Session = Depends(get_session), _=Depends(get_current_user)):
    users = session.exec(select(User)).all()
    return [to_user_read(u) for u in users]

# ---------------------------
# Me (current user) Endpoints  ← keep these BEFORE "/{user_id}"
# ---------------------------
@router.get("/me", response_model=UserRead)
def get_me(user=Depends(get_current_user)):
    return to_user_read(user)

@router.patch("/me", response_model=UserRead)
def update_me(
    payload: dict,
    session: Session = Depends(get_session),
    user=Depends(get_current_user),
):
    email = payload.get("email")
    full_name = payload.get("full_name")

    if email and email != user.email:
        exists = session.exec(select(User).where(User.email == email)).first()
        if exists and exists.id != user.id:
            raise HTTPException(status_code=400, detail="Email already exists")
        user.email = email

    if full_name is not None:
        user.full_name = full_name

    session.add(user)
    session.commit()
    session.refresh(user)
    return to_user_read(user)

@router.patch("/me/password")
def change_my_password(
    payload: dict,
    session: Session = Depends(get_session),
    user=Depends(get_current_user),
):
    current_password = payload.get("current_password")
    new_password = payload.get("new_password")

    if not new_password:
        raise HTTPException(status_code=400, detail="New password required")
    # ✅ verify against the correct field on the model
    if not current_password or not verify_password(current_password, getattr(user, "hashed_password", "") or ""):
        raise HTTPException(status_code=400, detail="Current password is incorrect")

    # ✅ write back to the correct field
    user.hashed_password = get_password_hash(new_password)
    session.add(user)
    session.commit()
    return {"ok": True}

# ---------------------------
# User by ID (place AFTER /me routes)
# ---------------------------
@router.get("/{user_id}", response_model=UserRead)
def get_user(user_id: int, session: Session = Depends(get_session), _=Depends(get_current_user)):
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return to_user_read(user)

@router.patch("/{user_id}", response_model=UserRead)
def update_user(user_id: int, payload: UserUpdate, session: Session = Depends(get_session), _=Depends(get_current_user)):
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    data = payload.model_dump(exclude_unset=True)

    if "username" in data:
        exists = session.exec(
            select(User).where(User.username == data["username"], User.id != user.id)
        ).first()
        if exists:
            raise HTTPException(status_code=400, detail="Username already exists")
        user.username = data["username"]

    if "email" in data:
        exists = session.exec(
            select(User).where(User.email == data["email"], User.id != user.id)
        ).first()
        if exists:
            raise HTTPException(status_code=400, detail="Email already exists")
        user.email = data["email"]

    if "full_name" in data:
        user.full_name = data["full_name"]

    if "role" in data and data["role"] is not None:
        user.role = coerce_role(data["role"])

    if "password" in data and data["password"] is not None:
        # ✅ hash on update into the correct column
        user.hashed_password = get_password_hash(data["password"])

    session.add(user)
    session.commit()
    session.refresh(user)
    return to_user_read(user)

@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(user_id: int, session: Session = Depends(get_session), _=Depends(get_current_user)):
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    session.delete(user)
    session.commit()
    return None
