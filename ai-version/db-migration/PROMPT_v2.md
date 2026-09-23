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
  codes as the in-memory version: 400 for a missing, empty, OR
  whitespace-only title (never let a bad request reach the database),
  404 for an unknown id.

Four things that matter specifically because this is SQLite behind
FastAPI, not a plain script:

1. FastAPI runs a synchronous `def` endpoint in a worker thread pool, not
   on the main thread. A single sqlite3 connection created once at import
   time and reused across requests will raise "SQLite objects created in
   a thread can only be used in that same thread" as soon as two requests
   land on different threads. Open a new connection per request (e.g. a
   context manager), not one shared global connection.
2. Use `id INTEGER PRIMARY KEY AUTOINCREMENT`, not bare
   `INTEGER PRIMARY KEY`. Without AUTOINCREMENT, once every row is
   deleted, SQLite restarts numbering from 1 and will hand out an id a
   client may already have seen and cached.
3. SQLite has no real boolean type — `done` is stored and read back as
   the integer 0 or 1. Cast it to a Python `bool` before returning it, so
   the JSON response has `"done": true`/`false`, exactly like the
   in-memory version, not `"done": 0`/`1`.
4. A title of `"   "` must be rejected the same as `""` — trim it before
   checking, not just `if not title`.

Here is the existing main.py: [pasted the current ai-version/main.py from
Stage 7 — the in-memory version, already fixed up after the first AI vs
me rematch]

Give me the whole updated main.py.
