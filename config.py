"""
config.py — Central configuration for Virtual Mouse.

Holds every tunable parameter as a single dataclass, plus JSON
load/save so the Control Panel GUI can persist user adjustments
between runs (saved to virtual_mouse_settings.json next to this file).
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field, fields

SETTINGS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "virtual_mouse_settings.json")


@dataclass
class Config:
    # --- Camera ---
    cam_index: int = 0
    cam_width: int = 960
    cam_height: int = 720

    # --- MediaPipe Hands ---
    max_num_hands: int = 1
    detection_confidence: float = 0.7
    tracking_confidence: float = 0.7

    # --- Activation zone ---
    frame_margin_x: float = 0.15
    frame_margin_y: float = 0.15

    # --- Smoothing ---
    smoothing_factor: float = 0.35
    history_len: int = 4

    # --- Click gestures ---
    click_pinch_threshold: int = 35
    click_cooldown: float = 0.4
    double_click_window: float = 0.45

    # --- Drag ---
    drag_hold_time: float = 0.25

    # --- Scroll ---
    scroll_pinch_threshold: int = 38
    scroll_sensitivity: float = 2.2

    # --- Screenshot gesture ---
    screenshot_cooldown: float = 1.5
    screenshot_dir: str = field(default_factory=lambda: os.path.join(os.path.expanduser("~"), "Pictures", "VirtualMouseShots"))

    # --- Misc ---
    flip_camera: bool = True
    show_fps: bool = True
    show_gesture_guide: bool = True
    hud_theme: str = "dark"   # "dark" or "light"

    # --- Control panel ---
    control_panel_enabled: bool = False

    def clamp(self) -> None:
        """Keep every field within a sane, safe range after external edits."""
        self.smoothing_factor = min(max(self.smoothing_factor, 0.05), 1.0)
        self.history_len = min(max(int(self.history_len), 1), 15)
        self.click_pinch_threshold = min(max(int(self.click_pinch_threshold), 10), 100)
        self.scroll_pinch_threshold = min(max(int(self.scroll_pinch_threshold), 10), 100)
        self.click_cooldown = min(max(self.click_cooldown, 0.05), 2.0)
        self.frame_margin_x = min(max(self.frame_margin_x, 0.0), 0.45)
        self.frame_margin_y = min(max(self.frame_margin_y, 0.0), 0.45)
        self.scroll_sensitivity = min(max(self.scroll_sensitivity, 0.1), 10.0)
        self.drag_hold_time = min(max(self.drag_hold_time, 0.0), 2.0)
        self.double_click_window = min(max(self.double_click_window, 0.1), 2.0)
        self.screenshot_cooldown = min(max(self.screenshot_cooldown, 0.3), 5.0)

    def to_dict(self) -> dict:
        return asdict(self)

    def save(self, path: str = SETTINGS_PATH) -> None:
        self.clamp()
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def load(cls, path: str = SETTINGS_PATH) -> "Config":
        cfg = cls()
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                valid_keys = {f.name for f in fields(cls)}
                for k, v in data.items():
                    if k in valid_keys:
                        setattr(cfg, k, v)
            except (json.JSONDecodeError, OSError):
                pass
        cfg.clamp()
        return cfg