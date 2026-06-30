"""
smoothing.py — Cursor motion smoothing.

Combines a short moving-average (knocks out single-frame landmark
spikes) with a lerp / one-pole low-pass filter (removes residual
frame-to-frame jitter and gives an organic "easing" feel).
"""

from __future__ import annotations

from collections import deque


class CursorSmoother:
    def __init__(self, smoothing_factor: float, history_len: int):
        self.factor = smoothing_factor
        self.history: deque[tuple[int, int]] = deque(maxlen=max(1, history_len))
        self.smoothed_x: float | None = None
        self.smoothed_y: float | None = None

    def set_params(self, smoothing_factor: float, history_len: int) -> None:
        """Allow the control panel to retune smoothing live."""
        self.factor = smoothing_factor
        if history_len != self.history.maxlen:
            old_items = list(self.history)
            self.history = deque(old_items, maxlen=max(1, history_len))

    def update(self, target_x: int, target_y: int) -> tuple[int, int]:
        self.history.append((target_x, target_y))
        avg_x = sum(p[0] for p in self.history) / len(self.history)
        avg_y = sum(p[1] for p in self.history) / len(self.history)

        if self.smoothed_x is None:
            self.smoothed_x, self.smoothed_y = avg_x, avg_y
        else:
            self.smoothed_x += (avg_x - self.smoothed_x) * self.factor
            self.smoothed_y += (avg_y - self.smoothed_y) * self.factor

        return int(self.smoothed_x), int(self.smoothed_y)

    def reset(self) -> None:
        self.history.clear()
        self.smoothed_x = None
        self.smoothed_y = None
