# Timed LMB Trigger — Timed Enter Button & Mouse Clicker

Timed LMB Trigger is a small Windows **timed Enter button clicker** and **timed left mouse button clicker**. It schedules one Enter key press or one left mouse click for a time you choose. It shows a confirmation before arming, counts down to the selected local time, and provides an emergency cancel shortcut.

**Typical use:** you've typed a message into an AI chat app (or any other program) but have to wait until a certain time — for example, until your usage limit resets overnight. Leave the PC on, schedule an Enter press (or a click on the Send button) for that time, and the app presses it for you while you're away.

The app sends input to the current desktop. It does not choose or activate a target window, so you must leave the intended application ready and focused.

> **Quick start:** go to the [**latest release**](../../releases/latest), download `TimedLMBTrigger-vX.Y.Z-windows-x64.zip`, extract it, and double-click `TimedLMBTrigger.exe`. No Python or other installs are needed.

## Contents

- [Features](#features)
- [Windows requirements](#windows-requirements)
- [Install and run the ready-to-use app](#install-and-run-the-ready-to-use-app) (recommended for beginners)
- [Run from source](#run-from-source)
- [Schedule a trigger](#schedule-a-trigger)
- [Build the standalone executable](#build-the-standalone-executable)
- [Troubleshooting](#troubleshooting)
- [Limitations](#troubleshooting-details-and-limitations)
- [Local files and privacy](#local-files-and-privacy)
- [License](#license)

## Features

- Schedule one left click or one Enter key press for a selected time.
- Click at the cursor's current position, or save and use screen coordinates.
- Test either action after a 10-second countdown.
- Cancel with the app button or **Ctrl+Alt+X**.
- Capture a click position with **Ctrl+Alt+S** or the in-app countdown button.
- Optionally ask Windows to keep the PC awake while a trigger is armed.
- Save preferences and a rotating activity log locally. The app has no network service, account, or telemetry.

## Windows requirements

- Windows 10 or Windows 11 on a desktop session.
- A signed-in, unlocked Windows session while the trigger is due.
- For the ready-to-run executable: no Python installation is needed.
- For running from source or building the executable: 64-bit Python 3.11 or newer with Tkinter. The official Windows Python installer includes Tkinter.

The app does not need administrator privileges. Windows may block input to applications that are running as administrator.

## Install and run the ready-to-use app

This is the easiest option. You do not need Python, Git, or any programming tools.

1. Open the repository's [**Releases**](../../releases) page. Under the newest version, click **Assets**, then click `TimedLMBTrigger-vX.Y.Z-windows-x64.zip` to download it. (Don't download "Source code" — that is for developers.)
2. Open your **Downloads** folder, right-click the ZIP and choose **Extract All...**, then **Extract**.
3. Move the extracted folder somewhere you can write to, such as **Documents** or the **Desktop**. Avoid `Program Files`, which is normally protected from regular user changes.
4. Open the extracted folder and double-click `TimedLMBTrigger.exe`.
5. If a blue **"Windows protected your PC"** (SmartScreen) window appears, it is because the app is new and not code-signed. Click **More info**, check that the file name is `TimedLMBTrigger.exe`, then click **Run anyway**. Only do this for a file you downloaded from this repository's Releases page.

Optional: to confirm the download wasn't altered, compare it with the `.sha256` file published next to the ZIP. In PowerShell, run `Get-FileHash .\TimedLMBTrigger-vX.Y.Z-windows-x64.zip` and check that the hash matches.

To uninstall, close the app and delete its folder. It does not install anything elsewhere or change the registry.

The executable is built as a single-file Windows app and includes the Python runtime it needs. The app creates its `config`, `logs`, and `work` folders next to the executable. If Windows shows a warning because the executable is unsigned, verify that it came from the project's release page before deciding whether to run it.

## Run from source

1. Download the repository as a ZIP from GitHub and extract it. (Git is not required.)
2. If Python is not installed, install 64-bit Python 3.11 or newer from [python.org](https://www.python.org/downloads/windows/). Keep the Python Launcher option enabled. Tkinter is included with the standard Windows installer.
3. Open the extracted `TimedLMBTrigger` folder in File Explorer.
4. Double-click `run.bat`.

No application packages need to be installed with `pip` to run from source. If Windows cannot find Python, rerun the Python installer and enable the Python Launcher, then reopen `run.bat`.

The app creates `config`, `logs`, and `work` inside the extracted project folder. Those files stay on your computer and should not be uploaded to GitHub.

## Schedule a trigger

1. Enter a time as `HH:MM:SS`, such as `09:01:00`. Choose 12-hour time and AM/PM, or 24-hour time.
2. Choose **Left mouse click** or **Enter key**. For a click, select **Current cursor position** or **Saved position**. If you want Windows to prevent ordinary idle sleep, turn on **Keep PC awake while armed**.
3. Check the date and time shown under **Scheduled trigger**.
4. Press **ARM** and confirm the action and time. If today's time has already passed, the app asks whether to schedule it for tomorrow. Declining leaves the app disarmed.
5. Leave the app running until the trigger completes. The app's banner and title show when it is armed.

The app returns to **DISARMED** after one attempt. It never repeats a trigger automatically. Preferences are remembered, but armed triggers are not restored after closing or restarting Windows.

### Enter key

After confirming an Enter trigger, switch to the target application and focus the intended field or control. The app sends a single Enter key-down/key-up pair to whichever application has keyboard focus when the time arrives. It does not remember or activate a target window. A notification or application switch can change which control receives Enter.

For a safe check, choose **Enter key**, press **TEST ENTER IN 10 SECONDS**, and switch to a harmless target such as a blank text document. **Ctrl+Alt+X** cancels the test.

### Current cursor position

Select **Current cursor position**, arm the trigger, then put the cursor over the intended target. The app does not move it in this mode. Leave it there until the trigger fires.

### Saved position

Put the cursor over the intended target and press **Ctrl+Alt+S**, or press **Save position in 3 seconds** and move the cursor before the countdown ends. Check the displayed X and Y coordinates, then choose **Saved position**. The app moves the cursor to those coordinates and clicks once. It leaves the cursor there afterward.

Saved coordinates use physical screen pixels and can become incorrect if the monitor layout or display scaling changes. Save the position again after changing display settings. If **Ctrl+Alt+S** is already in use, the in-app save button remains available.

### Test, cancel, and emergency stop

The test button schedules one click or Enter press in 10 seconds without the normal confirmation dialog. Put the cursor over a harmless target for a click test, or focus a harmless target for an Enter test. **CANCEL / DISARM** and **Ctrl+Alt+X** cancel either test. Escape cancels when the Timed LMB Trigger window is focused.

Closing the app cancels a pending trigger. Cancellation cannot undo input that Windows has already accepted. The app requires **Ctrl+Alt+X** to be available; if another program has claimed it, the app reports the conflict and closes.

## Build the standalone executable

Building is only needed if you want to make your own executable. Install 64-bit Python 3.11 or newer with Tkinter, then double-click `build.bat`. The script creates a local build environment, installs the pinned PyInstaller build dependency, runs the included automated checks, and writes:

```text
dist\TimedLMBTrigger.exe
```

The first build needs an internet connection to download PyInstaller and its build dependencies. The finished app runs offline. The build process leaves generated files in `.build-venv`, `build`, `dist`, and `work`; these are excluded from Git.

PyInstaller builds the executable for the Windows architecture of the Python interpreter used to build it. To make a 64-bit Windows release, build with 64-bit Python. The executable is unsigned, so Windows may show a warning for an unfamiliar app.

### Running the tests

With Python installed, open a Command Prompt in the project folder and run:

```bat
py -3 -m unittest discover -s tests -v
```

The tests simulate Windows input; they do not click or type into other applications.

### Publishing a release (maintainers)

Releases are built automatically by GitHub Actions (`.github/workflows/release.yml`) on a clean Windows machine whenever a version tag such as `v1.0.0` is pushed. The workflow runs the tests, builds the EXE, bundles the upstream license files, and attaches a ZIP plus SHA-256 checksum to the release. To build a release ZIP locally instead, run `release.bat 1.0.0`. See [RELEASING.md](RELEASING.md) for step-by-step instructions.

## Troubleshooting

| Problem | What to check |
| --- | --- |
| `run.bat` cannot find Python | Install 64-bit Python 3.11 or newer with the Python Launcher and Tkinter, then reopen the batch file. |
| Build fails while installing PyInstaller | Check your internet connection, then run `build.bat` again. A source-only run does not require PyInstaller. |
| `Ctrl+Alt+X` is unavailable | Close the program using that shortcut and restart Timed LMB Trigger. The in-app cancel button works while the app is open. |
| No click or Enter is received | Keep Windows unlocked, leave the intended app in the foreground, and check whether it is running as administrator. Some applications reject synthetic input. |
| The click lands in the wrong place | The app does not inspect the target under the cursor. Check the current cursor or saved coordinates, display scaling, and monitor layout. |
| A trigger fires late or is marked missed | Keep the computer awake and the app running. Windows is not a real-time operating system, so the requested second cannot be guaranteed. |
| Settings or logs cannot be written | Move the source or executable to a folder your Windows account can modify. |

## Troubleshooting details and limitations

- The computer must be powered on and the app must remain running. The app cannot trigger while Windows is shut down, sleeping, hibernating, or restarting, and it does not restore jobs after reboot.
- Windows may delay input because of system load or desktop conditions. The scheduler rechecks the Windows clock while waiting. If a forward clock change or resume makes the trigger more than five seconds late, it reports a missed trigger and disarms without sending input. A backward clock change extends the wait.
- Times use the PC's local clock and time zone. Changing the time zone after arming changes the displayed local time for the same confirmed instant; cancel and arm again if needed. Nonexistent local times during a daylight-saving change are rejected. Avoid scheduling during the repeated hour if the distinction matters.
- The click goes to the window under the cursor at trigger time. Enter goes to the currently focused window. The app does not open, focus, restore, or inspect other windows, and it cannot verify that the target completed the intended task.
- Windows may block synthetic input to an elevated application or a program that rejects it. The app does not bypass these protections.
- The app refuses to send input from a locked or secure desktop, when its own window is the target, or when relevant mouse buttons or modifier keys are held. Failures disarm the trigger and are not retried.
- **Keep PC awake** requests that Windows prevent ordinary idle sleep while armed. It does not prevent shutdown, manually initiated sleep, lid-close sleep, screen locking, or the display turning off.
- Only one app instance can run in a Windows session. Remote desktop disconnects, switching sessions, and secure-screen prompts can interrupt delivery.

## Local files and privacy

| Path | Contents |
| --- | --- |
| `config/settings.json` | Remembered time and action preferences, keep-awake preference, and optional saved screen coordinates. |
| `logs/trigger.log` | Trigger, cancellation, error, and click-coordinate events. The log rotates after about 512 KB and retains two older files. |
| `work/` | Temporary files used by the launcher and build process. |
| `.build-venv/`, `build/`, `dist/` | Local Python build environment and generated build outputs. |

Settings and logs stay local. The app does not record screenshots, target window names, typed text, or account credentials. Keep the generated configuration and logs private; the repository's `.gitignore` excludes them.

## License

The original Timed LMB Trigger code is released under the [MIT License](LICENSE), © 2026 Timed LMB Trigger contributors.

Python, Tcl/Tk, PyInstaller, and Windows components are **not** part of this project's work and remain under their own licenses; see [THIRD-PARTY-NOTICES.md](THIRD-PARTY-NOTICES.md). Release ZIPs include their license texts in a `licenses` folder.
