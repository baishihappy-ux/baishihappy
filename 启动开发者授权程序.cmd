@echo off
setlocal
cd /d "%~dp0"
if not exist "%~dp0tools\developer_authorizer.py" (
  echo ERROR: Current authorizer source is missing: %~dp0tools\developer_authorizer.py
  pause
  exit /b 1
)
python -B "%~dp0tools\developer_authorizer.py"
if errorlevel 1 pause
endlocal
