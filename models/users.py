# models/user.py

from datetime import datetime
from typing import Optional, TYPE_CHECKING, List
from enum import Enum
from sqlmodel import SQLModel, Field, Relationship
from pydantic import EmailStr
from sqlalchemy.orm import Mapped
from models.helper import short_uuid

if TYPE_CHECKING:
    from models.tasks import Task


# ---------------------------
# Enumerations
# ---------------------------
class Role(str, Enum):
    """
    Enumeration of user roles within the system.

    Values:
        - admin:    Full access to all resources
        - manager:  Elevated access to oversee tasks/users
        - employee: Standard role for regular task assignees
    """
    admin = "admin"
    manager = "manager"
    employee = "employee"


# ---------------------------
# USER MODELS
# ---------------------------
class UserBase(SQLModel):
    """
    Shared base schema for users.

    Attributes:
        username:   Unique short name for login
        email:      Email address of the user
        full_name:  Optional full name
        role:       User role (admin, manager, employee)
    """
    username: str
    email: EmailStr
    full_name: Optional[str] = None
    role: Role = Role.employee

    model_config = {"from_attributes": True}


class User(UserBase, table=True):
    """
    Database model for a user.

    Represents the actual 'users' table in SQLite.
    Extends UserBase by adding:
        - id:           Unique 5-character string ID
        - password_hash: Placeholder for password hashing
        - created_at:   Timestamp when the user was created
        - updated_at:   Timestamp when the user was last updated
        - tasks:        Relationship to tasks assigned to this user
    """

    __tablename__ = "users"  # ← explicit table name

    id: str = Field(default_factory=short_uuid, primary_key=True, index=True)
    password_hash: Optional[str] = None

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    tasks: Mapped[List["Task"]] = Relationship(back_populates="assignee")


class UserCreate(UserBase):
    """
    Schema for creating a new user.

    Used to validate incoming request bodies when a client
    submits data to create a user. Includes password.
    """
    password: str


class UserRead(UserBase):
    """
    Schema for reading (returning) a user.

    Used in API responses. Includes both UserBase fields
    and database-managed fields.
    
    Attributes:
        id:         Unique identifier for the user
        created_at: Timestamp when the user was created
        updated_at: Timestamp when the user was last updated
    """
    id: str
    created_at: datetime
    updated_at: datetime
    # Note: We do NOT expose `tasks` here by default (keeps API clean)


class UserUpdate(SQLModel):
    """
    Schema for updating an existing user.

    Used for PATCH/PUT requests. All fields are optional
    to allow partial updates.
    """
    username: Optional[str] = None
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    role: Optional[Role] = None
    password: Optional[str] = None

    model_config = {"from_attributes": True}


__all__ = [
    "Role",
    "UserBase",
    "User",
    "UserCreate",
    "UserRead",
    "UserUpdate",
]
