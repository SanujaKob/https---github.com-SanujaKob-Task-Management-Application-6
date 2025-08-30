# scripts/seed_admin.py
import os, sys
from sqlmodel import Session, select
from data.database import engine
from models.users import User, Role
from core.security import get_password_hash

def main(username: str, email: str, password: str, full_name: str = "Administrator"):
    with Session(engine) as s:
        existing = s.exec(select(User).where(User.username == username)).first()
        if existing:
            print("[INFO] Admin already exists:", existing.username)
            return
        u = User(
            username=username,
            email=email,
            full_name=full_name,
            role=Role.admin if hasattr(Role, "admin") else "admin",
            hashed_password=get_password_hash(password),
        )
        s.add(u)
        s.commit()
        s.refresh(u)
        print("[OK] Seeded admin:", u.id, u.username)

if __name__ == "__main__":
    # Usage: python -m scripts.seed_admin admin admin@example.com StrongPass123
    if len(sys.argv) < 4:
        print("Usage: python -m scripts.seed_admin <username> <email> <password> [full_name]")
        sys.exit(1)
    main(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4] if len(sys.argv) > 4 else "Administrator")
