"""
mapping.py — Camera-frame -> screen-pixel coordinate mapping.

Maps a fingertip position inside an "activation zone" (an inset
rectangle within the camera frame) linearly onto the full screen,
so the user doesn't need to reach the literal edges of the webcam's
field of view to reach the screen's corners.
"""

from __future__ import annotations

from config import Config


class CoordinateMapper:
    """
    Maps a fingertip position in camera-frame pixel space to a position in
    screen pixel space, using a smaller "activation zone" rectangle inside
    the camera frame as the effective input range.

    The math (linear remapping):
        normalized = (x - src_min) / (src_max - src_min)   # 0..1
        mapped     = dst_min + normalized * (dst_max - dst_min)
    """

    def __init__(self, cam_w: int, cam_h: int, screen_w: int, screen_h: int, cfg: Config):
        self.cam_w, self.cam_h = cam_w, cam_h
        self.screen_w, self.screen_h = screen_w, screen_h
        self.cfg = cfg
        self._recompute_zone()

    def _recompute_zone(self) -> None:
        self.zone_x_min = int(self.cam_w * self.cfg.frame_margin_x)
        self.zone_x_max = int(self.cam_w * (1 - self.cfg.frame_margin_x))
        self.zone_y_min = int(self.cam_h * self.cfg.frame_margin_y)
        self.zone_y_max = int(self.cam_h * (1 - self.cfg.frame_margin_y))

    def refresh_from_config(self) -> None:
        """Call after live-editing cfg.frame_margin_x/y from the control panel."""
        self._recompute_zone()

    def zone_rect(self) -> tuple[int, int, int, int]:
        """Returns (x1, y1, x2, y2) of the activation zone for drawing."""
        return self.zone_x_min, self.zone_y_min, self.zone_x_max, self.zone_y_max

    def map_to_screen(self, x: float, y: float) -> tuple[int, int]:
        """
        Map a fingertip (x, y) in camera-frame pixels to (screen_x, screen_y)
        in screen pixels. Values outside the zone are clamped.
        """
        clamped_x = min(max(x, self.zone_x_min), self.zone_x_max)
        clamped_y = min(max(y, self.zone_y_min), self.zone_y_max)

        zone_w = max(self.zone_x_max - self.zone_x_min, 1)
        zone_h = max(self.zone_y_max - self.zone_y_min, 1)

        norm_x = (clamped_x - self.zone_x_min) / zone_w
        norm_y = (clamped_y - self.zone_y_min) / zone_h

        screen_x = int(norm_x * self.screen_w)
        screen_y = int(norm_y * self.screen_h)

        screen_x = min(max(screen_x, 0), self.screen_w - 1)
        screen_y = min(max(screen_y, 0), self.screen_h - 1)

        return screen_x, screen_y
