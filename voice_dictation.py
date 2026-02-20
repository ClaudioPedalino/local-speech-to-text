# voice_dictation.py
# Offline voice dictation tool - System Tray, Ctrl+Shift+M to toggle record.
# Uses faster-whisper (CPU), sounddevice, pystray. No windows, no focus steal.

from __future__ import annotations

import logging
import sys
import threading
import time
import wave
from datetime import datetime
from enum import Enum
from pathlib import Path

# Logging: file + console. Recordings saved under logs/recordings/
LOG_DIR = Path(__file__).resolve().parent / "logs"
RECORDINGS_DIR = LOG_DIR / "recordings"

def _setup_logging() -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)
    log_file = LOG_DIR / "voice_dictation.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )


log = logging.getLogger(__name__)

# Optional imports with clear errors
try:
    import keyboard
except ImportError:
    print("Missing: pip install keyboard")
    sys.exit(1)
try:
    import sounddevice as sd
    import numpy as np
except ImportError:
    print("Missing: pip install sounddevice scipy")
    sys.exit(1)
try:
    from faster_whisper import WhisperModel
except ImportError:
    print("Missing: pip install faster-whisper (and FFmpeg in PATH)")
    sys.exit(1)
try:
    import pyperclip
    import pyautogui
except ImportError:
    print("Missing: pip install pyperclip pyautogui")
    sys.exit(1)
try:
    import pystray
    from PIL import Image, ImageDraw
except ImportError:
    print("Missing: pip install pystray Pillow")
    sys.exit(1)
import tkinter as tk
import ctypes
from queue import Queue, Empty


class State(Enum):
    IDLE = "idle"
    RECORDING = "recording"
    PROCESSING = "processing"


# --- Tray icons (Pillow: colored circles) ---
def make_icon_image(color: tuple[int, int, int], size: int = 64) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    margin = 4
    d.ellipse([margin, margin, size - margin, size - margin], fill=color, outline=(80, 80, 80))
    return img


# Prebuild tray icons (PIL Image for pystray)
ICON_SIZE = 64
ICON_IDLE = make_icon_image((120, 120, 120))       # Gray
ICON_RECORDING = make_icon_image((220, 50, 50))    # Red
ICON_PROCESSING = make_icon_image((50, 180, 80))   # Green

# --- Overlay window (small, top-right, no focus steal) ---
SW_SHOWNA = 8  # Show window without activating

def _overlay_thread(state_queue: Queue) -> None:
    root = tk.Tk()
    root.overrideredirect(1)
    root.attributes("-topmost", True)
    root.configure(bg="#1e1e1e", padx=12, pady=8)
    root.geometry("280x56")
    # Bottom-right, just above taskbar
    root.update_idletasks()
    w, h = root.winfo_reqwidth(), root.winfo_reqheight()
    y_bottom = root.winfo_screenheight() - h - 72
    root.geometry(f"+{root.winfo_screenwidth() - w - 16}+{y_bottom}")
    label = tk.Label(
        root,
        text="Idle",
        font=("Segoe UI", 12, "bold"),
        fg="#e0e0e0",
        bg="#1e1e1e",
    )
    label.pack(expand=True)
    try:
        hwnd = ctypes.windll.user32.GetParent(root.winfo_id())
    except Exception:
        hwnd = None
    if hwnd:
        ctypes.windll.user32.ShowWindow(hwnd, SW_SHOWNA)
    root.withdraw()  # start hidden; only show when Recording or Processing
    root.after(200, lambda: _overlay_poll(root, label, state_queue))

    def on_closing():
        root.quit()
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()

def _overlay_poll(root: tk.Tk, label: tk.Label, state_queue: Queue) -> None:
    try:
        while True:
            state = state_queue.get_nowait()
            if state is None:
                root.after(0, lambda: (root.quit(), root.destroy()))
                return
            if state == State.RECORDING:
                label.config(text="🔴 Speak now — then Ctrl+Shift+M to stop", fg="#ff6b6b")
                root.deiconify()
            elif state == State.PROCESSING:
                label.config(text="🟢 Processing...", fg="#69db7c")
                root.deiconify()
            else:
                root.withdraw()  # hide when Idle
    except Empty:
        pass
    try:
        root.after(200, lambda: _overlay_poll(root, label, state_queue))
    except tk.TclError:
        pass


# --- Recording ---
SAMPLE_RATE = 16000
CHANNELS = 1
DTYPE = np.int16
MIN_RECORDING_DURATION = 1.2  # seconds; ignore stop if shorter (avoids accidental double-press)


def record_audio_until_stop(stop_event: threading.Event) -> tuple[np.ndarray | None, float]:
    """Record from default input until stop_event is set. Returns (samples, duration_sec) or (None, 0) on error."""
    try:
        device = sd.default.device
        if device[0] is None:
            sd.default.device = None  # use system default
    except Exception as e:
        log.error("Audio device error: %s", e)
        return None, 0.0

    chunks: list[np.ndarray] = []
    start_time = time.perf_counter()

    def callback(indata: np.ndarray, frames: int, time_info, status):
        if status:
            log.warning("Sounddevice: %s", status)
        chunks.append(indata.copy())

    try:
        stream = sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            dtype=DTYPE,
            blocksize=1024,
            callback=callback,
        )
        stream.start()
        log.info("Recording started — speak now (Ctrl+Shift+M to stop)")
        while not stop_event.is_set():
            stop_event.wait(0.1)
        stream.stop()
        stream.close()
    except sd.PortAudioError as e:
        log.error("Microphone error: %s", e)
        return None, 0.0
    except Exception as e:
        log.exception("Recording error")
        return None, 0.0

    duration = time.perf_counter() - start_time
    if not chunks:
        log.warning("Recording stopped — no audio captured")
        return None, duration
    samples = np.concatenate(chunks, axis=0)
    log.info("Recording stopped — duration %.1f s, %d samples", duration, len(samples))
    return samples, duration


