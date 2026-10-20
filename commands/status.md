---
description: 查看当前磁盘剩余空间、阈值和后台监控状态
allowed-tools: Bash(bash "${CLAUDE_PLUGIN_ROOT}/runtime/bin/purrge" *)
---
用 Bash 工具执行 `bash "${CLAUDE_PLUGIN_ROOT}/runtime/bin/purrge" status`，用中文简要汇报：剩余空间 / 阈值 / 是否低于阈值 / 后台监控是否在运行 / 上次扫描时间。低于阈值时建议运行 /purrge:scan。
