import logging
import sys
import tempfile
import time
import tkinter as tk
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import app as application
from storage import DEFAULTS
from test_core import FakeBackend, wait_until


class FakeHotkeys:
    capture_available = True
    def __init__(self, *args):
        pass
    def close(self):
        pass


class GuiTests(unittest.TestCase):
    def setUp(self):
        self.root = tk.Tk()
        self.root.withdraw()
        self.backend = FakeBackend()
        self.patches = [patch.object(application, "load_settings", return_value=(DEFAULTS.copy(), None)),
                        patch.object(application, "save_settings")]
        for p in self.patches:
            p.start()
        self.app = application.App(self.root, logging.getLogger("gui-test"), self.backend, FakeHotkeys)

    def tearDown(self):
        self.app.close()
        for p in reversed(self.patches):
            p.stop()

    def test_starts_disarmed(self):
        self.assertIsNone(self.app.scheduler.job)
        self.assertEqual(self.app.banner.cget("text"), "DISARMED")

    def test_toggle_format_preserves_time(self):
        self.app.time_text.set("09:15:00")
        self.app.period.set("PM")
        self.app.clock_format.set("24")
        self.app.change_format()
        self.assertEqual(self.app.time_text.get(), "21:15:00")
        self.app.clock_format.set("12")
        self.app.change_format()
        self.assertEqual(self.app.time_text.get(), "09:15:00")
        self.assertEqual(self.app.period.get(), "PM")

    def test_test_button_ten_seconds_and_cancel(self):
        now = time.time()
        self.app.test_click()
        job = self.app.scheduler.job
        self.assertTrue(job.test)
        self.assertAlmostEqual(job.target - now, 10, delta=0.2)
        self.assertIn("TEST ARMED", self.app.banner.cget("text"))
        self.assertEqual(str(self.app.arm_button.cget("state")), "disabled")
        self.app.cancel()
        self.assertIsNone(self.app.scheduler.job)
        self.assertEqual(self.backend.clicks, [])

    def test_emergency_cancels_without_ui_pump(self):
        self.app.test_click()
        self.app.emergency_cancel()
        self.assertIsNone(self.app.scheduler.job)

    def test_confirmation_no_does_not_arm(self):
        with patch.object(application.messagebox, "askyesno", return_value=False) as confirm:
            self.app.arm()
            confirm.assert_called_once()
        self.assertIsNone(self.app.scheduler.job)

    def test_emergency_stop_during_confirmation_prevents_arm(self):
        def confirm(*args, **kwargs):
            self.app.emergency_cancel()
            return True
        with patch.object(application.messagebox, "askyesno", side_effect=confirm):
            self.app.arm()
        self.assertIsNone(self.app.scheduler.job)

    def test_past_time_confirmation_explicitly_offers_tomorrow(self):
        from datetime import datetime
        self.app.time_text.set("00:00:00")
        self.app.clock_format.set("24")
        with patch.object(application, "datetime") as dt, patch.object(application.messagebox, "askyesno", return_value=False) as confirm:
            dt.now.return_value = datetime(2026, 10, 3, 10)
            self.app.arm()
            self.assertIn("tomorrow", confirm.call_args.args[1])
            self.assertIn("October 4, 2026", confirm.call_args.args[1])
        self.assertIsNone(self.app.scheduler.job)

    def test_saved_mode_requires_coordinates(self):
        self.app.mode.set("saved")
        with patch.object(application.messagebox, "showerror") as error:
            self.app.test_click()
            error.assert_called_once()
        self.assertIsNone(self.app.scheduler.job)

    def test_hotkey_captures_and_displays_position(self):
        self.app.hotkey_capture()
        self.app._handle_events()
        self.app._update_state()
        self.assertEqual(self.app.saved_position, [100, 200])
        self.assertIn("X=100", self.app.position_text.get())

    def test_simulated_test_completion_returns_disarmed(self):
        self.app.test_click()
        target = self.app.scheduler.job.target
        self.app.scheduler.clock = lambda: target + .01
        self.app.scheduler.wake()
        deadline = time.monotonic() + 2
        while self.app.scheduler.job and time.monotonic() < deadline:
            time.sleep(.005)
        self.app._handle_events()
        self.app._update_state()
        self.assertEqual(self.backend.clicks, [None])
        self.assertEqual(self.app.banner.cget("text"), "DISARMED")
        self.assertIn("Test click sent", self.app.detail.get())

    def test_enter_ui_disables_mouse_controls_and_updates_test_button(self):
        self.app.action.set("enter")
        self.app._update_state()
        self.assertEqual(self.app.test_button.cget("text"), "TEST ENTER IN 10 SECONDS")
        self.assertEqual(str(self.app.saved_radio.cget("state")), "disabled")
        self.assertIn("keyboard focus", self.app.mode_text.get())
        self.app.action.set("click")
        self.app._update_state()
        self.assertEqual(str(self.app.saved_radio.cget("state")), "normal")

    def test_enter_test_ignores_saved_position_and_completes(self):
        self.app.mode.set("saved")
        self.app.action.set("enter")
        self.app.test_click()
        job = self.app.scheduler.job
        self.assertIsNone(job.position)
        self.assertEqual(job.action, "enter")
        self.assertIn("ONE ENTER", self.app.banner.cget("text"))
        self.assertEqual(str(self.app.click_action.cget("state")), "disabled")
        self.app.scheduler.clock = lambda: job.target + .01
        self.app.scheduler.wake()
        wait_until(lambda: self.app.scheduler.job is None)
        self.app._handle_events()
        self.app._update_state()
        self.assertEqual(self.backend.enter_presses, 1)
        self.assertEqual(self.backend.clicks, [])
        self.assertIn("Test Enter sent once", self.app.detail.get())
        self.assertEqual(self.app.banner.cget("text"), "DISARMED")

    def test_enter_confirmation_describes_action_and_focus(self):
        self.app.action.set("enter")
        with patch.object(application.messagebox, "askyesno", return_value=False) as confirm:
            self.app.arm()
        self.assertIn("ENTER KEY once", confirm.call_args.args[1])
        self.assertIn("foreground application", confirm.call_args.args[1])

    def test_enter_emergency_cancel(self):
        self.app.action.set("enter")
        self.app.test_click()
        self.app.emergency_cancel()
        self.assertIsNone(self.app.scheduler.job)
        self.assertEqual(self.backend.enter_presses, 0)
