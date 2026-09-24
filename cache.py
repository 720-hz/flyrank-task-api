"""
cache.py — the one place Redis is touched. This stage only needs a startup
ping proving the app can reach it (a real caching layer is W4's job); kept
in its own module for the same reason Postgres access lives only in db.py —
one small, swappable surface, not scattered through main.py.
"""

import os

import redis
from dotenv import load_dotenv

load_dotenv()

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")


def ping() -> bool:
    """True if Redis answered PONG, False if it couldn't be reached at all.
    Never raises — a health check should report a problem, not crash on
    one, and a missing/unreachable Redis shouldn't take the whole API down
    over a stretch-goal dependency."""
    try:
        client = redis.from_url(REDIS_URL, socket_connect_timeout=2)
        return bool(client.ping())
    except redis.RedisError:
        return False
