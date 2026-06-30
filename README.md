# Virtual Mouse — Hand Gesture Mouse Control

Control your OS cursor — and more — using hand gestures from a webcam.  
A modern, modular implementation with a live settings panel, on‑screen HUD, and gesture guide.

## Features

- **Move** – Index finger tip
- **Left click** – Thumb + Index pinch (tap)
- **Double click** – Two quick left‑clicks
- **Drag** – Thumb + Index pinch (hold)
- **Right click** – Thumb + Middle pinch (tap)
- **Scroll** – Thumb + Ring pinch, held + move hand up/down
- **Screenshot** – Thumb + Pinky pinch (saved to `~/Pictures/VirtualMouseShots`)

### On‑Screen HUD
- Status pill with current gesture
- FPS counter and activity sparkline
- Activation zone with corner brackets
- Configurable gesture guide (toggle with `g`)
- Dark/light theme (toggle with `t`)

### Live Control Panel
- Sliders for smoothing, pinch thresholds, cooldowns, and sensitivity
- Toggles for FPS, guide, and camera mirror
- Theme picker
- Save/Reset buttons – settings persist in `virtual_mouse_settings.json`

## Installation

```bash
pip install -r requirements.txt