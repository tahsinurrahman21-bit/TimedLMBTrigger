@echo off
rem Build a GitHub Release ZIP on this PC: release.bat 1.0.0
setlocal
set "PROJECT_ROOT=%~dp0"
cd /d "%PROJECT_ROOT%" || exit /b 1
set "VERSION=%~1"
if "%VERSION%"=="" (
    echo Usage: release.bat VERSION   e.g.  release.bat 1.0.0
    exit /b 1
)
call build.bat || exit /b 1
set "NAME=TimedLMBTrigger-v%VERSION%-windows-x64"
set "STAGE=%PROJECT_ROOT%release\%NAME%"
if exist "%STAGE%" rmdir /s /q "%STAGE%"
mkdir "%STAGE%" || exit /b 1
copy /y "dist\TimedLMBTrigger.exe" "%STAGE%\" >nul || exit /b 1
copy /y "README.md" "%STAGE%\" >nul
copy /y "LICENSE" "%STAGE%\" >nul
copy /y "THIRD-PARTY-NOTICES.md" "%STAGE%\" >nul
copy /y "CHANGELOG.md" "%STAGE%\" >nul
".build-venv\Scripts\python.exe" "tools\collect_licenses.py" "%STAGE%\licenses" || exit /b 1
powershell -NoProfile -Command "Compress-Archive -Path '%STAGE%\*' -DestinationPath 'release\%NAME%.zip' -Force; (Get-FileHash 'release\%NAME%.zip' -Algorithm SHA256).Hash + '  %NAME%.zip' | Out-File -Encoding ascii 'release\%NAME%.zip.sha256'" || exit /b 1
echo.
echo Created release\%NAME%.zip and release\%NAME%.zip.sha256
echo Upload both files to a new GitHub Release tagged v%VERSION%.
exit /b 0
