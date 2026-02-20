# Voice Dictation (Offline)

Offline voice-to-text tool for Windows. Lives in the system tray; use **Ctrl+Shift+M** to start/stop recording. Speech is transcribed locally with [faster-whisper](https://github.com/SYSTRAN/faster-whisper) (CPU) and pasted where the cursor is. No cloud, no focus stealing.

## Features

- **Shortcut:** Ctrl+Shift+M — first press starts recording, second press stops, transcribes, copies to clipboard and pastes.
- **System tray:** Red = recording, Green = processing, Gray = idle. Right-click → Exit.
- **Status overlay:** Small window above the taskbar when recording/processing (hidden when idle).
- **Logs:** `logs/voice_dictation.log` and recordings in `logs/recordings/` (WAV files).

## Quick start (recommended)

1. **Install Python 3.10, 3.11, or 3.12** (64-bit) from [python.org](https://www.python.org/downloads/). During setup, check **"Add python.exe to PATH"**.
2. **Install FFmpeg** and add its `bin` folder to your system PATH (see [Installing FFmpeg](#installing-ffmpeg) below).
3. **Run the launcher:** double-click **`run.bat`** (or run it from a terminal in this folder).
   - The first run creates a virtual environment and installs dependencies (may take a few minutes).
   - The app starts; an icon appears in the system tray. Use Ctrl+Shift+M to dictate.

## Manual run (without the launcher)

From a terminal in the project folder:

```powershell
# Use a supported Python (3.10–3.12). Example with Python Launcher:
py -3.12 -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
python voice_dictation.py
```

Or if your default `python` is already 3.10–3.12:

```powershell
pip install -r requirements.txt
python voice_dictation.py
```

## Requirements

- **Windows 10/11** (64-bit)
- **Python 3.10, 3.11, or 3.12** (64-bit). Newer versions (e.g. 3.14) may lack prebuilt wheels and require a C compiler.
- **FFmpeg** in your system PATH (required by faster-whisper for audio).
- Default microphone configured in Windows.

## Installing FFmpeg

### Option A: Download (recommended)

1. Go to [FFmpeg Windows builds](https://github.com/BtbN/FFmpeg-Builds/releases).
2. Download the **essentials** or **gpl** ZIP for Windows 64-bit (e.g. `ffmpeg-master-latest-win64-gpl.zip`).
3. Extract the ZIP. Inside you’ll see a folder with a **bin** subfolder containing `ffmpeg.exe`.
4. Add that **bin** folder to your system PATH:
   - Windows search → “Environment variables” → “Edit the system environment variables” → “Environment Variables…”
   - Under “System variables”, select **Path** → **Edit** → **New** → paste the full path to the **bin** folder (e.g. `C:\ffmpeg\bin`).
   - Confirm all dialogs and **open a new terminal**.
5. Check: `ffmpeg -version` should print version info.

### Option B: winget

```powershell
winget install FFmpeg
```

Then open a new terminal and run `ffmpeg -version`.

### Option C: Chocolatey

```powershell
choco install ffmpeg
```

## Usage

- **Start:** Ctrl+Shift+M → tray icon turns red, overlay shows “Speak now — then Ctrl+Shift+M to stop”.
- **Stop:** Ctrl+Shift+M again → icon turns green (processing), then transcription is copied to the clipboard and pasted into the focused window (e.g. Notepad++, editor).
- **Exit:** Right-click tray icon → **Exit**.

Record at least ~1–2 seconds; very short recordings are ignored. The result is always copied to the clipboard even if auto-paste fails.

## Troubleshooting

| Issue | What to do |
|--------|-------------|
| `python` / `py` not found | Install Python from python.org and check “Add to PATH”. Restart the terminal. |
| `Missing: pip install …` or import errors | Run the app via **run.bat** (it sets up the venv and installs dependencies), or run `pip install -r requirements.txt` inside the project folder (with the correct Python/venv). |
| Microphone error / PortAudioError | Set your mic as the default input in Windows (Settings → Sound → Input). Close other apps using the microphone. |
| No transcription / FFmpeg error | Ensure FFmpeg is on the PATH (see [Installing FFmpeg](#installing-ffmpeg)). Open a **new** terminal after changing PATH. |
| Ctrl+Shift+M does nothing | App must be running (tray icon visible). Run as normal user (not “Run as administrator”). |
| No paste / wrong window | Focus the target window (e.g. click in the editor) before pressing Ctrl+Shift+M the second time. Text is also copied to the clipboard for manual paste. |
| Tray icon not visible | On Windows 11, open the “^” tray overflow and look for the app icon there. |

## Building an executable (PyInstaller)

To distribute a single `.exe` (users still need FFmpeg on PATH, or you ship FFmpeg next to the exe):

```powershell
.\venv\Scripts\activate
pip install pyinstaller
pyinstaller --onefile --windowed --name VoiceDictation voice_dictation.py
```

The executable is created in `dist\VoiceDictation.exe`. End users must have FFmpeg in their PATH (or you provide the FFmpeg `bin` folder alongside the exe and document how to add it to PATH).

## License

Use and modify as you like. Dependencies have their own licenses (see PyPI / project pages).
