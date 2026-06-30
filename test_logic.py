"""
test_logic.py — Unit-style smoke tests for the non-GUI logic.

Mocks pyautogui (no display in this sandbox) so we can exercise the
real Config, CoordinateMapper, CursorSmoother and GestureEngine code
paths and catch logic bugs before a human runs this on real hardware.
"""

import sys
import types
import math

# ---- Mock pyautogui before any of our modules import it ----
mock_pyautogui = types.ModuleType("pyautogui")
mock_pyautogui.FAILSAFE = True
mock_pyautogui.PAUSE = 0.1
mock_pyautogui._calls = []

def _size():
    return (1920, 1080)

def _moveTo(x, y):
    mock_pyautogui._calls.append(("moveTo", x, y))

def _click(button="left"):
    mock_pyautogui._calls.append(("click", button))

def _mouseDown(button="left"):
    mock_pyautogui._calls.append(("mouseDown", button))

def _mouseUp(button="left"):
    mock_pyautogui._calls.append(("mouseUp", button))

def _scroll(amount):
    mock_pyautogui._calls.append(("scroll", amount))

def _position():
    return (0, 0)

class _FakeImage:
    def save(self, path):
        mock_pyautogui._calls.append(("screenshot_save", path))

def _screenshot():
    return _FakeImage()

mock_pyautogui.size = _size
mock_pyautogui.moveTo = _moveTo
mock_pyautogui.click = _click
mock_pyautogui.mouseDown = _mouseDown
mock_pyautogui.mouseUp = _mouseUp
mock_pyautogui.scroll = _scroll
mock_pyautogui.position = _position
mock_pyautogui.screenshot = _screenshot

sys.modules["pyautogui"] = mock_pyautogui

# ---- Now safe to import our real modules ----
from config import Config
from mapping import CoordinateMapper
from smoothing import CursorSmoother
from gestures import GestureEngine, GestureState, WRIST, THUMB_TIP, INDEX_TIP, INDEX_MCP, MIDDLE_TIP, MIDDLE_MCP, RING_TIP, RING_MCP, PINKY_TIP, PINKY_MCP

PASS = 0
FAIL = 0


def check(name, condition):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  OK   {name}")
    else:
        FAIL += 1
        print(f"  FAIL {name}")


def section(title):
    print(f"\n=== {title} ===")


# ──────────────────────────────────────────────────────────────────────────
section("Config")
cfg = Config()
check("defaults load", cfg.smoothing_factor == 0.35)
check("control panel is OFF by default", cfg.control_panel_enabled is False)
cfg.smoothing_factor = 5.0
cfg.clamp()
check("clamp caps smoothing_factor at 1.0", cfg.smoothing_factor == 1.0)

import tempfile, os
tmp_path = os.path.join(tempfile.gettempdir(), "vm_test_settings.json")
cfg2 = Config()
cfg2.click_pinch_threshold = 50
cfg2.control_panel_enabled = True
cfg2.save(tmp_path)
loaded = Config.load(tmp_path)
check("save/load round-trips a changed field", loaded.click_pinch_threshold == 50)
check("save/load round-trips control_panel_enabled=True", loaded.control_panel_enabled is True)
os.remove(tmp_path)

loaded_missing = Config.load("/tmp/does_not_exist_vm.json")
check("load() falls back to defaults when file missing", loaded_missing.smoothing_factor == 0.35)


# ──────────────────────────────────────────────────────────────────────────
section("CoordinateMapper")
cfg = Config()
mapper = CoordinateMapper(cam_w=640, cam_h=480, screen_w=1920, screen_h=1080, cfg=cfg)

cx, cy = mapper.map_to_screen(320, 240)
check("center maps near screen center", abs(cx - 960) < 5 and abs(cy - 540) < 5)

x1, y1, x2, y2 = mapper.zone_rect()
sx, sy = mapper.map_to_screen(x1, y1)
check("zone top-left maps to screen (0,0)", sx == 0 and sy == 0)

sx2, sy2 = mapper.map_to_screen(x2, y2)
check("zone bottom-right maps to screen bottom-right", sx2 == 1919 and sy2 == 1079)

sx3, sy3 = mapper.map_to_screen(-1000, -1000)
check("far out-of-bounds input clamps to (0,0)", sx3 == 0 and sy3 == 0)

sx4, sy4 = mapper.map_to_screen(100000, 100000)
check("far out-of-bounds input clamps to bottom-right", sx4 == 1919 and sy4 == 1079)

cfg.frame_margin_x = 0.0
cfg.frame_margin_y = 0.0
mapper.refresh_from_config()
x1b, y1b, x2b, y2b = mapper.zone_rect()
check("refresh_from_config updates zone bounds", x1b == 0 and x2b == 640)


