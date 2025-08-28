# data/database.py

from sqlmodel import SQLModel, create_engine, Session
import os

# ---------------------------
# Database configuration
# ---------------------------
DB_FILE = os.path.join(os.path.dirname(__file__), "abacus.db")
DATABASE_URL = f"sqlite:///{DB_FILE}"

# echo=True will log SQL statements to stdout (helpful for debugging)
engine = create_engine(DATABASE_URL, echo=True)


def init_db() -> None:
    """
    Initialize the database.

    Creates all tables defined in SQLModel metadata if they don't already exist.
    """
    import models.tasks    # register Task first
    import models.users    # then User (which references Task)

    SQLModel.metadata.create_all(engine)


def get_session() -> Session:
    """
    Dependency for FastAPI routes.

    Yields a database session that is automatically closed afterwards.
    """
    with Session(engine) as session:
        yield session

# Backwards-compat for routers that expect get_db()
get_db = get_session
