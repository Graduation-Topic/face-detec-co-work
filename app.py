import math
import os
import time
from datetime import datetime, timezone

# ========== 環境偵測：本地 vs Render ==========
# Render 會自動注入 RENDER=true 環境變數；本地開發則不會有這個變數。
IS_RENDER = os.environ.get("RENDER") == "true"

if not IS_RENDER:
    # 本地開發環境：從 .env 檔案載入環境變數（.env 已加入 .gitignore，不會上傳到 GitHub）
    from dotenv import load_dotenv
    load_dotenv()

from flask import Flask, jsonify, redirect, render_template, request, send_from_directory, url_for
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from werkzeug.security import check_password_hash, generate_password_hash

from alert_manager import AlertManager
from config import Config
from line_notifier import (
    format_fatigue_alert_message,
    get_default_line_token,
    send_line_push_message,
)
from database import (
    create_user,
    delete_user,
    get_user_by_id,
    get_user_by_username,
    init_db,
    insert_event,
    list_recent_alerts,
    list_users,
    purge_old_alerts,
    update_user,
)
from state import State


app = Flask(
    __name__,
    static_folder="assets",
    static_url_path="/assets",
    template_folder="templates",
)
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-change-me-in-production")
auth_serializer = URLSafeTimedSerializer(app.secret_key, salt="face-detection-auth")
AUTH_TOKEN_MAX_AGE = 86400

ALLOWED_FATIGUE_LEVELS = {"Normal", "Mild", "Severe"}

state = State(fps=Config.FPS, window_sec=Config.WINDOWS_SEC)
alert_manager = AlertManager(
    window_sec=Config.ALERT_WINDOW_SEC,
    trigger_count=Config.ALERT_TRIGGER_COUNT,
    notify_cooldown_sec=Config.ALERT_COOLDOWN_NOTIFY_SEC,
)

# 啟動時確認 Supabase 資料表可用
try:
    init_db()
except Exception as _db_init_err:
    print(f"[DB] init_db 連線檢測: {_db_init_err}")


# ========== 工具函式 ==========

def _require_admin():
    identity = _get_identity()
    role = identity.get("role") if identity else None
    if role not in ("admin", "developer", "super_admin"):
        return jsonify({"status": "error", "message": "請先以管理員身份登入"}), 401
    return None


def _get_identity():
    """取得目前分頁的登入身份，優先使用 Authorization Bearer Token，相容 Flask session。"""
    authorization = request.headers.get("Authorization", "")
    if authorization.startswith("Bearer "):
        token = authorization[7:].strip()
        if token:
            try:
                identity = auth_serializer.loads(token, max_age=AUTH_TOKEN_MAX_AGE)
                if isinstance(identity, dict) and identity.get("user_id"):
                    return identity
            except (BadSignature, SignatureExpired):
                pass

    if session.get("user_id"):
        return {
            "user_id": session.get("user_id"),
            "username": session.get("username"),
            "display_name": session.get("display_name"),
            "role": session.get("role"),
        }
    return None


# ========== 頁面路由 ==========

@app.route("/")
@app.route("/index")
@app.route("/index.html")
def index():
    response = app.make_response(render_template("index.html"))
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
    return response


@app.route("/demo")
@app.route("/demo.html")
def demo():
    response = app.make_response(render_template("demo.html"))
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
    return response


@app.route("/login")
@app.route("/login.html")
def login():
    response = app.make_response(render_template("login.html"))
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
    return response


@app.route("/docs")
@app.route("/docs.html")
def docs():
    response = app.make_response(render_template("docs.html"))
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
    return response



@app.route("/dashboard")
@app.route("/dashboard.html")
@app.route("/dashboard/<page>")
def dashboard(page="overview"):
    allowed_pages = [
        "overview",
        "manage",
        "settings"
    ]
    if page not in allowed_pages:
        return "Page Not Found", 404
    response = app.make_response(
        render_template("dashboard.html")
    )
    response.headers["Cache-Control"] = (
        "no-store, no-cache, must-revalidate"
    )
    return response


# ========== 驗證 API ==========

