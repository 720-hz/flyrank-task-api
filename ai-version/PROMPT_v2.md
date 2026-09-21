Build a REST API in Python using FastAPI for managing a simple to-do list of
tasks. Store the tasks in memory (a plain Python list) — no database, and
it's fine if the data resets when the server restarts. Seed it with 3
example tasks so it's not empty on startup.

Endpoints:
- GET / — basic info about the API (name, version)
- GET /health — a simple liveness check, returns something like {"status": "ok"}
- GET /tasks — list all tasks
- GET /tasks/{id} — get one task by id, 404 if it doesn't exist
- POST /tasks — create a task from a JSON body with a "title" field. Return
  201 on success.
- PUT /tasks/{id} — update a task's title and/or done status. 404 if the id
  doesn't exist.
- DELETE /tasks/{id} — delete a task. 404 if it doesn't exist, otherwise 204
  with no response body.

Validation (be strict about this):
- A task's title is invalid if it is missing, an empty string, or contains
  only whitespace — after trimming. Reject all three cases the same way,
  with a 400, not FastAPI's automatic 422. That means: do NOT declare
  `title: str` as a required Pydantic field, because a missing key will
  trigger Pydantic's own 422 before your code ever runs. Make the field
  Optional in the model and check it yourself.
- On PUT, the body must include at least one of "title" or "done" — reject
  a body with neither (e.g. `{}`) with a 400. If "title" is given, it must
  pass the same non-empty/non-whitespace rule as POST.
- Task ids must never be reused or collide, even after deletions. Do not
  derive a new id from `len(tasks)`. Compute it from the current maximum id
  in the list instead.

Error format:
- ALL errors — including your own 400s/404s AND FastAPI/Pydantic's built-in
  422 validation errors — must come back as JSON shaped like
  {"error": "some message"}. Register handlers for both HTTPException and
  RequestValidationError so nothing leaks through in FastAPI's default
  {"detail": ...} shape.

Give me interactive Swagger docs too (FastAPI provides this for free at
/docs). Use response_model typing on the read/write endpoints so Swagger
shows a concrete task schema, not just "any."

Please put it all in a single main.py file, using FastAPI + Pydantic +
uvicorn.