def save_wav(samples: np.ndarray, path: str | Path) -> None:
    path = Path(path)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(2)  # 16-bit
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(samples.tobytes())


# --- Transcription ---
def load_whisper_model():
    # CPU, base model, no download if already cached
    return WhisperModel("base", device="cpu", compute_type="int8")


def transcribe_audio(wav_path: str | Path) -> str:
    model = load_whisper_model()
    segments, info = model.transcribe(str(wav_path), language=None, vad_filter=True)
    text = " ".join(s.text.strip() for s in segments if s.text and s.text.strip()).strip()
    return text or ""


# --- Clipboard and paste ---
def copy_and_paste(text: str) -> None:
    """Always copy to clipboard; then try to paste with Ctrl+V."""
    try:
        pyperclip.copy(text)
        log.info("Copied to clipboard: %r", text[:80] + "..." if len(text) > 80 else text)
    except Exception as e:
        log.error("Clipboard copy error: %s", e)
        return
    if not text:
        return
    try:
        pyautogui.hotkey("ctrl", "v")
        log.info("Paste (Ctrl+V) sent to focused window")
    except Exception as e:
        log.warning("Paste hotkey error (text is in clipboard): %s", e)


# --- App state and tray ---
class DictationApp:
    def __init__(self, state_queue: Queue):
        self._state_queue = state_queue
        self.state = State.IDLE
        self._lock = threading.Lock()
        self._stop_recording = threading.Event()
        self._recording_thread: threading.Thread | None = None
        self._icon: pystray.Icon | None = None
        self._last_hotkey_time = 0.0
        self._hotkey_debounce_sec = 0.6

    def set_state(self, new: State) -> None:
        with self._lock:
            self.state = new
        try:
            self._state_queue.put_nowait(new)
        except Exception:
            pass
        self._update_tray_icon()

    def _update_tray_icon(self) -> None:
        if not self._icon:
            return
        if self.state == State.RECORDING:
            self._icon.icon = ICON_RECORDING
        elif self.state == State.PROCESSING:
            self._icon.icon = ICON_PROCESSING
        else:
            self._icon.icon = ICON_IDLE

    def _on_hotkey(self) -> None:
        now = time.monotonic()
        if now - self._last_hotkey_time < self._hotkey_debounce_sec:
            return  # debounce: avoid double trigger when switching apps
        self._last_hotkey_time = now
        with self._lock:
            s = self.state
        if s == State.IDLE:
            self._start_recording()
        elif s == State.RECORDING:
            self._stop_recording_event()

    def _start_recording(self) -> None:
        self.set_state(State.RECORDING)
        self._stop_recording.clear()
        self._recording_thread = threading.Thread(target=self._record_then_transcribe, daemon=True)
        self._recording_thread.start()

    def _stop_recording_event(self) -> None:
        self._stop_recording.set()

    def _record_then_transcribe(self) -> None:
        samples, duration = record_audio_until_stop(self._stop_recording)
        if samples is None or len(samples) == 0:
            self.set_state(State.IDLE)
            return
        if duration < MIN_RECORDING_DURATION:
            log.warning("Recording too short (%.1fs) — speak while red, then press to stop", duration)
            self.set_state(State.IDLE)
            return
        self.set_state(State.PROCESSING)
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        saved_wav = RECORDINGS_DIR / f"recording_{timestamp}.wav"
        try:
            save_wav(samples, saved_wav)
            log.info("Saved recording to %s", saved_wav)
            log.info("Transcribing...")
            text = transcribe_audio(saved_wav)
            log.info("Transcription result: %r", text if text else "(empty / no speech detected)")
            copy_and_paste(text)
        except Exception as e:
            log.exception("Transcribe/paste error: %s", e)
        self.set_state(State.IDLE)

    def run_tray(self) -> None:
        menu = pystray.Menu(
            pystray.MenuItem("Exit", self._quit, default=True),
        )
        self._icon = pystray.Icon(
            "voice_dictation",
            icon=ICON_IDLE,
            title="Voice Dictation (Ctrl+Shift+M)",
            menu=menu,
        )
        self._update_tray_icon()

        # Global hotkey (run in main thread after tray is ready is ok; keyboard hooks work globally)
        keyboard.add_hotkey("ctrl+shift+m", self._on_hotkey, suppress=True)

        # Run tray (blocking)
        self._icon.run()

    def _quit(self, icon: pystray.Icon, item: pystray.MenuItem) -> None:
        keyboard.unhook_all()
        self._stop_recording.set()
        try:
            self._state_queue.put_nowait(None)  # signal overlay to close
        except Exception:
            pass
        icon.stop()


def main() -> None:
    _setup_logging()
    log.info("Voice dictation starting (Ctrl+Shift+M)")
    pyautogui.FAILSAFE = False
    pyautogui.PAUSE = 0.05

    state_queue: Queue = Queue()
    overlay = threading.Thread(target=_overlay_thread, args=(state_queue,), daemon=True)
    overlay.start()
    time.sleep(0.3)  # let overlay create window

    app = DictationApp(state_queue)
    app.run_tray()


if __name__ == "__main__":
    main()