@app.route("/api/auth/login", methods=["POST"])
def api_login():
    """管理員與使用者登入"""
    data = request.get_json(silent=True) or {}
    username = str(data.get("username", "")).strip()
    password = str(data.get("password", ""))

    if not username or not password:
        return jsonify({"status": "error", "message": "請輸入帳號與密碼"}), 400

    user = get_user_by_username(username)
    if not user:
        return jsonify({"status": "error", "message": "帳號或密碼錯誤"}), 401

    is_valid_pw = False
    try:
        is_valid_pw = check_password_hash(user.password_hash, password)
    except Exception:
        is_valid_pw = False

    # 相容性機制：若資料庫內為未加密明文密碼（如在 Supabase 手動填入），予以通過並自動升級為雜湊
    if not is_valid_pw and user.password_hash == password:
        is_valid_pw = True
        try:
            new_hash = generate_password_hash(password)
            update_user(user.id, password_hash=new_hash)
        except Exception as update_err:
            app.logger.warning(f"[AUTH] Auto-upgrade password hash failed: {update_err}")

    if is_valid_pw:
        token = auth_serializer.dumps({
            "user_id": user.id,
            "username": user.username,
            "display_name": user.display_name or user.username,
            "role": user.role,
        })
        return jsonify({
            "status": "ok",
            "token": token,
            "role": user.role,
            "display_name": user.display_name,
        })
    return jsonify({"status": "error", "message": "帳號或密碼錯誤"}), 401


@app.route("/logout")
def logout():
    return redirect(url_for("login"))


@app.route("/api/auth/logout", methods=["POST"])
def api_logout():
    return jsonify({"status": "ok"})


@app.route("/api/auth/me")
def api_me():
    identity = _get_identity()
    if identity:
        return jsonify({
            "logged_in": True,
            "id": identity.get("user_id"),
            "username": identity.get("username"),
            "display_name": identity.get("display_name"),
            "role": identity.get("role"),
        })
    return jsonify({"logged_in": False})


# ========== 使用者個人設定 API (LINE 綁定與推播) ==========

@app.route("/api/user/line-settings", methods=["GET"])
def api_get_line_settings():
    """取得當前登入使用者的 LINE 綁定設定"""
    identity = _get_identity()
    user_id = identity.get("user_id") if identity else None
    if not user_id:
        return jsonify({"status": "error", "message": "請先登入"}), 401

    user = get_user_by_id(user_id)
    if not user:
        return jsonify({"status": "error", "message": "使用者不存在"}), 404

    return jsonify({
        "status": "success",
        "settings": {
            "user_id": user.id,
            "username": user.username,
            "display_name": user.display_name,
            "role": user.role,
            "line_user_id": user.line_user_id or "",
            "has_line": bool(user.line_user_id and user.line_user_id.strip()),
            "has_custom_token": bool(user.line_token and user.line_token.strip()),
            "has_system_token": bool(get_default_line_token()),
            "line_notify_enabled": user.line_notify_enabled,
            "line_notify_all": user.line_notify_all,
        }
    })


@app.route("/api/user/password", methods=["POST"])
def api_change_user_password():
    """更新當前登入使用者的密碼"""
    identity = _get_identity()
    user_id = identity.get("user_id") if identity else None
    if not user_id:
        return jsonify({"status": "error", "message": "請先登入"}), 401

    user = get_user_by_id(user_id)
    if not user:
        return jsonify({"status": "error", "message": "使用者不存在"}), 404

    data = request.get_json(silent=True) or {}
    new_password = str(data.get("password", "")).strip()
    if len(new_password) < 4:
        return jsonify({"status": "error", "message": "密碼至少需要 4 位數"}), 400

    try:
        update_user(user.id, password_hash=generate_password_hash(new_password))
        return jsonify({"status": "success", "message": "密碼已成功更新"})
    except Exception as e:
        app.logger.error(f"[USER] update password error: {e}")
        return jsonify({"status": "error", "message": "密碼更新失敗"}), 500


