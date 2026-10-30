import os

# ========== 環境偵測：本地 vs Render ==========
# Render 啟動時會自動注入 PORT 環境變數；本地開發則不會有這個變數。
# 藉此判斷目前執行環境，決定要不要載入 .env 檔案。
IS_RENDER = os.environ.get("PORT") is not None

if not IS_RENDER:
    # 本地開發環境：從 .env 檔案載入環境變數（.env 已加入 .gitignore，不會上傳到 GitHub）
    from dotenv import load_dotenv
    load_dotenv()

from flask import Flask, jsonify, render_template, request, send_from_directory
from alert_manager import AlertManager
from config import Config
from database import AlertEvent, init_db, SessionLocal
from state import State


app = Flask(
    __name__,
    static_folder="assets",
    template_folder="templates",
)
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0

state = State(fps=Config.FPS, window_sec=Config.WINDOWS_SEC)
alert_manager = AlertManager(
    window_sec=Config.ALERT_WINDOW_SEC,
    trigger_count=Config.ALERT_TRIGGER_COUNT,
    notify_cooldown_sec=Config.ALERT_COOLDOWN_NOTIFY_SEC,
)

# 啟動時建立資料表（若已存在則跳過）
init_db()


# 路徑設定
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

        # 環境亮度與高光門檻輸出至前端
        "ENV_LUMA_HIGHLIGHT": Config.ENV_LUMA_HIGHLIGHT,
        "ENV_NIGHT_BRIGHTNESS": Config.ENV_NIGHT_BRIGHTNESS,
        "ENV_NIGHT_HIGHLIGHT_RATIO": Config.ENV_NIGHT_HIGHLIGHT_RATIO,
        "ENV_DAY_BRIGHTNESS": Config.ENV_DAY_BRIGHTNESS,
        "ENV_DAY_HIGHLIGHT_RATIO": Config.ENV_DAY_HIGHLIGHT_RATIO,
    })


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
    except Exception as e:
        app.logger.error(f"[DB] Failed to save alert event: {e}")
    finally:
        db.close()

    return jsonify(result)


@app.route("/api/admin/alerts", methods=["GET"])
def api_admin_alerts():
    """提供後台管理者或老闆查詢即時警報與通報紀錄（優先從資料庫查詢）"""
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
    alert_manager.reset()
    state.escalated_alert = False
    state.recent_alert_count = 0
    return jsonify({
        "status": "success",
        "message": "警報統計與通報狀態已重置（資料庫紀錄保留）",
        "data": alert_manager.get_status(),
    })


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
