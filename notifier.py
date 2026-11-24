"""
notifier.py — 多管道通知統一調度器 (Unified Notification Dispatcher)

負責在駕駛疲勞事件升級 (Escalation) 或手動測試時，並行/循序調度多個通知管道：
1. LINE Messaging API (保持現有架構不變)
2. Discord Webhook (免審核、支援精美紅色警報卡片與即時推播)
3. Telegram Bot (全球開發者愛用、支援 HTML 警報格式)

各管道彼此隔離保護，單一管道異常或未配置不會影響其他管道正常運作。
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

from line_notifier import (
    format_fatigue_alert_message as format_line_alert_message,
    send_line_push_message,
)
from discord_notifier import (
    get_default_discord_webhook,
    send_discord_fatigue_alert,
)
from telegram_notifier import (
    get_default_telegram_token,
    get_default_telegram_chat_id,
    send_telegram_fatigue_alert,
)

logger = logging.getLogger(__name__)


def dispatch_fatigue_escalation_alert(
    driver_name: str,
    driver_username: str,
    reason: str,
    score: float,
    window_count: int,
    occurred_at: Optional[datetime] = None,
    driver: Optional[Any] = None,
    manager: Optional[Any] = None,
    admins: Optional[List[Any]] = None,
) -> Dict[str, Any]:
    """
    分發疲勞升級警報至所有已設定之通訊管道 (LINE, Discord, Telegram)。
    
    :param driver_name: 駕駛員顯示名稱
    :param driver_username: 駕駛員帳號
    :param reason: 警報觸發原因
    :param score: 當前疲勞分數
    :param window_count: 時間視窗內累積警告次數
    :param occurred_at: 事件發生時間
    :param driver: 駕駛員 User 物件 (可為 None)
    :param manager: 直屬主管 User 物件 (可為 None)
    :param admins: 管理員 User 物件清單 (可為 None)
    :return: 包含各管道派送結果的狀態字典
    """
    results: Dict[str, Any] = {
        "line": {"attempted": False, "success": False, "count": 0},
        "discord": {"attempted": False, "success": False},
        "telegram": {"attempted": False, "success": False},
    }

    # ----------------------------------------------------
    # 1. LINE Messaging API (保有原邏輯)
    # ----------------------------------------------------
    try:
        line_alert_msg = format_line_alert_message(
            driver_name=driver_name,
            driver_username=driver_username,
            reason=reason,
            score=score,
            window_count=window_count,
            occurred_at=occurred_at,
        )

        notified_line_uids: Set[str] = set()

        # 1.1 通報直屬主管
        if manager and getattr(manager, "is_active", True) and getattr(manager, "line_notify_enabled", True):
            mgr_uid = getattr(manager, "line_user_id", None)
            if mgr_uid and mgr_uid not in notified_line_uids:
                results["line"]["attempted"] = True
                res = send_line_push_message(
                    to_user_id=mgr_uid,
                    message_text=line_alert_msg,
                    channel_access_token=getattr(manager, "line_token", None),
                )
                if res.get("success"):
                    results["line"]["success"] = True
                    results["line"]["count"] += 1
                notified_line_uids.add(mgr_uid)

        # 1.2 通報管理員 (developer / admin)
        if admins:
            for sa in admins:
                if not getattr(sa, "is_active", True) or not getattr(sa, "line_notify_enabled", True):
                    continue
                sa_uid = getattr(sa, "line_user_id", None)
                if not sa_uid or sa_uid in notified_line_uids:
                    continue
                # 若 sa 設定接收全部，或者該駕駛無直屬主管，則通知管理員
                if getattr(sa, "line_notify_all", True) or not manager:
                    results["line"]["attempted"] = True
                    res = send_line_push_message(
                        to_user_id=sa_uid,
                        message_text=line_alert_msg,
                        channel_access_token=getattr(sa, "line_token", None),
                    )
                    if res.get("success"):
                        results["line"]["success"] = True
                        results["line"]["count"] += 1
                    notified_line_uids.add(sa_uid)

    except Exception as line_err:
        logger.error(f"[Notifier] LINE 通報派送失敗: {line_err}")
        results["line"]["error"] = str(line_err)

    # ----------------------------------------------------
    # 2. Discord Webhook
    # ----------------------------------------------------
    try:
        target_webhooks = set()
        # 2.1 直屬主管 Webhook
        if manager and getattr(manager, "discord_webhook", None):
            target_webhooks.add(getattr(manager, "discord_webhook").strip())

        # 2.2 管理員 (developer / admin) Webhook
        if admins:
            for sa in admins:
                if getattr(sa, "discord_webhook", None):
                    target_webhooks.add(getattr(sa, "discord_webhook").strip())

        # 2.3 駕駛員專屬 Webhook
        if driver and getattr(driver, "discord_webhook", None):
            target_webhooks.add(getattr(driver, "discord_webhook").strip())

        # 2.4 若個別皆未設定，則使用全域環境變數預設 Webhook
        sys_dc = get_default_discord_webhook()
        if sys_dc and not target_webhooks:
            target_webhooks.add(sys_dc.strip())

        if target_webhooks:
            results["discord"]["attempted"] = True
            all_dc_ok = True
            for wh in target_webhooks:
                dc_res = send_discord_fatigue_alert(
                    driver_name=driver_name,
                    driver_username=driver_username,
                    reason=reason,
                    score=score,
                    window_count=window_count,
                    occurred_at=occurred_at,
                    webhook_url=wh,
                )
                if not dc_res.get("success"):
                    all_dc_ok = False
            results["discord"]["success"] = all_dc_ok
        else:
            logger.debug("[Notifier] 未配置 Discord Webhook，跳過 Discord 派送")

    except Exception as dc_err:
        logger.error(f"[Notifier] Discord 通報派送失敗: {dc_err}")
        results["discord"]["error"] = str(dc_err)

    # ----------------------------------------------------
    # 3. Telegram Bot
    # ----------------------------------------------------
    try:
        tg_token = get_default_telegram_token()
        target_chats = set()

        if manager and getattr(manager, "telegram_chat_id", None):
            target_chats.add(getattr(manager, "telegram_chat_id").strip())

        if admins:
            for sa in admins:
                if getattr(sa, "telegram_chat_id", None):
                    target_chats.add(getattr(sa, "telegram_chat_id").strip())

        if driver and getattr(driver, "telegram_chat_id", None):
            target_chats.add(getattr(driver, "telegram_chat_id").strip())

        sys_tg_chat = get_default_telegram_chat_id()
        if sys_tg_chat and not target_chats:
            target_chats.add(sys_tg_chat.strip())

        if target_chats and tg_token:
            results["telegram"]["attempted"] = True
            all_tg_ok = True
            for chat in target_chats:
                tg_res = send_telegram_fatigue_alert(
                    driver_name=driver_name,
                    driver_username=driver_username,
                    reason=reason,
                    score=score,
                    window_count=window_count,
                    occurred_at=occurred_at,
                    chat_id=chat,
                    bot_token=tg_token,
                )
                if not tg_res.get("success"):
                    all_tg_ok = False
            results["telegram"]["success"] = all_tg_ok
        else:
            logger.debug("[Notifier] 未配置 Telegram Bot 或 Chat ID，跳過 Telegram 派送")

    except Exception as tg_err:
        logger.error(f"[Notifier] Telegram 通報派送失敗: {tg_err}")
        results["telegram"]["error"] = str(tg_err)

    return results
