---
description: 查看或修改 Purrge 设置，如阈值、检查频率、删除方式
argument-hint: "[thresholdGB 20 | intervalMinutes 60 | optionalAction delete]"
allowed-tools: Bash(bash "${CLAUDE_PLUGIN_ROOT}/runtime/bin/purrge" *)
---
用户参数：$ARGUMENTS

- 没有参数：执行 `bash "${CLAUDE_PLUGIN_ROOT}/runtime/bin/purrge" config`，用中文表格说明每项设置的含义和当前值。
- 有参数：把用户的意思翻译成 `config <键> <值>` 再执行。可改的键：thresholdGB（阈值，GB）、intervalMinutes（检查间隔，分钟）、cooldownHours（提醒冷却，小时）、optionalAction（trash 移到废纸篓 / delete 直接删除）。例如"阈值改成 20G" → `config thresholdGB 20`。

执行后用一句话确认改了什么。
