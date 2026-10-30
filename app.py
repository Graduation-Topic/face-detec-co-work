import os

# ========== 環境偵測：本地 vs Render ==========
# Render 會自動注入 RENDER=true 環境變數；本地開發則不會有這個變數。
IS_RENDER = os.environ.get("RENDER") == "true"

if not IS_RENDER:
    # 本地開發環境：從 .env 檔案載入環境變數（.env 已加入 .gitignore，不會上傳到 GitHub）
    from dotenv import load_dotenv
    load_dotenv()

from flask import Flask, jsonify, redirect, render_template, request, send_from_directory, session, url_for
from werkzeug.security import check_password_hash

from alert_manager import AlertManager
from config import Config
from database import AlertEvent, User, init_db, purge_old_alerts, seed_admin_user, SessionLocal
from state import State


app = Flask(
    __name__,
    static_folder="assets",
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

# 啟動時建立資料表（若已存在則跳過），並自動建立預設 admin 帳號
init_db()
_boot_db = SessionLocal()
try:
    created = seed_admin_user(_boot_db)
    if created:
        print("[DB] 預設 admin 帳號已建立")
    else:
        print("[DB] admin 帳號已存在，跳過建立")
finally:
    _boot_db.close()


# ========== 工具函式 ==========

def _require_admin():
    """若 session 不是 admin，回傳 401 JSON；否則回傳 None（代表通過）"""
    if session.get("role") != "admin":
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
    # 若已登入 admin，直接跳到 dashboard
    if session.get("role") == "admin":
        return redirect(url_for("dashboard"))
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
def dashboard():
    if session.get("role") != "admin":
        return redirect(url_for("login"))
    response = app.make_response(render_template("dashboard.html"))
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
    return response


# ========== 認證 API ==========

@app.route("/api/auth/login", methods=["POST"])
def api_login():
    """管理員登入"""
    data = request.get_json(silent=True) or {}
    username = str(data.get("username", "")).strip()
    password = str(data.get("password", ""))

    if not username or not password:
        return jsonify({"status": "error", "message": "請輸入帳號與密碼"}), 400

    db = SessionLocal()
    try:
        user = db.query(User).filter_by(username=username).first()
        if user and check_password_hash(user.password_hash, password):
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
    finally:
        db.close()


@app.route("/api/auth/logout", methods=["POST"])
def api_logout():
    """登出"""
    session.clear()
    return jsonify({"status": "ok"})


@app.route("/api/auth/me")
def api_me():
    """回傳目前登入狀態"""
    if "user_id" in session:
        return jsonify({
            "logged_in": True,
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
    db = None
    try:
        db = SessionLocal()
        event = AlertEvent(
            session_id=session_id,
            score=score,
            level=level,
            reason=reason,
            client_count=count,
            window_count=result["window_count"],
            is_escalated=1 if result["is_escalated"] else 0,
            is_new_escalation=1 if result["is_new_escalation"] else 0,
            client_timestamp=timestamp,
        )
        db.add(event)
        db.commit()

        # 4. 順便清理過期資料（不影響回應時間，偶發失敗可忽略）
        try:
            purge_old_alerts(db)
        except Exception as purge_err:
            app.logger.warning(f"[DB] purge_old_alerts failed (non-critical): {purge_err}")

    except Exception as e:
        app.logger.error(f"[DB] Failed to save alert event: {e}")
    finally:
        if db:
            db.close()

    return jsonify(result)


@app.route("/api/admin/alerts", methods=["GET"])
def api_admin_alerts():
    """提供後台管理者查詢即時警報與通報紀錄（需要 admin 登入）"""
    guard = _require_admin()
    if guard:
        return guard

    limit = int(request.args.get("limit", 50))

    # 從資料庫讀取最新警告事件（依時間倒序）
    try:
        db = SessionLocal()
        db_events = (
            db.query(AlertEvent)
            .order_by(AlertEvent.created_at.desc())
            .limit(limit)
            .all()
        )
        recent_alerts_from_db = [e.to_dict() for e in db_events]
    except Exception as e:
        app.logger.error(f"[DB] Failed to query alert events: {e}")
        recent_alerts_from_db = []
    finally:
        db.close()

    return jsonify({
        "status": alert_manager.get_status(),
        "recent_alerts": recent_alerts_from_db,
        "escalations": alert_manager.get_escalation_history(limit=limit),
    })


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
        db = SessionLocal()
        deleted = purge_old_alerts(db)
        return jsonify({
            "status": "success",
            "message": f"已清理 {deleted} 筆過期警告事件",
            "deleted_count": deleted,
        })
    except Exception as e:
        app.logger.error(f"[DB] purge failed: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        db.close()


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