@app.route("/api/user/line-settings", methods=["POST"])
def api_save_line_settings():
    """儲存當前登入使用者的 LINE 綁定設定"""
    identity = _get_identity()
    user_id = identity.get("user_id") if identity else None
    if not user_id:
        return jsonify({"status": "error", "message": "請先登入"}), 401

    user = get_user_by_id(user_id)
    if not user:
        return jsonify({"status": "error", "message": "使用者不存在"}), 404

    data = request.get_json(silent=True) or {}
    line_user_id = data.get("line_user_id")
    line_token = data.get("line_token")
    line_notify_enabled = data.get("line_notify_enabled")
    line_notify_all = data.get("line_notify_all")

    kwargs = {}
    if line_user_id is not None:
        kwargs["line_user_id"] = str(line_user_id).strip() or None
    if line_token is not None and line_token != "__UNCHANGED__":
        kwargs["line_token"] = str(line_token).strip() or None
    if line_notify_enabled is not None:
        kwargs["line_notify_enabled"] = bool(line_notify_enabled)
    if line_notify_all is not None and user.role in ("developer", "super_admin"):
        kwargs["line_notify_all"] = bool(line_notify_all)

    try:
        updated = update_user(user_id, **kwargs)
        return jsonify({
            "status": "success",
            "message": "LINE 設定已成功儲存",
            "settings": {
                "line_user_id": updated.line_user_id or "",
                "has_line": bool(updated.line_user_id and updated.line_user_id.strip()),
                "has_custom_token": bool(updated.line_token and updated.line_token.strip()),
                "line_notify_enabled": updated.line_notify_enabled,
                "line_notify_all": updated.line_notify_all,
            }
        })
    except Exception as e:
        app.logger.error(f"[USER] update line settings error: {e}")
        return jsonify({"status": "error", "message": f"儲存失敗: {e}"}), 500


@app.route("/api/user/line-settings/test", methods=["POST"])
def api_test_line_message():
    """發送 LINE 測試訊息"""
    identity = _get_identity()
    user_id = identity.get("user_id") if identity else None
    if not user_id:
        return jsonify({"status": "error", "message": "請先登入"}), 401

    user = get_user_by_id(user_id)
    if not user:
        return jsonify({"status": "error", "message": "使用者不存在"}), 404

    data = request.get_json(silent=True) or {}
    target_id = str(data.get("line_user_id") or user.line_user_id or "").strip()
    custom_token = data.get("line_token")
    if custom_token == "__UNCHANGED__" or custom_token is None:
        token_to_use = user.line_token
    else:
        token_to_use = str(custom_token).strip() or None

    if not target_id:
        return jsonify({"status": "error", "message": "請填寫 LINE User ID 或 Group ID"}), 400

    from datetime import timedelta
    now_tw = datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M:%S")
    test_msg = (
        f"🔔【舟車勞頓 系統推播測試】\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"您好，這是一則 LINE Messaging API 測試推播！\n"
        f"綁定帳號：{user.display_name or user.username} ({user.username})\n"
        f"帳號角色：{user.role}\n"
        f"發送時間：{now_tw}\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"若收到此訊息，表示 LINE 推播功能已正確運作！"
    )

    res = send_line_push_message(
        to_user_id=target_id,
        message_text=test_msg,
        channel_access_token=token_to_use,
    )

    if res["success"]:
        return jsonify({"status": "success", "message": "測試訊息已成功送達！請查看您的 LINE 訊息。"})
    else:
        return jsonify({"status": "error", "message": res["message"]}), 400


# ========== 配置 API ==========

