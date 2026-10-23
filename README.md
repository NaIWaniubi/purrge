<div align="center">

<img src="runtime/assets/icon-256.png" width="120" alt="Purrge">

# Purrge

**基于 AI 的磁盘空间管理工具（macOS / Windows）：低空间预警、智能识别可清理项、经用户审批后执行清理。**

<sub>名称取自 purr（猫咪呼噜）与 purge（清除）· by RabbittuX</sub>

<br>

<img src="https://img.shields.io/badge/macOS%20%7C%20Windows-1c1b22?style=flat-square" alt="macOS | Windows"> <img src="https://img.shields.io/badge/AI-Claude_Code_%7C_Codex_%7C_WorkBuddy_%7C_DeepSeek-f2a33a?style=flat-square" alt="AI 引擎"> <img src="https://img.shields.io/badge/License-PolyForm_Noncommercial-e5484d?style=flat-square" alt="License">

<br>

<img src="docs/screenshots/review.png" alt="Purrge 审查页" width="100%">

</div>

<br>

## ✨ 核心功能

<table>
<tr>
<td width="33%" valign="top">

**🔔 低空间预警**

后台服务定时检测磁盘剩余空间，低于设定阈值时发出提醒。检测过程不调用 AI，不消耗额度。

</td>
<td width="33%" valign="top">

**🧠 AI 智能分析**

调用本机的 Claude Code 或 Codex，对缓存、安装包、媒体文件及历史项目逐项评估，说明其用途、闲置时长及清理影响。

</td>
<td width="33%" valign="top">

**✅ 用户审批**

可重建的缓存默认选中，用户文件默认不选。仅执行用户勾选并确认的清理项，AI 不具备删除权限。

</td>
</tr>
</table>

## 📸 界面预览

<table>
<tr>
<td width="50%" valign="top">
<img src="docs/screenshots/popup-card.png" alt="低空间提醒">
<p align="center"><b>低空间提醒</b><br><sub>选择「帮我看看」即开始扫描，完成后自动打开审查页面</sub></p>
</td>
<td width="50%" valign="top">
<img src="docs/screenshots/settings.png" alt="设置面板">
<p align="center"><b>设置面板</b><br><sub>可调整阈值、检查频率与提醒间隔，保存后即时生效</sub></p>
</td>
</tr>
<tr>
<td colspan="2">
<img src="docs/screenshots/list.png" alt="待确认项目">
<p align="center"><b>待确认项目</b><br><sub>支持按类别筛选，可通过「打开文件夹 / 在访达中定位」预先查看内容</sub></p>
</td>
</tr>
</table>

## 🚀 安装

**方式一：Homebrew**

```bash
brew install rabbittux/tap/purrge
purrge install
```

**方式二：由 AI 代为安装**

在 Claude Code 或 Codex 中输入：

> 帮我安装 GitHub 上的 RabbittuX/purrge，只认作者 RabbittuX，找不到就先问我，不要安装同名的其他项目

