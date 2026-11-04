from collections import deque
import threading
import time
from typing import Any, Dict, List, Optional
from config import Config


class AlertManager:
    """
    警報管理器 (AlertManager)

    負責：
    1. 接收並記錄前端/邊緣端送達的嚴重警告 (Alert Events)。
    2. 使用滑動時間視窗 (Sliding Window) 統計一定時間內的警告次數。
    3. 當在設定的時間視窗內達到指定次數 (預設 3 次)，觸發通報狀態 (Escalation)。
    4. 支援通報冷卻防重複轟炸機制 (Notification Cooldown)。
    5. 保存歷史警告與通報事件，供後台管理者或老闆查詢。
    """

    def __init__(
        self,
        window_sec: Optional[float] = None,
        trigger_count: Optional[int] = None,
        notify_cooldown_sec: Optional[float] = None,
    ):
        self.window_sec = (
            window_sec
            if window_sec is not None
            else getattr(Config, "ALERT_WINDOW_SEC", 300)
        )
        self.trigger_count = (
            trigger_count
            if trigger_count is not None
            else getattr(Config, "ALERT_TRIGGER_COUNT", 3)
        )
        self.notify_cooldown_sec = (
            notify_cooldown_sec
            if notify_cooldown_sec is not None
            else getattr(Config, "ALERT_COOLDOWN_NOTIFY_SEC", 600)
        )

        self._lock = threading.Lock()

        # 存放所有歷史警報紀錄（供後台/老闆查詢，最多保留 500 筆）
        self.alert_history: List[Dict[str, Any]] = []

        # 滑動視窗內的有效警報隊列: deque of alert dicts
        self.window_alerts: deque = deque()

        # 紀錄升級通知歷史
        self.escalation_history: List[Dict[str, Any]] = []

        # 上一次觸發升級通知的時間戳
        self.last_escalated_time: Optional[float] = None

        # 當前是否處於升級警戒狀態
        self.is_escalated: bool = False

    def _prune_expired_window(self, now: float) -> None:
        """清除滑動視窗內已過期的警告 (必須在持有 _lock 的狀態下呼叫)"""
        threshold = now - self.window_sec
        while self.window_alerts and self.window_alerts[0]["timestamp"] < threshold:
            self.window_alerts.popleft()

    def record_alert(
        self,
        session_id: Optional[str] = None,
        score: float = 0.0,
        level: str = "Severe",
        reason: str = "疲勞警告",
        count: Optional[int] = None,
        timestamp: Optional[float] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        記錄一筆新的警告事件，並檢查是否在時間視窗內達到通報門檻。
        """
        now = timestamp if timestamp is not None else time.time()

        with self._lock:
            # 建立警報紀錄
            alert_item = {
                "id": len(self.alert_history) + 1,
                "session_id": session_id,
                "score": score,
                "level": level,
                "reason": reason,
                "client_count": count,
                "timestamp": now,
                "time_str": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(now)),
                "extra": extra or {},
            }

            self.alert_history.append(alert_item)
            if len(self.alert_history) > 500:
                self.alert_history.pop(0)

            self.window_alerts.append(alert_item)
            self._prune_expired_window(now)

            window_count = len(self.window_alerts)
            is_new_escalation = False
            message = (
                f"已記錄警告（{reason}），"
                f"最近 {int(self.window_sec)} 秒內累積 {window_count}/{self.trigger_count} 次"
            )

            # 檢查是否達到通報門檻
            if window_count >= self.trigger_count:
                self.is_escalated = True

                # 檢查冷卻時間，避免短時間內連環發送通知
                can_notify = (
                    self.last_escalated_time is None
                    or (now - self.last_escalated_time) >= self.notify_cooldown_sec
                )

                if can_notify:
                    self.last_escalated_time = now
                    is_new_escalation = True

                    escalation_record = {
                        "id": len(self.escalation_history) + 1,
                        "session_id": session_id,
                        "timestamp": now,
                        "time_str": time.strftime(
                            "%Y-%m-%d %H:%M:%S", time.localtime(now)
                        ),
                        "trigger_window_count": window_count,
                        "trigger_count_threshold": self.trigger_count,
                        "window_sec": self.window_sec,
                        "latest_reason": reason,
                        "trigger_alerts": list(self.window_alerts),
                    }
                    self.escalation_history.append(escalation_record)
                    message = (
                        f"🚨 警告在 {int(self.window_sec)} 秒內累積達 {window_count} 次"
                        f"（門檻為 {self.trigger_count} 次），已觸發後台通報！"
                    )
                else:
                    remaining_cd = int(
                        self.notify_cooldown_sec - (now - self.last_escalated_time)
                    )
                    message = (
                        f"⚠️ 警告次數已達標 ({window_count} 次)，"
                        f"後台通報冷卻中 (剩餘 {remaining_cd} 秒)"
                    )

            return {
                "status": "success",
                "alert": alert_item,
                "window_count": window_count,
                "trigger_count": self.trigger_count,
                "window_sec": self.window_sec,
                "is_escalated": self.is_escalated,
                "is_new_escalation": is_new_escalation,
                "message": message,
            }

    def get_status(self) -> Dict[str, Any]:
        """獲取當前警報與通報狀態快照"""
        now = time.time()
        with self._lock:
            self._prune_expired_window(now)
            window_count = len(self.window_alerts)
            return {
                "is_escalated": self.is_escalated,
                "window_count": window_count,
                "trigger_count": self.trigger_count,
                "window_sec": self.window_sec,
                "notify_cooldown_sec": self.notify_cooldown_sec,
                "total_alerts": len(self.alert_history),
                "total_escalations": len(self.escalation_history),
                "last_escalated_time": self.last_escalated_time,
                "last_escalated_time_str": (
                    time.strftime(
                        "%Y-%m-%d %H:%M:%S", time.localtime(self.last_escalated_time)
                    )
                    if self.last_escalated_time
                    else None
                ),
            }

    def get_recent_alerts(self, limit: int = 50) -> List[Dict[str, Any]]:
        """獲取最新警報清單（供後台或老闆查看）"""
        with self._lock:
            return list(self.alert_history[-limit:])

    def get_escalation_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """獲取升級通報歷史紀錄"""
        with self._lock:
            return list(self.escalation_history[-limit:])

    def reset(self) -> None:
        """重置當前滑動視窗與升級狀態"""
        with self._lock:
            self.window_alerts.clear()
            self.is_escalated = False

