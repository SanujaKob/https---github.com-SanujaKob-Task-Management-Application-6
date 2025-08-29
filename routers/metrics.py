# routers/metrics.py
from typing import Any, Dict, List
from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlmodel import Session, select

from data.database import get_session
from models.tasks import Task

router = APIRouter(prefix="/stats", tags=["stats"])

# Dashboard keys your TeamDashboard.vue expects
DASH_KEYS = ["todo","in_progress","over_due","completed","approved","rejected","resubmission"]

def _zero_dash() -> Dict[str, int]:
    return {k: 0 for k in DASH_KEYS} | {"total": 0}

def _norm(s: Any) -> str:
    """
    Normalize arbitrary status to a canonical token:
      "To Do" -> "todo"
      "In Progress" -> "in_progress"
      "Over Due", "Overdue" -> "over_due"
      "Completed" -> "completed"
      "Approved" -> "approved"
      "Rejected" -> "rejected"
      "Resubmission", "Re-Submission" -> "resubmission"
    Fallback: unknowns -> "todo" (or choose another default)
    """
    if not s:
        return "todo"
    x = str(s).strip().lower().replace("-", "_").replace(" ", "_")
    # common variants
    if x in {"to_do","todo"}: return "todo"
    if x in {"in_progress","progress"}: return "in_progress"
    if x in {"over_due","overdue","past_due"}: return "over_due"
    if x in {"completed","done","complete"}: return "completed"
    if x in {"approved","approve"}: return "approved"
    if x in {"rejected","reject"}: return "rejected"
    if x in {"re_submission","resubmission","re_submit"}: return "resubmission"
    # safety net: treat any unknown as "todo"
    return "todo"

@router.get("/ping")
def ping():
    return {"ok": True}

@router.get("/team")
def team_status_counts(session: Session = Depends(get_session)) -> Dict[str, int]:
    """
    Robust team counts, independent of exact DB strings.
    """
    rows = session.exec(select(Task.status, func.count()).group_by(Task.status)).all()

    out = _zero_dash()
    for raw_status, cnt in rows:
        key = _norm(raw_status)
        if key in out:
            out[key] += int(cnt)
        else:
            out["todo"] += int(cnt)  # bucket any unknowns to "todo"
    out["total"] = sum(out[k] for k in DASH_KEYS)
    return out

@router.get("/users")
def status_counts_by_user(session: Session = Depends(get_session)) -> List[Dict[str, Any]]:
    """
    Per-assignee counts; works whether you store assignee_id or assignee (text).
    """
    group_field = Task.assignee if not hasattr(Task, "assignee_id") else Task.assignee_id
    rows = session.exec(
        select(group_field, Task.status, func.count()).group_by(group_field, Task.status)
    ).all()

    per: Dict[Any, Dict[str, int]] = {}
    for assignee_key, raw_status, cnt in rows:
        if assignee_key not in per:
            per[assignee_key] = _zero_dash()
        key = _norm(raw_status)
        if key in per[assignee_key]:
            per[assignee_key][key] += int(cnt)
        else:
            per[assignee_key]["todo"] += int(cnt)

    out: List[Dict[str, Any]] = []
    for k, bucket in per.items():
        bucket["total"] = sum(bucket[d] for d in DASH_KEYS)
        out.append({"assignee_key": k, "counts": bucket})

    # Sort by total desc
    out.sort(key=lambda r: r["counts"]["total"], reverse=True)
    return out

# Optional: expose raw DB status distribution for debugging
@router.get("/debug/statuses")
def debug_status_groups(session: Session = Depends(get_session)):
    rows = session.exec(select(Task.status, func.count()).group_by(Task.status)).all()
    return [{"status_in_db": s, "count": int(c)} for s, c in rows]
