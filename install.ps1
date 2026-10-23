# Purrge Windows 安装脚本：
#   irm https://raw.githubusercontent.com/RabbittuX/purrge/master/install.ps1 | iex
#   或者 git clone 后运行：powershell -ExecutionPolicy Bypass -File install.ps1
# 可选参数（本地运行时）：--engine claude|codex|workbuddy|deepseek  --threshold 15  --yes
$ErrorActionPreference = "Stop"
$py = $null
foreach ($c in @("python", "py")) {
  if (Get-Command $c -ErrorAction SilentlyContinue) {
    & $c -c "import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)" 2>$null
    if ($LASTEXITCODE -eq 0) { $py = $c; break }
  }
}
if (-not $py) {
  Write-Host "需要 Python 3.8 以上。请先从 https://www.python.org 安装（安装时勾选 Add python.exe to PATH），然后重新运行这条命令。"
  exit 1
}
$src = if ($PSScriptRoot) { $PSScriptRoot } else { "" }
if (-not $src -or -not (Test-Path (Join-Path $src "runtime\lib\dg.py"))) {
  $tmp = Join-Path $env:TEMP ("purrge-" + [guid]::NewGuid())
  New-Item -ItemType Directory -Path $tmp | Out-Null
  Write-Host "正在下载 Purrge…"
  Invoke-WebRequest "https://codeload.github.com/RabbittuX/purrge/zip/refs/heads/master" -OutFile (Join-Path $tmp "purrge.zip")
  Expand-Archive (Join-Path $tmp "purrge.zip") -DestinationPath $tmp
  $src = (Get-ChildItem $tmp -Directory | Where-Object Name -like "purrge-*" | Select-Object -First 1).FullName
}
& $py (Join-Path $src "runtime\lib\dg.py") install @args
