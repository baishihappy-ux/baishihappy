@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"

if not exist "%~dp0recovery\restore.ps1" (
  echo [失败] 缺少恢复主程序：recovery\restore.ps1
  pause
  exit /b 1
)

powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0recovery\restore.ps1" %*
set "RESTORE_EXIT=%ERRORLEVEL%"

if not "%RESTORE_EXIT%"=="0" (
  echo.
  echo [失败] 生产环境恢复未完成。请查看 .recovery\reports\恢复报告.txt
) else (
  echo.
  echo [完成] 生产环境恢复和能力验证已经完成。
)

if /I not "%~1"=="-NonInteractive" pause
exit /b %RESTORE_EXIT%
