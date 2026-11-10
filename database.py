"""
database.py - 混合架構資料庫模組 (Hybrid Database Module)

- PostgreSQL 直連 (psycopg 3)：用於高效能資料查詢、原生 SQL 多表 JOIN (event + users)、
  批次清理與事務控制。
- Supabase SDK (Client)：保留雲端擴充能力 (例如 Storage 疲勞截圖上傳、Realtime 即時推播)。
- 具備優雅降級能力：若未設定 Direct Connection URL，自動降級走 Supabase REST API。
"""

import os
from datetime import datetime, timezone
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

# PostgreSQL 原生連線驅動
import psycopg
from psycopg import sql
from psycopg.rows import DictRow, dict_row

# Supabase 官方 SDK
try:
    from supabase import Client, create_client
except ImportError:
    Client = Any  # type: ignore
    create_client = None  # type: ignore


# ========== 環境變數載入 ==========

SUPABASE_DIRECT_CONNECTION_URL = os.environ.get("SUPABASE_DIRECT_CONNECTION_URL", "").strip()
SUPABASE_PROJECT_URL = os.environ.get("SUPABASE_PROJECT_URL", "").strip()
SUPABASE_PUBLISHABLE_KEY = os.environ.get("SUPABASE_PUBLISHABLE_KEY", "").strip()

# 初始化 Supabase SDK Client（供 Storage / Realtime / 降級查詢使用）
supabase: Optional[Client] = None
if SUPABASE_PROJECT_URL and SUPABASE_PUBLISHABLE_KEY and create_client is not None:
    try:
        supabase = create_client(SUPABASE_PROJECT_URL, SUPABASE_PUBLISHABLE_KEY)
    except Exception as _sdk_err:
        print(f"[Supabase SDK] 初始化失敗 (非致命): {_sdk_err}")


def is_direct_db_configured() -> bool:
    """是否已設定 PostgreSQL Direct Connection URL"""
    return bool(SUPABASE_DIRECT_CONNECTION_URL)


def _connect_dict() -> psycopg.Connection[DictRow]:
    """建立支援字典返回的 psycopg 連線"""
    if not SUPABASE_DIRECT_CONNECTION_URL:
        raise RuntimeError("SUPABASE_DIRECT_CONNECTION_URL 未設定")
    return psycopg.Connection[DictRow].connect(
        SUPABASE_DIRECT_CONNECTION_URL,
        row_factory=dict_row,
    )


def _response_rows(response: Any) -> List[Dict[str, Any]]:
    rows = response.data
    if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
        raise RuntimeError("Supabase returned an unexpected table response")
    return rows


# ========== 資料模型 (Dataclass) ==========

@dataclass
class User:
    uuid: str
    user_id: str
    user_name: str
    hash_password: str
    role: str
    is_active: bool = True
    manager_id: Optional[str] = None
    created_at: Optional[Any] = None
    updated_at: Optional[Any] = None

    @classmethod
    def from_row(cls, row: Dict[str, Any]) -> "User":
        return cls(
            uuid=str(row.get("uuid") or row.get("id") or ""),
            user_id=str(row.get("userID") or row.get("username") or row.get("user_id") or ""),
            user_name=str(row.get("userName") or row.get("display_name") or row.get("user_name") or ""),
            hash_password=str(row.get("hash_password") or row.get("password_hash") or ""),
            role=str(row.get("role") or "driver"),
            is_active=bool(row.get("is_active", True)),
            manager_id=str(row["manager_id"]) if row.get("manager_id") else None,
            created_at=row.get("created_at"),
            updated_at=row.get("updated_at"),
        )

    # 相容舊版呼叫的屬性
    @property
    def id(self) -> str:
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

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.uuid,
            "uuid": self.uuid,
            "username": self.user_id,
            "userID": self.user_id,
            "display_name": self.user_name or self.user_id,
            "userName": self.user_name or self.user_id,
            "role": self.role,
            "is_active": self.is_active,
            "manager_id": self.manager_id,
            "created_at": str(self.created_at) if self.created_at else None,
            "updated_at": str(self.updated_at) if self.updated_at else None,
        }


