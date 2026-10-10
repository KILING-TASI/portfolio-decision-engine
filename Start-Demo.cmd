@echo off
chcp 65001 >nul
setlocal
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
cd /d "%~dp0"
py -3 -c "import sys;sys.exit(0 if sys.version_info >= (3,10) else 1)" >nul 2>nul
if not errorlevel 1 (
  py -3 "%~dp0try_demo.py" %*
  goto :done
)
python -c "import sys;sys.exit(0 if sys.version_info >= (3,10) else 1)" >nul 2>nul
if not errorlevel 1 (
  python "%~dp0try_demo.py" %*
  goto :done
)
echo 未找到Python 3.10或以上。请先安装Python，再运行本入口。
exit /b 2

:done
exit /b %errorlevel%