@app.route("/api/config")
def api_config():
    return jsonify({
        "LEFT_EAR_POINTS": Config.LEFT_EAR_POINTS,
        "RIGHT_EAR_POINTS": Config.RIGHT_EAR_POINTS,
        "NOSE": list(Config.NOSE),
        "MOUTH": list(Config.MOUTH),
        "MAR_POINTS": Config.MAR_POINTS,

        "WINDOWS_SEC": Config.WINDOWS_SEC,
        "EAR_CLOSED_THRESHOLD": Config.EAR_CLOSED_THRESHOLD,
        "YAWN_THRESHOLD": Config.YAWN_THRESHOLD,
        "EYE_CLOSURE_MIN_DURATION": Config.EYE_CLOSURE_MIN_DURATION,
        "BLINK_MIN_DURATION": Config.BLINK_MIN_DURATION,
        "YAWN_MIN_DURATION": Config.YAWN_MIN_DURATION,

        # 頭部姿態參數輸出至前端
        "NOD_RATIO_THRESHOLD": Config.NOD_RATIO_THRESHOLD,
        "NOD_MIN_DURATION": Config.NOD_MIN_DURATION,
        "NOD_SNAP_WINDOW_SEC": Config.NOD_SNAP_WINDOW_SEC,
        "NOD_SNAP_DROP": Config.NOD_SNAP_DROP,
        "NOD_SNAP_RATIO_OFFSET": Config.NOD_SNAP_RATIO_OFFSET,
        "NOD_SNAP_MIN_FRAMES": Config.NOD_SNAP_MIN_FRAMES,
        "TURN_CENTER": Config.TURN_CENTER,
        "TURN_MARGIN": Config.TURN_MARGIN,

        "CALIBRATION_FRAMES": Config.CALIBRATION_FRAMES,
        "CALIBRATION_EAR_RATIO": Config.CALIBRATION_EAR_RATIO,
        "CALIBRATION_MAR_OFFSET": Config.CALIBRATION_MAR_OFFSET,
        "CALIBRATION_NOD_OFFSET": Config.CALIBRATION_NOD_OFFSET,
        "MICROSLEEP_MIN_DURATION": Config.MICROSLEEP_MIN_DURATION,

        "PERCLOS_SEVERE_RATIO": Config.PERCLOS_SEVERE_RATIO,
        "YAWN_RATE_SEVERE_PER_MIN": Config.YAWN_RATE_SEVERE_PER_MIN,

        "FATIGUE_WEIGHT_PERCLOS": Config.FATIGUE_WEIGHT_PERCLOS,
        "FATIGUE_WEIGHT_EYE_CLOSURE": Config.FATIGUE_WEIGHT_EYE_CLOSURE,
        "FATIGUE_WEIGHT_YAWN": Config.FATIGUE_WEIGHT_YAWN,

        "FATIGUE_SCORE_MILD": Config.FATIGUE_SCORE_MILD,
        "FATIGUE_SCORE_SEVERE": Config.FATIGUE_SCORE_SEVERE,

        "ALERT_COOLDOWN_SECONDS": Config.ALERT_COOLDOWN_SECONDS,
        "LOG_INTERVAL_SEC": Config.LOG_INTERVAL_SEC,

        # 警報累計與後台通報門檻
        "ALERT_WINDOW_SEC": Config.ALERT_WINDOW_SEC,
        "ALERT_TRIGGER_COUNT": Config.ALERT_TRIGGER_COUNT,
        "ALERT_COOLDOWN_NOTIFY_SEC": Config.ALERT_COOLDOWN_NOTIFY_SEC,

        # 資料庫清理設定
        "ALERT_RETENTION_DAYS": Config.ALERT_RETENTION_DAYS,
        "ALERT_MAX_DB_RECORDS": Config.ALERT_MAX_DB_RECORDS,

        # 環境亮度與高光門檻輸出至前端
        "ENV_LUMA_HIGHLIGHT": Config.ENV_LUMA_HIGHLIGHT,
        "ENV_NIGHT_BRIGHTNESS": Config.ENV_NIGHT_BRIGHTNESS,
        "ENV_NIGHT_HIGHLIGHT_RATIO": Config.ENV_NIGHT_HIGHLIGHT_RATIO,
        "ENV_DAY_BRIGHTNESS": Config.ENV_DAY_BRIGHTNESS,
        "ENV_DAY_HIGHLIGHT_RATIO": Config.ENV_DAY_HIGHLIGHT_RATIO,
    })


# ========== 狀態 API ==========

@app.route("/api/state", methods=["GET"])
def api_state():
    return jsonify(state.snapshot())


@app.route("/api/state", methods=["POST"])
def update_state():
    data = request.get_json(silent=True) or {}
    state.update_from_api(data)
    return jsonify(state.snapshot())


@app.route("/api/state/reset", methods=["POST"])
def reset_state():
    state.reset_metrics()
    alert_manager.reset()
    return jsonify(state.snapshot())


