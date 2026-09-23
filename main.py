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
    """Creates the table (and its index) if missing, then seeds three
    example tasks — but only the very first time, when the table is
    still empty. Runs once at startup, not per-request."""
    with get_db() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                done BOOLEAN NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
            """
        )
        # AUTOINCREMENT (not just "INTEGER PRIMARY KEY") matters here:
        # it guarantees ids are never reused, even after a delete. The W2
        # "AI vs me" review found a real bug where a naive id = len(list)+1
        # scheme collided after a delete-then-create — this is the SQL-side
        # fix for exactly that class of mistake.

        # An index backs the ?search= and ?sort=title extras below — without
        # it, every LIKE/ORDER BY on title would scan the whole table row by
        # row; with it, SQLite can look titles up the way a book's index
        # beats reading every page.
        conn.execute("CREATE INDEX IF NOT EXISTS idx_tasks_title ON tasks(title)")

        count = conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
        if count == 0:
            # All three seed rows share this one connection's single
            # commit() (see get_db above), so they're inserted as one
            # transaction: if the third insert failed partway through, the
            # first two would roll back with it. Ending up with zero seed
            # rows is fine; ending up with two out of three, silently, is
            # the kind of half-written state a transaction exists to rule
            # out.
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


@app.get("/")
def root():
    """Describes this API: its name, version, and top-level endpoints."""
    return {"name": "Task API", "version": "1.0", "endpoints": ["/tasks"]}


@app.get("/health")
def health():
    """Liveness check — used to confirm the server is up and responding."""
    return {"status": "ok"}


@app.get("/tasks")
def list_tasks(
    search: Optional[str] = None,
    done: Optional[bool] = None,
    sort: Optional[str] = None,
):
    """Returns every task, filtered in SQL by ?search= / ?done= and ordered
    by ?sort=title (default: insertion order, i.e. by id). All three are
    optional extras layered on top of the required GET /tasks."""
    query = "SELECT * FROM tasks WHERE 1 = 1"
    params: list = []
    if search:
        # % is a wildcard in LIKE; wrapping the term in %...% means
        # "contains", not "starts with" or an exact match.
        query += " AND title LIKE ?"
        params.append(f"%{search}%")
    if done is not None:
        query += " AND done = ?"
        params.append(1 if done else 0)
    query += " ORDER BY title" if sort == "title" else " ORDER BY id"

    with get_db() as conn:
        rows = conn.execute(query, params).fetchall()
    return [row_to_task(row) for row in rows]


@app.get("/stats")
def stats():
    """Task counts computed by SQL's COUNT(), not by looping over rows
    in Python — the database counts its own rows faster than we could."""
    with get_db() as conn:
        total = conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
        done_count = conn.execute("SELECT COUNT(*) FROM tasks WHERE done = 1").fetchone()[0]
    return {"total": total, "done": done_count, "open": total - done_count}


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


def clean_title(title: Optional[str]) -> Optional[str]:
    """Trims the title and returns None if it's missing, empty, or
    whitespace-only — the one check every write endpoint shares."""
    if title is None:
        return None
    trimmed = title.strip()
    return trimmed if trimmed else None


@app.post("/tasks", status_code=201)
def create_task(body: TaskCreate):
    """Creates a task from {"title": "..."}. Rejects a missing/empty/
    whitespace-only title with 400. The id is assigned by SQLite, not by
    counting rows in Python."""
    title = clean_title(body.title)
    if title is None:
        raise HTTPException(status_code=400, detail="title is required and cannot be empty")
    with get_db() as conn:
        cursor = conn.execute(
            "INSERT INTO tasks (title, done) VALUES (?, ?)", (title, 0)
        )
        new_row = conn.execute(
            "SELECT * FROM tasks WHERE id = ?", (cursor.lastrowid,)
        ).fetchone()
    return row_to_task(new_row)


class TaskUpdate(BaseModel):
    # Both optional: PUT here means "replace title and/or done with what's
    # given," not "you must resend every field." title, if given at all,
    # still has to pass the same non-empty rule as create.
    title: Optional[str] = None
    done: Optional[bool] = None


@app.put("/tasks/{task_id}")
def update_task(task_id: int, body: TaskUpdate):
    """Updates a task's title and/or done. 404 if unknown id, 400 if the
    body is empty or the title is invalid."""
    if body.title is None and body.done is None:
        raise HTTPException(status_code=400, detail="provide title and/or done to update")

    with get_db() as conn:
        row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

        new_title = row["title"]
        if body.title is not None:
            cleaned = clean_title(body.title)
            if cleaned is None:
                raise HTTPException(status_code=400, detail="title cannot be empty")
            new_title = cleaned

        new_done = row["done"] if body.done is None else (1 if body.done else 0)

        conn.execute(
            "UPDATE tasks SET title = ?, done = ?, updated_at = datetime('now') WHERE id = ?",
            (new_title, new_done, task_id),
        )
        updated = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    return row_to_task(updated)


@app.delete("/tasks/{task_id}", status_code=204)
def delete_task(task_id: int):
    """Removes a task. 204 with no body on success, 404 if unknown id."""
    with get_db() as conn:
        row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
        conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
