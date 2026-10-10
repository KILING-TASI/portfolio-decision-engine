@echo off
cd /d "%~dp0"
where py >nul 2>nul
if not errorlevel 1 (
  py -3 "%~dp0try_demo.py"
) else (
  python "%~dp0try_demo.py"
)
if errorlevel 1 (
  echo Python or demo failed. See README and the message above.
  pause
)
