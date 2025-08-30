# scripts/promote_user.py
import sys, os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from sqlmodel import Session, select
from data.database import engine
from models.tasks import Task        # ensure mappers load
from models.users import User, Role
from core.security import get_password_hash

def main(identifier: str, new_password: str):
    with Session(engine) as s:
        q = select(User).where((User.username == identifier) | (User.email == identifier))
        u = s.exec(q).first()
        if not u:
            print("User not found")
            return
        # promote + set password
        u.role = Role.admin if hasattr(Role, "admin") else "admin"
        u.password_hash = get_password_hash(new_password)
        s.add(u)
        s.commit()
        s.refresh(u)
        print(f"Promoted {u.username} to admin and reset password")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python -m scripts.promote_user <username_or_email> <new_password>")
        raise SystemExit(1)
    main(sys.argv[1], sys.argv[2])
