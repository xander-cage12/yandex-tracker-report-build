import os
import sys
from pathlib import Path
import tracker_core as core

base = Path(sys.executable).resolve().parent
if sys.platform == "darwin":
    bundle = next((p for p in Path(sys.executable).resolve().parents if p.suffix == ".app"), None)
    if bundle is not None:
        base = bundle.parent
if not os.access(base, os.W_OK):
    base = (Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "YandexTrackerReport"
            if sys.platform == "win32" else Path.home() / "Library/Application Support/YandexTrackerReport")
core.SCRIPT_DIR = str(base)
core.LOG_DIR = str(base / "logs")
core.DEFAULT_CONFIG_DIR = str(base / "config")
core._POINTER_FILE = str(base / "config/config_location.txt")
