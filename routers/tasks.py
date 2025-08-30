# routers/tasks.py
from typing import List, Optional, Tuple
from datetime import datetime, date

from fastapi import APIRouter, Depends, HTTPException, Query, status, Body
from sqlmodel import Session, select
from sqlalchemy import or_, func, cast, String

from data.database import get_session
from models.tasks import Task, TaskCreate, TaskRead
from routers.auth import get_current_user

# Optional role import
try:
    from models.users import Role  # type: ignore
except Exception:  # pragma: no cover
    Role = None  # fallback if roles aren't implemented yet

router = APIRouter(prefix="/tasks", tags=["tasks"])

# ---------------------------------------------------------------------
# Canonical enums & normalization
# ---------------------------------------------------------------------

VALID_STATUSES   = {"not_started", "in_progress", "completed", "approved", "rejected", "resubmit"}
VALID_PRIORITIES = {"low", "medium", "high", "critical"}
TERMINAL_STATUSES = {"completed", "approved", "rejected"}

# tolerate common UI labels/typos
STATUS_CANON = {
    "to do": "not_started",
    "todo": "not_started",
    "not started": "not_started",
    "in progress": "in_progress",
    "re-submission": "resubmit",
    "re submission": "resubmit",
    "re-submitted": "resubmit",
}
PRIORITY_CANON = {
    "normal": "medium",
}

def canon_status(val: Optional[str]) -> Optional[str]:
    """Return canonical status or None (treat blank/invalid as not provided)."""
    if val is None:
        return None
    s = str(val).strip()
    if not s:
        return None
    s = s.lower().replace("_", " ").replace("-", " ")
    s = STATUS_CANON.get(s, s)
    s = s.replace(" ", "_")
    return s if s in VALID_STATUSES else None

def canon_priority(val: Optional[str]) -> Optional[str]:
    """Return canonical priority or None (treat blank/invalid as not provided)."""
    if val is None:
        return None
    p = str(val).strip()
    if not p:
        return None
    p = p.lower()
    p = PRIORITY_CANON.get(p, p)
    return p if p in VALID_PRIORITIES else None

# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------

def to_read(t: Task) -> TaskRead:
    return TaskRead.model_validate(t)

def parse_sort(sort: Optional[str]) -> Tuple:
    key = (sort or "-updated_at").strip()
    desc = key.startswith("-")
    field = key[1:] if desc else key
    colmap = {
        "updated_at": Task.updated_at,
        "created_at": Task.created_at,
        "due_date":   Task.due_date,
        "priority":   Task.priority,
    }
    col = colmap.get(field, Task.updated_at)
    return (col.desc() if desc else col.asc(),)

def paginate(session: Session, stmt, page: int, size: int):
    total = session.exec(select(func.count()).select_from(stmt.subquery())).one()
    rows  = session.exec(stmt.offset((page - 1) * size).limit(size)).all()
    return rows, total

def is_admin_or_manager(user) -> bool:
    if not hasattr(user, "role"):
        return False
    if Role is not None:
        try:
            return user.role in {Role.admin, Role.manager}
        except Exception:
            pass
    return str(getattr(user, "role", "")).lower() in {"admin", "manager"}

def resolve_task(session: Session, task_key: str) -> Optional[Task]:
    """
    Accept either numeric PK or string code/id.
    Tries: PK(int) -> PK(str) -> cast(Task.id, String) == task_key
    """
    if task_key.isdigit():
        t = session.get(Task, int(task_key))
        if t:
            return t
    t = session.get(Task, task_key)
    if t:
        return t
    return session.exec(select(Task).where(cast(Task.id, String) == task_key)).first()

def parse_due_date(val):
    """Accept 'YYYY-MM-DD', ISO string, date, or datetime; return datetime or None."""
    if not val:
        return None
    try:
        if isinstance(val, datetime):
            return val
        if isinstance(val, date):
            return datetime(val.year, val.month, val.day)
        s = str(val).strip()
        if len(s) == 10 and s[4] == "-" and s[7] == "-":
            return datetime.fromisoformat(s + "T00:00:00")
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return None

def apply_common_filters(
    stmt,
    q: Optional[str],
    status_value: Optional[str],
    overdue: bool,
    assignee_id: Optional[int],
):
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(
                Task.title.ilike(like),
                Task.description.ilike(like),
                cast(Task.id, String).ilike(like),
            )
        )

    if status_value:
        norm = canon_status(status_value)
        if not norm:
            return stmt.where(False)  # invalid filter -> empty result
        stmt = stmt.where(Task.status == norm)

    if overdue:
        stmt = stmt.where(
            Task.due_date.is_not(None),
            Task.due_date < datetime.utcnow(),
            Task.status.notin_(TERMINAL_STATUSES),
        )

    if assignee_id is not None:
        stmt = stmt.where(Task.assignee_id == assignee_id)

    return stmt

# ---------------------------------------------------------------------
# Read endpoints (fixed paths BEFORE param route)
# ---------------------------------------------------------------------

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
    overdue: bool = Query(False, description="due_date < now and not in terminal statuses"),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=100),
    sort: Optional[str] = Query("-updated_at"),
):
    stmt = select(Task)
    stmt = apply_common_filters(stmt, q, status_value, overdue, current_user.id)
    stmt = stmt.order_by(*parse_sort(sort))
    rows, total = paginate(session, stmt, page, size)
    return {"items": [to_read(t) for t in rows], "page": page, "size": size, "total": total}

