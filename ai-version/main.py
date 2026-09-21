from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel

app = FastAPI(title="Task API", version="1.0")

tasks = [
    {"id": 1, "title": "Buy milk", "done": False},
    {"id": 2, "title": "Write README", "done": False},
    {"id": 3, "title": "Push to GitHub", "done": True},
]


class TaskCreate(BaseModel):
    title: Optional[str] = None


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    done: Optional[bool] = None


class TaskOut(BaseModel):
    id: int
    title: str
    done: bool


def next_id() -> int:
    return max((t["id"] for t in tasks), default=0) + 1


def clean_title(title: Optional[str]) -> Optional[str]:
    """Returns the trimmed title, or None if missing/empty/whitespace-only."""
    if title is None:
        return None
    trimmed = title.strip()
    return trimmed if trimmed else None


@app.exception_handler(HTTPException)
def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(status_code=exc.status_code, content={"error": exc.detail})


@app.exception_handler(RequestValidationError)
def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(status_code=422, content={"error": exc.errors()[0]["msg"]})


@app.get("/")
def root():
    return {"name": "Task API", "version": "1.0"}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/tasks", response_model=list[TaskOut])
def get_tasks():
    return tasks


@app.get("/tasks/{task_id}", response_model=TaskOut)
def get_task(task_id: int):
    for task in tasks:
        if task["id"] == task_id:
            return task
    raise HTTPException(status_code=404, detail="Task not found")


@app.post("/tasks", status_code=201, response_model=TaskOut)
def create_task(task: TaskCreate):
    title = clean_title(task.title)
    if title is None:
        raise HTTPException(status_code=400, detail="Title is required")
    new_task = {"id": next_id(), "title": title, "done": False}
    tasks.append(new_task)
    return new_task


@app.put("/tasks/{task_id}", response_model=TaskOut)
def update_task(task_id: int, update: TaskUpdate):
    if update.title is None and update.done is None:
        raise HTTPException(status_code=400, detail="Provide title and/or done to update")
    for task in tasks:
        if task["id"] == task_id:
            if update.title is not None:
                title = clean_title(update.title)
                if title is None:
                    raise HTTPException(status_code=400, detail="Title cannot be empty")
                task["title"] = title
            if update.done is not None:
                task["done"] = update.done
            return task
    raise HTTPException(status_code=404, detail="Task not found")


@app.delete("/tasks/{task_id}", status_code=204)
def delete_task(task_id: int):
    for i, task in enumerate(tasks):
        if task["id"] == task_id:
            tasks.pop(i)
            return
    raise HTTPException(status_code=404, detail="Task not found")
