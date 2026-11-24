"""Small ctypes boundary for local Windows input, hotkeys, and power requests."""
import ctypes as ct
from ctypes import wintypes as wt
import threading
import os

user32 = ct.WinDLL("user32", use_last_error=True)
kernel32 = ct.WinDLL("kernel32", use_last_error=True)


class MOUSEINPUT(ct.Structure):
    _fields_ = [("dx", wt.LONG), ("dy", wt.LONG), ("mouseData", wt.DWORD),
                ("dwFlags", wt.DWORD), ("time", wt.DWORD), ("dwExtraInfo", ct.c_size_t)]


class KEYBDINPUT(ct.Structure):
    _fields_ = [("wVk", wt.WORD), ("wScan", wt.WORD), ("dwFlags", wt.DWORD),
                ("time", wt.DWORD), ("dwExtraInfo", ct.c_size_t)]


class HARDWAREINPUT(ct.Structure):
    _fields_ = [("uMsg", wt.DWORD), ("wParamL", wt.WORD), ("wParamH", wt.WORD)]


class INPUTUNION(ct.Union):
    _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT), ("hi", HARDWAREINPUT)]


class INPUT(ct.Structure):
    _anonymous_ = ("data",)
    _fields_ = [("type", wt.DWORD), ("data", INPUTUNION)]


def bind(dll, name, args, result):
    function = getattr(dll, name)
    function.argtypes, function.restype = args, result
    return function


SendInput = bind(user32, "SendInput", [wt.UINT, ct.POINTER(INPUT), ct.c_int], wt.UINT)
GetCursorPos = bind(user32, "GetCursorPos", [ct.POINTER(wt.POINT)], wt.BOOL)
SetCursorPos = bind(user32, "SetCursorPos", [ct.c_int, ct.c_int], wt.BOOL)
MonitorFromPoint = bind(user32, "MonitorFromPoint", [wt.POINT, wt.DWORD], wt.HANDLE)
WindowFromPoint = bind(user32, "WindowFromPoint", [wt.POINT], wt.HWND)
GetForegroundWindow = bind(user32, "GetForegroundWindow", [], wt.HWND)
GetWindowThreadProcessId = bind(user32, "GetWindowThreadProcessId", [wt.HWND, ct.POINTER(wt.DWORD)], wt.DWORD)
GetAsyncKeyState = bind(user32, "GetAsyncKeyState", [ct.c_int], ct.c_short)
OpenInputDesktop = bind(user32, "OpenInputDesktop", [wt.DWORD, wt.BOOL, wt.DWORD], wt.HANDLE)
GetUserObjectInformation = bind(user32, "GetUserObjectInformationW",
    [wt.HANDLE, ct.c_int, ct.c_void_p, wt.DWORD, ct.POINTER(wt.DWORD)], wt.BOOL)
CloseDesktop = bind(user32, "CloseDesktop", [wt.HANDLE], wt.BOOL)
SetThreadExecutionState = bind(kernel32, "SetThreadExecutionState", [wt.DWORD], wt.DWORD)
CreateMutex = bind(kernel32, "CreateMutexW", [ct.c_void_p, wt.BOOL, wt.LPCWSTR], wt.HANDLE)
CloseHandle = bind(kernel32, "CloseHandle", [wt.HANDLE], wt.BOOL)
GetCurrentThreadId = bind(kernel32, "GetCurrentThreadId", [], wt.DWORD)
RegisterHotKey = bind(user32, "RegisterHotKey", [wt.HWND, ct.c_int, wt.UINT, wt.UINT], wt.BOOL)
UnregisterHotKey = bind(user32, "UnregisterHotKey", [wt.HWND, ct.c_int], wt.BOOL)
GetMessage = bind(user32, "GetMessageW", [ct.POINTER(wt.MSG), wt.HWND, wt.UINT, wt.UINT], wt.BOOL)
PostThreadMessage = bind(user32, "PostThreadMessageW", [wt.DWORD, wt.UINT, wt.WPARAM, wt.LPARAM], wt.BOOL)


def enable_dpi_awareness():
    # Call before Tk or cursor APIs so multi-monitor coordinates are physical pixels.
    try:
        set_context = bind(user32, "SetProcessDpiAwarenessContext", [ct.c_void_p], wt.BOOL)
        if set_context(ct.c_void_p(-4)):  # PER_MONITOR_AWARE_V2
            return
    except AttributeError:
        pass
    bind(user32, "SetProcessDPIAware", [], wt.BOOL)()


class SingleInstance:
    def __init__(self):
        self.handle = CreateMutex(None, False, "Local\\TimedLMBTrigger.SingleInstance.v1")
        if not self.handle:
            raise ct.WinError(ct.get_last_error())
        if ct.get_last_error() == 183:
            self.close()
            raise RuntimeError("Timed LMB Trigger is already running in this Windows session.")

    def close(self):
        if self.handle:
            CloseHandle(self.handle)
            self.handle = None


