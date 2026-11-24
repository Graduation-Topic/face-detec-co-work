"""
discord_notifier.py — Discord Webhook 推播通知模組

特點：
1. 完全免企業/官方帳號審核，任何個人使用者或車隊皆可 30 秒快速建立 Webhook。
2. 支援 Discord Rich Embed 精美警報卡片（包含嚴重等級顏色、發生時間戳記、駕駛資訊與統計欄位）。
3. 支援全域預設環境變數 (DISCORD_WEBHOOK_URL) 或個別使用者/主管設定之專屬 Webhook。
4. 使用 Python 內建 urllib，無須安裝額外依賴套件。
"""

import json
import logging
import os
import urllib.error
import urllib.request
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def get_default_discord_webhook() -> str:
    """取得系統全域預設的 Discord Webhook URL"""
    return os.environ.get("DISCORD_WEBHOOK_URL", "").strip()


def send_discord_message(
    webhook_url: Optional[str] = None,
    payload: Optional[Dict[str, Any]] = None,
    content: Optional[str] = None,
    embeds: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    發送訊息到指定的 Discord Webhook。
    
    :param webhook_url: Discord Webhook 完整 URL，若未提供則使用全域環境變數
    :param payload: 完整自訂 payload (包含 content 或 embeds)
    :param content: 純文字訊息 (選填)
    :param embeds: Discord Embed 格式物件清單 (選填)
    :return: dict 包含 {"success": bool, "message": str, "status_code": int}
    """
    url = (webhook_url or "").strip() or get_default_discord_webhook()

    if not url:
        logger.warning("[Discord API] 未設定 Discord Webhook URL，跳過推播")
        return {
            "success": False,
            "message": "未設定 Discord Webhook URL",
            "status_code": 400,
        }

    if not url.startswith("https://discord.com/api/webhooks/") and not url.startswith("https://discordapp.com/api/webhooks/"):
        logger.warning(f"[Discord API] 無效的 Discord Webhook URL: {url[:30]}...")
        return {
            "success": False,
            "message": "Discord Webhook URL 格式無效 (需為 https://discord.com/api/webhooks/...)",
            "status_code": 400,
        }

    if payload is None:
        payload = {
            "username": "舟車勞頓 駕駛安全防護中心",
            "avatar_url": "https://raw.githubusercontent.com/twitter/twemoji/master/assets/72x72/1f6a8.png",
        }
        if content:
            payload["content"] = content
        if embeds:
            payload["embeds"] = embeds

    data_bytes = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
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
            logger.info(f"[Discord API] 成功發送推播 (狀態碼: {status_code})")
            return {
                "success": True,
                "message": "Discord 推播發送成功",
                "status_code": status_code,
            }
    except urllib.error.HTTPError as e:
        err_body = ""
        try:
            err_body = e.read().decode("utf-8", errors="replace")
        except Exception:
            pass
        logger.error(f"[Discord API] 發送失敗 HTTP {e.code}: {err_body}")
        return {
            "success": False,
            "message": f"Discord API 回傳錯誤 ({e.code}): {err_body}",
            "status_code": e.code,
        }
    except Exception as e:
        logger.error(f"[Discord API] 連線異常: {e}")
        return {
            "success": False,
            "message": f"連線異常: {str(e)}",
            "status_code": 500,
        }


def format_discord_fatigue_embed(
    driver_name: str,
    driver_username: str,
    reason: str,
    score: float,
    window_count: int,
    occurred_at: Optional[datetime] = None,
) -> Dict[str, Any]:
    """格式化為 Discord Rich Embed 結構"""
    dt = occurred_at or datetime.now(timezone.utc)
    tw_time = dt.astimezone(timezone(timedelta(hours=8)))
    time_str = tw_time.strftime("%Y-%m-%d %H:%M:%S (UTC+8)")
    iso_time = dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # 0xE74C3C: 強烈紅色 (危險/警報)
    embed = {
        "title": "🚨【舟車勞頓 - 駕駛疲勞緊急通報】",
        "description": "車載 AI 邊緣端檢測到駕駛員出現**嚴重疲勞狀態**，已達通報門檻！",
        "color": 0xE74C3C,
        "fields": [
            {
                "name": "👤 駕駛人員",
                "value": f"{driver_name} (`{driver_username}`)",
                "inline": True,
            },
            {
                "name": "⚠️ 警報原因",
                "value": f"**{reason}**",
                "inline": True,
            },
            {
                "name": "📊 疲勞指數",
                "value": f"`{score:.1f}%`",
                "inline": True,
            },
            {
                "name": "⏱️ 視窗累積",
                "value": f"**{window_count} 次** (觸發升級)",
                "inline": True,
            },
            {
                "name": "🕒 發生時間",
                "value": time_str,
                "inline": True,
            },
            {
                "name": "🛡️ 安全指引",
                "value": "請車隊主管或相關人員立即以無線電/通話確認駕駛意識狀態，必要時安排替換或進服務區休息！",
                "inline": False,
            },
        ],
        "footer": {
            "text": "舟車勞頓 AI 智慧行車安全防護平台",
            "icon_url": "https://raw.githubusercontent.com/twitter/twemoji/master/assets/72x72/1f698.png",
        },
        "timestamp": iso_time,
    }
    return embed


def send_discord_fatigue_alert(
    driver_name: str,
    driver_username: str,
    reason: str,
    score: float,
    window_count: int,
    occurred_at: Optional[datetime] = None,
    webhook_url: Optional[str] = None,
) -> Dict[str, Any]:
    """快捷發送疲勞警報到 Discord"""
    embed = format_discord_fatigue_embed(
        driver_name=driver_name,
        driver_username=driver_username,
        reason=reason,
        score=score,
        window_count=window_count,
        occurred_at=occurred_at,
    )
    content = "@everyone ⚠️ **【緊急通報】駕駛員疲勞程度已達危險警戒！**"
    return send_discord_message(
        webhook_url=webhook_url,
        content=content,
        embeds=[embed],
    )


def send_discord_test_message(
    webhook_url: Optional[str] = None,
    user_name: str = "",
    role: str = "",
) -> Dict[str, Any]:
    """發送 Discord 測試連線訊息"""
    now_tw = datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M:%S")
    iso_time = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # 0x2ECC71: 綠色 (正常/測試成功)
    embed = {
        "title": "🔔【舟車勞頓 - Discord 推播連線測試】",
        "description": "恭喜！您的 Discord Webhook 已成功與「舟車勞頓」系統完成串接。",
        "color": 0x2ECC71,
        "fields": [
            {
                "name": "測試人員",
                "value": user_name or "管理者",
                "inline": True,
            },
            {
                "name": "帳號角色",
                "value": role or "developer",
                "inline": True,
            },
            {
                "name": "測試時間",
                "value": f"{now_tw} (UTC+8)",
                "inline": False,
            },
            {
                "name": "通報說明",
                "value": "當車輛行駛中檢測到微睡眠、連續打哈欠或嚴重低頭時，系統將即時發送紅色警報卡片至此頻道。",
                "inline": False,
            },
        ],
        "footer": {
            "text": "舟車勞頓 AI 智慧行車安全防護平台",
        },
        "timestamp": iso_time,
    }

    return send_discord_message(
        webhook_url=webhook_url,
        embeds=[embed],
    )
