from collections import deque
import time
from config import Config


class State:

    def __init__(self, fps=30, window_sec=5):
        self.fps = fps
        self.window_size = fps * window_sec

        self.reset()

    def reset(self):
        # Detection
        self.started = False
        self.session_id = None

        # Camera & Env
        self.camera_fps = 0
        self.latency = 0
        self.brightness = None
        self.is_night_mode = False
        self.frame_times = deque(maxlen=max(self.fps, 1))
        self.browser_last_frame_time = None

        # Face
        self.face_count = 0

        # EAR
        self.left_ear = None
        self.right_ear = None
        self.ear = None

        self.blink_times = 0
        self.eye_closure_frames = 0
        self.eye_closure_dur = 0.0

        self.is_eye_closed = False
        self.eye_closure_start_time = None

        # MAR
        self.mar = None
        self.yawn_times = 0
        self.yawn_dur = 0.0

        self.is_yawning = False
        self.yawning_start_time = None

        # Head / Nod / Turn 
        self.nod_ratio = None
        self.nod_velocity = 0.0
        self.nod_dur = 0.0
        self.is_nodding = False
        self.is_snap_nodding = False
        self.turn_ratio = None
        self.is_looking_away = False

        # PERCLOS
        self.perclos = 0.0
        self.eye_closure_history = deque(
            maxlen=self.window_size
        )

        # Fatigue
        self.fatigue_level = "Normal"
        self.fatigue_score = 0

        # Log
        self.log_history = []
        self.last_log_time = 0.0

        # Alert
        self.last_alert_time = None
        self.alert_count = 0
        self.is_alert_active = False
        self.alert_history = []

        # Calibration
        self.is_calibrating = False
        self.is_calibrated = False
        self.calibration_ear_samples = []
        self.calibration_mar_samples = []
        self.baseline_ear = None
        self.baseline_mar = None
        self.baseline_nod = None
        self.baseline_turn = None

        self.ear_threshold = Config.EAR_CLOSED_THRESHOLD
        self.mar_threshold = Config.YAWN_THRESHOLD
        self.nod_threshold = Config.NOD_RATIO_THRESHOLD

        self.start_record_time = time.time()
    
    def reset_metrics(self):
        self.latency = 0
        self.face_count = 0
        self.camera_fps = 0
        self.brightness = None
        self.is_night_mode = False
        self.frame_times.clear()
        self.browser_last_frame_time = None

        self.left_ear = None
        self.right_ear = None
        self.ear = None
        self.mar = None

        self.blink_times = 0
        self.yawn_times = 0

        self.eye_closure_frames = 0
        self.eye_closure_dur = 0.0
        self.is_eye_closed = False

        self.is_yawning = False
        self.yawning_start_time = None
        self.yawn_dur = 0.0

        self.perclos = 0.0
        self.eye_closure_history.clear()

        self.fatigue_level = "Normal"
        self.fatigue_score = 0

        self.is_calibrating = False
        self.calibration_ear_samples = []
        self.calibration_mar_samples = []

        self.start_record_time = time.time()

    def update_from_api(self, data):
        mapping = {
            "started": "started",
            "session_id": "session_id",
            "fps": "camera_fps",
            "latency": "latency",
            "brightness": "brightness",
            "is_night_mode": "is_night_mode",
            "faces": "face_count",
            "left_ear": "left_ear",
            "right_ear": "right_ear",
            "ear": "ear",
            "mar": "mar",
            "blink_times": "blink_times",
            "yawn_times": "yawn_times",
            "eye_closure_dur": "eye_closure_dur",
            "yawn_dur": "yawn_dur",
            "nod_ratio": "nod_ratio",
            "nod_velocity": "nod_velocity",
            "nod_dur": "nod_dur",
            "is_nodding": "is_nodding",
            "is_snap_nodding": "is_snap_nodding",
            "turn_ratio": "turn_ratio",
            "is_looking_away": "is_looking_away",
            "perclos": "perclos",
            "fatigue_level": "fatigue_level",
            "fatigue_score": "fatigue_score",
            "ear_threshold": "ear_threshold",
            "mar_threshold": "mar_threshold",
            "nod_threshold": "nod_threshold",
        }

        for key, attr in mapping.items():
            if key in data:
                setattr(self, attr, data[key])

        if "started" not in data:
            self.started = True

    def snapshot(self):
        return {
            "started": self.started,
            "session_id": self.session_id,
            "fps": self.camera_fps,
            "latency": self.latency,
            "brightness": self.brightness,
            "is_night_mode": self.is_night_mode,
            "faces": self.face_count,
            "left_ear": self.left_ear,
            "right_ear": self.right_ear,
            "ear": self.ear,
            "mar": self.mar,
            "blink_times": self.blink_times,
            "yawn_times": self.yawn_times,
            "eye_closure_dur": self.eye_closure_dur,
            "yawn_dur": self.yawn_dur,
            "nod_ratio": self.nod_ratio,
            "nod_velocity": self.nod_velocity,
            "nod_dur": self.nod_dur,
            "is_nodding": self.is_nodding,
            "is_snap_nodding": self.is_snap_nodding,
            "turn_ratio": self.turn_ratio,
            "is_looking_away": self.is_looking_away,
            "perclos": self.perclos,
            "fatigue_level": self.fatigue_level,
            "fatigue_score": self.fatigue_score,
            "ear_threshold": self.ear_threshold,
            "mar_threshold": self.mar_threshold,
            "nod_threshold": self.nod_threshold,
        }