@dataclass
class AlertEvent:
    data: Dict[str, Any]

    @classmethod
    def from_row(cls, row: Dict[str, Any]) -> "AlertEvent":
        return cls(data=dict(row))

    def to_dict(self) -> Dict[str, Any]:
        row = dict(self.data)
        row["is_escalated"] = bool(row.get("is_escalated"))
        row["is_new_escalation"] = bool(row.get("is_new_escalation"))
        if "created_at" in row and isinstance(row["created_at"], datetime):
            row["created_at"] = row["created_at"].isoformat()
        if "client_timestamp" in row and isinstance(row["client_timestamp"], datetime):
            row["client_timestamp"] = row["client_timestamp"].isoformat()
        return row


# ========== 資料庫連線測試與初始化 ==========

def init_db() -> None:
    """驗證資料庫表格可用性"""
    if is_direct_db_configured():
        with psycopg.connect(SUPABASE_DIRECT_CONNECTION_URL) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT uuid FROM public.users LIMIT 1")
                cursor.execute("SELECT id FROM public.event LIMIT 1")
    elif supabase:
        supabase.table("users").select("*").limit(1).execute()
        supabase.table("event").select("*").limit(1).execute()
    else:
        raise RuntimeError("未設定 SUPABASE_DIRECT_CONNECTION_URL 亦未設定 SUPABASE_PROJECT_URL")


# ========== 使用者操作 (User Operations) ==========

def get_user_by_username(username: str) -> Optional[User]:
    """依帳號名稱查詢已啟用的使用者"""
    if is_direct_db_configured():
        with _connect_dict() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT uuid, "userID", "userName", hash_password, role, is_active, manager_id, created_at, updated_at
                    FROM public.users
                    WHERE "userID" = %s
                      AND is_active = TRUE
                    LIMIT 1
                    """,
                    (username,),
                )
                rows = cursor.fetchall()
        return User.from_row(rows[0]) if rows else None
    elif supabase:
        try:
            res = supabase.table("users").select("*").eq("userID", username).eq("is_active", True).limit(1).execute()
            rows = _response_rows(res)
            if rows:
                return User.from_row(rows[0])
        except Exception:
            pass
        res = supabase.table("users").select("*").eq("username", username).limit(1).execute()
        rows = _response_rows(res)
        return User.from_row(rows[0]) if rows else None
    return None


def get_user_by_id(user_id: Any) -> Optional[User]:
    """依 UUID 查詢使用者"""
    uid_str = str(user_id).strip()
    if is_direct_db_configured():
        with _connect_dict() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT uuid, "userID", "userName", hash_password, role, is_active, manager_id, created_at, updated_at
                    FROM public.users
                    WHERE uuid::text = %s OR "userID" = %s
                    LIMIT 1
                    """,
                    (uid_str, uid_str),
                )
                rows = cursor.fetchall()
        return User.from_row(rows[0]) if rows else None
    elif supabase:
        try:
            res = supabase.table("users").select("*").eq("uuid", uid_str).limit(1).execute()
            rows = _response_rows(res)
            if rows:
                return User.from_row(rows[0])
        except Exception:
            pass
        res = supabase.table("users").select("*").eq("id", user_id).limit(1).execute()
        rows = _response_rows(res)
        return User.from_row(rows[0]) if rows else None
    return None


def list_users(
    role: Optional[str] = None,
    manager_id: Optional[Any] = None,
) -> List[User]:
    """列出使用者（支援依角色與所屬主管 manager_id 篩選）"""
    mgr_str = str(manager_id).strip() if manager_id else None

    if is_direct_db_configured():
        conditions = ["is_active = TRUE"]
        params: List[Any] = []
        if role:
            conditions.append("role = %s")
            params.append(role)
        if mgr_str:
            conditions.append("manager_id::text = %s")
            params.append(mgr_str)

        where_clause = " WHERE " + " AND ".join(conditions)
        query = f"""
            SELECT uuid, "userID", "userName", hash_password, role, is_active, manager_id, created_at, updated_at
            FROM public.users
            {where_clause}
            ORDER BY created_at ASC
        """
        with _connect_dict() as connection:
            with connection.cursor() as cursor:
                cursor.execute(query, tuple(params))
                rows = cursor.fetchall()
        return [User.from_row(row) for row in rows]
    elif supabase:
        query = supabase.table("users").select("*")
        if role:
            query = query.eq("role", role)
        if mgr_str:
            query = query.eq("manager_id", mgr_str)
        res = query.order("created_at", desc=False).execute()
        return [User.from_row(r) for r in _response_rows(res)]
    return []


