# Task API

A small CRUD API for managing a to-do list, built with **FastAPI** and backed by **SQLite**. This started as Week 2 · Assignment 1 ("Build your first CRUD API") of the FlyRank AI Internship, backend track, and continues with Week 3 · Assignment 1 ("Connecting your CRUD to the database").

Tasks used to live in a plain Python list in memory — every restart wiped them. They now live in a single file, `tasks.db`, managed with Python's built-in `sqlite3` module. The point of this stage isn't a new feature: the URLs, request bodies, status codes, and response shapes are all identical to Assignment 1. Only what's *behind* the API changed — persistence turned out to be an implementation detail, not a change to the contract clients rely on.

## Install and run

```bash
pip install -r requirements.txt && uvicorn main:app --reload
```

The server comes up on `http://127.0.0.1:8000`. `tasks.db` is created automatically, next to `main.py`, the first time the app starts — there's nothing to install or configure, and nothing to run in the background. Interactive Swagger docs are at `http://127.0.0.1:8000/docs` — every endpoint below can be exercised there with "Try it out," no `curl` required.

## Endpoints

| Method | Path            | Description                                                        | Success | Errors                          |
|--------|-----------------|---------------------------------------------------------------------|---------|----------------------------------|
| GET    | `/`             | API name, version, and top-level endpoints                          | 200     | —                                |
| GET    | `/health`       | Liveness check                                                       | 200     | —                                |
| GET    | `/tasks`        | List tasks, optionally filtered/sorted (`?search=`, `?done=`, `?sort=title`) | 200     | —                                |
| GET    | `/stats`        | Task counts: `{"total", "done", "open"}`                             | 200     | —                                |
| POST   | `/tasks`        | Create a task from `{"title": "..."}`                                | 201     | 400 missing/empty title          |
| GET    | `/tasks/{id}`   | Get one task by id                                                    | 200     | 404 unknown id                   |
| PUT    | `/tasks/{id}`   | Update a task's `title` and/or `done`                                 | 200     | 404 unknown id, 400 invalid body |
| DELETE | `/tasks/{id}`   | Delete a task                                                          | 204     | 404 unknown id                   |

Every error still comes back shaped as `{"error": "..."}` — that remapping didn't change when the storage layer did.

## Example

```
$ curl -i -X POST http://127.0.0.1:8000/tasks -H "Content-Type: application/json" -d '{"title": "Write the README"}'

HTTP/1.1 201 Created
date: Mon, 21 Sep 2026 18:43:23 GMT
server: uvicorn
content-length: 48
content-type: application/json

{"id":4,"title":"Write the README","done":false}
```

## Database

**Why SQLite.** The assignment's own framing is the reason: SQLite needs no separate server process, no install step, and no configuration — it's a single file that Python's standard library already knows how to talk to. For an API this size, reaching for Postgres or MySQL would mean standing up infrastructure to solve a problem SQLite already solves in one line (`sqlite3.connect("tasks.db")`). The same `sqlite3` module choice (over an ORM like SQLModel) keeps the codebase in the same "one file, on purpose" spirit as Assignment 1 — the SQL is written out directly, so what the database is doing is never hidden behind an abstraction layer.

**Where the data lives.** `tasks.db` sits next to `main.py` in the project root. It's gitignored (see [Project layout](#project-layout) below) — every clone creates its own copy the first time the app starts, and `CREATE TABLE IF NOT EXISTS` plus a seed-only-if-empty check mean that's always safe, even across dozens of restarts.

**Run it.** Same command as always: `uvicorn main:app --reload`. The first request or startup event creates the table and seeds three example tasks; every request after that just reads and writes the same file.

**One example query.** Stage 4 asked for manual exploration with a SQLite viewer. This sandbox couldn't install one (no `sqlite3` CLI or GUI browser available — see the note under the image below), so the same required queries were run through Python's `sqlite3` module directly against the live `tasks.db`, and `GET /tasks` was called before and after each one to confirm the API reflected the change immediately, with no restart:

```sql
UPDATE tasks SET done = 1;
-- 3 rows affected
```

![Terminal output of the five required Stage 4 SQL queries run against tasks.db](docs/stage4-sql.png)

