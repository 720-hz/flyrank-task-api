"""
db.py — the repository. Every line in this project that talks to the
database lives here; main.py never imports psycopg and never writes SQL.

This is the third storage engine behind the same API: a Python list (A1),
then SQLite (A2), now Postgres. Each swap has only ever touched this one
module (or, for A1 -> A2, the equivalent inline block in main.py) — the
routes and the service layer on top were never touched. That's the point
of keeping the database in one place: "swap storage" really does mean
"change one file."
"""

import os
from contextlib import contextmanager
from typing import Optional

import psycopg
from dotenv import load_dotenv
from psycopg.rows import dict_row

load_dotenv()

# No fallback default on purpose — a missing DATABASE_URL should fail loudly
# at import time, not silently try to connect to somewhere wrong.
DATABASE_URL = os.environ["DATABASE_URL"]


@contextmanager
def get_connection():
    """One connection per call, committed on a clean exit, closed either
    way. Never a single connection reused across requests: FastAPI runs
    synchronous endpoint functions in a worker thread pool, and a shared
    connection object handed between threads is not safe with psycopg any
    more than it is with sqlite3."""
    conn = psycopg.connect(DATABASE_URL, row_factory=dict_row)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    """Creates the tasks table (and its title index) if missing, then seeds
    three example tasks — but only the very first time, when the table is
    still empty. Runs once at startup, not per-request. Same seed-once rule
    as the in-memory and SQLite versions before it."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS tasks (
                    id SERIAL PRIMARY KEY,
                    title TEXT NOT NULL,
                    done BOOLEAN NOT NULL DEFAULT FALSE,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
                )
                """
            )
            # Backs ?search= (LIKE) and ?sort=title (ORDER BY) the same way
            # it did under SQLite — without it both would scan every row.
            cur.execute("CREATE INDEX IF NOT EXISTS idx_tasks_title ON tasks(title)")

            cur.execute("SELECT COUNT(*) AS n FROM tasks")
            count = cur.fetchone()["n"]
            if count == 0:
                # One executemany, one connection, one commit (see
                # get_connection above) — the three seed rows land as a
                # single all-or-nothing transaction, same guarantee the
                # SQLite version had.
                cur.executemany(
                    "INSERT INTO tasks (title, done) VALUES (%s, %s)",
                    [("Buy milk", False), ("Write README", False), ("Push to GitHub", True)],
                )


def list_tasks(
    search: Optional[str] = None,
    done: Optional[bool] = None,
    sort: Optional[str] = None,
) -> list[dict]:
    """Every task, filtered in SQL by search/done and ordered by sort=title
    (default: id). Parameterized throughout — %s placeholders, values passed
    separately, never glued into the query string."""
    query = "SELECT * FROM tasks WHERE 1 = 1"
    params: list = []
    if search:
        query += " AND title LIKE %s"
        params.append(f"%{search}%")
    if done is not None:
        query += " AND done = %s"
        params.append(done)
    query += " ORDER BY title" if sort == "title" else " ORDER BY id"

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
            return cur.fetchall()


def get_task(task_id: int) -> Optional[dict]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM tasks WHERE id = %s", (task_id,))
            return cur.fetchone()


def create_task(title: str) -> dict:
    """INSERT ... RETURNING * hands back the full row — including the id
    Postgres just assigned — in the same round trip as the write."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO tasks (title, done) VALUES (%s, %s) RETURNING *",
                (title, False),
            )
            return cur.fetchone()


def update_task(task_id: int, title: Optional[str], done: Optional[bool]) -> Optional[dict]:
    """Returns the updated row, or None if task_id doesn't exist. Only the
    fields actually given are changed; anything left as None keeps its
    current value."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM tasks WHERE id = %s", (task_id,))
            row = cur.fetchone()
            if row is None:
                return None

            new_title = row["title"] if title is None else title
            new_done = row["done"] if done is None else done

            cur.execute(
                "UPDATE tasks SET title = %s, done = %s, updated_at = now() "
                "WHERE id = %s RETURNING *",
                (new_title, new_done, task_id),
            )
            return cur.fetchone()


def delete_task(task_id: int) -> bool:
    """True if a row was deleted, False if task_id didn't exist."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM tasks WHERE id = %s", (task_id,))
            return cur.rowcount > 0


def stats() -> dict:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS n FROM tasks")
            total = cur.fetchone()["n"]
            cur.execute("SELECT COUNT(*) AS n FROM tasks WHERE done = TRUE")
            done_count = cur.fetchone()["n"]
    return {"total": total, "done": done_count, "open": total - done_count}
