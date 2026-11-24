import ctypes as ct
import sys
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import windows_api as win


class InputTests(unittest.TestCase):
    def setUp(self):
        self.backend = win.WindowsBackend()
        self.patches = [patch.object(self.backend, "_check_desktop"),
                        patch.object(self.backend, "_check_target"),
                        patch.object(self.backend, "position", return_value=(50, 80)),
                        patch.object(win, "GetAsyncKeyState", return_value=0)]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in reversed(self.patches):
            p.stop()

    def test_input_layout(self):
        self.assertEqual(ct.sizeof(win.INPUT), 40 if ct.sizeof(ct.c_void_p) == 8 else 28)

    def test_current_position_sends_only_one_down_up_pair(self):
        with patch.object(win, "SendInput", return_value=2) as send, patch.object(win, "SetCursorPos") as move:
            self.assertEqual(self.backend.click(), (50, 80))
            send.assert_called_once()
            count, events, size = send.call_args.args
            self.assertEqual(count, 2)
            self.assertEqual([e.mi.dwFlags for e in events], [2, 4])
            move.assert_not_called()

    def test_saved_mode_moves_once(self):
        with patch.object(win, "MonitorFromPoint", return_value=1), patch.object(win, "SetCursorPos", return_value=1) as move, patch.object(win, "SendInput", return_value=2):
            self.backend.click((50, 80))
            move.assert_called_once_with(50, 80)

    def test_partial_input_releases_without_second_down(self):
        with patch.object(win, "SendInput", side_effect=[1, 1]) as send:
            with self.assertRaises(RuntimeError):
                self.backend.click()
            self.assertEqual(send.call_count, 2)
            release = ct.cast(send.call_args.args[1], ct.POINTER(win.INPUT)).contents
            self.assertEqual(release.mi.dwFlags, 4)

    def test_blocked_input_no_retry(self):
        with patch.object(win, "SendInput", return_value=0) as send:
            with self.assertRaises(RuntimeError):
                self.backend.click()
            send.assert_called_once()

    def test_modifier_held_skips_click(self):
        with patch.object(win, "GetAsyncKeyState", return_value=0x8000), patch.object(win, "SendInput") as send:
            with self.assertRaises(RuntimeError):
                self.backend.click()
            send.assert_not_called()

    def test_disconnected_monitor_skips_click(self):
        with patch.object(win, "MonitorFromPoint", return_value=None), patch.object(win, "SendInput") as send:
            with self.assertRaises(ValueError):
                self.backend.click((5000, 100))
            send.assert_not_called()

    def test_locked_desktop_skips_click(self):
        with patch.object(self.backend, "_check_desktop", side_effect=RuntimeError("locked")), patch.object(win, "SendInput") as send:
            with self.assertRaises(RuntimeError):
                self.backend.click()
            send.assert_not_called()

    def test_own_window_cannot_restart_a_test(self):
        with patch.object(self.backend, "_check_target", side_effect=RuntimeError("own window")), patch.object(win, "SendInput") as send:
            with self.assertRaises(RuntimeError):
                self.backend.click()
            send.assert_not_called()

    def test_own_window_detection(self):
        def owner(hwnd, output):
            ct.cast(output, ct.POINTER(win.wt.DWORD)).contents.value = win.os.getpid()
            return 1
        with patch.object(win, "WindowFromPoint", return_value=123), patch.object(win, "GetWindowThreadProcessId", side_effect=owner):
            with self.assertRaises(RuntimeError):
                win.WindowsBackend._check_target(self.backend, (50, 80))


