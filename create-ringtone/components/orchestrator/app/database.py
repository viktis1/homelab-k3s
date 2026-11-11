import os
import psycopg
from psycopg.types.json import Jsonb
import uuid


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
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                user_id TEXT

            )
        """)


def create_job(job_id: str, user_id: str, value: dict) -> bool:
    """
    Create a job only if its ID does not already exist.

    Returns True if created, False if already present.
    """
    with connect() as conn:
        row = conn.execute(
            """
            INSERT INTO ringtone_jobs (
                job_id,
                status,
                details,
                user_id
            )
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (job_id) DO NOTHING
            RETURNING job_id
            """,
            (
                job_id,
                value["status"],
                Jsonb(value),
                user_id,
            ),
        ).fetchone()

    return row is not None


def set_job(job_id: str, value: dict):
    """
    Update a job.

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


def get_job(job_id: str, user_id: str) -> dict | None:
    """
    Retrieve a job from PostgreSQL.
    """

    with connect() as conn:
        row = conn.execute(
            """
            SELECT status, details, created_at
            FROM ringtone_jobs
            WHERE job_id = %s
                and user_id = %s
            """,
            (job_id, user_id),
        ).fetchone()

    if row is None:
        return None

    status, details, created_at = row

    return {
        **details,
        "status": status,
        "created_at": created_at,
    }


### ------------------------
### Voice Uploads
### ------------------------
def return_voice(voice_uuid: str, user_id: str) -> dict | None:
    """
    Retrieve an uploaded voice using its UUID.

    Allow access if:
    - The recording belongs to the authenticated user.
    - The recording is public.
    """
    with connect() as conn:
        row = conn.execute(
            """
            SELECT uuid, file_path, created_at, language
            FROM voice_uploads
            WHERE uuid = %s and (public = TRUE or user_id = %s)
            """, (uuid.UUID(voice_uuid), user_id)
        ).fetchone()

    if row is None:
        return None

    voice_id, file_path, created_at, language = row

    return {
        "uuid": str(voice_id),
        "file_path": file_path,
        "created_at": created_at,
        "language": language,
    }


def list_user_voices(user_id: str) -> dict:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT uuid, file_path, public, contact, created_at
            FROM voice_uploads
            WHERE user_id = %s OR public = TRUE
            ORDER BY contact, created_at DESC
            """,
            (user_id,),
        ).fetchall()

    voices = {
        "Public": {},
        "Your Uploads": {},
    }

    for voice_uuid, file_path, public, contact, created_at in rows:
        source = "Public" if public else "Your Uploads"

        # Create the person if they don't exist
        person = voices[source].setdefault(contact, {
            "clips": [],
        })

        # Append the recording
        person["clips"].append({
            "id": str(voice_uuid),
            "name": file_path,
            "created_at": created_at.isoformat(),
        })

    return voices