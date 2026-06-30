"""
gestures.py — Gesture recognition and OS-action dispatch.

Recognizes:
    Move          : index tip position (when no other gesture is active)
    Left click    : thumb + index pinch, quick tap
    Double click  : two left-click taps inside double_click_window
    Drag          : thumb + index pinch HELD past drag_hold_time
    Right click   : thumb + middle pinch, quick tap
    Scroll        : thumb + ring pinch HELD -> vertical hand movement
    Screenshot    : thumb + pinky pinch, quick tap

All thresholds and cooldowns are read live from the shared Config object.
"""

from __future__ import annotations

import math
import os
import time
from datetime import datetime
from enum import Enum, auto

import pyautogui

from config import Config

# ──────────────────────────────────────────────────────────────────────────
# MediaPipe Hands landmark indices
# ──────────────────────────────────────────────────────────────────────────
WRIST = 0
THUMB_TIP = 4
INDEX_TIP = 8
INDEX_MCP = 5
MIDDLE_TIP = 12
MIDDLE_MCP = 9
RING_TIP = 16
RING_MCP = 13
PINKY_TIP = 20
PINKY_MCP = 17


class GestureState(Enum):
    IDLE = auto()
    MOVING = auto()
    LEFT_CLICK = auto()
    DOUBLE_CLICK = auto()
    RIGHT_CLICK = auto()
    DRAGGING = auto()
    SCROLLING = auto()
    SCREENSHOT = auto()
    NO_HAND = auto()


def _dist(p1: tuple[float, float], p2: tuple[float, float]) -> float:
    return math.hypot(p1[0] - p2[0], p1[1] - p2[1])


class GestureEngine:
    """
    Stateful gesture recognizer. Call `update(landmarks_px)` once per frame
    with fingertip/joint pixel coordinates; it returns a GestureState plus
    any extra info (e.g. scroll amount) the HUD can display.
    """

    def __init__(self, cfg: Config):
        self.cfg = cfg

        self._last_click_time = 0.0
        self._last_left_click_time = 0.0
        self._pending_double = False

        self._pinch_start_time: float | None = None
        self._is_dragging = False

        self._scroll_active = False
        self._scroll_last_y: float | None = None

        self._last_screenshot_time = 0.0

        self.last_info: dict = {}

    # ------------------------------------------------------------------
    def reset(self):
        """Call when the hand leaves the frame so nothing stays 'stuck'."""
        if self._is_dragging:
            try:
                pyautogui.mouseUp(button="left")
            except Exception:
                pass
        self._is_dragging = False
        self._pinch_start_time = None
        self._scroll_active = False
        self._scroll_last_y = None
        self.last_info = {}

    # ------------------------------------------------------------------
    def update(self, lm_px: dict[int, tuple[float, float]]) -> tuple[GestureState, dict]:
        cfg = self.cfg
        now = time.time()
        info: dict = {}

        thumb = lm_px[THUMB_TIP]
        index = lm_px[INDEX_TIP]
        middle = lm_px[MIDDLE_TIP]
        ring = lm_px[RING_TIP]
        pinky = lm_px[PINKY_TIP]

        index_pinch = _dist(thumb, index)
        middle_pinch = _dist(thumb, middle)
        ring_pinch = _dist(thumb, ring)
        pinky_pinch = _dist(thumb, pinky)

        # ---- Priority 1: in-progress drag ----
        if self._is_dragging:
            if index_pinch < cfg.click_pinch_threshold * 1.4:
                self.last_info = info
                return GestureState.DRAGGING, info
            else:
                pyautogui.mouseUp(button="left")
                self._is_dragging = False
                self._pinch_start_time = None

        # ---- Priority 2: in-progress scroll ----
        if self._scroll_active:
            if ring_pinch < cfg.scroll_pinch_threshold * 1.4:
                if self._scroll_last_y is not None:
                    dy = self._scroll_last_y - index[1]
                    if abs(dy) > 1:
                        amount = int(dy * cfg.scroll_sensitivity)
                        if amount != 0:
                            pyautogui.scroll(amount)
                            info["scroll_amount"] = amount
                self._scroll_last_y = index[1]
                self.last_info = info
                return GestureState.SCROLLING, info
            else:
                self._scroll_active = False
                self._scroll_last_y = None

        # ---- Priority 3: screenshot ----
        if pinky_pinch < cfg.click_pinch_threshold:
            if (now - self._last_screenshot_time) >= cfg.screenshot_cooldown:
                self._take_screenshot()
                self._last_screenshot_time = now
                info["screenshot_taken"] = True
            self.last_info = info
            return GestureState.SCREENSHOT, info

        # ---- Priority 4: begin scroll ----
        if ring_pinch < cfg.scroll_pinch_threshold:
            self._scroll_active = True
            self._scroll_last_y = index[1]
            self.last_info = info
            return GestureState.SCROLLING, info

        # ---- Priority 5: right click ----
        if middle_pinch < cfg.click_pinch_threshold:
            if (now - self._last_click_time) >= cfg.click_cooldown:
                pyautogui.click(button="right")
                self._last_click_time = now
                info["clicked"] = "right"
            self.last_info = info
            return GestureState.RIGHT_CLICK, info

        # ---- Priority 6: left click / double click / drag ----
        if index_pinch < cfg.click_pinch_threshold:
            if self._pinch_start_time is None:
                self._pinch_start_time = now
            held_for = now - self._pinch_start_time

            if held_for >= cfg.drag_hold_time and not self._is_dragging:
                pyautogui.mouseDown(button="left")
                self._is_dragging = True
                self.last_info = info
                return GestureState.DRAGGING, info

            self.last_info = info
            return GestureState.LEFT_CLICK, info
        else:
            if self._pinch_start_time is not None:
                self._pinch_start_time = None
                if (now - self._last_click_time) >= cfg.click_cooldown:
                    pyautogui.click(button="left")
                    self._last_click_time = now

                    if self._pending_double and (now - self._last_left_click_time) <= cfg.double_click_window:
                        info["clicked"] = "double"
                        self._pending_double = False
                        self.last_info = info
                        return GestureState.DOUBLE_CLICK, info

                    self._pending_double = True
                    self._last_left_click_time = now
                    info["clicked"] = "left"
                    self.last_info = info
                    return GestureState.LEFT_CLICK, info

        self.last_info = info
        return GestureState.MOVING, info

    # ------------------------------------------------------------------
    def _take_screenshot(self) -> str | None:
        try:
            os.makedirs(self.cfg.screenshot_dir, exist_ok=True)
            filename = f"vm_shot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            path = os.path.join(self.cfg.screenshot_dir, filename)
            img = pyautogui.screenshot()
            img.save(path)
            return path
        except Exception:
            return None