# ──────────────────────────────────────────────────────────────────────────
section("CursorSmoother")
smoother = CursorSmoother(smoothing_factor=0.5, history_len=3)
p1 = smoother.update(100, 100)
check("first update snaps directly", p1 == (100, 100))
p2 = smoother.update(200, 100)
check("second update moves partway toward target", 100 < p2[0] < 200)
smoother.reset()
check("reset clears smoothed state", smoother.smoothed_x is None)

smoother2 = CursorSmoother(smoothing_factor=0.5, history_len=3)
smoother2.update(0, 0)
smoother2.set_params(smoothing_factor=0.9, history_len=6)
check("set_params updates factor", smoother2.factor == 0.9)
check("set_params resizes history deque", smoother2.history.maxlen == 6)


# ──────────────────────────────────────────────────────────────────────────
section("GestureEngine — basic click / no false positives while idle")

def make_hand(thumb, index, middle, ring, pinky, wrist=(320, 400),
              index_mcp=(300, 300), middle_mcp=(320, 300), ring_mcp=(340, 300), pinky_mcp=(360, 300)):
    return {
        WRIST: wrist,
        THUMB_TIP: thumb,
        INDEX_TIP: index,
        INDEX_MCP: index_mcp,
        MIDDLE_TIP: middle,
        MIDDLE_MCP: middle_mcp,
        RING_TIP: ring,
        RING_MCP: ring_mcp,
        PINKY_TIP: pinky,
        PINKY_MCP: pinky_mcp,
    }

cfg = Config()
cfg.click_cooldown = 0.0
cfg.drag_hold_time = 100.0
engine = GestureEngine(cfg)

hand_idle = make_hand(thumb=(200, 400), index=(320, 100), middle=(360, 100), ring=(400, 200), pinky=(440, 250))
state, info = engine.update(hand_idle)
check("idle open hand -> MOVING", state == GestureState.MOVING)
check("idle open hand fires no clicks", len(mock_pyautogui._calls) == 0)

hand_pinch = make_hand(thumb=(300, 300), index=(305, 300), middle=(360, 100), ring=(400, 200), pinky=(440, 250))
state, info = engine.update(hand_pinch)
check("pinch held -> LEFT_CLICK state (pre-release)", state == GestureState.LEFT_CLICK)

hand_release = make_hand(thumb=(200, 400), index=(320, 100), middle=(360, 100), ring=(400, 200), pinky=(440, 250))
mock_pyautogui._calls.clear()
state, info = engine.update(hand_release)
left_clicks = [c for c in mock_pyautogui._calls if c[0] == "click" and c[1] == "left"]
check("releasing a quick pinch fires exactly one left click", len(left_clicks) == 1)


# ──────────────────────────────────────────────────────────────────────────
section("GestureEngine — right click vs left click don't both fire")

cfg = Config()
cfg.click_cooldown = 0.0
engine = GestureEngine(cfg)
mock_pyautogui._calls.clear()

hand_right_pinch = make_hand(thumb=(300, 300), index=(320, 100), middle=(303, 302), ring=(400, 200), pinky=(440, 250))
state, info = engine.update(hand_right_pinch)
check("thumb+middle pinch -> RIGHT_CLICK", state == GestureState.RIGHT_CLICK)
right_clicks = [c for c in mock_pyautogui._calls if c[0] == "click" and c[1] == "right"]
left_clicks = [c for c in mock_pyautogui._calls if c[0] == "click" and c[1] == "left"]
check("right pinch fires right click", len(right_clicks) == 1)
check("right pinch does not also fire left click", len(left_clicks) == 0)


# ──────────────────────────────────────────────────────────────────────────
section("GestureEngine — drag engages after hold and releases cleanly")

cfg = Config()
cfg.click_cooldown = 0.0
cfg.drag_hold_time = 0.0
engine = GestureEngine(cfg)
mock_pyautogui._calls.clear()

hand_pinch = make_hand(thumb=(300, 300), index=(304, 301), middle=(360, 100), ring=(400, 200), pinky=(440, 250))
state, info = engine.update(hand_pinch)
state, info = engine.update(hand_pinch)
check("held pinch transitions to DRAGGING", state == GestureState.DRAGGING)
mouse_downs = [c for c in mock_pyautogui._calls if c[0] == "mouseDown"]
check("drag engagement calls mouseDown exactly once", len(mouse_downs) == 1)

