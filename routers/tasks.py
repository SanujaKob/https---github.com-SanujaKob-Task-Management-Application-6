# routers/tasks.py
from typing import List
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from data.database import get_session
from models.tasks import Task, TaskCreate, TaskRead, TaskUpdate

router = APIRouter(prefix="/tasks", tags=["tasks"])

def to_read(t: Task) -> TaskRead:
    return TaskRead.model_validate(t)

@router.get("", response_model=List[TaskRead])
def list_tasks(session: Session = Depends(get_session)):
    rows = session.exec(select(Task).order_by(Task.created_at.desc())).all()
    return [to_read(t) for t in rows]

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
    if not getattr(t, "created_at", None): t.created_at = now
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
