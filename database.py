"""
database.py - Supabase database access.

The Supabase tables must be created in the Supabase project before the
application starts. The client uses the project URL and publishable key from
the environment; no database password is stored by this application.
"""

import os
from datetime import datetime, timezone
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from supabase import Client, create_client


def _required_setting(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} is required")
    return value


SUPABASE_PROJECT_URL = _required_setting("SUPABASE_PROJECT_URL")
SUPABASE_PUBLISHABLE_KEY = _required_setting("SUPABASE_PUBLISHABLE_KEY")
supabase: Client = create_client(SUPABASE_PROJECT_URL, SUPABASE_PUBLISHABLE_KEY)


def _response_rows(response: Any) -> List[Dict[str, Any]]:
    rows = response.data
    if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
        raise RuntimeError("Supabase returned an unexpected table response")
    return rows


@dataclass
class User:
    id: int
    username: str
    display_name: Optional[str]
    password_hash: str
    role: str
    manager_id: Optional[int] = None
    created_at: Optional[str] = None

    @classmethod
    def from_row(cls, row: Dict[str, Any]) -> "User":
        return cls(
            id=row["id"],
            username=row["username"],
            display_name=row.get("display_name"),
            password_hash=row["password_hash"],
            role=row.get("role", "driver"),
            manager_id=row.get("manager_id"),
            created_at=row.get("created_at"),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "username": self.username,
            "display_name": self.display_name or self.username,
            "role": self.role,
            "manager_id": self.manager_id,
            "created_at": self.created_at,
        }


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
    for table in ("users", "event"):
        supabase.table(table).select("id").limit(1).execute()


def get_user_by_username(username: str) -> Optional[User]:
    response = (
        supabase.table("users")
        .select("*")
        .eq("username", username)
        .limit(1)
        .execute()
    )
    rows = _response_rows(response)
    return User.from_row(rows[0]) if rows else None


def get_user_by_id(user_id: int) -> Optional[User]:
    response = (
        supabase.table("users")
        .select("*")
        .eq("id", user_id)
        .limit(1)
        .execute()
    )
    rows = _response_rows(response)
    return User.from_row(rows[0]) if rows else None


def create_user(
    username: str,
    password_hash: str,
    display_name: Optional[str] = None,
    role: str = "driver",
    manager_id: Optional[int] = None,
) -> User:
    payload: Dict[str, Any] = {
        "username": username,
        "password_hash": password_hash,
        "display_name": display_name or username,
        "role": role,
    }
    if manager_id is not None:
        payload["manager_id"] = manager_id
    response = supabase.table("users").insert(payload).execute()
    rows = _response_rows(response)
    if not rows:
        raise RuntimeError("Supabase did not return the created user")
    return User.from_row(rows[0])


def list_users(
    role: Optional[str] = None,
    manager_id: Optional[int] = None,
) -> List[User]:
    query = supabase.table("users").select("*")
    if role:
        query = query.eq("role", role)
    if manager_id is not None:
        query = query.eq("manager_id", manager_id)
    response = query.order("id", desc=False).execute()
    return [User.from_row(r) for r in _response_rows(response)]


def delete_user(user_id: int) -> bool:
    supabase.table("users").delete().eq("id", user_id).execute()
    return True


def insert_event(data: Dict[str, Any]) -> AlertEvent:
    event_data = dict(data)
    event_data.setdefault(
        "created_at", datetime.now(timezone.utc).isoformat()
    )
    response = supabase.table("event").insert(event_data).execute()
    rows = _response_rows(response)
    if not rows:
        raise RuntimeError("Supabase did not return the inserted alert event")
    return AlertEvent.from_row(rows[0])


def list_recent_alerts(limit: int, driver_ids: Optional[List[int]] = None) -> List[AlertEvent]:
    try:
        query = supabase.table("event").select("*").order("created_at", desc=True).limit(limit)
        if driver_ids is not None:
            if not driver_ids:
                return []
            query = query.in_("user_id", driver_ids)
        response = query.execute()
        return [AlertEvent.from_row(row) for row in _response_rows(response)]
    except Exception:
        response = (
            supabase.table("event")
            .select("*")
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return [AlertEvent.from_row(row) for row in _response_rows(response)]


def purge_old_alerts() -> int:
    from config import Config

    cutoff = datetime.now(timezone.utc).timestamp() - (
        Config.ALERT_RETENTION_DAYS * 24 * 60 * 60
    )
    cutoff_iso = datetime.fromtimestamp(cutoff, timezone.utc).isoformat()
    old_rows = (
        supabase.table("event")
        .select("id")
        .lt("created_at", cutoff_iso)
        .execute()
    )
    deleted = 0
    for row in _response_rows(old_rows):
        supabase.table("event").delete().eq("id", row["id"]).execute()
        deleted += 1

    rows = (
        supabase.table("event")
        .select("id")
        .order("created_at", desc=True)
        .range(Config.ALERT_MAX_DB_RECORDS, 1000000)
        .execute()
    )
    for row in _response_rows(rows):
        supabase.table("event").delete().eq("id", row["id"]).execute()
        deleted += 1
    return deleted
