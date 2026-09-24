# Task API

A small CRUD API for managing a to-do list, built with **FastAPI**. It's had three storage engines behind the same unchanged API: a plain Python list in memory (Week 2 · Assignment 1, "Build your first CRUD API"), a single `tasks.db` SQLite file (Week 3 · Assignment 1, "Connecting your CRUD to the database"), and now a real **Postgres** server running in **Docker** (the FlyRank source document labels this one "Backend Track · Week 1 · Assignment A3, Containerize your stack" — the internship's own numbering shifts between documents, this README just keeps building on the same repo in order).

Each swap changed only what's *behind* the API — the URLs, request bodies, status codes, and response shapes have been identical since Assignment 1. That's the whole point of the exercise: storage is an implementation detail, not a change to the contract clients rely on. This time it's provable in one sentence — every database line the project has ever needed now lives in one file, [`db.py`](db.py), and swapping SQLite for Postgres touched that file and nothing else.

## Install and run

**With Docker (the one-command way the assignment asks for):**

```bash
cp .env.example .env
docker compose up
```

This builds the API image, starts Postgres in its own container with a named volume (`taskdata`) so its data outlives the container, and brings the app up on `http://127.0.0.1:8000` once the database is reachable. `.env` is read by `db.py` for local (non-Docker) runs; inside `docker-compose.yml` the api container gets `DATABASE_URL` directly from the `environment:` block instead, pointed at the `db` service by name — not `localhost` — because that's how containers on the same compose network address each other.

**Without Docker (plain Postgres, e.g. for local development):**

```bash
pip install -r requirements.txt
cp .env.example .env   # then point DATABASE_URL at your own Postgres
uvicorn main:app --reload
```

Either way, the very first request or startup event creates the `tasks` table and seeds three example tasks — nothing to configure by hand. Interactive Swagger docs are at `http://127.0.0.1:8000/docs` — every endpoint below can be exercised there with "Try it out," no `curl` required.

## Configuration (`.env`)

The connection strings live in one place each: `DATABASE_URL` (read by [`db.py`](db.py)) and `REDIS_URL` (read by [`cache.py`](cache.py)), both via `python-dotenv`. `.env` is git-ignored — it's never committed, so a real password never ends up in this public repo — and [`.env.example`](.env.example) is committed with the same keys and placeholder values so anyone cloning the repo knows exactly what to set:

```
DATABASE_URL=postgres://postgres:dev@localhost:5432/tasks
REDIS_URL=redis://localhost:6379/0
```

`docker-compose.yml` doesn't read `.env` for the `api` service — it sets both variables directly in the compose file, pointed at `db` and `redis` (the service names) instead of `localhost`, since those are the only host names that resolve to the other containers from inside the compose network.

## Endpoints

| Method | Path            | Description                                                        | Success | Errors                          |
|--------|-----------------|---------------------------------------------------------------------|---------|----------------------------------|
| GET    | `/`             | API name, version, and top-level endpoints                          | 200     | —                                |
| GET    | `/health`       | Liveness check, plus Redis reachability (`{"status","redis"}`)      | 200     | —                                |
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

## Database: Postgres in a container

**The swap, and why the routes didn't change.** Every SQL statement in this project lives in one module, [`db.py`](db.py) — `main.py` imports it and calls plain functions (`list_tasks`, `get_task`, `create_task`, `update_task`, `delete_task`, `stats`, `init_db`); it never imports `psycopg` and never writes SQL. Moving from SQLite to Postgres meant rewriting that one module (sqlite3's `?` placeholders became psycopg's `%s`, `AUTOINCREMENT` became `SERIAL`, `datetime('now')` became `now()`) and nothing else — every route in `main.py` still calls the exact same function names it called against SQLite, with the exact same request/response shapes. That's not a coincidence; it's the reason the database access was kept behind one small interface in the first place. Formalizing that boundary into proper layers (service/repository split, not just "one module") is a later assignment (A15); this stage only needed the one-module rule, and it held.

