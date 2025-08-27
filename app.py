# app.py

from fastapi import FastAPI
from data.database import init_db
from routers import users, tasks


# Create the FastAPI instance
app = FastAPI(
    title="Abacus Task Management Application",
    description="A lightweight FastAPI app for managing tasks. (Placeholder version)",
    version="0.1.0"
)

# Init DB
@app.on_event("startup")
def on_startup():
    init_db()


# Add routers
app.include_router(users.router)
app.include_router(tasks.router)

# Root endpoint
@app.get("/")
def read_root():
    return {"message": "Welcome to Abacus Task Management!"}
