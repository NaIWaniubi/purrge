#!/bin/bash
# Purrge 安装脚本：
#   curl -fsSL https://raw.githubusercontent.com/RabbittuX/purrge/master/install.sh | bash
#   或者 git clone 后运行：bash install.sh
# 可选参数：--engine claude|codex  --threshold 15  --yes
set -e
[ "$(uname)" = "Darwin" ] || { echo "Purrge 目前只支持 macOS"; exit 1; }

PY="$(command -v python3 || true)"
if [ -z "$PY" ] || ! "$PY" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)' 2>/dev/null; then
  echo "需要 python3（3.8 以上）。正在打开命令行工具安装窗口，装好后重新运行这条安装命令。"
  xcode-select --install 2>/dev/null || true
  exit 1
fi

SRC="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd || true)"
if [ ! -f "$SRC/runtime/lib/dg.py" ]; then          # 通过 curl 运行：下载最新代码
  TMP="$(mktemp -d)"
  trap 'rm -rf "$TMP"' EXIT
  echo "正在下载 Purrge…"
  curl -fsSL https://codeload.github.com/RabbittuX/purrge/tar.gz/refs/heads/master | tar -xz -C "$TMP"
  SRC="$(echo "$TMP"/purrge-*)"
fi

if [ -e /dev/tty ] && { : < /dev/tty; } 2>/dev/null; then
  "$PY" "$SRC/runtime/lib/dg.py" install "$@" < /dev/tty
else
  "$PY" "$SRC/runtime/lib/dg.py" install "$@"
fi