*No CLI/GUI SQLite viewer was installable in this environment, so the same five queries DB Browser for SQLite would run (`SELECT * FROM tasks`, `SELECT * FROM tasks WHERE done = 1`, `SELECT COUNT(*) FROM tasks`, `UPDATE tasks SET done = 1`, `DELETE FROM tasks WHERE done = 1`) were run for real through Python's `sqlite3` module against the actual `tasks.db` — this is that real output, not a mockup.*

## Extras implemented

All optional from the assignment's "★ Optional extras" list:

- **`?search=`** — `GET /tasks?search=milk` filters with SQL's `LIKE` and `%...%` wildcarding (contains, not just starts-with).
- **`?done=`** — `GET /tasks?done=true` filters with a `WHERE done = ?` clause.
- **`?sort=title`** — orders results alphabetically instead of by insertion order (`id`).
- **`GET /stats`** — returns `{"total", "done", "open"}` computed with two `SELECT COUNT(*)` queries, not by looping over rows in Python.
- **Timestamps** — every task carries `created_at` and `updated_at` (`TEXT`, defaulting to `datetime('now')`); `updated_at` is bumped on every `PUT`, verified by updating a task and diffing the two timestamps.

Two more, not on the assignment's list but a natural fit once the schema existed:

- **An index on `title`** (`CREATE INDEX IF NOT EXISTS idx_tasks_title ON tasks(title)`) backs `?search=` and `?sort=title` — without it, both would scan every row; with it, SQLite can look titles up the way a book's index beats reading every page.
- **Transactional seeding** — the three seed rows share `init_db()`'s single connection and its one `commit()` call (see `get_db()` in `main.py`), so they're inserted as one all-or-nothing transaction. Ending up with zero seed rows is fine; ending up with two out of three, silently, because a hypothetical third insert failed midway, is exactly the kind of half-written state a transaction rules out.

## Swagger UI

Run the server and open `/docs` to see the live, interactive Swagger UI for every endpoint above (a static screenshot of it was captured during development as part of this stage's verification).

## Project layout

```
main.py                the whole API — one file, on purpose, for something this size
requirements.txt       pinned dependency versions
tasks.db                SQLite database file — gitignored, created automatically on first run
.gitignore              Python/venv noise plus *.db and server*.log kept out of the repo
docs/                    screenshot(s) used in this README
ai-version/              Stage 7 (W2) — an AI-generated build of the in-memory API, kept
                         separate from the hand-built submission (see "AI vs me: the CRUD build")
ai-version/db-migration/ Stage 6 (W3) — an AI-generated migration to SQLite, kept separate
                         from the hand-built migration in main.py (see "AI vs me: the database
                         migration")
```

## AI vs me: the CRUD build

Stage 7 of Assignment 1: write a prompt from memory (no copying from the spec), have an AI generate the same API from it, then actually run both and compare. Everything below is real — I ran the AI's code, hit it with the same checkpoint `curl`s used to build Stages 0–4, and reported what actually happened, not what I expected to happen.

### The prompt (first attempt)

```
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
```

The generated code lives in [`ai-version/main_v1.py`](ai-version/main_v1.py). I ran it on a second port next to my own server and fired the same kind of checkpoint requests at it.

### What the AI did better

It added `response_model=TaskOut` (a real Pydantic model with typed `id`/`title`/`done` fields) on the read/create/update endpoints. My hand-built version just returns raw dicts, so its `/openapi.json` shows the `GET /tasks` response schema as an untyped `{}`. The AI's version shows a concrete, named `TaskOut` schema in Swagger — genuinely better API documentation than what I wrote by hand, and something my prompt never even asked for.

### What it got wrong or quietly ignored

- **A missing `title` key returned FastAPI's default `422`, not the `400 {"error": ...}` I asked for.** It declared `title: str` as a *required* Pydantic field, so `POST /tasks` with body `{}` never even reaches its own validation code — Pydantic rejects it first, with `{"detail": [...]}`. This is exactly the trap Stage 3 of my own build was designed to avoid (that's why my `TaskCreate.title` is `Optional`, with the empty-check done by hand).
- **A whitespace-only title (`"   "`) was silently accepted as valid**, creating a task with a blank-looking title and a `201`. My prompt said "missing or empty" — I never said "or whitespace," and the AI took that literally: `if not task.title` is `False` for `"   "`, so it sailed right through.
- **`PUT /tasks/{id}` with an empty body (`{}`) returned `200` and silently no-op'd** instead of the `400` my own spec requires. Same story for a `PUT` with `{"title": ""}` — it wrote the empty string straight into the task with no complaint.
- **Task ids can collide.** It computed new ids as `len(tasks) + 1`. Create a task, delete an earlier one, create another — `len(tasks) + 1` can land on an id that already exists elsewhere in the list. I reproduced this directly: after a delete-then-create sequence, the task list ended up with *two* entries carrying `id: 5`, and only the first one is reachable by `GET/PUT/DELETE /tasks/5` — the second is permanently stuck, invisible to every by-id operation. That's a real data-integrity bug, not a style nitpick.

