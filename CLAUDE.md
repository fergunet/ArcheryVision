# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Setup
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Run
python main.py
```

No tests, linter config, or CI exist yet.

## Architecture

Desktop app built with **PySide6 + OpenCV**. The target deployment platform is Windows 10/11; current development and testing is on Linux.

### Threading model

There are three types of worker threads, all `QThread` subclasses:

- **`CameraWorker`** (`app/camera/manager.py`) — one per active camera. Runs a tight `cap.read()` loop, pushes raw BGR frames to a `FrameRingBuffer`, and emits `frame_ready`. The `frame_ready` signal is **not connected to anything** — display is driven independently by a `QTimer`.
- **`HRMClient`** (`app/hrm/ble_client.py`) — a single thread with its own `asyncio` event loop for BLE scanning and Heart Rate Profile notifications.
- **`ClipExportWorker`** (`app/ui/main_window.py`) — created on demand when the user saves a clip; wraps `ClipExporter`.

### Display loop

`MainWindow` has a `QTimer` firing every 33 ms (`DISPLAY_REFRESH_MS`). On each tick it calls `_update_displays`, which computes `target_time = SyncClock.now() - slot.delay_seconds` and fetches the nearest buffered frame via `FrameRingBuffer.get_nearest()`. Playback only runs while `SyncClock.is_playing` is `True`.

`SyncClock.now()` returns `time.monotonic()` — the same clock used to timestamp frames in `CameraWorker`, so delay arithmetic is consistent with no offset correction needed.

### Buffer design

`FrameRingBuffer` (`app/camera/buffer.py`) stores `(timestamp, numpy_frame)` pairs in two parallel lists protected by a `threading.Lock`. Eviction is time-based (frames older than `_max_seconds`) with a secondary capacity cap.

The buffer is **dynamically sized**: it starts at 2 s and grows to `delay_seconds + 2 s` when the user moves a delay slider (`set_max_seconds()`). This prevents memory exhaustion — at 30 fps and 1280×720, a fixed 60 s buffer would use ~7 GB per camera.

### Clip export

`ClipExporter` (`app/recording/exporter.py`) reads back-in-time from each camera's buffer at `reference_time - slot.delay_seconds`, applies rotation, letterboxes each stream to 640×360, and composites a 1280×720 2×2 grid with `cv2.VideoWriter` (mp4v codec).

### Config persistence

`ConfigStore` (`app/config/persistence.py`) wraps `QSettings` (INI file on Linux, registry on Windows). Delay slider changes are debounced 400 ms before writing to avoid calling `setValue` on every tick.

### UI structure

- `QMdiArea` holds four `CameraSubWindow` (MDI subwindows), one per camera slot.
- A `QDockWidget` on the right contains `ControlsPanel`, which embeds one `SlotControl` per camera slot (device picker, delay slider/spinbox) plus the `HRMPanel`.
- Camera-slot state lives in `CameraSlot` objects inside `CameraManager`; the UI reflects it but is not the source of truth.