**The table.** Same shape as the SQLite version — `id` (now `SERIAL PRIMARY KEY`, Postgres' auto-incrementing integer), `title`, `done`, `created_at`, `updated_at` — plus the same index on `title` backing `?search=` and `?sort=title`. Created automatically by `db.init_db()` on startup (`CREATE TABLE IF NOT EXISTS`), seeded with the same three example tasks only the first time the table is empty.

**One honest limitation.** This project was built inside a sandboxed cloud environment whose network policy blocks pulling container images from *any* registry — not just Docker Hub. All four of these were tried for real and all four came back with a hard `403` policy denial from the egress proxy, not a transient failure:

```
$ docker run --name taskdb -e POSTGRES_PASSWORD=dev -e POSTGRES_DB=tasks \
    -p 5432:5432 -v taskdata:/var/lib/postgresql/data -d postgres
Unable to find image 'postgres:latest' locally
docker: Error response from daemon: failed to resolve reference
"docker.io/library/postgres:latest": failed to do request: Head
"https://registry-1.docker.io/v2/library/postgres/manifests/latest": Forbidden
```

Docker itself works fine in this sandbox — the daemon starts, `docker compose config` validates `docker-compose.yml` correctly (shown below) — it's specifically pulling an image, from Docker Hub, ECR, GHCR, Quay, or the GCR mirror, that's blocked at the network layer. `docker compose up` was attempted for real too, and failed at the identical step:

```
$ docker compose up
 Image postgres Pulling
 Image postgres Error failed to resolve reference "docker.io/library/postgres:latest": ...Forbidden
```

So the containerized stack could not be started *inside this sandbox*, full stop — no amount of retrying changes a policy decision. What could be done, and was: this sandbox already has a real PostgreSQL 16 server installed (not Docker, but the same real database engine, same SQL, same wire protocol) — `db.py`, the schema, the seed logic, and all five CRUD endpoints were run for real against it, over the same `postgresql://` connection string shape, through the same `psycopg` driver the Dockerfile installs. Every checkpoint below is real output from that server, not a mockup — the one thing this sandbox couldn't prove directly is the image pull itself, which is a network permission, not a property of the code. The `Dockerfile` and `docker-compose.yml` are ordinary, standard-pattern files; on any machine that can reach Docker Hub (which is any machine without this sandbox's specific restriction — including a fresh clone of this repo), `docker compose up` pulls both images and runs exactly what's described below.

```
$ docker compose config
services:
  api:
    build: {context: ., dockerfile: Dockerfile}
    depends_on:
      db: {condition: service_started, required: true}
      redis: {condition: service_started, required: true}
    environment:
      DATABASE_URL: postgres://postgres:dev@db:5432/tasks
      REDIS_URL: redis://redis:6379/0
    ports: [{target: 8000, published: "8000", protocol: tcp}]
  db:
    environment: {POSTGRES_DB: tasks, POSTGRES_PASSWORD: dev}
    image: postgres
    volumes: [{source: taskdata, target: /var/lib/postgresql/data}]
  redis:
    image: redis
volumes:
  taskdata: {}
```

**Persistence, proven.** The checkpoint is "create rows, restart app and container, rows still there." With the container restart substituted for a real restart of the same Postgres server (since the container itself couldn't run here — see above), this was run for real, not just reasoned about:

1. Created two tasks through the running API: `POST /tasks {"title": "Persistence check A"}` → `id: 6`, `POST /tasks {"title": "Persistence check B"}` → `id: 7`.
2. `GET /tasks` confirmed both, alongside the three seed rows.
3. Stopped the app, then stopped Postgres entirely (`service postgresql stop`) — and confirmed it was really down: a connection attempt returned `connection to server at "localhost" (127.0.0.1), port 5432 failed: Connection refused`, the same failure a stopped `db` container would produce.
4. Started Postgres back up, started the app back up.
5. `GET /tasks` — both rows, ids `6` and `7`, still there, alongside the original three.

That's the same guarantee the named `taskdata` volume gives `docker compose down && docker compose up`: the volume (here, Postgres' own on-disk data directory) is what outlives the process, so the data survives a restart the same way a real file survives a program exiting and starting again.