### What my prompt forgot to specify

- Exact id-generation strategy — I just said tasks need ids; the AI silently picked `len(tasks) + 1`, which is the classic in-memory-list mistake.
- Whether whitespace-only counts as "empty" — I only said "missing or empty," so the AI reasonably (if unhelpfully) treated `"   "` as present.
- Whether `PUT` requires at least one field — I never said what an empty update body should do, so it silently decided "do nothing, return `200`" was fine.
- The exact wording of error messages — I only specified the JSON shape, not the text, so the AI picked its own (`"Title is required"` vs. my `"title is required and cannot be empty"`).
- Response typing for Swagger — I didn't ask for typed response models at all; the AI added them on its own initiative, and it was the right call.

### The rematch

Second prompt, same structure, but with the four gaps above closed explicitly — see [`ai-version/PROMPT_v2.md`](ai-version/PROMPT_v2.md) for the full text; the key additions were: spelling out that missing/empty/whitespace-only titles must *all* return `400` (never Pydantic's automatic `422`, and naming exactly why — a required `str` field triggers it before your own code runs), that `PUT` must reject a body with neither field set, and that ids must come from `max(id) + 1`, never `len(tasks)`.

Regenerated as [`ai-version/main.py`](ai-version/main.py) and re-ran every checkpoint that failed the first time: missing-title now returns a clean `400`, whitespace-only titles are rejected, an empty `PUT` body returns `400`, and the delete-then-create sequence that previously produced a duplicate `id: 5` now increments cleanly with no collisions — one prompt revision fixed all four issues found in the first pass.

## AI vs me: the database migration

Stage 6 of Assignment 2 (the bonus): same exercise, this time for the in-memory → SQLite migration specifically. I wrote a fresh prompt from memory, handed it the fixed-up in-memory `main.py` from the rematch above, generated a migration, ran it, and compared it against the hand-built `main.py` at the root of this repo.

### The prompt (first attempt)

```
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

Here is the existing main.py: [pasted ai-version/main.py from Stage 7]

Give me the whole updated main.py.
```

Full text in [`ai-version/db-migration/PROMPT_v1.md`](ai-version/db-migration/PROMPT_v1.md); generated code in [`ai-version/db-migration/main_v1.py`](ai-version/db-migration/main_v1.py). I ran it on port 8001 and hit it with real `curl` requests, and separately exercised its exact schema/serialization choices in isolated Python scripts where the live server couldn't get far enough to show them.

### What it got wrong

- **Every endpoint that touched the database crashed with a `500`.** It created one `sqlite3` connection at import time and reused it for every request. FastAPI runs synchronous endpoint functions in a worker thread pool, not the main thread, and `sqlite3` connections refuse to be used outside the thread that created them: `SQLite objects created in a thread can only be used in that same thread`. `GET /` and `GET /health` (no database access) worked fine, which made this worse, not better — a quick smoke test would look healthy right up until the first real request to `/tasks`. I confirmed this live: five back-to-back `GET /tasks` calls, five `500`s.
- **Task ids can be reused.** It declared the primary key as plain `id INTEGER PRIMARY KEY`, not `AUTOINCREMENT`. I emptied the table completely (mirroring Stage 4's own `DELETE FROM tasks WHERE done = 1` after marking everything done) and created a new task — SQLite handed it back `id: 1`, the same id the very first seed task had. A client that cached `id: 1` from the original seed data would now be looking at a completely different task.
- **`done` came back as `0`/`1`, not `true`/`false`.** SQLite has no native boolean column type; it stores `done` as an integer either way. The in-memory version always serialized real Python `bool`s. Without an explicit cast, `dict(row)` passed the raw SQLite integer straight into the JSON response — a client checking `if (task.done)` in JavaScript still works by accident, but `task.done === true` silently breaks.
- **The whitespace-only-title gap from the first AI vs me round came back, worse.** My prompt only said "missing or empty," so `"   "` still isn't caught by `if not body.title`. In the in-memory version this produced a wrong-but-visible `201` with a blank task. Here, the bad title cleared validation and then hit the same broken database connection as everything else — so instead of a data-quality bug, it's now an availability bug: a `500` instead of a silently-created task.

### What my prompt forgot to specify

- That FastAPI's threadpool execution model means a single reused SQL connection isn't just inefficient, it's actively broken — I assumed "use sqlite3" was enough context; it isn't, unless you also know FastAPI won't run your `def` endpoint on the thread that created the connection.
- That "id" needs the same non-reuse guarantee across a full table wipe, not just across ordinary deletes — I only said "keep the same behavior," which doesn't obviously extend to "never had this failure mode before, in-memory ids were `max()+1` computed fresh every time."
- That SQLite's lack of a real boolean type needs an explicit cast on the way out — I said "keep exactly the same response shape" but didn't spell out *why* that's not automatic once the backing store is SQLite instead of Python objects.
- I repeated the same whitespace gap from the first prompt instead of learning from it — carrying a closed gap forward into a new prompt is its own mistake, not just the AI's.

### The rematch

Second prompt — see [`ai-version/db-migration/PROMPT_v2.md`](ai-version/db-migration/PROMPT_v2.md) — added four explicit requirements: open a new connection per request instead of one shared global connection (with the exact exception message named, so the "why" isn't lost); use `INTEGER PRIMARY KEY AUTOINCREMENT`, not bare `INTEGER PRIMARY KEY`; cast `done` to `bool` before returning it; and trim titles before the empty check, so whitespace-only is rejected too.

Regenerated as [`ai-version/db-migration/main.py`](ai-version/db-migration/main.py) and re-verified all four: five consecutive `GET /tasks` calls now all return `200`, `done` serializes as `true`/`false`, a whitespace-only title returns a clean `400` instead of a `500`, and deleting every row and creating a new task now returns `id: 4` — continuing on, never reusing `id: 1`.

## Development history

This repo's commit history is deliberately staged, one checkpoint at a time, mirroring how the API was actually built:

**Assignment 1 — the CRUD API (in-memory)**

1. **Stage 0** — a bare "hello world" server, just to prove FastAPI and uvicorn were wired up.
2. **Stage 1** — `/` and `/health`, the two endpoints with no state behind them.
3. **Stage 2** — the in-memory task list plus the two read endpoints (`GET /tasks`, `GET /tasks/{id}`), including the 404 case.
4. **Stage 3** — `POST /tasks` with hand-written validation instead of relying on Pydantic's automatic rejection, so a bad request comes back as the spec's `400 {"error": ...}` rather than FastAPI's default `422`.
5. **Stage 4** — `PUT /tasks/{id}` and `DELETE /tasks/{id}`, completing full CRUD.
6. **Stage 5/6** — Swagger verification and this README.
7. **Stage 7 (bonus)** — an AI-generated rematch of the same API, kept in `ai-version/` and compared against the hand-built version above; see "AI vs me: the CRUD build."  

**Assignment 2 — connecting the CRUD to SQLite**

8. **Stage 0** — created `tasks.db`, the `tasks` table, and seed-once logic in place of the in-memory list.
9. **Stage 1** — `GET /tasks` and `GET /tasks/{id}` reading from SQLite via parameterized queries.
10. **Stage 2** — `POST /tasks` inserting a row; verified data survives a server restart for the first time.
11. **Stage 3** — `PUT /tasks/{id}` and `DELETE /tasks/{id}` reimplemented in SQL.
12. **Stage 4** — manually ran the five required SQL queries against the live database and confirmed the API reflected each change with no restart; documented in "Database" above.
13. **Stage 5** — this README's database documentation.
14. **Extras** — `?search=`, `?done=`, `?sort=title`, `GET /stats`, `created_at`/`updated_at` timestamps, an index on `title`, and transactional seeding.
15. **Stage 6 (bonus)** — an AI-generated rematch of the SQLite migration, kept in `ai-version/db-migration/` and compared against the hand-built migration above; see "AI vs me: the database migration."