def create_user(
    username: str,
    password_hash: str,
    display_name: Optional[str] = None,
    role: str = "driver",
    manager_id: Optional[Any] = None,
) -> User:
    """建立新使用者"""
    d_name = display_name or username
    mgr_val = str(manager_id).strip() if manager_id else None

    if is_direct_db_configured():
        with _connect_dict() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO public.users ("userID", "userName", hash_password, role, is_active, manager_id)
                    VALUES (%s, %s, %s, %s, TRUE, %s)
                    RETURNING uuid, "userID", "userName", hash_password, role, is_active, manager_id, created_at, updated_at
                    """,
                    (username, d_name, password_hash, role, mgr_val),
                )
                row = cursor.fetchone()
        if row is None:
            raise RuntimeError("PostgreSQL did not return the created user")
        return User.from_row(row)
    elif supabase:
        payload = {
            "userID": username,
            "userName": d_name,
            "hash_password": password_hash,
            "role": role,
            "is_active": True,
        }
        if mgr_val:
            payload["manager_id"] = mgr_val
        res = supabase.table("users").insert(payload).execute()
        rows = _response_rows(res)
        if not rows:
            raise RuntimeError("Supabase did not return the created user")
        return User.from_row(rows[0])
    raise RuntimeError("資料庫連線尚未設定")


def update_user(
    user_id: Any,
    display_name: Optional[str] = None,
    role: Optional[str] = None,
    manager_id: Optional[Any] = None,
    password_hash: Optional[str] = None,
    is_active: Optional[bool] = None,
) -> Optional[User]:
    """更新使用者資料"""
    uid_str = str(user_id).strip()
    if is_direct_db_configured():
        set_clauses = ['updated_at = NOW()']
        params: List[Any] = []
        if display_name is not None:
            set_clauses.append('"userName" = %s')
            params.append(display_name)
        if role is not None:
            set_clauses.append("role = %s")
            params.append(role)
        if manager_id is not None:
            mgr_val = str(manager_id).strip() if manager_id else None
            set_clauses.append("manager_id = %s")
            params.append(mgr_val)
        if password_hash is not None:
            set_clauses.append("hash_password = %s")
            params.append(password_hash)
        if is_active is not None:
            set_clauses.append("is_active = %s")
            params.append(bool(is_active))

        params.append(uid_str)
        sql_query = f"""
            UPDATE public.users
            SET {', '.join(set_clauses)}
            WHERE uuid::text = %s
            RETURNING uuid, "userID", "userName", hash_password, role, is_active, manager_id, created_at, updated_at
        """
        with _connect_dict() as connection:
            with connection.cursor() as cursor:
                cursor.execute(sql_query, tuple(params))
                row = cursor.fetchone()
        return User.from_row(row) if row else None
    elif supabase:
        patch: Dict[str, Any] = {}
        if display_name is not None:
            patch["userName"] = display_name
        if role is not None:
            patch["role"] = role
        if manager_id is not None:
            patch["manager_id"] = str(manager_id).strip() if manager_id else None
        if password_hash is not None:
            patch["hash_password"] = password_hash
        if is_active is not None:
            patch["is_active"] = bool(is_active)
        res = supabase.table("users").update(patch).eq("uuid", uid_str).execute()
        rows = _response_rows(res)
        return User.from_row(rows[0]) if rows else None
    return None


def delete_user(user_id: Any) -> bool:
    """刪除使用者 (優先軟刪除停用)"""
    uid_str = str(user_id).strip()
    if is_direct_db_configured():
        with _connect_dict() as connection:
            with connection.cursor() as cursor:
                cursor.execute('UPDATE public.users SET is_active = FALSE, updated_at = NOW() WHERE uuid::text = %s', (uid_str,))
        return True
    elif supabase:
        supabase.table("users").update({"is_active": False}).eq("uuid", uid_str).execute()
        return True
    return False


# ========== 警報事件操作 (Alert Events) ==========

def insert_event(data: Dict[str, Any]) -> AlertEvent:
    """插入一筆警報紀錄"""
    event_data = dict(data)
    event_data.setdefault("created_at", datetime.now(timezone.utc).isoformat())

    # 確保 uuid 正確設定
    driver_uuid = event_data.pop("user_id", None) or event_data.get("uuid")
    if driver_uuid:
        event_data["uuid"] = str(driver_uuid)

    if is_direct_db_configured():
        columns = list(event_data)
        placeholders = sql.SQL(", ").join(sql.Placeholder() for _ in columns)
        with _connect_dict() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    sql.SQL("INSERT INTO event ({}) VALUES ({}) RETURNING *").format(
                        sql.SQL(", ").join(sql.Identifier(column) for column in columns),
                        placeholders,
                    ),
                    [event_data[column] for column in columns],
                )
                row = cursor.fetchone()
        if row is None:
            raise RuntimeError("PostgreSQL did not return the inserted alert event")
        return AlertEvent.from_row(row)
    elif supabase:
        res = supabase.table("event").insert(event_data).execute()
        rows = _response_rows(res)
        if not rows:
            raise RuntimeError("Supabase did not return the inserted alert event")
        return AlertEvent.from_row(rows[0])
    raise RuntimeError("資料庫連線尚未設定")


def list_recent_alerts(limit: int, driver_ids: Optional[List[Any]] = None) -> List[AlertEvent]:
    """
    查詢最新警報紀錄，使用 LEFT JOIN 同時取得司機帳號 (userID) 與名稱 (userName)。
    支援依 driver_ids 篩選 (車隊管理員查看轄下司機)。
    """
    if is_direct_db_configured():
        where_sql = ""
        params: List[Any] = []
        if driver_ids is not None:
            if not driver_ids:
                return []
            placeholders = ", ".join(["%s"] * len(driver_ids))
            where_sql = f"WHERE event.uuid::text IN ({placeholders})"
            params.extend([str(d) for d in driver_ids])

        query = f"""
            SELECT
                event.*,
                users."userID" AS user_id,
                users."userName" AS user_name
            FROM public.event AS event
            LEFT JOIN public.users AS users ON users.uuid = event.uuid
            {where_sql}
            ORDER BY event.created_at DESC
            LIMIT %s
        """
        params.append(limit)

        with _connect_dict() as connection:
            with connection.cursor() as cursor:
                cursor.execute(query, tuple(params))
                rows = cursor.fetchall()
        return [AlertEvent.from_row(row) for row in rows]
    elif supabase:
        query = supabase.table("event").select("*, users:uuid(userID, userName)")
        if driver_ids is not None:
            if not driver_ids:
                return []
            query = query.in_("uuid", [str(d) for d in driver_ids])
        res = query.order("created_at", desc=True).limit(limit).execute()
        results: List[AlertEvent] = []
        for r in _response_rows(res):
            item = dict(r)
            users_info = item.pop("users", None)
            if isinstance(users_info, dict):
                item["user_id"] = users_info.get("userID")
                item["user_name"] = users_info.get("userName")
            results.append(AlertEvent.from_row(item))
        return results
    return []


def purge_old_alerts() -> int:
    """清理過期警報資料"""
    from config import Config

    cutoff = datetime.now(timezone.utc).timestamp() - (
        Config.ALERT_RETENTION_DAYS * 24 * 60 * 60
    )
    cutoff_iso = datetime.fromtimestamp(cutoff, timezone.utc).isoformat()

    if is_direct_db_configured():
        with psycopg.connect(SUPABASE_DIRECT_CONNECTION_URL) as connection:
            with connection.cursor() as cursor:
                cursor.execute("DELETE FROM event WHERE created_at < %s", (cutoff_iso,))
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
    elif supabase:
        old_rows = supabase.table("event").select("id").lt("created_at", cutoff_iso).execute()
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
    return 0
