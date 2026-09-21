from fastapi import FastAPI

app = FastAPI(
    title="Task API",
    version="1.0",
    description="A small in-memory CRUD API for managing a to-do list.",
)


@app.get("/")
def root():
    """Describes this API: its name, version, and top-level endpoints."""
    return {"name": "Task API", "version": "1.0", "endpoints": ["/tasks"]}


@app.get("/health")
def health():
    """Liveness check — used to confirm the server is up and responding."""
    return {"status": "ok"}
