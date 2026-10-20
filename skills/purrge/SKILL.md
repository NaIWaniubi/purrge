---
name: purrge
description: Purrge by RabbittuX，macOS 磁盘清理工具。用户说"磁盘空间不够/快满了""帮我清理磁盘/缓存""硬盘还剩多少""阈值改成 xxG""磁盘提醒"时使用：查看状态、扫描并打开 AI 审查页面、修改阈值。清理必须由用户在审查页面勾选确认，Claude 不直接删除文件。
allowed-tools: Bash(bash "${CLAUDE_PLUGIN_ROOT}/runtime/bin/purrge" *)
---
# Purrge by RabbittuX

命令入口：`bash "${CLAUDE_PLUGIN_ROOT}/runtime/bin/purrge" <子命令>`

| 用户意图 | 子命令 |
|---|---|
| 第一次使用 / 安装 / 开启提醒 | `setup --threshold <GB>`（默认 15） |
| 清理磁盘 / 空间不够 | `run --background`（扫描 + AI 判断 + 自动打开审查页面） |
| 还剩多少空间 / 监控状态 | `status` |
| 改阈值、频率、删除方式 | `config thresholdGB 20`、`config intervalMinutes 60`、`config optionalAction trash|delete` |
| 关掉提醒 / 卸载 | `uninstall`（`--purge` 连配置一起删） |

## 规则
- **绝不自己用 rm 等命令删除文件**。所有清理都必须经过审查页面，由用户勾选并点击「确认清理」。
- 用户问"这个能不能删"时，可以读 `~/.purrge/runs/<最新>/review.json` 里对应项的 tier 和 reason 来解释。
- 没有运行过 setup 时（`~/.purrge/config.json` 不存在），先引导用户运行 setup。
- 只支持 macOS。