# ========== 警報與後台管理 API ==========

@app.route("/api/alert", methods=["POST"])
def api_record_alert():
    """接收前端嚴重警告事件，進行滑動視窗累計、通報判定，並寫入資料庫"""
    identity = _get_identity()
    user_uuid = identity.get("user_id") if identity else None
    if not user_uuid:
        return jsonify({"status": "error", "message": "請先登入後再開始偵測"}), 401

    data = request.get_json(silent=True) or {}
    session_id = data.get("session_id")
    try:
        score = float(data.get("score", 0.0))
    except (TypeError, ValueError):
        return jsonify({"status": "error", "message": "警告分數格式錯誤"}), 400
    if not math.isfinite(score):
        return jsonify({"status": "error", "message": "警告分數格式錯誤"}), 400

    level = str(data.get("level", "Severe"))
    if level not in ALLOWED_FATIGUE_LEVELS:
        return jsonify({"status": "error", "message": "疲勞等級格式錯誤"}), 400

    reason = str(data.get("reason", "疲勞警告"))
    count = data.get("count")
    client_timestamp = data.get("timestamp")
    if client_timestamp is not None:
        try:
            client_timestamp = datetime.fromtimestamp(
                float(client_timestamp), timezone.utc
            )
        except (TypeError, ValueError, OverflowError):
            return jsonify({"status": "error", "message": "事件時間格式錯誤"}), 400

    # 1. AlertManager 處理滑動視窗邏輯 (使用伺服器時間防偏)
    result = alert_manager.record_alert(
        session_id=session_id,
        score=score,
        level=level,
        reason=reason,
        count=count,
        timestamp=time.time(),
        extra=data.get("extra"),
    )

    # 2. 同步更新當前 state 狀態
    state.escalated_alert = result["is_escalated"]
    state.recent_alert_count = result["window_count"]

    # 3. 寫入資料庫（異常不影響主流程回應）
    try:
        event_payload = {
            "uuid": user_uuid,
            "session_id": session_id,
            "score": score,
            "level": level,
            "reason": reason,
            "client_count": count,
            "window_count": result["window_count"],
            "is_escalated": bool(result["is_escalated"]),
            "is_new_escalation": bool(result["is_new_escalation"]),
            "client_timestamp": client_timestamp,
        }

        insert_event(event_payload)

        # 4. 疲勞升級時，發送 LINE Messaging API 推播通知
        if result.get("is_new_escalation"):
            try:
                driver = get_user_by_id(user_uuid)
                driver_name = (driver.display_name or driver.username) if driver else f"駕駛員 #{user_uuid}"
                driver_username = driver.username if driver else str(user_uuid)
                alert_msg = format_fatigue_alert_message(
                    driver_name=driver_name,
                    driver_username=driver_username,
                    reason=reason,
                    score=score,
                    window_count=result["window_count"],
                    occurred_at=client_timestamp or datetime.now(timezone.utc),
                )

                notified_uids = set()

                # 4.1 通報直屬主管 (車隊管理員)
                if driver and driver.manager_id:
                    try:
                        manager = get_user_by_id(driver.manager_id)
                        if (
                            manager
                            and manager.is_active
                            and manager.line_notify_enabled
                            and manager.line_user_id
                            and manager.line_user_id not in notified_uids
                        ):
                            send_line_push_message(
                                to_user_id=manager.line_user_id,
                                message_text=alert_msg,
                                channel_access_token=manager.line_token,
                            )
                            notified_uids.add(manager.line_user_id)
                    except Exception as mgr_err:
                        app.logger.warning(f"[LINE] 通報主管失敗: {mgr_err}")

                # 4.2 通報總管理員 / 開發者 (若 line_notify_all 開啟，或該駕駛員未指派直屬主管)
                try:
                    super_admins = list_users(role="developer") + list_users(role="super_admin")
                    for sa in super_admins:
                        if not sa.is_active or not sa.line_notify_enabled or not sa.line_user_id:
                            continue
                        if sa.line_user_id in notified_uids:
                            continue
                        if sa.line_notify_all or not (driver and driver.manager_id):
                            send_line_push_message(
                                to_user_id=sa.line_user_id,
                                message_text=alert_msg,
                                channel_access_token=sa.line_token,
                            )
                            notified_uids.add(sa.line_user_id)
                except Exception as sa_err:
                    app.logger.warning(f"[LINE] 通報總管理員失敗: {sa_err}")

            except Exception as line_err:
                app.logger.error(f"[LINE] 疲勞升級推播異常: {line_err}")

        # 5. 順便清理過期資料（不影響回應時間，偶發失敗可忽略）
        try:
            purge_old_alerts()
        except Exception as purge_err:
            app.logger.warning(f"[DB] Automatic alert cleanup failed: {purge_err}")

    except Exception as e:
        app.logger.error(f"[DB] Failed to save alert event: {e}")
        return jsonify({"status": "error", "message": "警告事件儲存失敗"}), 500

    return jsonify(result)


