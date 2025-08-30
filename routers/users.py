# routers/users.py
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select
from sqlalchemy import or_

from data.database import get_session
from models.users import User, UserCreate, UserRead, UserUpdate, Role
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
    return Role(value)

def is_admin(user: User) -> bool:
    # works whether Role is an Enum or plain strings
    return getattr(user, "role", None) == (Role.admin if hasattr(Role, "admin") else "admin")

def resolve_user(session: Session, ref: str) -> Optional[User]:
    """
    Resolve a user by many possible identifiers:
      - primary key as-is (supports str/UUID PKs)
      - integer PK (if ref is digits)
      - id/public_id/username/email equality
    """
    # 0) Try PK as-is (covers string/UUID primary keys)
    u = session.get(User, ref)
    if u:
        return u

    # 1) If numeric-looking, try integer PK
    if isinstance(ref, str) and ref.isdigit():
        u = session.get(User, int(ref))
        if u:
            return u

    # 2) Fallbacks over likely-unique columns
    preds = []
    if hasattr(User, "id"):
        preds.append(User.id == ref)          # string PKs matched via WHERE
    if hasattr(User, "public_id"):
        preds.append(User.public_id == ref)
    if hasattr(User, "username"):
        preds.append(User.username == ref)
    if hasattr(User, "email"):
        preds.append(User.email == ref)       # keep if emails are unique

    if not preds:
        return None

    return session.exec(select(User).where(or_(*preds))).first()

# ---------------------------
# CRUD Endpoints
# ---------------------------
@router.post("", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreate,
    session: Session = Depends(get_session),
    current=Depends(get_current_user),  # kept; bypassed for bootstrap
):
    # Bootstrap: if there are no users yet, allow creation without admin and force admin role
    first_exists = session.exec(select(User.id).limit(1)).first() is not None
    is_bootstrap = not first_exists

    if not is_bootstrap:
        if not is_admin(current):
            raise HTTPException(status_code=403, detail="Admin privileges required")

    # Uniqueness checks
    if session.exec(select(User).where(User.username == payload.username)).first():
        raise HTTPException(status_code=400, detail="Username already exists")
    if session.exec(select(User).where(User.email == payload.email)).first():
        raise HTTPException(status_code=400, detail="Email already exists")

    role_value = Role.admin if is_bootstrap else coerce_role(getattr(payload, "role", None))

    user = User(
        username=payload.username,
        email=payload.email,
        full_name=payload.full_name,
        role=role_value,
        password_hash=get_password_hash(payload.password),  # correct column
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
# Me (current user)
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

    if not current_password or not verify_password(current_password, (user.password_hash or "")):
        raise HTTPException(status_code=400, detail="Current password is incorrect")

    user.password_hash = get_password_hash(new_password)
    session.add(user)
    session.commit()
    return {"ok": True}

# ---------------------------
# User by ref (id/public_id/username/email)
# ---------------------------
@router.get("/{user_ref}", response_model=UserRead)
def get_user(user_ref: str, session: Session = Depends(get_session), _=Depends(get_current_user)):
    user = resolve_user(session, user_ref)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return to_user_read(user)

@router.api_route("/{user_ref}", methods=["PATCH", "PUT"], response_model=UserRead)
@router.api_route("/{user_ref}/", methods=["PATCH", "PUT"], response_model=UserRead)
def update_user(
    user_ref: str,
    payload: UserUpdate,
    session: Session = Depends(get_session),
    current=Depends(get_current_user),
):
    # Only admins can update *other* users (self edits go via /me)
    if not is_admin(current):
        raise HTTPException(status_code=403, detail="Admin privileges required")

    user = resolve_user(session, user_ref)
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
        user.password_hash = get_password_hash(data["password"])

    session.add(user)
    session.commit()
    session.refresh(user)
    return to_user_read(user)

@router.delete("/{user_ref}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_ref: str,
    session: Session = Depends(get_session),
    current=Depends(get_current_user),
):
    if not is_admin(current):
        raise HTTPException(status_code=403, detail="Admin privileges required")

    user = resolve_user(session, user_ref)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    session.delete(user)
    session.commit()
    return None  # 204
