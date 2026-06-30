"""
hud.py — Modern on-camera HUD overlay.

Replaces the original plain cv2.putText status lines with a designed
overlay: a translucent rounded status pill, a small gesture-guide panel,
an activation-zone frame with corner brackets, and a sparkline for cursor
activity.
"""

from __future__ import annotations

from collections import deque

import cv2
import numpy as np

from gestures import GestureState
from mapping import CoordinateMapper

# ──────────────────────────────────────────────────────────────────────────
# THEME
# ──────────────────────────────────────────────────────────────────────────
THEMES = {
    "dark": {
        "panel_bg": (28, 24, 22),
        "panel_alpha": 0.55,
        "text_primary": (240, 240, 240),
        "text_secondary": (170, 170, 170),
        "accent": (255, 184, 77),     # warm amber
        "zone_border": (90, 90, 90),
    },
    "light": {
        "panel_bg": (235, 235, 235),
        "panel_alpha": 0.6,
        "text_primary": (30, 30, 30),
        "text_secondary": (90, 90, 90),
        "accent": (200, 110, 20),
        "zone_border": (160, 160, 160),
    },
}

STATE_STYLE = {
    GestureState.MOVING:       {"label": "Tracking",      "color": (255, 184, 77)},
    GestureState.LEFT_CLICK:   {"label": "Left Click",    "color": (102, 220, 120)},
    GestureState.DOUBLE_CLICK: {"label": "Double Click",  "color": (102, 220, 120)},
    GestureState.RIGHT_CLICK:  {"label": "Right Click",   "color": (90, 140, 255)},
    GestureState.DRAGGING:     {"label": "Dragging",      "color": (255, 120, 200)},
    GestureState.SCROLLING:    {"label": "Scrolling",     "color": (140, 220, 255)},
    GestureState.SCREENSHOT:   {"label": "Screenshot!",   "color": (255, 240, 120)},
    GestureState.NO_HAND:      {"label": "No Hand",       "color": (120, 120, 120)},
}

GESTURE_GUIDE_LINES = [
    ("Move",        "Index finger"),
    ("Left click",  "Thumb + Index"),
    ("Drag",        "Hold the pinch"),
    ("Right click", "Thumb + Middle"),
    ("Scroll",      "Thumb + Ring, move"),
    ("Screenshot",  "Thumb + Pinky"),
]


def _blend_rounded_rect(frame, x1, y1, x2, y2, color, alpha, radius=14):
    """Draw a filled rounded rectangle blended into `frame` with transparency."""
    overlay = frame.copy()
    cv2.rectangle(overlay, (x1 + radius, y1), (x2 - radius, y2), color, cv2.FILLED)
    cv2.rectangle(overlay, (x1, y1 + radius), (x2, y2 - radius), color, cv2.FILLED)
    cv2.circle(overlay, (x1 + radius, y1 + radius), radius, color, cv2.FILLED)
    cv2.circle(overlay, (x2 - radius, y1 + radius), radius, color, cv2.FILLED)
    cv2.circle(overlay, (x1 + radius, y2 - radius), radius, color, cv2.FILLED)
    cv2.circle(overlay, (x2 - radius, y2 - radius), radius, color, cv2.FILLED)
    cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0, frame)


def draw_activation_zone(frame, mapper: CoordinateMapper, theme: dict):
    x1, y1, x2, y2 = mapper.zone_rect()
    color = theme["zone_border"]
    cv2.rectangle(frame, (x1, y1), (x2, y2), color, 1, cv2.LINE_AA)

    bracket = 18
    accent = theme["accent"]
    for cx, cy, dx, dy in [
        (x1, y1, 1, 1), (x2, y1, -1, 1), (x1, y2, 1, -1), (x2, y2, -1, -1)
    ]:
        cv2.line(frame, (cx, cy), (cx + bracket * dx, cy), accent, 2, cv2.LINE_AA)
        cv2.line(frame, (cx, cy), (cx, cy + bracket * dy), accent, 2, cv2.LINE_AA)