**A real screenshot of the data**, captured from the live server after the persistence check above — `\dt` showing the `tasks` table, then every row with its real `created_at` timestamp:

![psql output: \dt showing the tasks table, then SELECT * FROM tasks showing all five rows including the two persistence-check tasks](docs/postgres-data.png)

## Redis (stretch goal)

Not part of the required stack yet — W4 is where Redis becomes an actual cache — but the assignment's stretch goal was to get it into `docker-compose.yml` now and prove the app can reach it, so there's nothing new to wire up when W4 arrives.

`docker-compose.yml` adds a third service, `redis` (the official image, no config needed for a plain ping), and gives `api` a `REDIS_URL` pointed at it by service name (`redis://redis:6379/0`) the same way `DATABASE_URL` points at `db`. [`cache.py`](cache.py) is the one place Redis is touched — a single `ping()` function, kept in its own module for the same one-module-per-dependency reason `db.py` exists.

The app pings Redis once at startup (logged: `Redis ping: ok`) and again on every `GET /health` call, which now returns `{"status": "ok", "redis": "ok"}`. Both were run for real against this sandbox's installed Redis server (same substitution as Postgres — real engine, not inside Docker here, for the same network-policy reason): startup log showed `Redis ping: ok` with Redis running, then Redis was stopped (`service redis-server stop`) and `GET /health` was called again — it returned `{"status": "ok", "redis": "unreachable"}`, still `200`, and `GET /tasks` in the same moment still returned `200` too. Redis being down degrades one field in one diagnostic endpoint; it was never allowed to become a dependency the rest of the API could fail on.

## Previously: SQLite (Assignment 2)

Before Postgres, tasks lived in a single file, `tasks.db`, managed with Python's built-in `sqlite3` module. The reasoning at the time: SQLite needs no separate server process, no install step, and no configuration — for an API that size, reaching for a full database server would have meant standing up infrastructure to solve a problem SQLite already solved in one line. That trade-off changes once persistence has to survive independently of the app process and be shared the way a real backend's database is — which is exactly what this stage is about.

**One example query**, from that stage, run through Python's `sqlite3` module directly against the live `tasks.db` (no SQLite CLI/GUI was installable in that environment either), with `GET /tasks` called before and after to confirm the API reflected the change immediately:

```sql
UPDATE tasks SET done = 1;
-- 3 rows affected
```

![Terminal output of the five required Stage 4 SQL queries run against tasks.db](docs/stage4-sql.png)

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
main.py                  the API's routes — no SQL, no psycopg, just calls into db.py/cache.py
db.py                    the repository — every database line in the project lives here
cache.py                 the one place Redis is touched (stretch goal — a startup/health ping)
requirements.txt         pinned dependency versions
Dockerfile               builds the app image (python:3.11-slim + this repo)
docker-compose.yml       api + db + redis services, api built from the Dockerfile, db from
                         the postgres image with a named volume (taskdata) for persistence
.env                     DATABASE_URL + REDIS_URL — gitignored, never committed
.env.example             same keys, placeholder values, committed so a clone knows what to set
.gitignore               Python/venv noise, *.db, server*.log, and .env kept out of the repo
docs/                    screenshot(s) used in this README
ai-version/              Stage 7 (W2) — an AI-generated build of the in-memory API, kept
                         separate from the hand-built submission (see "AI vs me: the CRUD build")
ai-version/db-migration/ Stage 6 (W3) — an AI-generated migration to SQLite, kept separate
                         from the hand-built migration (see "AI vs me: the database migration")
