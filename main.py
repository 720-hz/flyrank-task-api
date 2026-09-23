import sqlite3
from contextlib import contextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

# A single file on disk instead of a variable in memory. Created
# automatically the first time a connection touches it — no server,
# no install, nothing to run in the background.
DB_PATH = "tasks.db"

app = FastAPI(
    title="Task API",
    version="1.0",
    description="A small CRUD API for managing a to-do list, backed by SQLite.",
)


@contextmanager
def get_db():
    """One connection per request. Commits on a clean exit, rolls back
    (by simply not committing, then closing) if anything inside raises —
    so a request either fully lands in the database or leaves no trace."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    """Creates the table if missing, then seeds three example tasks —
    but only the very first time, when the table is still empty. Runs
    once at startup, not per-request."""
    with get_db() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                done BOOLEAN NOT NULL DEFAULT 0
            )
            """
        )
        count = conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
        if count == 0:
            conn.executemany(
                "INSERT INTO tasks (title, done) VALUES (?, ?)",
                [("Buy milk", 0), ("Write README", 0), ("Push to GitHub", 1)],
            )


@app.on_event("startup")
def on_startup():
    init_db()


# FastAPI's default error body is {"detail": "..."}. The assignment spec
# wants {"error": "..."} instead, so every raise HTTPException(...) below
# comes out shaped the way the checkpoint curls expect.
@app.exception_handler(HTTPException)
def error_shape_handler(request: Request, exc: HTTPException):
    return JSONResponse(status_code=exc.status_code, content={"error": exc.detail})


def row_to_task(row: sqlite3.Row) -> dict:
    """SQLite stores done as 0/1; the API contract says true/false."""
    return {"id": row["id"], "title": row["title"], "done": bool(row["done"])}


# create/update/delete haven't moved to SQL yet (next two stages), so this
# in-memory list stays around until they do — only the two GET endpoints
# below read from the database now.
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
    """Returns every task, read straight from the database."""
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM tasks").fetchall()
    return [row_to_task(row) for row in rows]


@app.get("/tasks/{task_id}")
def get_task(task_id: int):
    """Returns a single task by id, or 404 if no task has that id."""
    with get_db() as conn:
        row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    return row_to_task(row)


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


class TaskUpdate(BaseModel):
    # Both optional: PUT here means "replace title and/or done with what's
    # given," not "you must resend every field." title, if given at all,
    # still has to pass the same non-empty rule as create.
    title: Optional[str] = None
    done: Optional[bool] = None


@app.put("/tasks/{task_id}")
def update_task(task_id: int, body: TaskUpdate):
    """Replaces a task's title and/or done. 404 if unknown id, 400 if the body is invalid."""
    for task in tasks:
        if task["id"] == task_id:
            if body.title is not None and not body.title.strip():
                raise HTTPException(status_code=400, detail="title cannot be empty")
            if body.title is None and body.done is None:
                raise HTTPException(status_code=400, detail="provide title and/or done to update")
            if body.title is not None:
                task["title"] = body.title.strip()
            if body.done is not None:
                task["done"] = body.done
            return task
    raise HTTPException(status_code=404, detail=f"Task {task_id} not found")


@app.delete("/tasks/{task_id}", status_code=204)
def delete_task(task_id: int):
    """Removes a task. 204 with no body on success, 404 if unknown id."""
    for i, task in enumerate(tasks):
        if task["id"] == task_id:
            tasks.pop(i)
            return
    raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
