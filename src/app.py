"""Timed LMB Trigger: local Windows utility, standard library only."""
import math
import queue
import sys
import time
import traceback
from datetime import datetime
import tkinter as tk
from tkinter import ttk, messagebox

from core import Job, Scheduler, checked_timestamp, format_datetime, next_trigger, parse_time
from storage import ROOT, initialize, load_settings, save_settings
from windows_api import Hotkeys, SingleInstance, WindowsBackend, enable_dpi_awareness


class DisplayText(tk.StringVar):
    """Avoid Tcl variable traces and redraws when a displayed value is unchanged."""
    def set(self, value):
        if self.get() != value:
            super().set(value)


class App:
    def __init__(self, root, logger, backend=None, hotkeys_factory=Hotkeys):
        self.root, self.logger = root, logger
        self.backend = backend or WindowsBackend()
        self.events = queue.Queue()
        self.scheduler = Scheduler(self.backend, self.emit)
        self.hotkeys = None
        self.closed = False
        self.capture_until = None
        self.last_saved = None
        self.stop_generation = 0
        self._state_signature = None
        self._last_format = None
        self.settings, warning = load_settings()
        self.saved_position = self.settings["saved_position"]
        self.time_text = tk.StringVar(value=self.settings["time"])
        self.clock_format = tk.StringVar(value=self.settings["clock_format"])
        self._last_format = self.clock_format.get()
        self.period = tk.StringVar(value=self.settings["period"])
        self.mode = tk.StringVar(value=self.settings["click_mode"])
        self.action = tk.StringVar(value=self.settings["action"])
        self.awake = tk.BooleanVar(value=self.settings["keep_awake"])
        self.current = DisplayText()
        self.preview = DisplayText()
        self.position_text = DisplayText()
        self.countdown = DisplayText(value="--:--:--")
        self.detail = DisplayText(value="Choose a time, then ARM. No trigger is active.")
        self.mode_text = DisplayText()
        self._build()
        self.root.report_callback_exception = self._tk_exception
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.root.bind("<Escape>", lambda event: self.cancel())
        try:
            self.hotkeys = hotkeys_factory(self.emergency_cancel, self.hotkey_capture, self.hotkey_failure)
        except Exception:
            self.scheduler.close()
            raise
        if not self.hotkeys.capture_available:
            self.shortcut_label.config(text="Ctrl+Alt+X: emergency stop  |  Save shortcut unavailable; use the button")
        self.logger.info("START | Program started; DISARMED")
        if warning:
            self.logger.warning("ERROR | %s", warning)
            self.detail.set(warning)
        self._refresh()

    def _build(self):
        self.root.title("Timed LMB Trigger")
        self.root.configure(bg="#f3f5f8")
        self.root.resizable(False, False)
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TFrame", background="#f3f5f8")
        style.configure("TLabel", background="#f3f5f8", foreground="#172b42", font=("Segoe UI", 10))
        style.configure("TButton", font=("Segoe UI", 10), padding=(10, 7))
        style.configure("TRadiobutton", background="#f3f5f8", font=("Segoe UI", 10))
        style.configure("TCheckbutton", background="#f3f5f8", font=("Segoe UI", 10))
        body = ttk.Frame(self.root, padding=20)
        body.grid(sticky="nsew")
        ttk.Label(body, text="TIMED LMB TRIGGER", font=("Segoe UI", 19, "bold")).grid(row=0, sticky="w")
        ttk.Label(body, text="One scheduled click or Enter key. Entirely local.").grid(row=1, sticky="w", pady=(0, 12))
        self.banner = tk.Label(body, text="DISARMED", bg="#dfe7ef", fg="#263d53",
                               font=("Segoe UI", 17, "bold"), padx=12, pady=9)
        self.banner.grid(row=2, sticky="ew")
        ttk.Label(body, textvariable=self.current, font=("Segoe UI", 12)).grid(row=3, sticky="w", pady=(12, 10))
        ttk.Label(body, text="Trigger time").grid(row=4, sticky="w")
        time_row = ttk.Frame(body)
        time_row.grid(row=5, sticky="ew", pady=(4, 10))
        self.time_entry = ttk.Entry(time_row, textvariable=self.time_text, width=12, font=("Consolas", 16))
        self.time_entry.pack(side="left")
        self.period_box = ttk.Combobox(time_row, textvariable=self.period, values=("AM", "PM"), width=4, state="readonly")
        self.period_box.pack(side="left", padx=8)
        self.format_12 = ttk.Radiobutton(time_row, text="12-hour", variable=self.clock_format, value="12", command=self.change_format)
        self.format_12.pack(side="left", padx=5)
        self.format_24 = ttk.Radiobutton(time_row, text="24-hour", variable=self.clock_format, value="24", command=self.change_format)
        self.format_24.pack(side="left", padx=5)
        action_row = ttk.Frame(body)
        action_row.grid(row=6, sticky="w", pady=(0, 4))
        ttk.Label(action_row, text="Trigger:").pack(side="left", padx=(0, 12))
        self.click_action = ttk.Radiobutton(action_row, text="Left mouse click", variable=self.action,
                                            value="click", command=self._update_state)
        self.click_action.pack(side="left", padx=(0, 14))
        self.enter_action = ttk.Radiobutton(action_row, text="Enter key", variable=self.action,
                                            value="enter", command=self._update_state)
        self.enter_action.pack(side="left")
        self.current_radio = ttk.Radiobutton(body, text="Current cursor position (cursor stays where you leave it)",
                                            variable=self.mode, value="current")
        self.current_radio.grid(row=7, sticky="w", pady=(4, 2))
        self.saved_radio = ttk.Radiobutton(body, text="Saved position (moves cursor before clicking)", variable=self.mode, value="saved")
        self.saved_radio.grid(row=8, sticky="w")
        ttk.Label(body, textvariable=self.position_text).grid(row=9, sticky="w", pady=(6, 4))
        self.save_button = ttk.Button(body, text="Save position in 3 seconds", command=self.start_capture)
        self.save_button.grid(row=10, sticky="w")
        self.awake_check = ttk.Checkbutton(body, text="Keep PC awake while armed", variable=self.awake)
        self.awake_check.grid(row=11, sticky="w", pady=(12, 10))
        ttk.Separator(body).grid(row=12, sticky="ew")
        ttk.Label(body, text="Scheduled trigger (Windows local time)").grid(row=13, sticky="w", pady=(10, 3))
        ttk.Label(body, textvariable=self.preview, font=("Segoe UI", 11, "bold"), wraplength=510).grid(row=14, sticky="w")
        ttk.Label(body, textvariable=self.mode_text, wraplength=510).grid(row=15, sticky="w", pady=(4, 4))
        ttk.Label(body, textvariable=self.countdown, font=("Consolas", 29, "bold")).grid(row=16, sticky="w")
        buttons = ttk.Frame(body)
        buttons.grid(row=17, sticky="ew", pady=(7, 5))
        self.arm_button = ttk.Button(buttons, text="ARM", command=self.arm)
        self.arm_button.pack(side="left", fill="x", expand=True)
        self.cancel_button = ttk.Button(buttons, text="CANCEL / DISARM", command=self.cancel)
        self.cancel_button.pack(side="left", fill="x", expand=True, padx=(10, 0))
        self.test_button = ttk.Button(body, text="TEST CLICK IN 10 SECONDS", command=self.test_click)
        self.test_button.grid(row=18, sticky="ew", pady=(4, 8))
        ttk.Label(body, textvariable=self.detail, wraplength=510).grid(row=19, sticky="w")
        self.shortcut_label = ttk.Label(body, text="Ctrl+Alt+X: emergency stop  |  Ctrl+Alt+S: save cursor position", font=("Segoe UI", 9))
        self.shortcut_label.grid(row=20, sticky="w", pady=(10, 0))
        self.edit_controls = [self.time_entry, self.format_12, self.format_24, self.current_radio,
                              self.saved_radio, self.awake_check, self.save_button, self.arm_button, self.test_button,
                              self.click_action, self.enter_action]

    def emit(self, kind, detail):
        # Called from worker threads: Queue is the only bridge to the GUI.
        self.events.put((kind, detail))

    def emergency_cancel(self):
        self.stop_generation += 1
        self.scheduler.cancel("Emergency hotkey Ctrl+Alt+X")
        self.emit("STOP_CAPTURE", None)

    def hotkey_failure(self, detail):
        self.scheduler.cancel("Emergency hotkey listener failed")
        self.emit("HOTKEY_ERROR", detail)

    def hotkey_capture(self):
        if self.scheduler.job is None:
            try:
                self.emit("CAPTURE", self.backend.position())
            except Exception as exc:
                self.emit("ERROR", str(exc))

    def change_format(self):
        try:
            h, m, s = parse_time(self.time_text.get(), self._last_format, self.period.get())
            if self.clock_format.get() == "12":
                self.period.set("PM" if h >= 12 else "AM")
                h = h % 12 or 12
            self.time_text.set(f"{h:02}:{m:02}:{s:02}")
        except ValueError:
            pass
        self._last_format = self.clock_format.get()

    def preferences(self):
        parse_time(self.time_text.get(), self.clock_format.get(), self.period.get())
        return dict(time=self.time_text.get(), clock_format=self.clock_format.get(), period=self.period.get(),
                    click_mode=self.mode.get(), saved_position=self.saved_position, keep_awake=self.awake.get(),
                    action=self.action.get())

    def persist(self):
        values = self.preferences()
        if values != self.last_saved:
            save_settings(values)
            self.last_saved = values

    def selected_position(self):
        if self.action.get() == "enter":
            return None
        if self.mode.get() == "saved":
            if self.saved_position is None:
                raise ValueError("Save a cursor position before using Saved Position mode.")
            position = tuple(self.saved_position)
            self.backend.validate_position(position)
            return position
        return None

    def arm(self):
        if self.scheduler.job or self.capture_until:
            return
        try:
            hms = parse_time(self.time_text.get(), self.clock_format.get(), self.period.get())
            local_time, tomorrow = next_trigger(datetime.now(), hms)
            stamp = checked_timestamp(local_time)
            position = self.selected_position()
            action = self.action.get()
            mode = "Current cursor position" if position is None else f"Saved position: X={position[0]}, Y={position[1]}"
            if action == "enter":
                mode = "ENTER KEY once in the foreground application.\nSwitch to the intended application after arming."
            generation = self.stop_generation
            text = ("That time has passed today. Schedule it for tomorrow?\n\n" if tomorrow else
                    ("Arm one Enter key press?\n\n" if action == "enter" else "Arm one left click?\n\n"))
            text += f"{format_datetime(stamp)}\n\n{mode}\nKeep PC awake: {'Yes' if self.awake.get() else 'No'}\n\nCtrl+Alt+X cancels."
            if not messagebox.askyesno("Confirm scheduled trigger", text, parent=self.root, default="no"):
                return
            if generation != self.stop_generation:
                self.detail.set("DISARMED. Emergency stop cancelled the pending confirmation.")
                return
            self.persist()
            self.scheduler.arm(Job(stamp, position, self.awake.get(), action=action))
            self._update_state()
        except Exception as exc:
            self.show_error(str(exc))

    def test_click(self):
        if self.scheduler.job or self.capture_until:
            return
        try:
            position = self.selected_position()
            self.persist()
            self.scheduler.arm(Job(time.time() + 10, position, self.awake.get(), True, action=self.action.get()))
            self._update_state()
        except Exception as exc:
            self.show_error(str(exc))

    def cancel(self):
        self.capture_until = None
        if not self.scheduler.cancel():
            self.detail.set("DISARMED. No trigger is active.")
        self._update_state()

    def start_capture(self):
        if self.scheduler.job is None and self.action.get() == "click":
            self.capture_until = time.monotonic() + 3
            self.detail.set("Move the cursor to the intended button. Position will be saved in 3 seconds.")

    def show_error(self, detail):
        self.logger.error("ERROR | %s", detail)
        self.detail.set("DISARMED. " + detail)
        messagebox.showerror("Timed LMB Trigger", detail, parent=self.root)

    def _tk_exception(self, exc_type, value, tb):
        self.scheduler.cancel("Interface error")
        self.logger.error("ERROR | %s", "".join(traceback.format_exception(exc_type, value, tb)))
        self.show_error(str(value))

    def _handle_events(self):
        while True:
            try:
                kind, data = self.events.get_nowait()
            except queue.Empty:
                break
            if kind == "ARMED":
                mode = "current cursor" if data.position is None else f"saved X={data.position[0]} Y={data.position[1]}"
                if data.action == "enter":
                    mode = "ENTER key | foreground application"
                self.logger.info("ARMED | %sTrigger scheduled for %s | %s | keep awake=%s",
                                 "TEST | " if data.test else "", format_datetime(data.target), mode, data.keep_awake)
                if data.action == "enter":
                    self.detail.set("TEST: one Enter in 10 seconds. Switch to the target application now." if data.test else
                                    "ARMED for ENTER. Switch to the intended application and leave it focused.")
                else:
                    self.detail.set("TEST: one click in 10 seconds. Position your cursor now." if data.test else "ARMED. Leave the intended application ready for one click.")
            elif kind == "ENTER":
                lateness, test = data
                self.logger.info("ENTER | %sEnter key | SendInput accepted key down/up | lateness=%.3fs",
                                 "TEST | " if test else "", lateness)
                self.detail.set(f"DISARMED. {'Test Enter' if test else 'Enter'} sent once. No further input scheduled.")
            elif kind == "CLICK":
                (x, y), lateness, test = data
                self.logger.info("CLICK | %sLMB at X=%s Y=%s | SendInput accepted both events | lateness=%.3fs", "TEST | " if test else "", x, y, lateness)
                self.detail.set(f"DISARMED. {'Test click' if test else 'Click'} sent at X={x}, Y={y}. No further clicks scheduled.")
            elif kind in ("CANCELLED", "MISSED"):
                self.logger.info("%s | %s", kind, data)
                self.detail.set(f"DISARMED. {data}")
            elif kind == "CAPTURE" and self.scheduler.job is None and self.action.get() == "click":
                self.saved_position = list(data)
                self.capture_until = None
                self.detail.set(f"Saved position: X={data[0]}, Y={data[1]}. Select Saved position mode to use it.")
            elif kind == "STOP_CAPTURE":
                self.capture_until = None
            elif kind == "HOTKEY_ERROR":
                self.show_error("Emergency hotkey unavailable. Application will close. " + data)
                self.close()
                return
            elif kind == "ERROR":
                self.show_error(data)

    def _update_state(self):
        job = self.scheduler.job
        capturing = self.capture_until is not None
        action = job.action if job else self.action.get()
        signature = (job, capturing, self.clock_format.get(), action)
        if signature != self._state_signature:
            for control in self.edit_controls:
                control.configure(state="disabled" if job or capturing else "normal")
            for control in (self.current_radio, self.saved_radio, self.save_button):
                control.configure(state="disabled" if job or capturing or action == "enter" else "normal")
            self.test_button.configure(text="TEST ENTER IN 10 SECONDS" if action == "enter" else "TEST CLICK IN 10 SECONDS")
            self.period_box.configure(state="disabled" if job or capturing or self.clock_format.get() == "24" else "readonly")
            self.cancel_button.configure(state="normal" if job or capturing else "disabled")
            if job:
                label = ("TEST ARMED" if job.test else "ARMED") + (" — ONE ENTER" if action == "enter" else " — ONE CLICK")
                self.banner.config(text=label, bg="#a92816", fg="white")
                self.root.title(("TEST ARMED" if job.test else "ARMED") + " | Timed LMB Trigger")
            else:
                self.banner.config(text="DISARMED", bg="#dfe7ef", fg="#263d53")
                self.root.title("Timed LMB Trigger | DISARMED")
            self._state_signature = signature
        if job:
            remaining = max(0, math.ceil(job.target - time.time()))
            self.countdown.set(f"{remaining // 3600:02}:{remaining // 60 % 60:02}:{remaining % 60:02}")
            self.preview.set(format_datetime(job.target))
        else:
            self.countdown.set("--:--:--")
            try:
                candidate, tomorrow = next_trigger(datetime.now(), parse_time(self.time_text.get(), self.clock_format.get(), self.period.get()))
                self.preview.set(format_datetime(checked_timestamp(candidate)) + ("\nTomorrow — confirmation required" if tomorrow else "\nToday — not armed"))
            except ValueError as exc:
                self.preview.set(str(exc))
        self.position_text.set("Saved position: not set" if self.saved_position is None else f"Saved position: X={self.saved_position[0]}, Y={self.saved_position[1]}")
        position = job.position if job else (self.saved_position if self.mode.get() == "saved" else None)
        self.mode_text.set(f"Active mode: saved position X={position[0]}, Y={position[1]}" if position is not None else ("Active mode: saved position — not set" if self.mode.get() == "saved" else "Active mode: current cursor position"))
        if action == "enter":
            self.mode_text.set("Active action: ENTER KEY once\nTarget: whichever application has keyboard focus when it fires.")

    def _refresh(self):
        if self.closed:
            return
        self._handle_events()
        if self.closed:
            return
        self.current.set("Current time:  " + datetime.now().strftime("%I:%M:%S %p  |  %H:%M:%S"))
        if self.capture_until is not None:
            left = math.ceil(self.capture_until - time.monotonic())
            if left <= 0:
                self.capture_until = None
                self.hotkey_capture()
            else:
                text = f"Saving in {left}… move your cursor"
                if self.save_button.cget("text") != text:
                    self.save_button.config(text=text)
        elif self.save_button.cget("text") != "Save position in 3 seconds":
            self.save_button.config(text="Save position in 3 seconds")
        self._update_state()
        if self.scheduler.job is None:
            try:
                self.persist()
            except ValueError:
                pass  # An incomplete time entry is not saved.
            except OSError as exc:
                # Keep a visible error; arming also checks persistence and will fail.
                message = f"Could not save preferences: {exc}"
                if self.detail.get() != message:
                    self.logger.error("ERROR | %s", message)
                    self.detail.set(message)
        self.root.after(250, self._refresh)

    def close(self):
        if self.closed:
            return
        self.closed = True
        self.scheduler.close()
        if self.hotkeys:
            self.hotkeys.close()
        try:
            self.persist()
        except Exception as exc:
            self.logger.error("ERROR | Could not save settings on exit: %s", exc)
        self._handle_events()
        self.logger.info("STOP | Program closed; DISARMED")
        self.root.destroy()


def main():
    root = None
    instance = None
    app = None
    logger = None
    try:
        enable_dpi_awareness()
        instance = SingleInstance()
        logger = initialize()
        root = tk.Tk()
        app = App(root, logger)
        root.mainloop()
    except Exception as exc:
        if logger:
            logger.exception("ERROR | Startup or main loop failed")
        messagebox.showerror("Timed LMB Trigger", f"Could not run Timed LMB Trigger:\n\n{exc}\n\nData location: {ROOT}")
        return 1
    finally:
        if app and not app.closed:
            app.close()
        elif root:
            try:
                root.destroy()
            except tk.TclError:
                pass
        if instance:
            instance.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
