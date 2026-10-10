#!/bin/sh
set -eu
export PYTHONUTF8=1
export PYTHONIOENCODING=utf-8
root=$(CDPATH= cd "$(dirname "$0")" && pwd)
for candidate in python3 python; do
  if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -c 'import sys;sys.exit(0 if sys.version_info >= (3,10) else 1)' >/dev/null 2>&1; then
    exec "$candidate" "$root/try_demo.py" "$@"
  fi
done
printf '%s\n' '未找到Python 3.10或以上。请安装后重试。' >&2
exit 2
