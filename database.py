"""
database.py — 資料庫連線與表格定義

架構設計（SQLAlchemy ORM）：
- 本地開發：自動使用 SQLite (DATABASE_URL=sqlite:///local_test.db)
- Render 部署：自動切換為 Supabase PostgreSQL (DATABASE_URL=postgresql://...)
- 不需要改任何程式碼，只要設定環境變數即可

資料表：
- users        ─ 使用者帳號（支援 admin / driver 角色）
- alert_events ─ 警告事件紀錄（每次 /api/alert 觸發時儲存）
"""

import os
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.orm import DeclarativeBase, sessionmaker


# ========== 資料庫連線 ==========

def _get_database_url() -> str:
    """
    讀取 DATABASE_URL 環境變數。
    - 本地：.env 設定的 sqlite:///local_test.db
    - Render：Supabase 的 postgresql://... 連線字串
    """
    url = os.environ.get("DATABASE_URL", "sqlite:///local_test.db")

    # Supabase / Heroku 有時會給 postgres:// (舊格式)，SQLAlchemy 2.x 需要 postgresql://
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)

    return url


DATABASE_URL = _get_database_url()

# SQLite 不支援 pool_size 等參數，需要分開設定
if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},  # SQLite 多執行緒需要
        echo=False,
    )
else:
    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,   # 每次使用前 ping 確認連線存活
        pool_recycle=300,     # 5 分鐘回收連線，防止 Supabase 閒置中斷
        echo=False,
    )

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


# ========== 資料表定義 ==========

class Base(DeclarativeBase):
    pass


class User(Base):
    """使用者帳號表（支援 admin / driver 角色）"""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(64), unique=True, nullable=False, index=True)
    display_name = Column(String(128), nullable=True)
    password_hash = Column(String(256), nullable=False)
    role = Column(String(16), nullable=False, default="driver")  # "admin" or "driver"
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    def to_dict(self):
        return {
            "id": self.id,
            "username": self.username,
            "display_name": self.display_name,
            "role": self.role,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class AlertEvent(Base):
    """
    警告事件紀錄表

    每次前端觸發 /api/alert 時（fatigueLevel == Severe），
    後端會寫入一筆紀錄到這張表。舊資料依 ALERT_RETENTION_DAYS 自動清理。
    """
    __tablename__ = "alert_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(64), nullable=True, index=True)   # 前端的 sessionId
    user_id = Column(Integer, nullable=True, index=True)          # 對應 users.id（未來登入後使用）
    score = Column(Float, nullable=True)                          # 疲勞分數 (0~100)
    level = Column(String(16), nullable=True)                     # "Severe"
    reason = Column(String(128), nullable=True)                   # 觸發原因（微睡眠、Head Snap…）
    client_count = Column(Integer, nullable=True)                 # 前端本次 session 累計警告次數
    window_count = Column(Integer, nullable=True)                 # 後端滑動視窗內警告次數
    is_escalated = Column(Integer, default=0)                     # 是否已升級通報（0/1）
    is_new_escalation = Column(Integer, default=0)                # 本次是否首次觸發升級（0/1）
    client_timestamp = Column(Float, nullable=True)               # 前端送來的時間戳（Unix）
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    def to_dict(self):
        return {
            "id": self.id,
            "session_id": self.session_id,
            "user_id": self.user_id,
            "score": self.score,
            "level": self.level,
            "reason": self.reason,
            "client_count": self.client_count,
            "window_count": self.window_count,
            "is_escalated": bool(self.is_escalated),
            "is_new_escalation": bool(self.is_new_escalation),
            "client_timestamp": self.client_timestamp,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


# ========== 初始化（建立資料表） ==========

def init_db():
    """建立所有資料表（若已存在則跳過）"""
    Base.metadata.create_all(bind=engine)


# ========== Session 輔助工具 ==========

def get_db():
    """
    產生一個資料庫 Session，使用 with 語法自動管理生命週期：

        with get_db() as db:
            db.add(record)
            db.commit()
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ========== 管理功能 ==========

def purge_old_alerts(db):
    """
    自動清理過期的警告事件紀錄。
    1. 刪除超過 ALERT_RETENTION_DAYS 天前的記錄
    2. 若總筆數超過 ALERT_MAX_DB_RECORDS，刪除最舊的超量部分
    """
    from datetime import timedelta
    from config import Config

    deleted_count = 0

    # 1. 按時間刪除（超過保留天數）
    cutoff_date = datetime.utcnow() - timedelta(days=Config.ALERT_RETENTION_DAYS)
    old_by_date = (
        db.query(AlertEvent)
        .filter(AlertEvent.created_at < cutoff_date)
        .delete(synchronize_session=False)
    )
    deleted_count += old_by_date

    # 2. 按總數限制刪除（保留最新 N 筆）
    total = db.query(AlertEvent).count()
    if total > Config.ALERT_MAX_DB_RECORDS:
        # 找出第 N 新的記錄的 id（作為刪除邊界）
        cutoff_row = (
            db.query(AlertEvent.id)
            .order_by(AlertEvent.created_at.desc())
            .offset(Config.ALERT_MAX_DB_RECORDS)
            .first()
        )
        if cutoff_row:
            old_by_count = (
                db.query(AlertEvent)
                .filter(AlertEvent.id <= cutoff_row[0])
                .delete(synchronize_session=False)
            )
            deleted_count += old_by_count

    db.commit()
    return deleted_count


def seed_admin_user(db):
    """
    首次啟動時自動建立預設 admin 帳號（若已存在則跳過）。
    帳號密碼由環境變數 ADMIN_USERNAME / ADMIN_PASSWORD 設定。
    """
    from werkzeug.security import generate_password_hash

    username = os.environ.get("ADMIN_USERNAME", "admin")
    password = os.environ.get("ADMIN_PASSWORD", "admin123")
    display = os.environ.get("ADMIN_DISPLAY_NAME", "系統管理員")

    existing = db.query(User).filter_by(username=username).first()
    if not existing:
        admin = User(
            username=username,
            display_name=display,
            password_hash=generate_password_hash(password),
            role="admin",
        )
        db.add(admin)
        db.commit()
        return True   # 新建立
    return False      # 已存在
