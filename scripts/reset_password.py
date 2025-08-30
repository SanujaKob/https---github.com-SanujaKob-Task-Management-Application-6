# scripts/reset_password.py
import sys, os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from sqlmodel import Session, select
from data.database import engine

# ✅ Ensure related models are imported BEFORE using User
from models.tasks import Task          # <-- important
from models.users import User          # your User model
from core.security import get_password_hash

def main(identifier: str, new_password: str):
    with Session(engine) as s:
        q = select(User).where((User.username == identifier) | (User.email == identifier))
        u = s.exec(q).first()
        if not u:
            print("User not found")
            return
        # ✅ correct column name
        u.password_hash = get_password_hash(new_password)
        s.add(u)
        s.commit()
        print("Password reset for:", u.username)

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python -m scripts.reset_password <username_or_email> <new_password>")
        sys.exit(1)
    main(sys.argv[1], sys.argv[2])
