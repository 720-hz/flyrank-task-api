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
main.py            the whole API — one file, on purpose, for something this size
requirements.txt   pinned dependency versions
.gitignore         Python/venv noise kept out of the repo
```

## Development history

This repo's commit history is deliberately staged, one checkpoint at a time, mirroring how the API was actually built:

1. **Stage 0** — a bare "hello world" server, just to prove FastAPI and uvicorn were wired up.
2. **Stage 1** — `/` and `/health`, the two endpoints with no state behind them.
3. **Stage 2** — the in-memory task list plus the two read endpoints (`GET /tasks`, `GET /tasks/{id}`), including the 404 case.
4. **Stage 3** — `POST /tasks` with hand-written validation instead of relying on Pydantic's automatic rejection, so a bad request comes back as the spec's `400 {"error": ...}` rather than FastAPI's default `422`.
5. **Stage 4** — `PUT /tasks/{id}` and `DELETE /tasks/{id}`, completing full CRUD.
6. **Stage 5/6** — Swagger verification and this README.
