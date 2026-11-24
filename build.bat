@echo off
setlocal
set "PROJECT_ROOT=%~dp0"
cd /d "%PROJECT_ROOT%" || exit /b 1
if not exist "work" mkdir "work"
set "TEMP=%PROJECT_ROOT%work"
set "TMP=%PROJECT_ROOT%work"
set "PIP_CACHE_DIR=%PROJECT_ROOT%work\pip-cache"
set "PYINSTALLER_CONFIG_DIR=%PROJECT_ROOT%work\pyinstaller-cache"
set "PYTHONPYCACHEPREFIX=%PROJECT_ROOT%work\pycache"
if exist ".build-venv\Scripts\python.exe" goto dependencies
py -3.11 -m venv ".build-venv"
if errorlevel 1 python -m venv ".build-venv"
if errorlevel 1 goto failed
:dependencies
".build-venv\Scripts\python.exe" -m pip install -r "requirements-build.txt"
if errorlevel 1 goto failed
".build-venv\Scripts\python.exe" -m unittest discover -s tests -v
if errorlevel 1 goto failed
".build-venv\Scripts\python.exe" -m PyInstaller --noconfirm --clean --onefile --windowed --noupx --name TimedLMBTrigger --distpath "%PROJECT_ROOT%dist" --workpath "%PROJECT_ROOT%build\pyinstaller" --specpath "%PROJECT_ROOT%build" "src\app.py"
if errorlevel 1 goto failed
echo Built dist\TimedLMBTrigger.exe
exit /b 0
:failed
echo Build failed. Read the error above. Python 3.11 or newer with Tkinter is required.
exit /b 1
