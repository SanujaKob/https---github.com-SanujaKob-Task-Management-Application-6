# models/task.py

from enum import Enum
from datetime import datetime, date
from typing import Optional, TYPE_CHECKING
from sqlmodel import SQLModel, Field, Relationship
from sqlalchemy.orm import Mapped
from models.helper import short_uuid

if TYPE_CHECKING:
    from models.users import User


# ---------------------------
# Enumerations
# ---------------------------
class TaskPriority(str, Enum):
    """
    Enumeration of task priority levels.

    Values:
        - low:     Low priority task
        - medium:  Normal priority task
        - high:    High urgency task
        - critical: Must be addressed immediately
    """
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class TaskStatus(str, Enum):
    """
    Enumeration of task workflow states.

    Values:
        - not_started: Task has not been started
        - in_progress: Task is currently being worked on
        - completed:   Task is finished
        - approved:    Task has been reviewed and accepted
        - rejected:    Task has been reviewed and declined
        - resubmit:    Task must be revised and resubmitted
    """
    not_started = "not_started"
    in_progress = "in_progress"
    completed = "completed"
    approved = "approved"
    rejected = "rejected"
    resubmit = "resubmit"


# ---------------------------
# TASK MODELS
# ---------------------------
class TaskBase(SQLModel):
    """
    Shared base schema for tasks.

    Defines fields that are common across multiple task schemas
    (create, read, update). Not mapped as a database table.

    Attributes:
        title:       Short title for the task
        description: Longer optional description of the task
        priority:    Priority level of the task
        status:      Current status of the task
        progress:    Percent completion (0–100)
        due_date:    Optional due date
        assignee_id: Reference to the assigned user's ID
    """
    title: str
    description: Optional[str] = None
    priority: TaskPriority = TaskPriority.medium
    status: TaskStatus = TaskStatus.not_started
    progress: int = Field(default=0, ge=0, le=100)
    due_date: Optional[date] = None

    model_config = {"from_attributes": True}


class Task(TaskBase, table=True):
    """
    Database model for a task.

    Represents the actual SQL table 'task' in SQLite. Extends
    TaskBase by adding:
        - id: unique 5-character string ID
        - created_at: timestamp when the task was created
        - updated_at: timestamp when the task was last updated
        - assignee: relationship to the User who owns the task
    """

    __tablename__ = "tasks"  # ← explicit table name


    id: str = Field(default_factory=short_uuid, primary_key=True, index=True)
    
    # IMPORTANT: match the table name above
    assignee_id: Optional[str] = Field(default=None, foreign_key="users.id")

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    assignee: Optional["User"] = Relationship(back_populates="tasks")  # ✅


class TaskCreate(TaskBase):
    """
    Schema for creating a new task.

    Used to validate incoming request bodies when a client
    submits data to create a task. Inherits all fields from TaskBase.
    """
    assignee_id: Optional[str] = None


class TaskRead(TaskBase):
    """
    Schema for reading (returning) a task.

    Used in API responses. Includes both TaskBase fields
    and database-managed fields.
    
    Attributes:
        id:         Unique identifier
        created_at: Timestamp when the task was created
        updated_at: Timestamp when the task was last updated
    """
    id: str
    created_at: datetime
    updated_at: datetime
    assignee_id: Optional[str] = None


class TaskUpdate(SQLModel):
    """
    Schema for updating an existing task.

    Used for PATCH/PUT requests. All fields are optional
    to allow partial updates.
    """
    title: Optional[str] = None
    description: Optional[str] = None
    priority: Optional[TaskPriority] = None
    status: Optional[TaskStatus] = None
    progress: Optional[int] = Field(None, ge=0, le=100)
    due_date: Optional[date] = None
    assignee_id: Optional[str] = None

    model_config = {"from_attributes": True}


__all__ = [
    "TaskPriority", "TaskStatus",
    "TaskBase", "Task", "TaskCreate", "TaskRead", "TaskUpdate",
]
