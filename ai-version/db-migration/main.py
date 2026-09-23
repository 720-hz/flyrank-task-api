import sqlite3
from contextlib import contextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

app = FastAPI(title="Task API", version="1.0")

DB_PATH = "tasks_v2.db"


@contextmanager
def get_db():
    # A fresh connection per request — not one shared global connection —
    # so it never crosses the "created in one thread, used in another"
    # line that FastAPI's threadpool triggers.
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
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


@app.exception_handler(HTTPException)
def error_shape_handler(request: Request, exc: HTTPException):
    return JSONResponse(status_code=exc.status_code, content={"error": exc.detail})


def row_to_task(row: sqlite3.Row) -> dict:
    return {"id": row["id"], "title": row["title"], "done": bool(row["done"])}


@app.get("/")
def root():
    return {"name": "Task API", "version": "1.0", "endpoints": ["/tasks"]}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/tasks")
def list_tasks():
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM tasks").fetchall()
    return [row_to_task(r) for r in rows]


@app.get("/tasks/{task_id}")
def get_task(task_id: int):
    with get_db() as conn:
        row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    return row_to_task(row)


class TaskCreate(BaseModel):
    title: Optional[str] = None


def clean_title(title: Optional[str]) -> Optional[str]:
    if title is None:
        return None
    trimmed = title.strip()
    return trimmed if trimmed else None


@app.post("/tasks", status_code=201)
def create_task(body: TaskCreate):
    title = clean_title(body.title)
    if title is None:
        raise HTTPException(status_code=400, detail="Title is required")
    with get_db() as conn:
        cursor = conn.execute(
            "INSERT INTO tasks (title, done) VALUES (?, ?)", (title, 0)
        )
        row = conn.execute(
            "SELECT * FROM tasks WHERE id = ?", (cursor.lastrowid,)
        ).fetchone()
    return row_to_task(row)


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    done: Optional[bool] = None


@app.put("/tasks/{task_id}")
def update_task(task_id: int, body: TaskUpdate):
    with get_db() as conn:
        row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

        new_title = row["title"]
        if body.title is not None:
            cleaned = clean_title(body.title)
            if cleaned is None:
                raise HTTPException(status_code=400, detail="Title cannot be empty")
            new_title = cleaned

        new_done = row["done"] if body.done is None else (1 if body.done else 0)

        conn.execute(
            "UPDATE tasks SET title = ?, done = ? WHERE id = ?",
            (new_title, new_done, task_id),
        )
        updated = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    return row_to_task(updated)


@app.delete("/tasks/{task_id}", status_code=204)
def delete_task(task_id: int):
    with get_db() as conn:
        row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
        conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
