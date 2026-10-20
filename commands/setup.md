---
description: 一键安装 Purrge：设置阈值、注册后台监控（默认剩余低于 15GB 提醒）
argument-hint: "[阈值GB，如 20]"
allowed-tools: Bash(bash "${CLAUDE_PLUGIN_ROOT}/runtime/bin/purrge" *)
---
运行安装：

```bash
bash "${CLAUDE_PLUGIN_ROOT}/runtime/bin/purrge" setup --threshold <阈值>
```

参数：$ARGUMENTS 。把 <阈值> 换成用户给的数字（只取数字，单位 GB；没给就用 15），用 Bash 工具执行。根据输出的 JSON 用中文告诉用户：
1. 当前剩余空间、阈值、检查频率，后台监控已开启；
2. 如果 claude 显示"未找到"，说明 AI 判断会改用规则；
3. 如果 fullDiskAccess 是 false：说明部分系统缓存目录读不到，指导用户在「系统设置 → 隐私与安全性 → 完全磁盘访问权限」里给终端（或 python3）打开权限，这一步是可选的；
4. 最后问用户要不要现在就扫描一次（可以用 /purrge:scan）。
