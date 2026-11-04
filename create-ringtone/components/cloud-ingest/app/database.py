import os
import uuid
import psycopg


def connect():
    """
    Create a connection to db.
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
    Initialize the schema.
    """
    with connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS voice_uploads (
                uuid UUID PRIMARY KEY,
                user_id TEXT NOT NULL,
                file_path TEXT NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)


def upload_voice(voice_uuid: str,  user_id: str, file_path: str) -> bool:
    """
    Register an uploaded voice.

    Returns True if created, False if the UUID already exists.
    """
    with connect() as conn:
        row = conn.execute(
            """
            INSERT INTO voice_uploads (uuid, user_id, file_path)
            VALUES (%s, %s, %s)
            ON CONFLICT (uuid) DO NOTHING
            RETURNING uuid
            """,
            (uuid.UUID(voice_uuid), user_id, file_path),
        ).fetchone()

    return row is not None
