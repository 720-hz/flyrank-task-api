import os
import sqlite3
from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

app = FastAPI(title="Task API", version="1.0")

DB_PATH = "tasks_v1.db"

# A literal reading of "seed the first time the database is created": check
# whether the file was already there, then connect. Looks reasonable on its
# own line — the bug is what happens next.
db_already_existed = os.path.exists(DB_PATH)
conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row

conn.execute(
    """
    CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY,
        title TEXT NOT NULL,
        done BOOLEAN NOT NULL DEFAULT 0
    )
    """
)
conn.commit()

if not db_already_existed:
    conn.executemany(
        "INSERT INTO tasks (title, done) VALUES (?, ?)",
        [("Buy milk", 0), ("Write README", 0), ("Push to GitHub", 1)],
    )
    conn.commit()


@app.exception_handler(HTTPException)
def error_shape_handler(request: Request, exc: HTTPException):
    return JSONResponse(status_code=exc.status_code, content={"error": exc.detail})


@app.get("/")
def root():
    return {"name": "Task API", "version": "1.0", "endpoints": ["/tasks"]}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/tasks")
def list_tasks():
    rows = conn.execute("SELECT * FROM tasks").fetchall()
    return [dict(row) for row in rows]


@app.get("/tasks/{task_id}")
def get_task(task_id: int):
    row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    return dict(row)


class TaskCreate(BaseModel):
    title: Optional[str] = None


@app.post("/tasks", status_code=201)
def create_task(body: TaskCreate):
    if not body.title:
        raise HTTPException(status_code=400, detail="Title is required")
    cursor = conn.execute(
        "INSERT INTO tasks (title, done) VALUES (?, ?)", (body.title, 0)
    )
    conn.commit()
    row = conn.execute(
        "SELECT * FROM tasks WHERE id = ?", (cursor.lastrowid,)
    ).fetchone()
    return dict(row)


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    done: Optional[bool] = None


@app.put("/tasks/{task_id}")
def update_task(task_id: int, body: TaskUpdate):
    row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

    new_title = body.title if body.title is not None else row["title"]
    new_done = body.done if body.done is not None else row["done"]

    conn.execute(
        "UPDATE tasks SET title = ?, done = ? WHERE id = ?",
        (new_title, new_done, task_id),
    )
    conn.commit()
    updated = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    return dict(updated)


@app.delete("/tasks/{task_id}", status_code=204)
def delete_task(task_id: int):
    row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    conn.commit()
