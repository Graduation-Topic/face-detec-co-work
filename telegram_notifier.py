"""
telegram_notifier.py — Telegram Bot API 推播通知模組

特點：
1. 完全個人免企業帳號，與 @BotFather 互動即可 1 分鐘免費獲得 Bot Token。
2. 支援 HTML 標籤豐富排版（粗體、代碼、自訂連結）。
3. 支援全域預設環境變數 (TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID) 或個別使用者專屬設定。
4. 使用 Python 內建 urllib，無須安裝額外依賴套件。
"""

import json
import logging
import os
import urllib.error
import urllib.request
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def get_default_telegram_token() -> str:
    """取得系統全域預設的 Telegram Bot Token"""
    return os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()


def get_default_telegram_chat_id() -> str:
    """取得系統全域預設的 Telegram Chat ID"""
    return os.environ.get("TELEGRAM_CHAT_ID", "").strip()


def send_telegram_message(
    chat_id: Optional[str] = None,
    message_text: str = "",
    bot_token: Optional[str] = None,
    parse_mode: str = "HTML",
    disable_web_page_preview: bool = True,
) -> Dict[str, Any]:
    """
    發送訊息到指定的 Telegram Chat ID (個人或群組)。
    
    :param chat_id: 接收者或群組的 Chat ID (例如 123456789 或 -100123456789)
    :param message_text: 要發送的文字訊息 (支援 HTML 標籤)
    :param bot_token: Telegram Bot Token (若留空則使用全域環境變數)
    :param parse_mode: 格式解析模式 ("HTML" 或 "Markdown")
    :param disable_web_page_preview: 是否停用連結預覽
    :return: dict 包含 {"success": bool, "message": str, "status_code": int}
    """
    token = (bot_token or "").strip() or get_default_telegram_token()
    target_chat = (chat_id or "").strip() or get_default_telegram_chat_id()

    if not token:
        logger.warning("[Telegram API] 未設定 Telegram Bot Token，跳過推播")
        return {
            "success": False,
            "message": "未設定 Telegram Bot Token",
            "status_code": 400,
        }

    if not target_chat:
        logger.warning("[Telegram API] 未指定接收對象 Telegram Chat ID")
        return {
            "success": False,
            "message": "未指定接收對象 Telegram Chat ID",
            "status_code": 400,
        }

    api_url = f"https://api.telegram.org/bot{token}/sendMessage"

    payload = {
        "chat_id": target_chat,
        "text": message_text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": disable_web_page_preview,
    }

    data_bytes = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        api_url,
        data=data_bytes,
        headers={
            "Content-Type": "application/json",
            "User-Agent": "Face-Detection-Alert/1.0",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            status_code = resp.getcode()
            logger.info(f"[Telegram API] 成功發送推播至 {target_chat} (狀態碼: {status_code})")
            return {
                "success": True,
                "message": "Telegram 推播發送成功",
                "status_code": status_code,
            }
    except urllib.error.HTTPError as e:
        err_body = ""
        try:
            err_body = e.read().decode("utf-8", errors="replace")
        except Exception:
            pass
        logger.error(f"[Telegram API] 推播發送失敗 HTTP {e.code}: {err_body}")
        return {
            "success": False,
            "message": f"Telegram API 回傳錯誤 ({e.code}): {err_body}",
            "status_code": e.code,
        }
    except Exception as e:
        logger.error(f"[Telegram API] 連線異常: {e}")
        return {
            "success": False,
            "message": f"連線異常: {str(e)}",
            "status_code": 500,
        }


def format_telegram_fatigue_message(
    driver_name: str,
    driver_username: str,
    reason: str,
    score: float,
    window_count: int,
    occurred_at: Optional[datetime] = None,
) -> str:
    """格式化為 Telegram 支援之 HTML 訊息"""
    dt = occurred_at or datetime.now(timezone.utc)
    tw_time = dt.astimezone(timezone(timedelta(hours=8)))
    time_str = tw_time.strftime("%Y-%m-%d %H:%M:%S")

    return (
        f"🚨 <b>【舟車勞頓 - 駕駛疲勞緊急通報】</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 <b>駕駛人員：</b>{driver_name} (<code>{driver_username}</code>)\n"
        f"⚠️ <b>警報原因：</b><b>{reason}</b>\n"
        f"📊 <b>疲勞分數：</b><code>{score:.1f}%</code> (嚴重疲勞)\n"
        f"⏱️ <b>累積次數：</b>{window_count} 次 (已觸發通報門檻)\n"
        f"🕒 <b>發生時間：</b>{time_str} (UTC+8)\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"⚠️ <b>請車隊主管或相關人員立即確認駕駛狀態以確保行車安全！</b>"
    )


def send_telegram_fatigue_alert(
    driver_name: str,
    driver_username: str,
    reason: str,
    score: float,
    window_count: int,
    occurred_at: Optional[datetime] = None,
    chat_id: Optional[str] = None,
    bot_token: Optional[str] = None,
) -> Dict[str, Any]:
    """快捷發送疲勞警報到 Telegram"""
    msg = format_telegram_fatigue_message(
        driver_name=driver_name,
        driver_username=driver_username,
        reason=reason,
        score=score,
        window_count=window_count,
        occurred_at=occurred_at,
    )
    return send_telegram_message(
        chat_id=chat_id,
        message_text=msg,
        bot_token=bot_token,
    )


def send_telegram_test_message(
    chat_id: Optional[str] = None,
    bot_token: Optional[str] = None,
    user_name: str = "",
    role: str = "",
) -> Dict[str, Any]:
    """發送 Telegram 測試連線訊息"""
    now_tw = datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M:%S")
    msg = (
        f"🔔 <b>【舟車勞頓 - Telegram 推播連線測試】</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"恭喜！您的 Telegram Bot 已成功與系統完成串接。\n\n"
        f"👤 <b>測試人員：</b>{user_name or '管理者'}\n"
        f"🛡️ <b>帳號角色：</b>{role or 'developer'}\n"
        f"🕒 <b>發送時間：</b>{now_tw} (UTC+8)\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"當行駛中檢測到微睡眠、連續打哈欠或異常低頭時，將即時發送警報至此對話！"
    )
    return send_telegram_message(
        chat_id=chat_id,
        message_text=msg,
        bot_token=bot_token,
    )
