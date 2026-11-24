"""Choose a writable, project-local root for persistent application files."""
import json
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import sys


def application_root():
    """Keep app data beside the source project or downloaded executable."""
    if getattr(sys, "frozen", False):
        executable_dir = Path(sys.executable).resolve().parent
        project_root = executable_dir.parent
        # A locally built executable lives in the project's dist directory.
        # Keep using the project root there; a downloaded one-file app uses its
        # own containing folder instead.
        if (project_root / "src" / "app.py").is_file():
            return project_root
        return executable_dir
    return Path(__file__).resolve().parent.parent


ROOT = application_root()
DEFAULTS = {
    "time": "09:00:00", "clock_format": "12", "period": "AM",
    "click_mode": "current", "saved_position": None, "keep_awake": False,
    "action": "click",
}


def initialize():
    for name in ("config", "logs", "work"):
        (ROOT / name).mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("TimedLMBTrigger")
    logger.setLevel(logging.INFO)
    handler = RotatingFileHandler(ROOT / "logs" / "trigger.log", maxBytes=512_000,
                                  backupCount=2, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s | %(message)s", "%Y-%m-%d %H:%M:%S"))
    logger.addHandler(handler)
    return logger


def load_settings(path=None):
    path = path or ROOT / "config" / "settings.json"
    if not path.exists():
        return DEFAULTS.copy(), None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("Settings must be a JSON object.")
        result = DEFAULTS.copy()
        from core import parse_time
        parse_time(data.get("time", result["time"]), data.get("clock_format", "12"), data.get("period", "AM"))
        for key in ("time", "clock_format", "period"):
            result[key] = data.get(key, result[key])
        if data.get("click_mode", "current") not in ("current", "saved"):
            raise ValueError("Invalid click mode.")
        result["click_mode"] = data.get("click_mode", "current")
        if data.get("action", "click") not in ("click", "enter"):
            raise ValueError("Invalid trigger action.")
        result["action"] = data.get("action", "click")
        position = data.get("saved_position")
        if position is not None:
            if (not isinstance(position, list) or len(position) != 2
                    or any(type(v) is not int or not -2147483648 <= v <= 2147483647 for v in position)):
                raise ValueError("Invalid saved coordinates.")
            result["saved_position"] = position
        if type(data.get("keep_awake", False)) is not bool:
            raise ValueError("Invalid keep-awake preference.")
        result["keep_awake"] = data.get("keep_awake", False)
        return result, None
    except (OSError, ValueError, TypeError, AttributeError) as exc:
        return DEFAULTS.copy(), f"Could not load preferences; using defaults. {exc}"


def save_settings(settings, path=None):
    path = path or ROOT / "config" / "settings.json"
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")
    temp.replace(path)
