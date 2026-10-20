---
description: 立即扫描可清理的内容，AI 逐项判断后打开审查页面（勾选确认后才会清理）
allowed-tools: Bash(bash "${CLAUDE_PLUGIN_ROOT}/runtime/bin/purrge" *)
---
用 Bash 工具执行：

```bash
bash "${CLAUDE_PLUGIN_ROOT}/runtime/bin/purrge" run --background
```

然后用中文告诉用户：扫描已在后台开始，大约 1 分钟后浏览器会自动打开审查页面；页面里"首要清理"是可再生缓存（默认勾选），"需要你决定"是用户文件等（默认不选），点「确认清理」之前不会删除任何东西。不要自己去删除任何文件。
