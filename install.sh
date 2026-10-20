#!/bin/bash
# Purrge 一键安装（不用 Claude Code 插件时）：bash install.sh [阈值GB]
set -e
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
[ "$(uname)" = "Darwin" ] || { echo "Purrge 目前只支持 macOS"; exit 1; }
bash "$DIR/runtime/bin/purrge" setup --threshold "${1:-15}"
echo
echo "安装完成。常用命令（也可加到 PATH：ln -s ~/.purrge/app/bin/purrge /usr/local/bin/）："
echo "  ~/.purrge/app/bin/purrge run       立即扫描并打开审查页面"
echo "  ~/.purrge/app/bin/purrge status    查看状态"
echo "  ~/.purrge/app/bin/purrge config thresholdGB 20   修改阈值"
echo "  ~/.purrge/app/bin/purrge uninstall 卸载后台监控"
