# scripts/peek_users.py
import sys, os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from sqlmodel import Session, select
from data.database import engine
from models.tasks import Task         # ✅ ensure Task is imported
from models.users import User         # ✅ then import User

with Session(engine) as s:
    users = s.exec(select(User)).all()
    for u in users:
        print(u.id, u.username, u.email, getattr(u, "role", None), bool(getattr(u, "hashed_password", "")))
