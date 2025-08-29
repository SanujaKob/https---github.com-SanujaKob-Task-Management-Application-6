# app.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from data.database import init_db
from routers import users, tasks, auth
from routers import metrics
from routers.metrics import router as metrics_router 


# --- FastAPI instance ---
app = FastAPI(
    title="Abacus Task Management Application",
    description="A lightweight FastAPI app for managing tasks.",
    version="0.1.0",
)

# --- CORS: allow your Vite dev server(s) ---
origins = [
    "http://localhost:5173", "http://127.0.0.1:5173",
    "http://localhost:5174", "http://127.0.0.1:5174",
    "http://localhost:5175", "http://127.0.0.1:5175",
    "http://localhost:5178", "http://127.0.0.1:5178",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Init DB on startup ---
@app.on_event("startup")
def on_startup():
    init_db()

# --- Routers (mounted under /api) ---
app.include_router(auth.router,  prefix="/api")  # <-- login at POST /api/auth/login
app.include_router(users.router, prefix="/api")
app.include_router(tasks.router, prefix="/api")
app.include_router(metrics_router, prefix="/api")     

# --- Simple roots / health ---
@app.get("/")
def read_root():
    return {"message": "Welcome to Abacus Task Management!"}

@app.get("/health")
def health():
    return {"status": "ok"}
