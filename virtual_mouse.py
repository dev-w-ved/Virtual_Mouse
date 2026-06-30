"""
Virtual Mouse — Hand Gesture Mouse Control (v2)
================================================

Control your OS cursor and more with hand gestures from a webcam.

Gestures (shown live in the on-screen guide):
    Move          : index finger tip
    Left click    : thumb + index pinch (tap)
    Double click  : two quick left‑click taps
    Drag          : thumb + index pinch, HELD
    Right click   : thumb + middle pinch (tap)
    Scroll        : thumb + ring pinch, HELD + move hand up/down
    Screenshot    : thumb + pinky pinch (tap)

Dependencies:
    pip install opencv-python mediapipe pyautogui numpy

Run:
    python virtual_mouse.py

Controls:
    q  — quit
    g  — toggle gesture guide panel
    p  — toggle the Control Panel window
    t  — toggle dark/light HUD theme
"""

from __future__ import annotations

import time

import cv2
import mediapipe as mp
import pyautogui

from config import Config
from control_panel import ControlPanel
from gestures import GestureEngine, GestureState, INDEX_TIP, MIDDLE_TIP, PINKY_TIP, RING_TIP, THUMB_TIP, WRIST, INDEX_MCP, MIDDLE_MCP, RING_MCP, PINKY_MCP
from hud import (
    ActivitySpark,
    THEMES,
    draw_activation_zone,
    draw_fps_chip,
    draw_footer_hint,
    draw_gesture_guide,
    draw_status_pill,
    draw_tracking_point,
)
from mapping import CoordinateMapper
from smoothing import CursorSmoother

# ──────────────────────────────────────────────────────────────────────────
# PYAUTOGUI SAFETY
# ──────────────────────────────────────────────────────────────────────────
pyautogui.FAILSAFE = False
pyautogui.PAUSE = 0.0

SCREEN_W, SCREEN_H = pyautogui.size()

ALL_LANDMARKS_NEEDED = [WRIST, THUMB_TIP, INDEX_TIP, INDEX_MCP, MIDDLE_TIP, MIDDLE_MCP, RING_TIP, RING_MCP, PINKY_TIP, PINKY_MCP]


def main(cfg: Config | None = None):
    cfg = cfg or Config.load()

    mp_hands = mp.solutions.hands
    mp_drawing = mp.solutions.drawing_utils
    mp_drawing_styles = mp.solutions.drawing_styles

    cap = cv2.VideoCapture(cfg.cam_index)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, cfg.cam_width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, cfg.cam_height)

    if not cap.isOpened():
        raise RuntimeError(
            f"Could not open webcam at index {cfg.cam_index}. "
            "Check that no other application is using it and that the "
            "index is correct (try 0, 1, 2...)."
        )

    mapper: CoordinateMapper | None = None
    smoother = CursorSmoother(cfg.smoothing_factor, cfg.history_len)
    engine = GestureEngine(cfg)
    spark = ActivitySpark()

    # Control panel is closed by default; press 'p' to open it.
    panel = ControlPanel(cfg, on_change=lambda: smoother.set_params(cfg.smoothing_factor, cfg.history_len))
    # Do NOT auto‑open the panel — the user must toggle it manually.

    prev_time = time.time()
    prev_cursor_pos: tuple[int, int] | None = None

    window_name = "Virtual Mouse"
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)

    with mp_hands.Hands(
        max_num_hands=cfg.max_num_hands,
        min_detection_confidence=cfg.detection_confidence,
        min_tracking_confidence=cfg.tracking_confidence,
    ) as hands:

        try:
            while True:
                success, frame = cap.read()
                if not success:
                    print("Warning: failed to read frame from webcam, skipping.")
                    continue

                if cfg.flip_camera:
                    frame = cv2.flip(frame, 1)

                frame_h, frame_w = frame.shape[:2]
                if mapper is None:
                    mapper = CoordinateMapper(frame_w, frame_h, SCREEN_W, SCREEN_H, cfg)
                else:
                    mapper.refresh_from_config()

                theme = THEMES[cfg.hud_theme if cfg.hud_theme in THEMES else "dark"]

                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                rgb_frame.flags.writeable = False
                results = hands.process(rgb_frame)

                draw_activation_zone(frame, mapper, theme)

                state = GestureState.NO_HAND
                info: dict = {}

                if results.multi_hand_landmarks:
                    hand_landmarks = results.multi_hand_landmarks[0]

                    mp_drawing.draw_landmarks(
                        frame,
                        hand_landmarks,
                        mp_hands.HAND_CONNECTIONS,
                        mp_drawing_styles.get_default_hand_landmarks_style(),
                        mp_drawing_styles.get_default_hand_connections_style(),
                    )

                    def to_px(idx):
                        lm = hand_landmarks.landmark[idx]
                        return (lm.x * frame_w, lm.y * frame_h)

                    lm_px = {idx: to_px(idx) for idx in ALL_LANDMARKS_NEEDED}

                    raw_screen_x, raw_screen_y = mapper.map_to_screen(*lm_px[INDEX_TIP])
                    smooth_x, smooth_y = smoother.update(raw_screen_x, raw_screen_y)

                    state, info = engine.update(lm_px)

                    moves_cursor = state in (
                        GestureState.MOVING,
                        GestureState.LEFT_CLICK,
                        GestureState.DOUBLE_CLICK,
                        GestureState.RIGHT_CLICK,
                        GestureState.DRAGGING,
                    )
                    if moves_cursor:
                        pyautogui.moveTo(smooth_x, smooth_y)

                    if prev_cursor_pos is not None:
                        speed = ((smooth_x - prev_cursor_pos[0]) ** 2 + (smooth_y - prev_cursor_pos[1]) ** 2) ** 0.5
                        spark.push(speed)
                    prev_cursor_pos = (smooth_x, smooth_y)

                    index_px = (int(lm_px[INDEX_TIP][0]), int(lm_px[INDEX_TIP][1]))
                    thumb_px = (int(lm_px[THUMB_TIP][0]), int(lm_px[THUMB_TIP][1]))
                    middle_px = (int(lm_px[MIDDLE_TIP][0]), int(lm_px[MIDDLE_TIP][1]))

                    draw_tracking_point(frame, index_px, state, theme)
                    cv2.line(frame, thumb_px, index_px, (0, 255, 255), 2, cv2.LINE_AA)
                    cv2.line(frame, thumb_px, middle_px, (255, 0, 255), 2, cv2.LINE_AA)
                else:
                    engine.reset()
                    smoother.reset()
                    prev_cursor_pos = None

                now = time.time()
                fps = 1.0 / max(now - prev_time, 1e-6)
                prev_time = now

                bottom = draw_status_pill(frame, state, theme)
                if cfg.show_fps:
                    bottom = draw_fps_chip(frame, fps, bottom - 10, theme)
                spark.draw(frame, bottom - 10, theme)

                draw_gesture_guide(frame, theme, cfg.show_gesture_guide)
                draw_footer_hint(frame, theme)

                cv2.imshow(window_name, frame)

                key = cv2.waitKey(1) & 0xFF
                if key == ord("q"):
                    break
                elif key == ord("g"):
                    cfg.show_gesture_guide = not cfg.show_gesture_guide
                elif key == ord("t"):
                    cfg.hud_theme = "light" if cfg.hud_theme == "dark" else "dark"
                elif key == ord("p"):
                    panel.toggle()
                    cfg.control_panel_enabled = panel.is_running()

        finally:
            engine.reset()
            cfg.save()
            cap.release()
            cv2.destroyAllWindows()


if __name__ == "__main__":
    main()