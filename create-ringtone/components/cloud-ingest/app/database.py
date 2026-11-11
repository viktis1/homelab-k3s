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
                user_id TEXT,
                contact TEXT NOT NULL,
                file_path TEXT NOT NULL,
                public BOOLEAN NOT NULL DEFAULT FALSE,
                language TEXT DEFAULT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)



def register_voice(
    voice_uuid: str,
    user_id: str | None,
    contact: str,
    public: bool,
    file_path: str,
) -> bool:
    """Register a voice recording without its language."""
    with connect() as conn:
        row = conn.execute(
            """
            INSERT INTO voice_uploads
                (uuid, user_id, contact, file_path, public)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (uuid) DO NOTHING
            RETURNING uuid
            """,
            (uuid.UUID(voice_uuid), user_id, contact, file_path, public),
        ).fetchone()

    return row is not None

def update_voice_language(voice_uuid: str, language: str):
    """Update the detected language of a recording."""
    with connect() as conn:
        conn.execute(
            """
            UPDATE voice_uploads
            SET language = %s
            WHERE uuid = %s
            """,
            (language, uuid.UUID(voice_uuid)),
        )
