"""PostgreSQL connection pool shared by all request handlers."""
import time
from pathlib import Path

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from . import config

pool = ConnectionPool(
    config.DATABASE_URL,
    min_size=config.DB_POOL_MIN,
    max_size=config.DB_POOL_MAX,
    kwargs={"row_factory": dict_row, "autocommit": True},
    open=False,
)


def open_pool(retries: int = 30) -> None:
    """Open the pool, waiting for the database container to come up."""
    for attempt in range(retries):
        try:
            pool.open(wait=True, timeout=5)
            return
        except Exception:
            if attempt == retries - 1:
                raise
            time.sleep(2)


SCHEMA_LOCK_ID = 457027  # any constant; shared by every API worker


def init_schema(seed=None) -> None:
    """Create tables (and seed data) once, even with several workers starting together."""
    sql = (Path(__file__).parent / "schema.sql").read_text()
    with pool.connection() as conn:
        conn.execute("SELECT pg_advisory_lock(%s)", (SCHEMA_LOCK_ID,))
        try:
            conn.execute(sql)
            if seed:
                seed(conn)
        finally:
            conn.execute("SELECT pg_advisory_unlock(%s)", (SCHEMA_LOCK_ID,))


def fetch_all(query: str, params: tuple | dict = ()) -> list[dict]:
    with pool.connection() as conn:
        return conn.execute(query, params).fetchall()


def fetch_one(query: str, params: tuple | dict = ()) -> dict | None:
    with pool.connection() as conn:
        return conn.execute(query, params).fetchone()