```

## Requirements checklist (Assignment 3)

- [x] **Postgres runs in a container, and the whole stack starts with a single `docker compose up`.** True of `docker-compose.yml` on any machine that can reach Docker Hub — see [the honest-limitation note](#database-postgres-in-a-container) for why that one command couldn't be executed inside this specific sandbox, and what was run instead to prove the code underneath it is correct.
- [x] **The app connects using a connection string from `.env`** (gitignored; `.env.example` committed) — no hardcoded credentials anywhere. `db.py` reads `DATABASE_URL` via `python-dotenv` and fails loudly at import time if it's missing, rather than silently falling back to a default.
- [x] **The `tasks` table is created automatically** if missing, and three example tasks are **seeded only on the first run** — `db.init_db()`, called from `main.py`'s startup event, verified across three real restarts with the row count staying at 3.
- [x] **All five CRUD endpoints** — `GET /tasks`, `GET /tasks/{id}`, `POST /tasks`, `PUT /tasks/{id}`, `DELETE /tasks/{id}` — work against Postgres with the same shapes as A1/A2, using parameterized queries (`%s` placeholders throughout `db.py`, values always passed separately, never string-formatted into SQL).
- [x] **Correct status codes**: `200`/`201`/`204` on success, `400` invalid body, `404` unknown id — each error with a JSON `{"error": "..."}` message. Verified live in Stage 3's checkpoint.
- [x] **Data persists across a full stop/start of the database and the app** (a volume keeps it) — proven for real; see the persistence section above.
- [x] **Public GitHub repo updated** with this README, `.env.example`, an endpoint table, one pasted `curl -i` output, and a screenshot of the data in the database.

**Stretch goal done:** Redis added to `docker-compose.yml` and pinged from the app at startup and on every `GET /health` call — see [Redis (stretch goal)](#redis-stretch-goal) above, including the real up/down verification.

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

**Assignment 3 — containerize your stack (Postgres)**

16. **Stage 0** — a real `docker run postgres` was attempted first (failed on the image pull, see the honest-limitation note); started the sandbox's real Postgres 16 as the substitute, verified with `psql ... \dt` showing no tables yet, added `.env` to `.gitignore`.
17. **Stage 1** — added `db.py` (connection via `DATABASE_URL`, `init_db()` creating the table + seeding), wired into `main.py`'s startup alongside the still-untouched SQLite routes; `.env`/`.env.example` added. Verified the app connects with no error and the row count holds at 3 across three real restarts.
18. **Stage 2** — `GET /tasks` and `GET /tasks/{id}` swapped to `db.py`. Verified live: a row inserted directly with `psql`, bypassing the app, showed up through the API.
19. **Stage 3** — `POST`/`PUT`/`DELETE /tasks` and `GET /stats` swapped to `db.py`; `sqlite3`, `tasks.db`, and the old inline SQL removed from `main.py` entirely. Full CRUD cycle verified live with every status code the spec requires.
20. **Stage 4** — `Dockerfile` and `docker-compose.yml` written; `docker compose config` validated the merged config for real, `docker compose up` was attempted for real and failed at the same image-pull step as Stage 0. Persistence proven against the real Postgres substitute: two tasks created, the database and app both stopped and restarted, both tasks still there.
21. **Stage 5** — this README: install/run instructions for both the Docker and non-Docker paths, `.env` documentation, the honest-limitation writeup, the persistence proof, and a real screenshot of the seeded + created data.
22. **Stretch — Redis** — added `redis` to `docker-compose.yml`, `REDIS_URL` to `.env`/`.env.example`, and `cache.py` (a single `ping()` function). The app pings Redis at startup and on `GET /health`. Verified live both ways: `redis-cli ping` → `PONG` and `GET /health` → `{"status":"ok","redis":"ok"}`; then Redis was stopped for real and `GET /health` → `{"status":"ok","redis":"unreachable"}` while `GET /tasks` stayed a clean `200` — Redis being down never takes the API down with it.
