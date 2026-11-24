# Releasing Timed LMB Trigger

This guide is for the repository maintainer.

## Before the first public release

1. `LICENSE` is filled in (MIT, © 2026 Timed LMB Trigger contributors). Update the year range for later releases if you like.
2. Do **not** publish the old `dist\TimedLMBTrigger.exe` that may be on your PC from
   before 2026-11-24. It was built with a temporary folder hard-coded to
   `G:/TimedLMBTrigger/work`, so it can fail on other computers. Use the automated
   build below (or rebuild with the current `build.bat`).
3. Confirm the `.gitignore` is in place so `config/`, `logs/`, `work/`, `build/`,
   `dist/`, `.build-venv/` and `VERIFICATION.md` are not committed.

## Option A — automatic release (recommended)

1. Update `CHANGELOG.md` with the new version and date, and commit it.
2. Create and push a tag that starts with `v`:
   - **GitHub Desktop:** *History* tab → right-click the latest commit → *Create Tag…*
     → enter `v1.0.0` → *Create Tag* → *Push origin*.
   - **Command line:** `git tag v1.0.0` then `git push origin v1.0.0`.
3. Open the repository's **Actions** tab and wait for *Build Windows release* to finish
   (about 2–4 minutes).
4. The **Releases** page now has `TimedLMBTrigger-v1.0.0-windows-x64.zip` and its
   `.sha256` file. Edit the release notes if you like.

To try a build without publishing, open **Actions → Build Windows release → Run
workflow**. The ZIP appears as a downloadable artifact on that run.

## Option B — build on your own PC

1. Install 64-bit Python 3.11+ from python.org (with the Python Launcher).
2. In the project folder run: `release.bat 1.0.0`
3. Upload `release\TimedLMBTrigger-v1.0.0-windows-x64.zip` and its `.sha256` file to a
   new release at **Releases → Draft a new release**, with tag `v1.0.0`.

## What goes into the release ZIP

| File | Why |
| --- | --- |
| `TimedLMBTrigger.exe` | The standalone app (includes its own Python runtime). |
| `README.md`, `CHANGELOG.md` | Instructions and changes. |
| `LICENSE` | License for this project's original code. |
| `THIRD-PARTY-NOTICES.md`, `licenses/` | Python, Tcl/Tk and PyInstaller license texts, collected by `tools/collect_licenses.py` from the interpreter that built the EXE. |

## Code signing (optional)

The EXE is unsigned, so Windows SmartScreen will warn first-time users. Warnings fade as
a release gains downloads. To remove them, sign the EXE with a code-signing certificate.
Never commit certificate files (`*.pfx`, `*.p12`) or their passwords; the `.gitignore`
already excludes them. Store them as encrypted GitHub Actions secrets instead.