@app.route("/api/admin/alerts", methods=["GET"])
def api_admin_alerts():
    """提供後台管理者查詢即時警報與通報紀錄（需要 admin 登入）"""
    guard = _require_admin()
    if guard:
        return guard

    try:
        limit = int(request.args.get("limit", 50))
    except (TypeError, ValueError):
        return jsonify({"status": "error", "message": "顯示筆數格式錯誤"}), 400
    if not 1 <= limit <= 50:
        return jsonify({"status": "error", "message": "單頁最多顯示 50 筆"}), 400

    identity = _get_identity()
    current_role = identity.get("role")
    current_user_id = identity.get("user_id")

    driver_ids = None
    if current_role == "admin":
        # 一般管理員只能查看自己名下駕駛的警報
        try:
            my_drivers = list_users(role="driver", manager_id=current_user_id)
            driver_ids = [d.id for d in my_drivers]
        except Exception as err:
            app.logger.warning(f"[DB] list_users failed when filtering alerts: {err}")

    # 從資料庫讀取最新警告事件（依時間倒序）
    try:
        recent_alerts_from_db = [
            event.to_dict() for event in list_recent_alerts(limit, driver_ids=driver_ids)
        ]
    except Exception as e:
        app.logger.error(f"[DB] Failed to query alert events: {e}")
        return jsonify({"status": "error", "message": "警告事件查詢失敗"}), 500

    return jsonify({
        "status": alert_manager.get_status(),
        "recent_alerts": recent_alerts_from_db,
        "escalations": alert_manager.get_escalation_history(limit=limit),
    })


# ========== 使用者與員工管理 API (RBAC) ==========

@app.route("/api/admin/users", methods=["GET"])
def api_admin_list_users():
    """獲取可管轄的使用者列表"""
    guard = _require_admin()
    if guard:
        return guard

    identity = _get_identity()
    current_role = identity.get("role")
    current_user_id = identity.get("user_id")

    try:
        # 建立管理者名稱查找表
        managers_dict = {}
        try:
            for m in list_users(role="admin"):
                managers_dict[m.id] = m.display_name or m.username
            for m in list_users(role="developer"):
                managers_dict[m.id] = m.display_name or m.username
        except Exception:
            pass

        if current_role == "developer":
            # 開發者可以看到所有使用者
            users = list_users()
        else:
            # 一般管理員只能看到自己名下的駕駛
            users = list_users(role="driver", manager_id=current_user_id)

        user_list = []
        for u in users:
            item = u.to_dict()
            if u.manager_id:
                item["manager_name"] = managers_dict.get(u.manager_id, f"管理員 #{u.manager_id}")
            else:
                item["manager_name"] = "無"
            user_list.append(item)

        return jsonify({
            "status": "success",
            "users": user_list,
            "current_role": current_role,
            "current_user_id": current_user_id,
        })
    except Exception as e:
        app.logger.error(f"[DB] list_users error: {e}")
        return jsonify({"status": "error", "message": f"載入使用者清單失敗: {e}"}), 500


