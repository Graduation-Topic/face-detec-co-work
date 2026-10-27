class Config:

    # ========================================================================================
    # Mediapipe Face Landmark
    #
    # https://ai.google.dev/edge/api/mediapipe/python/mp/tasks/vision/FaceLandmarksConnections
    # ========================================================================================

    # 左眼
    LEFT_EAR_POINTS = [
        33, 160, 158, 133, 153, 144
    ]

    # 右眼
    RIGHT_EAR_POINTS = [
        362, 385, 387, 263, 373, 380
    ]

    # 鼻子
    NOSE = {1, 10, 152, 234, 454}

    # 嘴巴
    MOUTH = {
        # 外嘴唇
        61, 146, 91, 181, 84, 17,
        314, 405, 321, 375, 291,

        # 外嘴唇下方 / 周圍
        185, 40, 39, 37, 0,
        267, 269, 270, 409,

        # 內嘴唇
        78, 191, 80, 81, 82,
        13,
        312, 311, 310, 415,
        308,

        # 內嘴唇下方
        95, 88, 178, 87,
        14,
        317, 402, 318, 324
    }

    MAR_POINTS = {
        "left": 61,
        "right": 291,
        "top": 13,
        "bottom": 14
    }

    # 系統參數
    FPS = 30

    # 論文(https://www.mdpi.com/1424-8220/23/19/8267)
    WINDOWS_SEC = 5
    WINDOW_SIZE = FPS * WINDOWS_SEC

    # 門檻設定 (系統預設值)

    # 眼睛閉合率門檻
    EAR_CLOSED_THRESHOLD = 0.2

    # 連續閉眼 (https://www.mdpi.com/1424-8220/23/19/8267)
    # 連續閉眼 >= 20 frames
    EYE_CLOSURE_MIN_FRAMES = 20
    EYE_CLOSURE_MIN_DURATION = EYE_CLOSURE_MIN_FRAMES / FPS

    # 微睡眠致命門檻 (秒)
    MICROSLEEP_MIN_DURATION = 1.5

    # 一般眨眼
    BLINK_MIN_FRAMES = 2
    BLINK_MIN_DURATION = BLINK_MIN_FRAMES / FPS

    # 打哈欠門檻
    YAWN_THRESHOLD = 0.65

    # 連續打哈欠 (https://www.mdpi.com/1424-8220/23/19/8267)
    # 連續打哈欠 >= 30 frames
    YAWN_MIN_FRAMES = 30
    YAWN_MIN_DURATION = YAWN_MIN_FRAMES / FPS

    # ========== 頭部姿態與環境門檻 ==========
    NOD_RATIO_THRESHOLD = 0.30      # 預設低頭比例門檻
    NOD_MIN_DURATION = 1.5          # 持續低頭打瞌睡門檻 (秒)
    NOD_SNAP_VELOCITY = 0.40        # 瞬間點頭下墜速度門檻 (Head Snap)
    TURN_CENTER = 0.50              # 預設正視前方中心點
    TURN_MARGIN = 0.25              # 左右轉頭分心容許範圍

    # ========== 校準 ==========
    CALIBRATION_FRAMES = 100 # 校準需要花費的時間 (幀數)

    # Baseline 校準後計算門檻的公式參數
    # ear_threshold = baseline_ear * CALIBRATION_EAR_RATIO
    CALIBRATION_EAR_RATIO = 0.75
    # mar_threshold = baseline_mar + CALIBRATION_MAR_OFFSET
    CALIBRATION_MAR_OFFSET = 0.25
    # nod_threshold = baseline_nod + CALIBRATION_nod_OFFSET
    CALIBRATION_NOD_OFFSET = 0.04

    # 疲勞分數
    PERCLOS_SEVERE_RATIO = 0.4
    YAWN_RATE_SEVERE_PER_MIN = 3.0

    FATIGUE_WEIGHT_PERCLOS = 0.5
    FATIGUE_WEIGHT_EYE_CLOSURE = 0.3
    FATIGUE_WEIGHT_YAWN = 0.2

    FATIGUE_SCORE_MILD = 30
    FATIGUE_SCORE_SEVERE = 60

    # 警告
    ALERT_COOLDOWN_SECONDS = 5

    # 日誌
    LOG_INTERVAL_SEC = 0.2

    # ========== 環境亮度與高光門檻 ==========
    ENV_LUMA_HIGHLIGHT = 220           # 像素 RGB 亮度大於此值，視為高光/車燈/反光
    ENV_NIGHT_BRIGHTNESS = 70          # 畫面平均亮度小於此值，進入夜間模式
    ENV_NIGHT_HIGHLIGHT_RATIO = 0.05   # 夜間模式下，高光像素佔比 > 5%，啟動「壓高光」
    ENV_DAY_BRIGHTNESS = 180           # 畫面平均亮度大於此值，啟動「強光壓制」
    ENV_DAY_HIGHLIGHT_RATIO = 0.15     # 畫面高光像素佔比 > 15%，啟動「強光壓制」