class WindowsBackend:
    def position(self):
        point = wt.POINT()
        if not GetCursorPos(ct.byref(point)):
            raise ct.WinError(ct.get_last_error())
        return point.x, point.y

    def validate_position(self, position):
        if not MonitorFromPoint(wt.POINT(*position), 0):
            raise ValueError("The saved position is outside the connected monitors. Save it again.")

    def keep_awake(self, enabled):
        # This is always called by the scheduler thread, including cleanup.
        flags = 0x80000000 | (0x00000001 if enabled else 0)
        if not SetThreadExecutionState(flags):
            raise ct.WinError(ct.get_last_error())

    def _check_desktop(self):
        desktop = OpenInputDesktop(0, False, 0x0001)
        if not desktop:
            raise RuntimeError("The Windows input desktop is unavailable (locked or secure screen).")
        try:
            name = ct.create_unicode_buffer(256)
            needed = wt.DWORD()
            if not GetUserObjectInformation(desktop, 2, name, ct.sizeof(name), ct.byref(needed)):
                raise ct.WinError(ct.get_last_error())
            if name.value.lower() != "default":
                raise RuntimeError("Windows is on a locked or secure desktop; no input sent.")
        finally:
            CloseDesktop(desktop)

    def click(self, position=None):
        self._check_desktop()
        # Avoid turning a plain click into a drag or modified click.
        if any(GetAsyncKeyState(key) & 0x8000 for key in (1, 2, 4, 5, 6, 16, 17, 18, 91, 92)):
            raise RuntimeError("A mouse button or modifier key is held down; no click sent.")
        if position is not None:
            self.validate_position(position)
            if not SetCursorPos(*position):
                raise ct.WinError(ct.get_last_error())
            if self.position() != tuple(position):
                raise RuntimeError("Windows constrained the cursor away from the saved position; no click sent.")
        coordinates = self.position()
        self._check_target(coordinates)
        events = (INPUT * 2)()
        events[0].type = events[1].type = 0  # INPUT_MOUSE
        events[0].mi.dwFlags = 0x0002  # LEFTDOWN; no MOVE flag in current-position mode.
        events[1].mi.dwFlags = 0x0004  # LEFTUP
        ct.set_last_error(0)
        sent = SendInput(2, events, ct.sizeof(INPUT))
        if sent != 2:
            error = ct.get_last_error()
            if sent == 1:
                # Never repeat DOWN; release only if the first event was accepted.
                release = INPUT()
                release.mi.dwFlags = 0x0004
                SendInput(1, ct.byref(release), ct.sizeof(INPUT))
            raise RuntimeError(f"SendInput accepted {sent}/2 events (Windows error {error}). "
                               "Input may be blocked or the target may be elevated.")
        return coordinates

    def _check_target(self, coordinates):
        window = WindowFromPoint(wt.POINT(*coordinates))
        owner = wt.DWORD()
        if window:
            GetWindowThreadProcessId(window, ct.byref(owner))
            if owner.value == os.getpid():
                raise RuntimeError("The cursor is over Timed LMB Trigger itself. No click sent; "
                                   "place it over the intended target application.")

    def _check_enter_target(self):
        window = GetForegroundWindow()
        owner = wt.DWORD()
        if not window or not GetWindowThreadProcessId(window, ct.byref(owner)):
            raise RuntimeError("No foreground application is available; no Enter key sent.")
        if owner.value == os.getpid():
            raise RuntimeError("Timed LMB Trigger has keyboard focus. Switch to the intended "
                               "application before the trigger fires; no Enter key sent.")

    def press_enter(self):
        """Send one ordinary Enter down/up pair to the current keyboard focus."""
        self._check_desktop()
        if any(GetAsyncKeyState(key) & 0x8000 for key in (13, 16, 17, 18, 91, 92)):
            raise RuntimeError("Enter or a modifier key is held down; no Enter key sent.")
        events = (INPUT * 2)()
        events[0].type = events[1].type = 1  # INPUT_KEYBOARD
        events[0].ki.wVk = events[1].ki.wVk = 0x0D  # VK_RETURN (main Enter key)
        events[1].ki.dwFlags = 0x0002  # KEYEVENTF_KEYUP
        self._check_enter_target()
        ct.set_last_error(0)
        sent = SendInput(2, events, ct.sizeof(INPUT))
        if sent != 2:
            error = ct.get_last_error()
            if sent == 1:
                # Release only; never resend DOWN or repeat the trigger.
                SendInput(1, ct.byref(events[1]), ct.sizeof(INPUT))
            raise RuntimeError(f"SendInput accepted {sent}/2 Enter events (Windows error {error}). "
                               "Input may be blocked or the target may be elevated.")


class Hotkeys:
    """Dedicated blocking message loop; emergency cancellation does not wait for Tk."""
    def __init__(self, cancel, capture, failure):
        self.cancel, self.capture, self.failure = cancel, capture, failure
        self.ready = threading.Event()
        self.thread_id = None
        self.registered = set()
        self.error = None
        self.thread = threading.Thread(target=self._run, name="global-hotkeys", daemon=True)
        self.thread.start()
        if not self.ready.wait(timeout=3):
            raise RuntimeError("Could not start emergency hotkey listener.")
        if self.error:
            self.close()
            raise RuntimeError(self.error)

    @property
    def capture_available(self):
        return 2 in self.registered

    def _run(self):
        try:
            self.thread_id = GetCurrentThreadId()
            for identifier, key in ((1, ord("X")), (2, ord("S"))):
                if RegisterHotKey(None, identifier, 0x4003, key):
                    self.registered.add(identifier)
                elif identifier == 1:
                    raise RuntimeError("Ctrl+Alt+X is in use by another program. Close that program "
                                       "or release its shortcut, then restart Timed LMB Trigger.")
            self.ready.set()
            message = wt.MSG()
            while True:
                result = GetMessage(ct.byref(message), None, 0, 0)
                if result == -1:
                    raise ct.WinError(ct.get_last_error())
                if result == 0:
                    break
                if message.message == 0x0312:
                    if message.wParam == 1:
                        self.cancel()
                    elif message.wParam == 2:
                        self.capture()
        except Exception as exc:
            self.error = str(exc)
            self.failure(self.error)
        finally:
            for identifier in self.registered:
                UnregisterHotKey(None, identifier)
            self.ready.set()

    def close(self):
        if self.thread_id and self.thread.is_alive():
            PostThreadMessage(self.thread_id, 0x0012, 0, 0)  # WM_QUIT
            self.thread.join(timeout=3)
