import os
from datetime import datetime, timezone
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import psycopg
from psycopg import sql
from psycopg.rows import DictRow, dict_row


def _required_setting(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} is required")
    return value


SUPABASE_DIRECT_CONNECTION_URL = _required_setting("SUPABASE_DIRECT_CONNECTION_URL")


def _connect_dict() -> psycopg.Connection[DictRow]:
    return psycopg.Connection[DictRow].connect(
        SUPABASE_DIRECT_CONNECTION_URL,
        row_factory=dict_row,
    )


@dataclass
class User:
    uuid: str
    user_id: str
    user_name: str
    hash_password: str
    role: str
    is_active: bool
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    @classmethod
    def from_row(cls, row: Dict[str, Any]) -> "User":
        return cls(
            uuid=str(row["uuid"]),
            user_id=row["userID"],
            user_name=row["userName"],
            hash_password=row["hash_password"],
            role=row["role"],
            is_active=bool(row["is_active"]),
            created_at=row.get("created_at"),
            updated_at=row.get("updated_at"),
        )

    @property
    def id(self) -> str:
        """Backward-compatible session identifier for existing callers."""
        return self.uuid

    @property
    def username(self) -> str:
        return self.user_id

    @property
    def display_name(self) -> str:
        return self.user_name

    @property
    def password_hash(self) -> str:
        return self.hash_password


@dataclass
class AlertEvent:
    data: Dict[str, Any]

    @classmethod
    def from_row(cls, row: Dict[str, Any]) -> "AlertEvent":
        return cls(data=row)

    def to_dict(self) -> Dict[str, Any]:
        row = dict(self.data)
        row["is_escalated"] = bool(row.get("is_escalated"))
        row["is_new_escalation"] = bool(row.get("is_new_escalation"))
        return row


def init_db() -> None:
    """Verify that the required Supabase tables are available."""
    with psycopg.connect(SUPABASE_DIRECT_CONNECTION_URL) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT uuid FROM public.users LIMIT 1")
            cursor.execute("SELECT id FROM public.event LIMIT 1")


def get_user_by_username(username: str) -> Optional[User]:
    with _connect_dict() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    uuid,
                    "userID",
                    "userName",
                    hash_password,
                    role,
                    is_active,
                    created_at,
                    updated_at
                FROM public.users
                WHERE "userID" = %s
                  AND is_active = TRUE
                LIMIT 1
                """,
                (username,),
            )
            rows = cursor.fetchall()
    return User.from_row(rows[0]) if rows else None


def insert_event(data: Dict[str, Any]) -> AlertEvent:
    event_data = dict(data)
    event_data.setdefault(
        "created_at", datetime.now(timezone.utc).isoformat()
    )
    columns = list(event_data)
    placeholders = sql.SQL(", ").join(sql.Placeholder() for _ in columns)
    with _connect_dict() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                sql.SQL(
                    "INSERT INTO event ({}) VALUES ({}) RETURNING *"
                ).format(
                    sql.SQL(", ").join(sql.Identifier(column) for column in columns),
                    placeholders,
                ),
                [event_data[column] for column in columns],
            )
            row = cursor.fetchone()
    if row is None:
        raise RuntimeError("PostgreSQL did not return the inserted alert event")
    return AlertEvent.from_row(row)


def list_recent_alerts(limit: int) -> List[AlertEvent]:
    with _connect_dict() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    event.*,
                    users."userID" AS user_id
                FROM public.event AS event
                JOIN public.users AS users ON users.uuid = event.uuid
                ORDER BY event.created_at DESC
                LIMIT %s
                """,
                (limit,),
            )
            rows = cursor.fetchall()
    return [AlertEvent.from_row(row) for row in rows]


def purge_old_alerts() -> int:
    from config import Config

    cutoff = datetime.now(timezone.utc).timestamp() - (
        Config.ALERT_RETENTION_DAYS * 24 * 60 * 60
    )
    cutoff_iso = datetime.fromtimestamp(cutoff, timezone.utc).isoformat()
    with psycopg.connect(SUPABASE_DIRECT_CONNECTION_URL) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "DELETE FROM event WHERE created_at < %s",
                (cutoff_iso,),
            )
            deleted = cursor.rowcount
            cursor.execute(
                """
                DELETE FROM event
                WHERE id IN (
                    SELECT id
                    FROM event
                    ORDER BY created_at DESC
                    OFFSET %s
                )
                """,
                (Config.ALERT_MAX_DB_RECORDS,),
            )
            deleted += cursor.rowcount
    return deleted
