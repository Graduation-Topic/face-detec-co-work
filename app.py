import os

# ========== 環境偵測：本地 vs Render ==========
# Render 會自動注入 RENDER=true 環境變數；本地開發則不會有這個變數。
IS_RENDER = os.environ.get("RENDER") == "true"

if not IS_RENDER:
    # 本地開發環境：從 .env 檔案載入環境變數（.env 已加入 .gitignore，不會上傳到 GitHub）
    from dotenv import load_dotenv
    load_dotenv()

from flask import Flask, jsonify, redirect, render_template, request, send_from_directory, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from alert_manager import AlertManager
from config import Config
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

state = State(fps=Config.FPS, window_sec=Config.WINDOWS_SEC)
alert_manager = AlertManager(
    window_sec=Config.ALERT_WINDOW_SEC,
    trigger_count=Config.ALERT_TRIGGER_COUNT,
    notify_cooldown_sec=Config.ALERT_COOLDOWN_NOTIFY_SEC,
)

# 啟動時確認 Supabase 資料表可用
init_db()


# ========== 工具函式 ==========

def _require_admin():
    """若 session 不是 admin 或 super_admin，回傳 401 JSON；否則回傳 None（代表通過）"""
    role = session.get("role")
    if role not in ("admin", "super_admin"):
        return jsonify({"status": "error", "message": "請先以管理員身份登入"}), 401
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
    if session.get("role") in ("admin", "super_admin"):
        return redirect(url_for("dashboard", page="overview"))
    elif session.get("role") == "driver":
        return redirect(url_for("demo"))
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
    if session.get("role") not in ("admin", "super_admin"):
        return redirect(url_for("login"))
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
            from database import supabase
            new_hash = generate_password_hash(password)
            try:
                supabase.table("users").update({"hash_password": new_hash}).eq("uuid", str(user.id)).execute()
            except Exception:
                supabase.table("users").update({"password_hash": new_hash}).eq("id", user.id).execute()
        except Exception as update_err:
            app.logger.warning(f"[AUTH] Auto-upgrade password hash failed: {update_err}")

    if is_valid_pw:
        session.clear()
        session["user_id"] = user.id
        session["username"] = user.username
        session["display_name"] = user.display_name or user.username
        session["role"] = user.role
        return jsonify({
            "status": "ok",
            "role": user.role,
            "display_name": user.display_name,
        })
    return jsonify({"status": "error", "message": "帳號或密碼錯誤"}), 401


@app.route("/api/auth/logout", methods=["POST"])
def api_logout():
    session.clear()
    return jsonify({"status": "ok"})


@app.route("/api/auth/me")
def api_me():
    if "user_id" in session:
        return jsonify({
            "logged_in": True,
            "id": session.get("user_id"),
            "username": session.get("username"),
            "display_name": session.get("display_name"),
            "role": session.get("role"),
        })
    return jsonify({"logged_in": False})


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
    data = request.get_json(silent=True) or {}
    session_id = data.get("session_id")
    score = float(data.get("score", 0.0))
    level = str(data.get("level", "Severe"))
    reason = str(data.get("reason", "疲勞警告"))
    count = data.get("count")
    timestamp = data.get("timestamp")

    # 1. AlertManager 處理滑動視窗邏輯
    result = alert_manager.record_alert(
        session_id=session_id,
        score=score,
        level=level,
        reason=reason,
        count=count,
        timestamp=timestamp,
        extra=data.get("extra"),
    )

    # 2. 同步更新當前 state 狀態
    state.escalated_alert = result["is_escalated"]
    state.recent_alert_count = result["window_count"]

    # 3. 寫入資料庫（異常不影響主流程回應）
    try:
        event_payload = {
            "session_id": session_id,
            "score": score,
            "level": level,
            "reason": reason,
            "client_count": count,
            "window_count": result["window_count"],
            "is_escalated": 1 if result["is_escalated"] else 0,
            "is_new_escalation": 1 if result["is_new_escalation"] else 0,
            "client_timestamp": timestamp,
        }
        if session.get("user_id"):
            event_payload["user_id"] = session.get("user_id")

        insert_event(event_payload)

        # 4. 順便清理過期資料（不影響回應時間，偶發失敗可忽略）
        try:
            purge_old_alerts()
        except Exception as purge_err:
            app.logger.warning(f"[DB] purge_old_alerts failed (non-critical): {purge_err}")

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

    limit = int(request.args.get("limit", 50))
    current_role = session.get("role")
    current_user_id = session.get("user_id")

    driver_ids = None
    if current_role == "admin":
        # 一般管理員只能查看自己名下駕駛員的警報
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

    current_role = session.get("role")
    current_user_id = session.get("user_id")

    try:
        # 建立管理者名稱查找表
        managers_dict = {}
        try:
            for m in list_users(role="admin"):
                managers_dict[m.id] = m.display_name or m.username
            for m in list_users(role="super_admin"):
                managers_dict[m.id] = m.display_name or m.username
        except Exception:
            pass

        if current_role == "super_admin":
            # 總管理員可以看到所有使用者
            users = list_users()
        else:
            # 一般管理員只能看到自己名下的駕駛員
            users = list_users(role="driver", manager_id=current_user_id)

        user_list = []
        for u in users:
            item = u.to_dict()
            if u.manager_id:
                item["manager_name"] = managers_dict.get(u.manager_id, f"管理員 #{u.manager_id}")
            else:
                item["manager_name"] = "無 (直屬/管理者)"
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
    """獲取所有管理員列表（供總管理員指派所屬主管使用）"""
    guard = _require_admin()
    if guard:
        return guard

    try:
        admins = list_users(role="admin")
        supers = list_users(role="super_admin")
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
    """建立新使用者 (模式 A: 後台管理員開通)"""
    guard = _require_admin()
    if guard:
        return guard

    current_role = session.get("role")
    current_user_id = session.get("user_id")

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
    if current_role != "super_admin":
        # 一般管理員只能建立 driver，且 manager_id 強制為當前登入者
        requested_role = "driver"
        manager_id = current_user_id
    else:
        # 總管理員可以建立 admin 或 driver
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


@app.route("/api/admin/users/<user_id>", methods=["DELETE"])
def api_admin_delete_user(user_id):
    """刪除使用者"""
    guard = _require_admin()
    if guard:
        return guard

    current_role = session.get("role")
    current_user_id = session.get("user_id")

    if user_id == current_user_id:
        return jsonify({"status": "error", "message": "無法刪除目前登入的自己帳號"}), 400

    try:
        target = get_user_by_id(user_id)
        if not target:
            return jsonify({"status": "error", "message": "找不到該使用者"}), 404

        # 權限驗證：一般管理員只能刪除自己管轄名下的 driver
        if current_role != "super_admin":
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