hand_release = make_hand(thumb=(200, 400), index=(320, 100), middle=(360, 100), ring=(400, 200), pinky=(440, 250))
mock_pyautogui._calls.clear()
state, info = engine.update(hand_release)
mouse_ups = [c for c in mock_pyautogui._calls if c[0] == "mouseUp"]
clicks_after_drag = [c for c in mock_pyautogui._calls if c[0] == "click"]
check("releasing after a drag calls mouseUp", len(mouse_ups) == 1)
check("releasing after a drag does NOT also fire a click", len(clicks_after_drag) == 0)


# ──────────────────────────────────────────────────────────────────────────
section("GestureEngine — reset() releases a stuck drag")

cfg = Config()
cfg.drag_hold_time = 0.0
engine = GestureEngine(cfg)
hand_pinch = make_hand(thumb=(300, 300), index=(304, 301), middle=(360, 100), ring=(400, 200), pinky=(440, 250))
engine.update(hand_pinch)
engine.update(hand_pinch)
check("drag is engaged before reset", engine._is_dragging is True)
mock_pyautogui._calls.clear()
engine.reset()
mouse_ups = [c for c in mock_pyautogui._calls if c[0] == "mouseUp"]
check("reset() while dragging calls mouseUp", len(mouse_ups) == 1)
check("reset() clears _is_dragging flag", engine._is_dragging is False)


# ──────────────────────────────────────────────────────────────────────────
section("GestureEngine — scroll mode")

cfg = Config()
cfg.click_cooldown = 0.0
engine = GestureEngine(cfg)
mock_pyautogui._calls.clear()

hand_scroll_1 = make_hand(thumb=(300, 300), index=(320, 200), middle=(360, 100), ring=(304, 301), pinky=(440, 250))
state, info = engine.update(hand_scroll_1)
check("thumb+ring pinch -> SCROLLING", state == GestureState.SCROLLING)

hand_scroll_2 = make_hand(thumb=(300, 300), index=(320, 150), middle=(360, 100), ring=(304, 301), pinky=(440, 250))
state, info = engine.update(hand_scroll_2)
scrolls = [c for c in mock_pyautogui._calls if c[0] == "scroll"]
check("moving hand up during scroll mode fires scroll()", len(scrolls) >= 1)
if scrolls:
    check("hand moving up scrolls up (positive amount)", scrolls[-1][1] > 0)


# ──────────────────────────────────────────────────────────────────────────
section("GestureEngine — screenshot gesture + cooldown")

cfg = Config()
cfg.click_cooldown = 0.0
cfg.screenshot_cooldown = 1.0
engine = GestureEngine(cfg)
mock_pyautogui._calls.clear()

hand_pinky = make_hand(thumb=(300, 300), index=(320, 100), middle=(360, 100), ring=(400, 200), pinky=(303, 302))
state, info = engine.update(hand_pinky)
check("thumb+pinky pinch -> SCREENSHOT state", state == GestureState.SCREENSHOT)
saves = [c for c in mock_pyautogui._calls if c[0] == "screenshot_save"]
check("screenshot gesture saves a file", len(saves) == 1)

state, info = engine.update(hand_pinky)
saves2 = [c for c in mock_pyautogui._calls if c[0] == "screenshot_save"]
check("screenshot cooldown prevents immediate repeat", len(saves2) == 1)


# ──────────────────────────────────────────────────────────────────────────
section("GestureEngine — no-hand reset doesn't crash on fresh engine")
cfg = Config()
engine = GestureEngine(cfg)
try:
    engine.reset()
    check("reset() on fresh engine (no prior drag) doesn't raise", True)
except Exception as e:
    check(f"reset() on fresh engine raised {e}", False)


# ──────────────────────────────────────────────────────────────────────────
section("ControlPanel — toggle bookkeeping (no real display needed)")
from control_panel import ControlPanel

cfg = Config()
panel = ControlPanel(cfg)
check("panel not running before start() is ever called", panel.is_running() is False)

import threading, time as _time

def _fake_run(self):
    self._fake_stop = False
    while not self._fake_stop:
        _time.sleep(0.01)

panel._run = _fake_run.__get__(panel)
panel._fake_stop = False

panel.start()
_time.sleep(0.05)
check("is_running() is True after start() with a live thread", panel.is_running() is True)

panel._fake_stop = True
_time.sleep(0.05)
check("is_running() is False once the thread exits", panel.is_running() is False)

panel._fake_stop = False
panel.toggle()
_time.sleep(0.05)
check("toggle() starts the panel when it was closed", panel.is_running() is True)
panel._fake_stop = True
_time.sleep(0.05)


# ──────────────────────────────────────────────────────────────────────────
print(f"\n{'='*40}\nPASS: {PASS}  FAIL: {FAIL}\n{'='*40}")
sys.exit(1 if FAIL else 0)