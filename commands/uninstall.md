---
description: 卸载 Purrge 的后台监控（加 purge 同时删除配置和扫描记录）
argument-hint: "[purge]"
allowed-tools: Bash(bash "${CLAUDE_PLUGIN_ROOT}/runtime/bin/purrge" *)
---
用户参数：$ARGUMENTS 。如果包含 purge，执行 `bash "${CLAUDE_PLUGIN_ROOT}/runtime/bin/purrge" uninstall --purge`，否则执行 `bash "${CLAUDE_PLUGIN_ROOT}/runtime/bin/purrge" uninstall`。告诉用户结果；如需彻底移除插件本身，再运行 `/plugin uninstall purrge`。
