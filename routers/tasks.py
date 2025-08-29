# routers/tasks.py
from typing import List, Optional, Tuple
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import Session, select
from sqlalchemy import or_, func, cast, String  # SQLAlchemy helpers

from data.database import get_session
from models.tasks import Task, TaskCreate, TaskRead, TaskUpdate
from routers.auth import get_current_user  # ← depend directly on the function

# If you have a Role enum on User, import it; otherwise this stays None and we fallback.
try:
    from models.users import Role  # type: ignore
except Exception:  # pragma: no cover
    Role = None  # fallback if roles aren't implemented yet

router = APIRouter(prefix="/tasks", tags=["tasks"])

# ---------------------------
# Helpers
# ---------------------------

def to_read(t: Task) -> TaskRead:
    return TaskRead.model_validate(t)

TERMINAL_STATUSES = {"Completed", "Approved", "Rejected"}

def apply_common_filters(
    stmt,
    q: Optional[str],
    status_value: Optional[str],
    overdue: bool,
    assignee_id: Optional[int],
):
    """Apply q/status/overdue/assignee filters to a select() statement."""
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(
                Task.title.ilike(like),
                Task.description.ilike(like),
                cast(Task.id, String).ilike(like),  # search by id as text
            )
        )

    if status_value:
        stmt = stmt.where(Task.status == status_value)

    if overdue:
        # Derived overdue: due_date < now AND not in terminal states
        stmt = stmt.where(
            Task.due_date.is_not(None),
            Task.due_date < datetime.utcnow(),
            Task.status.notin_(TERMINAL_STATUSES),
        )

    if assignee_id is not None:
        stmt = stmt.where(Task.assignee_id == assignee_id)

    return stmt

def parse_sort(sort: Optional[str]) -> Tuple:
    """
    Map sort keys to columns; supports leading '-' for DESC.
    Allowed: updated_at (default), created_at, due_date, priority
    """
    key = (sort or "-updated_at").strip()
    desc = key.startswith("-")
    field = key[1:] if desc else key

    colmap = {
        "updated_at": Task.updated_at,
        "created_at": Task.created_at,
        "due_date": Task.due_date,
        "priority": Task.priority,  # must be comparable (enum/int/text)
    }
    col = colmap.get(field, Task.updated_at)
    return (col.desc() if desc else col.asc(),)

def paginate(session: Session, stmt, page: int, size: int):
    """Return (rows, total) for the given stmt with offset/limit."""
    total = session.exec(
        select(func.count()).select_from(stmt.subquery())
    ).one()
    rows = session.exec(
        stmt.offset((page - 1) * size).limit(size)
    ).all()
    return rows, total

def is_admin_or_manager(user) -> bool:
    """Role check (works whether Role is an enum or a string)."""
    if not hasattr(user, "role"):
        return False
    if Role is not None:
        try:
            return user.role in {Role.admin, Role.manager}
        except Exception:
            pass
    # string fallback
    return str(getattr(user, "role", "")).lower() in {"admin", "manager"}

# ---------------------------
# Existing CRUD (kept intact)
# ---------------------------

@router.get("", response_model=List[TaskRead])
def list_tasks(session: Session = Depends(get_session)):
    rows = session.exec(select(Task).order_by(Task.created_at.desc())).all()
    return [to_read(t) for t in rows]

@router.get("/my")
def list_my_tasks(
    current_user = Depends(get_current_user),
    session: Session = Depends(get_session),
    q: Optional[str] = Query(None, description="Search in id/title/description"),
    status_value: Optional[str] = Query(None, alias="status", description="Exact workflow status"),
    overdue: bool = Query(False, description="Derived: due_date < now and not in terminal states"),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=100),
    sort: Optional[str] = Query("-updated_at", description="e.g. -updated_at, created_at, due_date, priority"),
):
    """
    Returns only tasks assigned to the logged-in user.
    Envelope: { items, page, size, total }
    """
    stmt = select(Task)
    stmt = apply_common_filters(
        stmt, q=q, status_value=status_value, overdue=overdue, assignee_id=current_user.id
    )
    stmt = stmt.order_by(*parse_sort(sort))
    rows, total = paginate(session, stmt, page, size)
    return {
        "items": [to_read(t) for t in rows],
        "page": page,
        "size": size,
        "total": total,
    }

