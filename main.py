from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

import cache
import db

app = FastAPI(
    title="Task API",
    version="1.0",
    description="A small CRUD API for managing a to-do list, backed by Postgres.",
)


@app.on_event("startup")
def on_startup():
    db.init_db()
    # Stretch goal: prove the app can reach Redis too, ahead of actually
    # using it as a cache in W4. Never blocks startup — an unreachable
    # Redis is worth logging, not worth refusing to serve /tasks over.
    print(f"Redis ping: {'ok' if cache.ping() else 'unreachable'}")


# FastAPI's default error body is {"detail": "..."}. The assignment spec
# wants {"error": "..."} instead, so every raise HTTPException(...) below
# comes out shaped the way the checkpoint curls expect.
@app.exception_handler(HTTPException)
def error_shape_handler(request: Request, exc: HTTPException):
    return JSONResponse(status_code=exc.status_code, content={"error": exc.detail})


def row_to_task(row: dict) -> dict:
    """db.py already hands back real bool/int types (psycopg maps Postgres'
    BOOLEAN straight to Python bool) — this just narrows the row down to the
    three fields the API contract promises, dropping created_at/updated_at."""
    return {"id": row["id"], "title": row["title"], "done": bool(row["done"])}


@app.get("/")
def root():
    """Describes this API: its name, version, and top-level endpoints."""
    return {"name": "Task API", "version": "1.0", "endpoints": ["/tasks"]}


@app.get("/health")
def health():
    """Liveness check — used to confirm the server is up and responding.
    Also reports Redis reachability (the stretch-goal ping) alongside the
    main {"status": "ok"} the assignment asks for; Redis being down never
    changes this endpoint's own 200."""
    return {"status": "ok", "redis": "ok" if cache.ping() else "unreachable"}


@app.get("/tasks")
def list_tasks(
    search: Optional[str] = None,
    done: Optional[bool] = None,
    sort: Optional[str] = None,
):
    """Returns every task, filtered by ?search= / ?done= and ordered by
    ?sort=title (default: insertion order, i.e. by id)."""
    rows = db.list_tasks(search=search, done=done, sort=sort)
    return [row_to_task(row) for row in rows]


@app.get("/stats")
def stats():
    """Task counts, computed by Postgres' own COUNT(), not by looping over
    rows in Python. Stage 3: reads from db.py."""
    return db.stats()


@app.get("/tasks/{task_id}")
def get_task(task_id: int):
    """Returns a single task by id, or 404 if no task has that id."""
    row = db.get_task(task_id)
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
    whitespace-only title with 400. The id is assigned by Postgres (SERIAL),
    not by counting rows in Python. Stage 3: writes through db.py."""
    title = clean_title(body.title)
    if title is None:
        raise HTTPException(status_code=400, detail="title is required and cannot be empty")
    new_row = db.create_task(title)
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
    body is empty or the title is invalid. Stage 3: writes through db.py."""
    if body.title is None and body.done is None:
        raise HTTPException(status_code=400, detail="provide title and/or done to update")

    cleaned_title = None
    if body.title is not None:
        cleaned_title = clean_title(body.title)
        if cleaned_title is None:
            raise HTTPException(status_code=400, detail="title cannot be empty")

    updated = db.update_task(task_id, title=cleaned_title, done=body.done)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    return row_to_task(updated)


@app.delete("/tasks/{task_id}", status_code=204)
def delete_task(task_id: int):
    """Removes a task. 204 with no body on success, 404 if unknown id.
    Stage 3: writes through db.py."""
    deleted = db.delete_task(task_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
