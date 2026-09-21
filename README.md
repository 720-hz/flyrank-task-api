# Task API

A small in-memory CRUD API for managing a to-do list, built with **FastAPI**. This is Week 2 · Assignment 1 ("Build your first CRUD API") of the FlyRank AI Internship, backend track.

Tasks live in a plain Python list in memory — there is no database. That's intentional for this assignment: the point is REST semantics (methods, status codes, request/response shapes), not persistence. The API starts with three seed tasks and resets to them every time the server restarts.

## Install and run

```bash
pip install -r requirements.txt && uvicorn main:app --reload
```

The server comes up on `http://127.0.0.1:8000`. Interactive Swagger docs are at `http://127.0.0.1:8000/docs` — every endpoint below can be exercised there with "Try it out," no `curl` required.

## Endpoints

| Method | Path            | Description                                      | Success        | Errors                          |
|--------|-----------------|---------------------------------------------------|-----------------|----------------------------------|
| GET    | `/`             | API name, version, and top-level endpoints        | 200             | —                                |
| GET    | `/health`       | Liveness check                                     | 200             | —                                |
| GET    | `/tasks`        | List every task                                    | 200             | —                                |
| POST   | `/tasks`        | Create a task from `{"title": "..."}`              | 201             | 400 missing/empty title          |
| GET    | `/tasks/{id}`   | Get one task by id                                 | 200             | 404 unknown id                   |
| PUT    | `/tasks/{id}`   | Update a task's `title` and/or `done`              | 200             | 404 unknown id, 400 invalid body |
| DELETE | `/tasks/{id}`   | Delete a task                                      | 204             | 404 unknown id                   |

Every error comes back shaped as `{"error": "..."}` — FastAPI's default `{"detail": "..."}` is remapped globally so the shape is consistent across all four error cases above.

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

## Swagger UI

Run the server and open `/docs` to see the live, interactive Swagger UI for all seven endpoints (a static screenshot of it was captured during development as part of this stage's verification).

## Project layout

```
main.py             the whole API — one file, on purpose, for something this size
requirements.txt    pinned dependency versions
.gitignore          Python/venv noise kept out of the repo
ai-version/          Stage 7 — an AI-generated build of the same API, kept separate
                     from the hand-built submission above (see "AI vs me" below)
```

## AI vs me

Stage 7 of the assignment: write a prompt from memory (no copying from the spec), have an AI generate the same API from it, then actually run both and compare. Everything below is real — I ran the AI's code, hit it with the same checkpoint `curl`s used to build Stages 0–4, and reported what actually happened, not what I expected to happen.

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

## Development history

This repo's commit history is deliberately staged, one checkpoint at a time, mirroring how the API was actually built:

1. **Stage 0** — a bare "hello world" server, just to prove FastAPI and uvicorn were wired up.
2. **Stage 1** — `/` and `/health`, the two endpoints with no state behind them.
3. **Stage 2** — the in-memory task list plus the two read endpoints (`GET /tasks`, `GET /tasks/{id}`), including the 404 case.
4. **Stage 3** — `POST /tasks` with hand-written validation instead of relying on Pydantic's automatic rejection, so a bad request comes back as the spec's `400 {"error": ...}` rather than FastAPI's default `422`.
5. **Stage 4** — `PUT /tasks/{id}` and `DELETE /tasks/{id}`, completing full CRUD.
6. **Stage 5/6** — Swagger verification and this README.
7. **Stage 7 (bonus)** — an AI-generated rematch of the same API, kept in `ai-version/` and compared against the hand-built version above; see "AI vs me."
