import logging
import queue
import sys
import tempfile
import threading
import time
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from core import Job, Scheduler, next_trigger, parse_time
from storage import DEFAULTS, load_settings, save_settings


class FakeBackend:
    def __init__(self):
        self.clicks = []
        self.power = []
        self.fail_click = False
        self.fail_power = False
        self.enter_presses = 0
        self.fail_enter = False

    def press_enter(self):
        self.enter_presses += 1
        if self.fail_enter:
            raise OSError("keyboard input blocked")

    def click(self, position):
        self.clicks.append(position)
        if self.fail_click:
            raise OSError("blocked")
        return position or (100, 200)

    def keep_awake(self, state):
        self.power.append((state, threading.get_ident()))
        if self.fail_power:
            raise OSError("power request failed")

    def position(self):
        return (100, 200)

    def validate_position(self, position):
        pass


def wait_until(predicate, timeout=2):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.005)
    raise AssertionError("Condition did not become true")


class TimeTests(unittest.TestCase):
    def test_12_hour_boundaries(self):
        self.assertEqual(parse_time("12:00:00", "12", "AM"), (0, 0, 0))
        self.assertEqual(parse_time("12:00:00", "12", "PM"), (12, 0, 0))
        self.assertEqual(parse_time("09:01:02", "12", "PM"), (21, 1, 2))

    def test_24_hour_boundaries(self):
        self.assertEqual(parse_time("00:00:00", "24"), (0, 0, 0))
        self.assertEqual(parse_time("23:59:59", "24"), (23, 59, 59))

    def test_invalid_input(self):
        for text, fmt in (("24:00:00", "24"), ("00:00:00", "12"), ("13:00:00", "12"),
                          ("9:60:00", "12"), ("9:00:60", "12"), ("9:00", "12"),
                          ("x:00:00", "24"), ("-1:00:00", "24")):
            with self.subTest(text=text), self.assertRaises(ValueError):
                parse_time(text, fmt)

    def test_next_today(self):
        self.assertEqual(next_trigger(datetime(2026, 10, 3, 8), (9, 0, 0)),
                         (datetime(2026, 10, 3, 9), False))

    def test_passed_or_equal_requires_tomorrow(self):
        for hour in (9, 10):
            self.assertEqual(next_trigger(datetime(2026, 10, 3, hour), (9, 0, 0)),
                             (datetime(2026, 10, 4, 9), True))

    def test_midnight_year_rollover(self):
        self.assertEqual(next_trigger(datetime(2026, 12, 31, 23, 59), (0, 0, 0)),
                         (datetime(2027, 1, 1), True))


