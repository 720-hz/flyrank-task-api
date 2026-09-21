Build a REST API in Python using FastAPI for managing a simple to-do list of
tasks. Store the tasks in memory (a plain Python list) — no database, and it's
fine if the data resets when the server restarts. Seed it with 3 example
tasks so it's not empty on startup.

Endpoints:
- GET / — basic info about the API (name, version)
- GET /health — a simple liveness check, returns something like {"status": "ok"}
- GET /tasks — list all tasks
- GET /tasks/{id} — get one task by id, 404 if it doesn't exist
- POST /tasks — create a task from a JSON body with a "title" field. Return
  201 on success. Return 400 if the title is missing or empty.
- PUT /tasks/{id} — update a task's title and/or done status. 404 if the id
  doesn't exist.
- DELETE /tasks/{id} — delete a task. 404 if it doesn't exist, otherwise 204
  with no response body.

Errors should come back as JSON shaped like {"error": "some message"} — not
FastAPI's default {"detail": "..."} shape.

Give me interactive Swagger docs too (FastAPI provides this for free at
/docs, so that should just work).

Please put it all in a single main.py file, using FastAPI + Pydantic +
uvicorn.
