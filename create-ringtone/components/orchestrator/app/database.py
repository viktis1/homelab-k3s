import os
import psycopg
from psycopg.types.json import Jsonb


def connect():
    """
    Create a PostgreSQL connection.
    """

    return psycopg.connect(
        host=os.environ["DB_HOST"],
        port=5432,
        dbname=os.environ["DB_NAME"],
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        connect_timeout=5,
    )


def init_db():
    """
    Initialize the database schema.
    """

    with connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS ringtone_jobs (
                job_id TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                details JSONB NOT NULL DEFAULT '{}'::jsonb,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)


def set_job(job_id: str, value: dict):
    """
    Insert or update a job.

    Existing details are preserved when new
    information becomes available.
    """

    with connect() as conn:
        conn.execute(
            """
            INSERT INTO ringtone_jobs (
                job_id,
                status,
                details
            )
            VALUES (%s, %s, %s)

            ON CONFLICT (job_id)
            DO UPDATE SET
                status = EXCLUDED.status,
                details = ringtone_jobs.details
                          || EXCLUDED.details,
                updated_at = NOW()
            """,
            (
                job_id,
                value["status"],
                Jsonb(value),
            ),
        )


def get_job(job_id: str) -> dict | None:
    """
    Retrieve a job from PostgreSQL.
    """

    with connect() as conn:
        row = conn.execute(
            """
            SELECT status, details, created_at
            FROM ringtone_jobs
            WHERE job_id = %s
            """,
            (job_id,),
        ).fetchone()

    if row is None:
        return None

    status, details, created_at = row

    return {
        **details,
        "status": status,
        "created_at": created_at,
    }