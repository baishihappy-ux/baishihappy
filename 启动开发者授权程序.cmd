@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
if not exist "%~dp0tools\developer_authorizer.py" (
  echo ERROR: Current authorizer source is missing: %~dp0tools\developer_authorizer.py
  pause
  exit /b 1
)
set "PYTHON_EXE=%~dp0.recovery\venv\Scripts\python.exe"
if not exist "%PYTHON_EXE%" (
  echo ERROR: Restored Python environment is missing.
  echo Run 恢复生产环境.cmd first.
  pause
  exit /b 1
)
"%PYTHON_EXE%" -B "%~dp0tools\developer_authorizer.py"
if errorlevel 1 pause
endlocal
