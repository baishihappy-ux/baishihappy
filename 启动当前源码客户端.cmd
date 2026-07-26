@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"

if not exist "%~dp0electron\main.js" (
  echo ERROR: Current client source is missing: %~dp0electron\main.js
  pause
  exit /b 1
)
set "DEV_ELECTRON_ROOT=%~dp0electron"
set "DEV_ELECTRON_CMD=%~dp0electron\node_modules\.bin\electron.cmd"
set "DEV_ELECTRON_RESOURCES=%~dp0electron\node_modules\electron\dist\resources"

if not exist "%DEV_ELECTRON_CMD%" (
  echo ERROR: Restored Electron development runtime is missing.
  echo Run 恢复生产环境.cmd first.
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
set "DINGFENG_RUNTIME_ROOT=%~dp0.recovery\development-runtime"
set "PYTHON_EXECUTABLE=%~dp0.recovery\venv\Scripts\python.exe"

if not exist "%PYTHON_EXECUTABLE%" (
  echo ERROR: Restored Python environment is missing.
  echo Run 恢复生产环境.cmd first.
  pause
  exit /b 1
)

call "%DEV_ELECTRON_CMD%" "%~dp0electron\main.js"
if errorlevel 1 pause
endlocal