@router.get("/search")
def search_tasks(
    current_user = Depends(get_current_user),
    session: Session = Depends(get_session),
    q: Optional[str] = Query(None, description="Search in id/title/description"),
    status_value: Optional[str] = Query(None, alias="status", description="Exact workflow status"),
    overdue: bool = Query(False, description="due_date < now and not in terminal statuses"),
    assignee: Optional[str] = Query(None, description="'me' or a numeric user_id"),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=100),
    sort: Optional[str] = Query("-updated_at"),
):
    # Determine assignee scope
    assignee_id: Optional[int] = None
    if assignee == "me":
        assignee_id = current_user.id
    elif assignee and assignee.isdigit():
        assignee_id = int(assignee)

    # Visibility: non-managers see only their own tasks
    if not is_admin_or_manager(current_user):
        assignee_id = current_user.id

    stmt = select(Task)
    stmt = apply_common_filters(stmt, q, status_value, overdue, assignee_id)
    stmt = stmt.order_by(*parse_sort(sort))
    rows, total = paginate(session, stmt, page, size)
    return {"items": [to_read(t) for t in rows], "page": page, "size": size, "total": total}

# ---------------------------------------------------------------------
# Flexible key endpoints (string or int)
# ---------------------------------------------------------------------

@router.get("/{task_key}", response_model=TaskRead)
def get_task(task_key: str, session: Session = Depends(get_session)):
    t = resolve_task(session, task_key)
    if not t:
        raise HTTPException(status_code=404, detail="Task not found")
    return to_read(t)

@router.post("", response_model=TaskRead, status_code=status.HTTP_201_CREATED)
def create_task(payload: TaskCreate, session: Session = Depends(get_session)):
    # Accept FE aliases (percent_complete) and tolerant due_date
    data = payload.model_dump()
    if "percent_complete" in data and "progress" not in data:
        try:
            pc = int(float(data.get("percent_complete") or 0))
            data["progress"] = max(0, min(100, pc))
        except Exception:
            data["progress"] = 0
        data.pop("percent_complete", None)

    if "due_date" in data:
        parsed = parse_due_date(data.get("due_date"))
        data["due_date"] = parsed

    # Normalize enums if present
    if "status" in data and data["status"] is not None:
        s = canon_status(data["status"])
        if s is not None:
            data["status"] = s
        else:
            data.pop("status", None)
    if "priority" in data and data["priority"] is not None:
        p = canon_priority(data["priority"])
        if p is not None:
            data["priority"] = p
        else:
            data.pop("priority", None)

    t = Task(**data)
    now = datetime.utcnow()
    if not getattr(t, "created_at", None):
        t.created_at = now
    t.updated_at = now
    session.add(t)
    session.commit()
    session.refresh(t)
    return to_read(t)

@router.put("/{task_key}", response_model=TaskRead)
def update_task(
    task_key: str,
    payload: dict = Body(...),             # <— accept raw dict to avoid schema dropping fields
    session: Session = Depends(get_session),
):
    t = resolve_task(session, task_key)
    if not t:
        raise HTTPException(status_code=404, detail="Task not found")

    # Work on a mutable copy
    data = dict(payload or {})

    # Normalize (forgiving: blank/invalid -> ignore field)
    if "status" in data:
        s = canon_status(data.get("status"))
        if s is not None:
            data["status"] = s
        else:
            data.pop("status", None)

    if "priority" in data:
        p = canon_priority(data.get("priority"))
        if p is not None:
            data["priority"] = p
        else:
            data.pop("priority", None)

    # Accept FE alias for progress
    if "percent_complete" in data:
        try:
            pc = int(float(data.get("percent_complete") or 0))
            data["progress"] = max(0, min(100, pc))
        except Exception:
            pass
        data.pop("percent_complete", None)

    # Tolerant due_date parsing
    if "due_date" in data:
        parsed = parse_due_date(data.get("due_date"))
        if parsed is not None:
            data["due_date"] = parsed
        else:
            data.pop("due_date", None)

    # Apply fields
    for k, v in data.items():
        setattr(t, k, v)

    t.updated_at = datetime.utcnow()
    session.add(t)
    session.commit()
    session.refresh(t)
    return to_read(t)

@router.delete("/{task_key}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(task_key: str, session: Session = Depends(get_session)):
    t = resolve_task(session, task_key)
    if not t:
        raise HTTPException(status_code=404, detail="Task not found")
    session.delete(t)
    session.commit()
    return None

@router.put("/{task_key}/status", response_model=TaskRead)
def update_status(task_key: str, status_payload: dict, session: Session = Depends(get_session)):
    """Accepts: {'status': 'in_progress'} or human labels like 'In Progress'."""
    t = resolve_task(session, task_key)
    if not t:
        raise HTTPException(status_code=404, detail="Task not found")
    new_status = canon_status(status_payload.get("status"))
    if not new_status:
        raise HTTPException(status_code=400, detail="Missing or invalid 'status'")
    t.status = new_status
    t.updated_at = datetime.utcnow()
    session.add(t)
    session.commit()
    session.refresh(t)
    return to_read(t)