@router.get("/{task_id}", response_model=TaskRead)
def get_task(task_id: int, session: Session = Depends(get_session)):
    t = session.get(Task, task_id)
    if not t:
        raise HTTPException(status_code=404, detail="Task not found")
    return to_read(t)

@router.post("", response_model=TaskRead, status_code=status.HTTP_201_CREATED)
def create_task(payload: TaskCreate, session: Session = Depends(get_session)):
    t = Task(**payload.model_dump())
    now = datetime.utcnow()
    if not getattr(t, "created_at", None):
        t.created_at = now
    t.updated_at = now
    session.add(t)
    session.commit()
    session.refresh(t)
    return to_read(t)

@router.put("/{task_id}", response_model=TaskRead)
def update_task(task_id: int, payload: TaskUpdate, session: Session = Depends(get_session)):
    t = session.get(Task, task_id)
    if not t:
        raise HTTPException(status_code=404, detail="Task not found")
    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(t, k, v)
    t.updated_at = datetime.utcnow()
    session.add(t)
    session.commit()
    session.refresh(t)
    return to_read(t)

@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(task_id: int, session: Session = Depends(get_session)):
    t = session.get(Task, task_id)
    if not t:
        raise HTTPException(status_code=404, detail="Task not found")
    session.delete(t)
    session.commit()
    return None

@router.put("/{task_id}/status", response_model=TaskRead)
def update_status(task_id: int, status_payload: dict, session: Session = Depends(get_session)):
    """expects: {"status": "In Progress"}"""
    t = session.get(Task, task_id)
    if not t:
        raise HTTPException(status_code=404, detail="Task not found")
    new_status = status_payload.get("status")
    if not new_status:
        raise HTTPException(status_code=400, detail="Missing 'status'")
    t.status = new_status
    t.updated_at = datetime.utcnow()
    session.add(t)
    session.commit()
    session.refresh(t)
    return to_read(t)

# ---------------------------
# NEW: Read endpoints for pages (envelope responses)
# ---------------------------

@router.get("/search")
def search_tasks(
    current_user = Depends(get_current_user),
    session: Session = Depends(get_session),
    q: Optional[str] = Query(None, description="Search in id/title/description"),
    status_value: Optional[str] = Query(None, alias="status", description="Exact workflow status"),
    overdue: bool = Query(False, description="Derived: due_date < now and not in terminal states"),
    assignee: Optional[str] = Query(None, description="'me' or a numeric user_id"),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=100),
    sort: Optional[str] = Query("-updated_at"),
):
    """
    Team-visible list with filters & pagination.
    - Non-managers: restricted to their own tasks.
    - Managers/Admins: can see all; 'assignee=me|<id>' narrows results.
    Envelope: { items, page, size, total }
    """
    # Resolve assignee filter
    assignee_id: Optional[int] = None
    if assignee == "me":
        assignee_id = current_user.id
    elif assignee and assignee.isdigit():
        assignee_id = int(assignee)

    # Visibility policy
    if not is_admin_or_manager(current_user):
        # Non-managers can only see their own tasks regardless of filter
        assignee_id = current_user.id

    stmt = select(Task)
    stmt = apply_common_filters(
        stmt, q=q, status_value=status_value, overdue=overdue, assignee_id=assignee_id
    )
    stmt = stmt.order_by(*parse_sort(sort))
    rows, total = paginate(session, stmt, page, size)
    return {
        "items": [to_read(t) for t in rows],
        "page": page,
        "size": size,
        "total": total,
    }
