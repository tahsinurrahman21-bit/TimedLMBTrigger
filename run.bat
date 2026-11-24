@echo off
setlocal
cd /d "%~dp0" || exit /b 1
if not exist "work" mkdir "work"
set "TEMP=%CD%\work"
set "TMP=%CD%\work"
if exist ".build-venv\Scripts\pythonw.exe" (
    start "" ".build-venv\Scripts\pythonw.exe" "src\app.py"
    exit /b 0
)
where pythonw >nul 2>nul
if not errorlevel 1 (
    start "" pythonw "src\app.py"
    exit /b 0
)
py -3 "src\app.py"
if errorlevel 1 pause
