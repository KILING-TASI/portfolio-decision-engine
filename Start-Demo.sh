#!/bin/sh
set -eu
cd "$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
if ! command -v python3 >/dev/null 2>&1; then
  printf "%s\n" "需要 Python 3；按 README 安装后重试。" >&2
  exit 2
fi
exec python3 try_demo.py "$@"