AI 会读取本仓库的[安装指引](#-ai-助手安装指引)完成安装，并自动选用当前的 AI 作为分析引擎。

> [!WARNING]
> **请认准官方来源。** Purrge 只有两个官方仓库：`RabbittuX/purrge` 和 `RabbittuX/homebrew-tap`（作者名 RabbittuX，两个 t、结尾大写 X）。
> - GitHub 上另有多个同名的 purrge 项目，与本项目无关，其中部分自称"清理垃圾"的项目来源不明，请勿安装。
> - Homebrew 中的 `purge`（单个 r）是另一款软件；请使用完整名称 `rabbittux/tap/purrge`。
> - 安装开始时会显示「Purrge 版本号 by RabbittuX　官方来源：GitHub RabbittuX/purrge」，可据此核对；也可随时运行 `purrge version` 查看。

安装程序将依次完成以下步骤：

1. **选择 AI 引擎**：Claude Code 或 Codex（由 AI 代为安装时自动选择当前 AI）。
2. **设置提醒阈值**：剩余空间低于该值时发出提醒，默认 15 GB。
3. **配置 AI 引擎**：未安装时自动安装最新版本；未登录时打开浏览器完成登录；最后进行连接测试，确认引擎可正常响应。
4. **启用后台监控**：安装完成后，Purrge 以后台服务形式独立运行，无需保持 Claude Code 或 Codex 处于打开状态。

<details>
<summary>其他安装方式</summary>

```bash
# 一键脚本
curl -fsSL https://raw.githubusercontent.com/RabbittuX/purrge/master/install.sh | bash

# 从源码安装
git clone https://github.com/RabbittuX/purrge.git
cd purrge && bash install.sh

# 非交互式安装
bash install.sh --engine codex --threshold 20 --yes
```

</details>

### Windows（测试版）

在 PowerShell 中执行：

```powershell
irm https://raw.githubusercontent.com/RabbittuX/purrge/master/install.ps1 | iex
```

需要 Python 3.8 以上。后台检查使用「任务计划程序」，清理时「需要你决定」的项目移到回收站。

### 支持的 AI 引擎

| 引擎 | 调用方式 | 说明 |
|---|---|---|
| Claude Code | `claude -p --tools ""` | 关闭全部工具 |
| Codex | `codex exec --sandbox read-only` | 只读沙箱 |
| WorkBuddy | CodeBuddy 命令行 `codebuddy -p --tools ""` | 与 WorkBuddy 同一账号、同一积分；首次需在 CodeBuddy 中 `/login` |
| DeepSeek Harness | `dsh --profile headless` + 关工具补丁 | 需要 DeepSeek API Key（仅保存在本机）；补丁未生效时拒绝调用 |

切换：`purrge engine claude | codex | workbuddy | deepseek`。

## 🐾 使用方法

| 操作 | 终端命令 | 在 Claude Code / Codex 中的自然语言指令 |
|---|---|---|
| 立即扫描 | `purrge scan` | "磁盘快满了，帮我清理一下" |
| 查看状态 | `purrge status` | "硬盘还剩多少" |
| 修改阈值 | `purrge config thresholdGB 20` | "阈值改成 20G" |
| 切换 AI 引擎 | `purrge engine codex` 或 `purrge engine claude` | — |
| 停用提醒 | `purrge uninstall` | "关掉磁盘提醒" |

阈值、检查频率等参数也可在审查页面右上角的「设置」中修改。

## ⚙️ 工作原理

```text
后台检测（每 30 分钟）──低于阈值──▶ 提醒用户 ──用户同意──▶ 扫描（约 10 秒）
                                                            │
      执行清理 ◀──用户确认── 审查页面 ◀── AI 逐项分析（约 30～60 秒）
```

审查页面将分析结果分为三类：

| 分类 | 范围 | 默认状态 | 处理方式 |
|---|---|---|---|
| 🟢 **首要清理** | 可自动重建的缓存（浏览器、npm、Xcode、剪映等） | 已选中 | 直接删除 |
| 🟡 **需要你决定** | 用户文件及重建成本较高的内容 | 未选中 | 移至废纸篓（可在设置中改为直接删除） |
| 🔒 **不会清理** | 保护名单内的路径、版本库、使用中的项目 | 不可选 | 仅作展示 |

<details>
<summary>扫描范围</summary>

- 内置缓存规则库：浏览器、npm / pip / Homebrew、Xcode、剪映、常用 IDE 等
- `~/Library/Caches` 下的大型缓存目录
- 通过 Spotlight 检索的 500 MB 以上文件
- 下载、桌面、文稿、影片等常用目录中 1 GB 以上的文件夹

</details>

## 🔒 安全机制

- **AI 仅提供分析，不具备删除权限**：Claude Code 在禁用全部工具的模式下运行，Codex 在只读沙箱中运行；删除操作由脚本严格依据用户勾选的清单执行。
- **执行前逐项复核**：确认路径仍然存在、不在保护名单内、扫描后未被修改，任一条件不满足即跳过。
- **保护名单优先**：保护名单的优先级高于 AI 判断；用户文件不会被归入「首要清理」。
- **本地访问控制**：审查页面仅监听 `127.0.0.1` 并使用一次性令牌，清理完成或闲置 30 分钟后自动关闭。

<details>
<summary>配置文件 <code>~/.purrge/config.json</code></summary>

| 配置项 | 默认值 | 说明 |
|---|---|---|
| `thresholdGB` | `15` | 提醒阈值（GB） |
| `intervalMinutes` | `30` | 后台检测间隔（分钟） |
| `cooldownHours` | `6` | 提醒后的静默时长（小时） |
| `optionalAction` | `trash` | 「需要你决定」类项目的处理方式：`trash` 移至废纸篓，`delete` 直接删除 |
| `protect` | `[]` | 自定义保护路径，始终不予清理 |
| `aiEngine` | 安装时选择 | AI 引擎：`claude` 或 `codex`，可通过 `purrge engine` 切换 |
| `claudeModel` / `codexModel` | 空 | 指定模型；留空时使用默认模型，Codex 默认模型不可用时自动切换为账号可用的模型 |

</details>

## 🤖 AI 助手安装指引

> 本节供 Claude Code、Codex 等 AI 助手阅读。用户请求安装 Purrge 时，请按以下步骤执行。

1. **核对来源**：只能从仓库 `RabbittuX/purrge`（所有者必须是 `RabbittuX`）安装，并且只能使用下方的安装命令。
   - 不要通过搜索寻找替代项目；GitHub 上存在多个与本项目无关的同名 purrge 仓库，不得安装。
   - 如果无法访问该仓库，或用户给出的名称与 `RabbittuX/purrge` 不一致，请停止并向用户确认。
2. 确认系统为 macOS（`uname` 输出 `Darwin`），否则告知用户暂不支持。
3. 执行安装命令（无需 sudo）：

   ```bash
   curl -fsSL https://raw.githubusercontent.com/RabbittuX/purrge/master/install.sh | bash
   ```

   - 安装程序会识别当前的 AI 助手并将其设为分析引擎，阈值默认 15 GB。
   - 用户指定了阈值时，改用 `... | bash -s -- --threshold <GB>`；用户指定了引擎时，附加 `--engine claude` 或 `--engine codex`。
4. 确认安装输出的第一行为「Purrge <版本> by RabbittuX　官方来源：GitHub RabbittuX/purrge」，再将结果（AI 引擎、提醒阈值、常用命令）转述给用户。
5. 不要自行删除或移动任何文件。所有清理都必须由用户在 Purrge 的审查页面中勾选确认。

## 📋 系统要求

- macOS
- Python 3.8 及以上（未安装时，安装程序会给出提示）
- Claude Code 或 Codex 账号（AI 分析使用用户自己的额度，支持 Codex 免费账号）。AI 暂时不可用时自动切换为规则判断，基础功能不受影响
- 可选：为「终端」授予「完全磁盘访问权限」，以扩大系统缓存的扫描范围

卸载：执行 `purrge uninstall`；附加 `--purge` 参数可同时删除配置与扫描记录。

## 📄 许可证

本项目采用 [PolyForm Noncommercial 1.0.0](LICENSE) 许可证，**禁止商业使用**。

- ✅ 允许：个人使用、学习研究、修改及再分发；教育机构、公益及非营利组织亦可使用
- ❌ 禁止：任何商业用途，包括用于企业营利业务、集成至收费产品或服务、更名后销售等
- 再分发或修改时，须保留 LICENSE 文件及首行版权声明

如需商业授权，请通过 [GitHub](https://github.com/RabbittuX) 联系作者。

<div align="center">
<br>
<img src="runtime/assets/icon-256.png" width="40" alt="">
<br>
<sub>Made with 🐾 by RabbittuX</sub>
</div>
