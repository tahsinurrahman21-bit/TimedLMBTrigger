"""Clock-based one-shot scheduling. No GUI or Windows dependencies."""
from dataclasses import dataclass
from datetime import datetime, timedelta
import threading
import time


def parse_time(text, clock_format, period="AM"):
    parts = text.strip().split(":")
    if len(parts) != 3 or any(not p.isascii() or not p.isdigit() for p in parts):
        raise ValueError("Enter a time as HH:MM:SS, for example 09:01:00.")
    h, m, s = map(int, parts)
    if not (0 <= m <= 59 and 0 <= s <= 59):
        raise ValueError("Minutes and seconds must be between 00 and 59.")
    if clock_format == "12":
        if not 1 <= h <= 12 or period not in ("AM", "PM"):
            raise ValueError("Use hours 01 through 12 and choose AM or PM.")
        h = h % 12 + (12 if period == "PM" else 0)
    elif clock_format != "24" or not 0 <= h <= 23:
        raise ValueError("In 24-hour mode, use hours 00 through 23.")
    return h, m, s


def next_trigger(now, hms):
    candidate = now.replace(hour=hms[0], minute=hms[1], second=hms[2], microsecond=0)
    tomorrow = candidate <= now
    if tomorrow:
        candidate += timedelta(days=1)
    return candidate, tomorrow


def checked_timestamp(local_time):
    stamp = local_time.timestamp()
    if datetime.fromtimestamp(stamp) != local_time:
        raise ValueError("That local time does not exist because of a daylight-saving change. Choose another time.")
    return stamp


def format_datetime(stamp):
    dt = datetime.fromtimestamp(stamp)
    return f"{dt:%B} {dt.day}, {dt.year}  |  {dt:%I:%M:%S %p} ({dt:%H:%M:%S})"


@dataclass(frozen=True)
class Job:
    target: float
    position: tuple | None = None
    keep_awake: bool = False
    test: bool = False
    action: str = "click"


class Scheduler:
    """One worker owns sleep requests; the condition serializes cancel and fire.

    emit(kind, detail) must be thread-safe and must not call Tk. The click is
    consumed before invoking the backend, even if the backend raises an error.
    """
    MAX_LATENESS = 5.0

    def __init__(self, backend, emit, clock=time.time):
        self.backend, self.emit, self.clock = backend, emit, clock
        self.condition = threading.Condition(threading.RLock())
        self._job = None
        self._closed = False
        self.worker = threading.Thread(target=self._run, name="one-shot-scheduler", daemon=True)
        self.worker.start()

    @property
    def job(self):
        with self.condition:
            return self._job

    def arm(self, job):
        with self.condition:
            if job.action not in ("click", "enter"):
                raise ValueError("Choose Left mouse click or Enter key.")
            if job.action == "enter" and job.position is not None:
                raise ValueError("Enter key triggers do not use mouse coordinates.")
            if self._closed or not self.worker.is_alive():
                raise RuntimeError("The scheduler is unavailable. Restart the application.")
            if self._job is not None:
                raise ValueError("A trigger is already armed. Cancel it first.")
            if job.target <= self.clock():
                raise ValueError("That time passed while confirming. Choose and confirm a new time.")
            self._job = job
            self.emit("ARMED", job)
            self.condition.notify_all()

    def cancel(self, reason="Cancelled by user"):
        with self.condition:
            if self._job is None:
                return False
            self._job = None
            self.emit("CANCELLED", reason)
            self.condition.notify_all()
            return True

    def wake(self):
        """Recheck immediately (also useful with a simulated clock in tests)."""
        with self.condition:
            self.condition.notify_all()

    def close(self):
        with self.condition:
            self.cancel("Application closed")
            self._closed = True
            self.condition.notify_all()
        self.worker.join(timeout=3)

    def _run(self):
        awake = False
        try:
            with self.condition:
                while not self._closed:
                    job = self._job
                    desired_awake = bool(job and job.keep_awake)
                    if desired_awake != awake:
                        try:
                            self.backend.keep_awake(desired_awake)
                            awake = desired_awake
                        except Exception as exc:
                            self._job = None
                            self.emit("ERROR", f"Could not update sleep prevention: {exc}")
                            # Stop on power API failure; thread exit also clears its request.
                            break
                    if job is None:
                        self.condition.wait()
                        continue
                    remaining = job.target - self.clock()
                    if remaining > 0:
                        self.condition.wait(timeout=min(0.5, max(0.001, remaining)))
                        continue
                    self._job = None  # Claim exactly once before any native side effect.
                    try:
                        if -remaining > self.MAX_LATENESS:
                            self.emit("MISSED", f"Scheduled time missed by {-remaining:.1f}s; no input sent.")
                        elif job.action == "enter":
                            self.backend.press_enter()
                            self.emit("ENTER", (-remaining, job.test))
                        else:
                            coordinates = self.backend.click(job.position)
                            self.emit("CLICK", (coordinates, -remaining, job.test))
                    except Exception as exc:
                        self.emit("ERROR", f"{'Enter key' if job.action == 'enter' else 'Click'} not completed; no retry: {exc}")
                    finally:
                        if awake:
                            self.backend.keep_awake(False)
                            awake = False
        except Exception as exc:
            with self.condition:
                self._job = None
            self.emit("ERROR", f"Scheduler stopped: {exc}")
        finally:
            if awake:
                try:
                    self.backend.keep_awake(False)
                except Exception as exc:
                    self.emit("ERROR", f"Sleep request cleanup failed: {exc}")