def draw_status_pill(frame, state: GestureState, theme: dict):
    style = STATE_STYLE.get(state, {"label": str(state), "color": theme["accent"]})
    label = style["label"]
    color = style["color"]

    pad_x, pad_y = 18, 10
    (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2)
    x1, y1 = 16, 16
    x2, y2 = x1 + tw + pad_x * 2 + 22, y1 + th + pad_y * 2

    _blend_rounded_rect(frame, x1, y1, x2, y2, theme["panel_bg"], theme["panel_alpha"], radius=(y2 - y1) // 2)

    dot_center = (x1 + pad_x, (y1 + y2) // 2)
    cv2.circle(frame, dot_center, 7, color, cv2.FILLED)
    cv2.circle(frame, dot_center, 9, color, 1, cv2.LINE_AA)

    text_origin = (dot_center[0] + 16, y2 - pad_y - 2)
    cv2.putText(frame, label, text_origin, cv2.FONT_HERSHEY_SIMPLEX, 0.7, theme["text_primary"], 2, cv2.LINE_AA)

    return y2


def draw_fps_chip(frame, fps: float, top_offset: int, theme: dict):
    label = f"{fps:.0f} FPS"
    pad_x, pad_y = 14, 8
    (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 1)
    x1, y1 = 16, top_offset + 10
    x2, y2 = x1 + tw + pad_x * 2, y1 + th + pad_y * 2
    _blend_rounded_rect(frame, x1, y1, x2, y2, theme["panel_bg"], theme["panel_alpha"] * 0.8, radius=(y2 - y1) // 2)
    cv2.putText(frame, label, (x1 + pad_x, y2 - pad_y - 2), cv2.FONT_HERSHEY_SIMPLEX, 0.55, theme["text_secondary"], 1, cv2.LINE_AA)
    return y2


def draw_gesture_guide(frame, theme: dict, visible: bool):
    if not visible:
        return
    fh, fw = frame.shape[:2]
    pad = 14
    line_h = 24
    col_gap = 12

    action_col_w = max(
        cv2.getTextSize(action, cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1)[0][0]
        for action, _ in GESTURE_GUIDE_LINES
    )
    how_col_w = max(
        cv2.getTextSize(how, cv2.FONT_HERSHEY_SIMPLEX, 0.42, 1)[0][0]
        for _, how in GESTURE_GUIDE_LINES
    )

    panel_w = pad * 2 + action_col_w + col_gap + how_col_w
    panel_w = min(panel_w, fw - 32)
    panel_h = pad * 2 + line_h * len(GESTURE_GUIDE_LINES) + 26

    x2 = fw - 16
    x1 = x2 - panel_w
    y1 = 16
    y2 = y1 + panel_h

    _blend_rounded_rect(frame, x1, y1, x2, y2, theme["panel_bg"], min(theme["panel_alpha"] + 0.15, 0.9), radius=14)

    cv2.putText(frame, "GESTURES", (x1 + pad, y1 + pad + 12), cv2.FONT_HERSHEY_SIMPLEX, 0.55, theme["accent"], 2, cv2.LINE_AA)

    how_col_x = x1 + pad + action_col_w + col_gap
    y = y1 + pad + 36
    for action, how in GESTURE_GUIDE_LINES:
        cv2.putText(frame, action, (x1 + pad, y), cv2.FONT_HERSHEY_SIMPLEX, 0.45, theme["text_primary"], 1, cv2.LINE_AA)
        cv2.putText(frame, how, (how_col_x, y), cv2.FONT_HERSHEY_SIMPLEX, 0.42, theme["text_secondary"], 1, cv2.LINE_AA)
        y += line_h


def draw_tracking_point(frame, point: tuple[int, int], state: GestureState, theme: dict):
    style = STATE_STYLE.get(state, {"color": theme["accent"]})
    color = style["color"]
    cv2.circle(frame, point, 10, color, cv2.FILLED)
    cv2.circle(frame, point, 15, (255, 255, 255), 2, cv2.LINE_AA)


def draw_footer_hint(frame, theme: dict):
    fh, fw = frame.shape[:2]
    text = "Press 'q' to quit   |   'g' toggle guide   |   'p' toggle control panel   |   't' toggle theme"
    cv2.putText(frame, text, (16, fh - 14), cv2.FONT_HERSHEY_SIMPLEX, 0.45, theme["text_secondary"], 1, cv2.LINE_AA)


class ActivitySpark:
    """Tiny inline sparkline showing recent cursor speed."""

    def __init__(self, maxlen: int = 50):
        self.values: deque[float] = deque(maxlen=maxlen)

    def push(self, value: float):
        self.values.append(value)

    def draw(self, frame, top_offset: int, theme: dict):
        if len(self.values) < 2:
            return top_offset
        fh, fw = frame.shape[:2]
        w, h = 150, 36
        x1, y1 = 16, top_offset + 10
        x2, y2 = x1 + w, y1 + h
        _blend_rounded_rect(frame, x1, y1, x2, y2, theme["panel_bg"], theme["panel_alpha"] * 0.8, radius=10)

        vals = list(self.values)
        vmax = max(vals) or 1.0
        pts = []
        for i, v in enumerate(vals):
            px = x1 + 6 + int((w - 12) * (i / max(len(vals) - 1, 1)))
            py = y2 - 6 - int((h - 12) * (v / vmax))
            pts.append((px, py))
        for a, b in zip(pts, pts[1:]):
            cv2.line(frame, a, b, theme["accent"], 2, cv2.LINE_AA)
        return y2