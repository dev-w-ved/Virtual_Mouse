"""
control_panel.py — Live settings window for Virtual Mouse.

A small always-on-top Tkinter panel with sliders/toggles for every
tunable in Config. Runs in its own thread so it doesn't block the
OpenCV capture loop; edits write straight into the shared Config
instance (read by the main loop every frame) and are persisted to
disk on close or on explicit Save.
"""

from __future__ import annotations

import threading
import tkinter as tk
from tkinter import ttk

from config import Config


class ControlPanel:
    def __init__(self, cfg: Config, on_change=None):
        self.cfg = cfg
        self.on_change = on_change or (lambda: None)
        self._root: tk.Tk | None = None
        self._vars: dict[str, tk.Variable] = {}
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    # ------------------------------------------------------------------
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self):
        """Launch the panel in a background thread. No-op if already open."""
        if self.is_running():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        """Close the panel window and fully reset state so start() can reopen it cleanly."""
        self._stop_event.set()
        if self._root is not None:
            try:
                self._root.quit()
                self._root.destroy()
            except Exception:
                pass
        self._root = None

    def toggle(self):
        if self.is_running():
            self.stop()
        else:
            self.start()

    # ------------------------------------------------------------------
    def _run(self):
        self._root = tk.Tk()
        self._root.title("Virtual Mouse — Control Panel")
        self._root.geometry("380x580")
        self._root.attributes("-topmost", True)
        self._root.protocol("WM_DELETE_WINDOW", self._on_close)

        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        container = ttk.Frame(self._root, padding=14)
        container.pack(fill="both", expand=True)

        ttk.Label(container, text="Virtual Mouse Settings", font=("Segoe UI", 14, "bold")).pack(anchor="w", pady=(0, 10))

        self._build_slider(container, "Smoothing factor", "smoothing_factor", 0.05, 1.0, 0.01)
        self._build_slider(container, "Smoothing history (frames)", "history_len", 1, 15, 1, is_int=True)
        self._build_slider(container, "Click pinch threshold (px)", "click_pinch_threshold", 10, 100, 1, is_int=True)
        self._build_slider(container, "Scroll pinch threshold (px)", "scroll_pinch_threshold", 10, 100, 1, is_int=True)
        self._build_slider(container, "Click cooldown (s)", "click_cooldown", 0.05, 2.0, 0.05)
        self._build_slider(container, "Drag hold time (s)", "drag_hold_time", 0.0, 1.5, 0.05)
        self._build_slider(container, "Double-click window (s)", "double_click_window", 0.1, 1.5, 0.05)
        self._build_slider(container, "Scroll sensitivity", "scroll_sensitivity", 0.2, 8.0, 0.1)
        self._build_slider(container, "Activation zone margin X", "frame_margin_x", 0.0, 0.4, 0.01)
        self._build_slider(container, "Activation zone margin Y", "frame_margin_y", 0.0, 0.4, 0.01)
        self._build_slider(container, "Screenshot cooldown (s)", "screenshot_cooldown", 0.3, 5.0, 0.1)

        ttk.Separator(container).pack(fill="x", pady=10)

        self._build_toggle(container, "Show FPS", "show_fps")
        self._build_toggle(container, "Show gesture guide", "show_gesture_guide")
        self._build_toggle(container, "Mirror camera (flip)", "flip_camera")

        ttk.Separator(container).pack(fill="x", pady=10)

        theme_frame = ttk.Frame(container)
        theme_frame.pack(fill="x", pady=4)
        ttk.Label(theme_frame, text="HUD theme").pack(side="left")
        theme_var = tk.StringVar(value=self.cfg.hud_theme)
        self._vars["hud_theme"] = theme_var

        def on_theme_change(*_):
            self.cfg.hud_theme = theme_var.get()
            self.on_change()

        theme_dropdown = ttk.Combobox(theme_frame, textvariable=theme_var, values=["dark", "light"], width=10, state="readonly")
        theme_dropdown.pack(side="right")
        theme_dropdown.bind("<<ComboboxSelected>>", on_theme_change)

        btn_frame = ttk.Frame(container)
        btn_frame.pack(fill="x", pady=(16, 0))
        ttk.Button(btn_frame, text="Save settings", command=self._save).pack(side="left", expand=True, fill="x", padx=(0, 6))
        ttk.Button(btn_frame, text="Reset to defaults", command=self._reset_defaults).pack(side="left", expand=True, fill="x", padx=(6, 0))

        ttk.Button(container, text="Close panel", command=self._on_close).pack(fill="x", pady=(8, 0))

        self._status_label = ttk.Label(container, text="", foreground="#2a7d2a")
        self._status_label.pack(anchor="w", pady=(10, 0))

        self._root.mainloop()

    # ------------------------------------------------------------------
    def _build_slider(self, parent, label, attr, lo, hi, step, is_int=False):
        frame = ttk.Frame(parent)
        frame.pack(fill="x", pady=4)

        top = ttk.Frame(frame)
        top.pack(fill="x")
        ttk.Label(top, text=label).pack(side="left")
        value_label = ttk.Label(top, text=str(getattr(self.cfg, attr)))
        value_label.pack(side="right")

        var = tk.DoubleVar(value=getattr(self.cfg, attr))
        self._vars[attr] = var

        def on_move(val):
            v = float(val)
            if is_int:
                v = int(round(v))
            setattr(self.cfg, attr, v)
            value_label.config(text=str(v))
            self.on_change()

        scale = ttk.Scale(frame, from_=lo, to=hi, orient="horizontal", variable=var, command=on_move)
        scale.pack(fill="x")

    def _build_toggle(self, parent, label, attr):
        var = tk.BooleanVar(value=getattr(self.cfg, attr))
        self._vars[attr] = var

        def on_toggle():
            setattr(self.cfg, attr, var.get())
            self.on_change()

        ttk.Checkbutton(parent, text=label, variable=var, command=on_toggle).pack(anchor="w", pady=2)

    # ------------------------------------------------------------------
    def _save(self):
        self.cfg.save()
        self._status_label.config(text="Settings saved.")
        self._root.after(1800, lambda: self._status_label.config(text=""))

    def _reset_defaults(self):
        defaults = Config()
        for f in defaults.__dataclass_fields__:
            setattr(self.cfg, f, getattr(defaults, f))
        self._refresh_widgets()
        self.on_change()
        self._status_label.config(text="Reset to defaults.")
        self._root.after(1800, lambda: self._status_label.config(text=""))

    def _refresh_widgets(self):
        for attr, var in self._vars.items():
            try:
                var.set(getattr(self.cfg, attr))
            except Exception:
                pass

    def _on_close(self):
        self.cfg.save()
        self.cfg.control_panel_enabled = False
        try:
            self._root.destroy()
        except Exception:
            pass
        self._root = None