class EnterInputTests(unittest.TestCase):
    def setUp(self):
        self.backend = win.WindowsBackend()
        self.patches = [patch.object(self.backend, "_check_desktop"),
                        patch.object(win, "GetAsyncKeyState", return_value=0),
                        patch.object(win, "GetForegroundWindow", return_value=123),
                        patch.object(win, "GetWindowThreadProcessId", side_effect=self.foreign_owner)]
        for p in self.patches:
            p.start()

    @staticmethod
    def foreign_owner(window, output):
        ct.cast(output, ct.POINTER(win.wt.DWORD)).contents.value = win.os.getpid() + 1
        return 1

    def tearDown(self):
        for p in reversed(self.patches):
            p.stop()

    def test_enter_down_up_no_mouse_input(self):
        with patch.object(win, "SendInput", return_value=2) as send, patch.object(win, "SetCursorPos") as move, patch.object(win, "GetCursorPos") as cursor:
            self.backend.press_enter()
            send.assert_called_once()
            count, events, size = send.call_args.args
            self.assertEqual(count, 2)
            self.assertEqual([e.type for e in events], [1, 1])
            self.assertEqual([e.ki.wVk for e in events], [13, 13])
            self.assertEqual([e.ki.dwFlags for e in events], [0, 2])
            self.assertEqual(size, ct.sizeof(win.INPUT))
            move.assert_not_called()
            cursor.assert_not_called()

    def test_enter_partial_injection_releases_only(self):
        with patch.object(win, "SendInput", side_effect=[1, 1]) as send:
            with self.assertRaises(RuntimeError):
                self.backend.press_enter()
            self.assertEqual(send.call_count, 2)
            release = ct.cast(send.call_args.args[1], ct.POINTER(win.INPUT)).contents
            self.assertEqual((release.type, release.ki.wVk, release.ki.dwFlags), (1, 13, 2))

    def test_enter_blocked_no_retry(self):
        with patch.object(win, "SendInput", return_value=0) as send:
            with self.assertRaises(RuntimeError):
                self.backend.press_enter()
            send.assert_called_once()

    def test_held_enter_or_modifiers_skip_input(self):
        for held in (13, 16, 17, 18, 91, 92):
            with patch.object(win, "GetAsyncKeyState", side_effect=lambda key: 0x8000 if key == held else 0), patch.object(win, "SendInput") as send:
                with self.assertRaises(RuntimeError):
                    self.backend.press_enter()
                send.assert_not_called()

    def test_own_foreground_window_rejected(self):
        def own(window, output):
            ct.cast(output, ct.POINTER(win.wt.DWORD)).contents.value = win.os.getpid()
            return 1
        with patch.object(win, "GetWindowThreadProcessId", side_effect=own), patch.object(win, "SendInput") as send:
            with self.assertRaises(RuntimeError):
                self.backend.press_enter()
            send.assert_not_called()

    def test_no_foreground_window_rejected(self):
        with patch.object(win, "GetForegroundWindow", return_value=None), patch.object(win, "SendInput") as send:
            with self.assertRaises(RuntimeError):
                self.backend.press_enter()
            send.assert_not_called()

    def test_secure_desktop_rejected(self):
        with patch.object(self.backend, "_check_desktop", side_effect=RuntimeError("locked")), patch.object(win, "SendInput") as send:
            with self.assertRaises(RuntimeError):
                self.backend.press_enter()
            send.assert_not_called()


class NativeLifecycleTests(unittest.TestCase):
    def test_mutex_prevents_duplicate_instance(self):
        # Exercise native exclusion without conflicting with a user's armed copy.
        create_mutex = win.CreateMutex
        def isolated_mutex(attributes, owner, name):
            return create_mutex(attributes, owner, name + f".Test.{win.os.getpid()}")
        with patch.object(win, "CreateMutex", side_effect=isolated_mutex):
            mutex = win.SingleInstance()
            try:
                with self.assertRaises(RuntimeError):
                    win.SingleInstance()
            finally:
                mutex.close()

    def test_real_hotkey_message_loop_without_keyboard_injection(self):
        cancelled, captured = threading.Event(), threading.Event()
        errors = []
        # Use Ctrl+Alt+Shift+F9/F10 only within this test so Ctrl+Alt+X/S remain
        # registered to the user's live utility throughout a build.
        register = win.RegisterHotKey
        with patch.object(win, "RegisterHotKey", side_effect=lambda hwnd, ident, mods, key:
                          register(hwnd, ident, 0x4007, 0x78 if ident == 1 else 0x79)):
            keys = win.Hotkeys(cancelled.set, captured.set, errors.append)
        try:
            self.assertTrue(win.PostThreadMessage(keys.thread_id, 0x0312, 1, 0))
            self.assertTrue(cancelled.wait(2))
            if keys.capture_available:
                self.assertTrue(win.PostThreadMessage(keys.thread_id, 0x0312, 2, 0))
                self.assertTrue(captured.wait(2))
            self.assertEqual(errors, [])
        finally:
            keys.close()
        self.assertFalse(keys.thread.is_alive())

    def test_real_power_request_lifecycle(self):
        backend = win.WindowsBackend()
        try:
            backend.keep_awake(True)
        finally:
            backend.keep_awake(False)
