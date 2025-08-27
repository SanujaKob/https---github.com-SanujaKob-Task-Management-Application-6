# routers/tasks.py

from typing import List
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from data.database import get_session
from models.tasks import Task, TaskCreate, TaskRead, TaskUpdate

router = APIRouter(prefix="/tasks", tags=["tasks"])


def to_task_read(t: Task) -> TaskRead:
    """Convert a Task ORM object to a TaskRead schema."""
    return TaskRead.model_validate(t)


@router.post("", response_model=TaskRead, status_code=status.HTTP_201_CREATED)
def create_task(payload: TaskCreate, session: Session = Depends(get_session)):
    task = Task(**payload.model_dump())
    session.add(task)
    session.commit()
    session.refresh(task)
    return to_task_read(task)


@router.get("", response_model=List[TaskRead])
def list_tasks(session: Session = Depends(get_session)):
    tasks = session.exec(select(Task)).all()
    return [to_task_read(t) for t in tasks]

@router.get("/by-user/{user_id}", response_model=List[TaskRead])
def list_tasks_for_user(user_id: str, session: Session = Depends(get_session)):
    """
    Return all tasks whose `assignee_id` matches *user_id*.
    """
    tasks = session.exec(
        select(Task).where(Task.assignee_id == user_id)
    ).all()

    if not tasks:
        # optional: skip 404 if you prefer to just return an empty list
        raise HTTPException(status_code=404, detail="No tasks found for that user")

    return [to_task_read(t) for t in tasks]


@router.get("/{task_id}", response_model=TaskRead)
def get_task(task_id: str, session: Session = Depends(get_session)):
    task = session.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return to_task_read(task)


@router.patch("/{task_id}", response_model=TaskRead)
def update_task(task_id: str, payload: TaskUpdate, session: Session = Depends(get_session)):
    task = session.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    data = payload.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(task, key, value)

    task.updated_at = datetime.utcnow()

    session.add(task)
    session.commit()
    session.refresh(task)
    return to_task_read(task)


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(task_id: str, session: Session = Depends(get_session)):
    task = session.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    session.delete(task)
    session.commit()
    return None
