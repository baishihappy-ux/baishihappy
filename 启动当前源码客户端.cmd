@echo off
setlocal
cd /d "%~dp0"

if not exist "%~dp0electron\main.js" (
  echo ERROR: Current client source is missing: %~dp0electron\main.js
  pause
  exit /b 1
)
set "DEV_ELECTRON_ROOT=%~dp0.tmp_dev_electron"
set "DEV_ELECTRON_CMD=%~dp0.tmp_dev_electron\node_modules\.bin\electron.cmd"
set "DEV_ELECTRON_RESOURCES=%~dp0.tmp_dev_electron\node_modules\electron\dist\resources"

if not exist "%DEV_ELECTRON_CMD%" (
  echo ERROR: Clean Electron development runtime is missing.
  echo Run: npm.cmd install --prefix "%DEV_ELECTRON_ROOT%" --offline --no-audit --no-fund --save=false electron@31.7.7
  pause
  exit /b 1
)
if not exist "%DEV_ELECTRON_RESOURCES%\default_app.asar" (
  echo ERROR: Electron development runtime has no default_app.asar.
  pause
  exit /b 1
)
if exist "%DEV_ELECTRON_RESOURCES%\app.asar" (
  echo ERROR: Electron development runtime is contaminated by a packaged app.asar.
  pause
  exit /b 1
)
if not exist "%~dp0python\main.py" (
  echo ERROR: Current Python engine source is missing: %~dp0python\main.py
  pause
  exit /b 1
)

set "DINGFENG_HOME=%~dp0"
set "DINGFENG_RUNTIME_ROOT=%~dp0.tmp_dev_client\runtime"
set "PYTHON_EXECUTABLE=python"

call "%DEV_ELECTRON_CMD%" "%~dp0electron\main.js"
if errorlevel 1 pause
endlocal
