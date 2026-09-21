from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

app = FastAPI(
    title="Task API",
    version="1.0",
    description="A small in-memory CRUD API for managing a to-do list.",
)


# FastAPI's default error body is {"detail": "..."}. The assignment spec
# wants {"error": "..."} instead, so every raise HTTPException(...) below
# comes out shaped the way the checkpoint curls expect.
@app.exception_handler(HTTPException)
def error_shape_handler(request: Request, exc: HTTPException):
    return JSONResponse(status_code=exc.status_code, content={"error": exc.detail})

# In-memory "database" — a plain list of dicts. Gone on restart, on purpose:
# that's next week's lesson (persistence), not a bug in this one.
tasks = [
    {"id": 1, "title": "Buy milk", "done": False},
    {"id": 2, "title": "Write README", "done": False},
    {"id": 3, "title": "Push to GitHub", "done": True},
]


@app.get("/")
def root():
    """Describes this API: its name, version, and top-level endpoints."""
    return {"name": "Task API", "version": "1.0", "endpoints": ["/tasks"]}


@app.get("/health")
def health():
    """Liveness check — used to confirm the server is up and responding."""
    return {"status": "ok"}


@app.get("/tasks")
def list_tasks():
    """Returns every task currently in memory."""
    return tasks


@app.get("/tasks/{task_id}")
def get_task(task_id: int):
    """Returns a single task by id, or 404 if no task has that id."""
    for task in tasks:
        if task["id"] == task_id:
            return task
    raise HTTPException(status_code=404, detail=f"Task {task_id} not found")


class TaskCreate(BaseModel):
    # title is intentionally Optional here, not required, so a body like {}
    # reaches our own validation below and gets a clean 400 — instead of
    # Pydantic auto-rejecting it with a 422 the spec never asked for.
    title: Optional[str] = None


def next_id() -> int:
    """The next free id — one higher than whatever is currently the largest."""
    return max((t["id"] for t in tasks), default=0) + 1


@app.post("/tasks", status_code=201)
def create_task(body: TaskCreate):
    """Creates a task from {"title": "..."}. Rejects a missing/empty title with 400."""
    if not body.title or not body.title.strip():
        raise HTTPException(status_code=400, detail="title is required and cannot be empty")
    task = {"id": next_id(), "title": body.title.strip(), "done": False}
    tasks.append(task)
    return task
