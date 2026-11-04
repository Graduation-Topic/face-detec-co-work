"""
db_check.py — 快速檢查本地資料庫狀態
執行方式：python db_check.py
"""
import sys
sys.path.insert(0, r"C:\Users\zhen0\Desktop\畢業專題\face-detec-co-work-main")

import os
from database import DATABASE_URL, engine, AlertEvent, User, SessionLocal

print("=" * 50)
print("📦 資料庫連線資訊")
print("=" * 50)
print(f"URL : {DATABASE_URL}")
print(f"類型: {'SQLite (本地)' if 'sqlite' in DATABASE_URL else 'PostgreSQL (雲端)'}")

# 確認資料表存在
from sqlalchemy import inspect
inspector = inspect(engine)
tables = inspector.get_table_names()
print(f"\n✅ 已建立的資料表: {tables}")

# 查詢資料筆數
db = SessionLocal()
try:
    alert_count = db.query(AlertEvent).count()
    user_count  = db.query(User).count()
    print(f"\n📊 資料筆數：")
    print(f"   users        : {user_count} 筆")
    print(f"   alert_events : {alert_count} 筆")

    if alert_count > 0:
        print(f"\n🔔 最新 5 筆警告紀錄：")
        events = db.query(AlertEvent).order_by(AlertEvent.created_at.desc()).limit(5).all()
        for e in events:
            flag = "🚨" if e.is_escalated else "⚠️"
            print(f"   {flag} [{e.created_at}] {e.reason} | score={e.score} | window_count={e.window_count}")
    else:
        print("\n（尚無警告紀錄，啟動偵測並觸發警告後才會有資料）")
finally:
    db.close()

print("\n" + "=" * 50)
print("✅ 資料庫連線正常！")
print("=" * 50)

