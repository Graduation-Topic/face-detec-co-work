"""
line_notifier.py — LINE Messaging API 推播通知模組

支援：
1. 每個帳號各自綁定不同的 LINE User ID / Group ID。
2. 每個帳號可自訂 Channel Access Token（亦可使用全域預設 Token）。
3. 疲勞事件升級時，依車隊主管與總管理員名單進行推播。
"""

import json
import logging
import os
import urllib.error
import urllib.request
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

LINE_PUSH_URL = "https://api.line.me/v2/bot/message/push"


def get_default_line_token() -> str:
    """取得系統全域預設的 LINE Channel Access Token"""
    return os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "").strip()


def send_line_push_message(
    to_user_id: str,
    message_text: str,
    channel_access_token: Optional[str] = None,
) -> Dict[str, Any]:
    """
    發送 LINE 訊息到指定的 User ID 或 Group ID。
    
    :param to_user_id: 接收者的 LINE User ID (例如 U123...) 或 Group ID (C123...)
    :param message_text: 要發送的文字訊息
    :param channel_access_token: 若指定則優先使用該帳號專屬 Token，否則使用全域 Token
    :return: dict 包含 {"success": bool, "message": str, "status_code": int}
    """
    token = (channel_access_token or "").strip() or get_default_line_token()
    target_id = (to_user_id or "").strip()

    if not token:
        logger.warning("[LINE API] 未設定 Channel Access Token，無法發送推播")
        return {
            "success": False,
            "message": "未設定 LINE Channel Access Token",
            "status_code": 400,
        }

    if not target_id:
        logger.warning("[LINE API] 未指定接收對象 LINE User ID")
        return {
            "success": False,
            "message": "未填寫 LINE User ID 或 Group ID",
            "status_code": 400,
        }

    payload = {
        "to": target_id,
        "messages": [
            {
                "type": "text",
                "text": message_text,
            }
        ],
    }

    data_bytes = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        LINE_PUSH_URL,
        data=data_bytes,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
            "User-Agent": "Face-Detection-Alert/1.0",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            status_code = resp.getcode()
            logger.info(f"[LINE API] 成功發送推播至 {target_id[:6]}*** (狀態碼: {status_code})")
            return {
                "success": True,
                "message": "推播發送成功",
                "status_code": status_code,
            }
    except urllib.error.HTTPError as e:
        err_body = ""
        try:
            err_body = e.read().decode("utf-8", errors="replace")
        except Exception:
            pass
        logger.error(f"[LINE API] 推播發送失敗 HTTP {e.code}: {err_body}")
        return {
            "success": False,
            "message": f"LINE API 回傳錯誤 ({e.code}): {err_body}",
            "status_code": e.code,
        }
    except Exception as e:
        logger.error(f"[LINE API] 連線異常: {e}")
        return {
            "success": False,
            "message": f"連線異常: {str(e)}",
            "status_code": 500,
        }


def format_fatigue_alert_message(
    driver_name: str,
    driver_username: str,
    reason: str,
    score: float,
    window_count: int,
    occurred_at: Optional[datetime] = None,
) -> str:
    """格式化疲勞警報通知文字"""
    # 轉換為台灣時區 (UTC+8) 顯示
    dt = occurred_at or datetime.now(timezone.utc)
    tw_time = dt.astimezone(timezone(timedelta(hours=8)))
    time_str = tw_time.strftime("%Y-%m-%d %H:%M:%S")

    return (
        f"【舟車勞頓 - 駕駛疲勞通報】\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"駕駛人員：{driver_name} ({driver_username})\n"
        f"警報原因：{reason}\n"
        f"疲勞指數：{score:.1f}% (嚴重疲勞)\n"
        f"視窗累積：{window_count} 次 (已觸發通報門檻)\n"
        f"發生時間：{time_str}\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"請車隊管理員立即確認駕駛員狀態並確保安全！"
    )