class SchedulerTests(unittest.TestCase):
    def setUp(self):
        self.now = 1000.0
        self.backend = FakeBackend()
        self.events = queue.Queue()
        self.scheduler = Scheduler(self.backend, lambda k, d: self.events.put((k, d)), lambda: self.now)

    def tearDown(self):
        self.scheduler.close()

    def advance(self, stamp):
        self.now = stamp
        self.scheduler.wake()

    def test_startup_disarmed(self):
        self.assertIsNone(self.scheduler.job)
        self.assertEqual(self.backend.clicks, [])

    def test_one_click_no_repeats(self):
        self.scheduler.arm(Job(1010))
        self.advance(1010)
        wait_until(lambda: len(self.backend.clicks) == 1)
        self.advance(1020)
        self.assertIsNone(self.scheduler.job)
        self.assertEqual(self.backend.clicks, [None])

    def test_duplicate_arm_rejected(self):
        self.scheduler.arm(Job(1010))
        with self.assertRaises(ValueError):
            self.scheduler.arm(Job(1011))

    def test_past_rejected(self):
        with self.assertRaises(ValueError):
            self.scheduler.arm(Job(1000))

    def test_cancel_then_rearm(self):
        self.scheduler.arm(Job(1010))
        self.assertTrue(self.scheduler.cancel())
        self.advance(1010)
        self.assertEqual(self.backend.clicks, [])
        self.scheduler.arm(Job(1020, (45, -20)))
        self.advance(1020)
        wait_until(lambda: self.backend.clicks == [(45, -20)])

    def test_clock_backwards_waits(self):
        self.scheduler.arm(Job(1010))
        self.advance(900)
        self.assertIsNotNone(self.scheduler.job)
        self.advance(1009)
        self.assertEqual(self.backend.clicks, [])
        self.advance(1010)
        wait_until(lambda: len(self.backend.clicks) == 1)

    def test_clock_forward_or_resume_misses(self):
        self.scheduler.arm(Job(1010))
        self.advance(2000)
        wait_until(lambda: self.scheduler.job is None)
        self.assertEqual(self.backend.clicks, [])
        kinds = []
        while not self.events.empty():
            kinds.append(self.events.get()[0])
        self.assertIn("MISSED", kinds)

    def test_short_delay_fires(self):
        self.scheduler.arm(Job(1010))
        self.advance(1010.2)
        wait_until(lambda: len(self.backend.clicks) == 1)

    def test_click_exception_never_retries(self):
        self.backend.fail_click = True
        self.scheduler.arm(Job(1010))
        self.advance(1010)
        wait_until(lambda: self.scheduler.job is None)
        self.advance(1011)
        self.assertEqual(len(self.backend.clicks), 1)

    def test_sleep_request_cleared_same_thread_on_cancel(self):
        self.scheduler.arm(Job(1010, keep_awake=True))
        wait_until(lambda: len(self.backend.power) == 1)
        self.scheduler.cancel()
        wait_until(lambda: len(self.backend.power) == 2)
        self.assertEqual([p[0] for p in self.backend.power], [True, False])
        self.assertEqual(self.backend.power[0][1], self.backend.power[1][1])

    def test_sleep_request_cleared_after_click_failure(self):
        self.backend.fail_click = True
        self.scheduler.arm(Job(1010, keep_awake=True))
        wait_until(lambda: len(self.backend.power) == 1)
        self.advance(1010)
        wait_until(lambda: len(self.backend.power) == 2)
        self.assertEqual([p[0] for p in self.backend.power], [True, False])

    def test_sleep_request_failure_disarms(self):
        self.backend.fail_power = True
        self.scheduler.arm(Job(1010, keep_awake=True))
        wait_until(lambda: not self.scheduler.worker.is_alive())
        self.assertIsNone(self.scheduler.job)
        self.assertEqual(self.backend.clicks, [])

    def test_close_disarms_and_clears_sleep(self):
        self.scheduler.arm(Job(1010, keep_awake=True))
        wait_until(lambda: len(self.backend.power) == 1)
        self.scheduler.close()
        self.assertIsNone(self.scheduler.job)
        self.assertFalse(self.scheduler.worker.is_alive())
        self.assertEqual([p[0] for p in self.backend.power], [True, False])

    def test_enter_once_without_mouse_click(self):
        self.scheduler.arm(Job(1010, action="enter"))
        self.advance(1010)
        wait_until(lambda: self.scheduler.job is None)
        self.advance(1020)
        self.assertEqual(self.backend.enter_presses, 1)
        self.assertEqual(self.backend.clicks, [])
        self.assertEqual([self.events.get()[0], self.events.get()[0]], ["ARMED", "ENTER"])

    def test_enter_cancel_does_not_press(self):
        self.scheduler.arm(Job(1010, action="enter"))
        self.scheduler.cancel()
        self.advance(1010)
        self.assertEqual(self.backend.enter_presses, 0)

    def test_missed_enter_does_not_press(self):
        self.scheduler.arm(Job(1010, action="enter"))
        self.advance(1100)
        wait_until(lambda: self.scheduler.job is None)
        self.assertEqual(self.backend.enter_presses, 0)

    def test_enter_failure_no_retry_and_power_cleared(self):
        self.backend.fail_enter = True
        self.scheduler.arm(Job(1010, keep_awake=True, action="enter"))
        wait_until(lambda: len(self.backend.power) == 1)
        self.advance(1010)
        wait_until(lambda: self.scheduler.job is None)
        self.advance(1011)
        self.assertEqual(self.backend.enter_presses, 1)
        self.assertEqual([p[0] for p in self.backend.power], [True, False])

    def test_invalid_action_or_enter_coordinates_rejected(self):
        for job in (Job(1010, action="other"), Job(1010, position=(1, 2), action="enter")):
            with self.assertRaises(ValueError):
                self.scheduler.arm(job)
        self.assertIsNone(self.scheduler.job)


class SettingsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1] / "work")
        self.path = Path(self.temp.name) / "settings.json"

    def tearDown(self):
        self.temp.cleanup()

    def test_roundtrip(self):
        values = dict(DEFAULTS, time="23:59:59", clock_format="24", saved_position=[-1200, 720], keep_awake=True)
        save_settings(values, self.path)
        self.assertEqual(load_settings(self.path), (values, None))
        self.assertFalse(self.path.with_suffix(".tmp").exists())

    def test_bad_settings_recover_disarmed(self):
        for value in ('{"time":"bad"}', '[1,2]', '{"saved_position":[true,2]}', '{broken'):
            self.path.write_text(value)
            settings, warning = load_settings(self.path)
            self.assertEqual(settings, DEFAULTS)
            self.assertIsNotNone(warning)

    def test_no_armed_state_persisted(self):
        self.path.write_text('{"armed":true}')
        values, _ = load_settings(self.path)
        self.assertNotIn("armed", values)

    def test_old_settings_default_to_click_and_enter_roundtrips(self):
        self.path.write_text('{"time":"09:00:00"}')
        self.assertEqual(load_settings(self.path)[0]["action"], "click")
        values = dict(DEFAULTS, action="enter")
        save_settings(values, self.path)
        self.assertEqual(load_settings(self.path), (values, None))
