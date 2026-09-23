Take this existing FastAPI to-do list API, currently storing tasks in a
Python list in memory, and change it to store tasks in a SQLite database
file called tasks.db instead. Use Python's built-in sqlite3 module.

Requirements:
- On startup, create a `tasks` table if it doesn't already exist, with
  columns `id`, `title`, `done`.
- Seed three example tasks the first time the database is created, but
  don't re-add them on every restart.
- Every endpoint (GET /, GET /health, GET /tasks, GET /tasks/{id},
  POST /tasks, PUT /tasks/{id}, DELETE /tasks/{id}) should keep exactly
  the same request/response shape and status codes as before — only the
  storage layer changes.
- Use parameterized queries, not string formatting, for anything built
  from user input.
- Errors should still come back as {"error": "..."} with the same status
  codes as the in-memory version: 400 for a missing/empty title, 404 for
  an unknown id.

Here is the existing main.py: [pasted the current ai-version/main.py from
Stage 7 — the in-memory version, already fixed up after the first AI vs
me rematch]

Give me the whole updated main.py.