@app.route("/api/admin/managers", methods=["GET"])
def api_admin_list_managers():
    """獲取所有管理員列表（供開發者指派所屬主管使用）"""
    guard = _require_admin()
    if guard:
        return guard

    try:
        admins = list_users(role="admin")
        supers = list_users(role="developer")
        all_mgrs = admins + supers
        return jsonify({
            "status": "success",
            "managers": [
                {
                    "id": m.id,
                    "username": m.username,
                    "display_name": m.display_name or m.username,
                    "role": m.role,
                }
                for m in all_mgrs
            ]
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/api/admin/users", methods=["POST"])
def api_admin_create_user():
    guard = _require_admin()
    if guard:
        return guard

    identity = _get_identity()
    current_role = identity.get("role")
    current_user_id = identity.get("user_id")

    data = request.get_json(silent=True) or {}
    username = str(data.get("username", "")).strip()
    password = str(data.get("password", ""))
    display_name = str(data.get("display_name", "")).strip() or username
    requested_role = str(data.get("role", "driver")).strip()

    if not username or not password:
        return jsonify({"status": "error", "message": "帳號與密碼為必填欄位"}), 400

    if len(password) < 4:
        return jsonify({"status": "error", "message": "密碼長度至少需 4 個字元"}), 400

    # 權限驗證與角色分配
    if current_role != "developer":
        # 一般管理員只能建立 driver，且 manager_id 強制為當前登入者
        requested_role = "driver"
        manager_id = current_user_id
    else:
        # 開發者可以建立 admin 或 driver
        if requested_role not in ("admin", "driver"):
            requested_role = "driver"
        
        if requested_role == "driver":
            raw_mgr = data.get("manager_id")
            manager_id = str(raw_mgr).strip() if raw_mgr else None
        else:
            manager_id = None

    try:
        # 檢查帳號是否已存在
        existing = get_user_by_username(username)
        if existing:
            return jsonify({"status": "error", "message": f"帳號 '{username}' 已被使用"}), 400

        pw_hash = generate_password_hash(password)
        new_user = create_user(
            username=username,
            password_hash=pw_hash,
            display_name=display_name,
            role=requested_role,
            manager_id=manager_id,
        )
        return jsonify({
            "status": "success",
            "message": f"成功建立帳號：{new_user.username}",
            "user": new_user.to_dict(),
        }), 201
    except Exception as e:
        app.logger.error(f"[DB] create_user error: {e}")
        return jsonify({"status": "error", "message": f"建立失敗: {e}"}), 500


@app.route("/api/admin/users/<user_id>", methods=["PUT"])
def api_admin_update_user(user_id):
    """修改使用者資料 (開發者/總管理員可修改全部帳號資料；一般管理員僅可修改自己管轄名下的司機)"""
    guard = _require_admin()
    if guard:
        return guard

    identity = _get_identity()
    current_role = identity.get("role") if identity else None
    current_user_id = identity.get("user_id") if identity else None
    is_super = current_role in ("developer", "super_admin")

    target = get_user_by_id(user_id)
    if not target:
        return jsonify({"status": "error", "message": "找不到該使用者"}), 404

    data = request.get_json(silent=True) or {}

    # 權限檢查：一般管理員只能修改自己管轄名下的 driver
    if not is_super:
        if target.role != "driver" or target.manager_id != current_user_id:
            return jsonify({"status": "error", "message": "您無權修改此員工資料"}), 403

    update_fields = {}

    # 1. 姓名 / 顯示名稱
    if "display_name" in data:
        new_name = str(data["display_name"]).strip()
        if new_name:
            update_fields["display_name"] = new_name

    # 2. 密碼重設 (選填)
    if "password" in data:
        new_pw = str(data["password"]).strip()
        if new_pw:
            if len(new_pw) < 4:
                return jsonify({"status": "error", "message": "新密碼長度至少需 4 個字元"}), 400
            update_fields["password_hash"] = generate_password_hash(new_pw)

    # 3. 帳號啟用狀態
    if "is_active" in data:
        is_active = bool(data["is_active"])
        if target.id == current_user_id and not is_active:
            return jsonify({"status": "error", "message": "無法停用自己目前的帳號"}), 400
        update_fields["is_active"] = is_active

    # 4. 僅開發者/總管理員可修改的欄位 (身分角色、所屬主管、全域推播開關)
    if is_super:
        if "role" in data:
            requested_role = str(data["role"]).strip()
            if requested_role in ("developer", "super_admin", "admin", "driver"):
                if target.id == current_user_id and requested_role not in ("developer", "super_admin"):
                    return jsonify({"status": "error", "message": "開發者無法變更自己的身分角色"}), 400
                update_fields["role"] = requested_role

        if "manager_id" in data:
            raw_mgr = data["manager_id"]
            mgr_id = str(raw_mgr).strip() if (raw_mgr and str(raw_mgr).strip()) else None
            update_fields["manager_id"] = mgr_id

        if "line_notify_all" in data:
            update_fields["line_notify_all"] = bool(data["line_notify_all"])

    # 5. LINE User ID, Token, 推播開關
    if "line_user_id" in data:
        raw_luid = data["line_user_id"]
        update_fields["line_user_id"] = str(raw_luid).strip() if (raw_luid and str(raw_luid).strip()) else None

    if "line_token" in data and is_super:
        raw_token = data["line_token"]
        if raw_token != "__UNCHANGED__":
            update_fields["line_token"] = str(raw_token).strip() if (raw_token and str(raw_token).strip()) else None

    if "line_notify_enabled" in data:
        update_fields["line_notify_enabled"] = bool(data["line_notify_enabled"])

    try:
        updated = update_user(target.id, **update_fields)
        return jsonify({
            "status": "success",
            "message": f"已成功更新使用者「{updated.username}」的資料",
            "user": updated.to_dict(),
        })
    except Exception as e:
        app.logger.error(f"[DB] update_user error: {e}")
        return jsonify({"status": "error", "message": f"更新失敗: {e}"}), 500


@app.route("/api/admin/users/<user_id>", methods=["DELETE"])
def api_admin_delete_user(user_id):
    """刪除使用者"""
    guard = _require_admin()
    if guard:
        return guard

    identity = _get_identity()
    current_role = identity.get("role")
    current_user_id = identity.get("user_id")

    if user_id == current_user_id:
        return jsonify({"status": "error", "message": "無法刪除目前登入的自己帳號"}), 400

    try:
        target = get_user_by_id(user_id)
        if not target:
            return jsonify({"status": "error", "message": "找不到該使用者"}), 404

        # 權限驗證：一般管理員只能刪除自己管轄名下的 driver
        if current_role != "developer":
            if target.role != "driver" or target.manager_id != current_user_id:
                return jsonify({"status": "error", "message": "您無權刪除此員工"}), 403

        delete_user(user_id)
        return jsonify({"status": "success", "message": f"已刪除使用者：{target.username}"})
    except Exception as e:
        app.logger.error(f"[DB] delete_user error: {e}")
        return jsonify({"status": "error", "message": f"刪除失敗: {e}"}), 500


@app.route("/api/admin/alerts/reset", methods=["POST"])
def api_admin_alerts_reset():
    """管理員手動重置記憶體中的警報滑動視窗狀態（不刪除資料庫紀錄）"""
    guard = _require_admin()
    if guard:
        return guard

    alert_manager.reset()
    state.escalated_alert = False
    state.recent_alert_count = 0
    return jsonify({
        "status": "success",
        "message": "警報統計與通報狀態已重置（資料庫紀錄保留）",
        "data": alert_manager.get_status(),
    })


@app.route("/api/admin/alerts/purge", methods=["POST"])
def api_admin_alerts_purge():
    """管理員手動觸發清理過期警告事件"""
    guard = _require_admin()
    if guard:
        return guard

    try:
        deleted = purge_old_alerts()
        return jsonify({
            "status": "success",
            "message": f"已清理 {deleted} 筆過期警告事件",
            "deleted_count": deleted,
        })
    except Exception as e:
        app.logger.error(f"[DB] purge failed: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/model/<path:filename>")
def model_file(filename):
    return send_from_directory(
        os.path.join(app.root_path, "model"),
        filename,
    )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 4000))
    debug = os.environ.get("FLASK_DEBUG") == "1"

    print(f"[ENV] Running on {'Render' if IS_RENDER else 'Local'} | port={port} | debug={debug}")

    app.run(
        host="0.0.0.0",
        port=port,
        debug=debug,
        use_reloader=debug,
        threaded=True,
    )
