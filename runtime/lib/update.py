"""更新：purrge update 一条命令升级到最新版；后台检查时顺带看一眼有没有新版本（每天最多一次，只读版本号）。
更新流程：取新代码 → 备份旧程序 → 替换 ~/.purrge/app → 用新程序重新注册后台任务并自检 → 自检失败自动换回旧版本。
设置（config.json）、扫描记录、AI 引擎都不动。"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

from common import APP_DIR, DG_HOME, VERSION

INSTALLED_APP = DG_HOME / "app"
BACKUP = DG_HOME / "app.bak"
LATEST = DG_HOME / "latest.json"
TARBALL = "https://codeload.github.com/RabbittuX/purrge/tar.gz/refs/heads/master"
RELEASES = "https://api.github.com/repos/RabbittuX/purrge/releases/latest"


def _ver(v):
    """'0.3.0-beta' → (0, 3, 0, 0)；正式版 (0, 3, 0, 1) 比 beta 新。"""
    m = re.match(r"v?(\d+)\.(\d+)\.(\d+)(-\S+)?", str(v or ""))
    if not m:
        return (0, 0, 0, 0)
    return (int(m.group(1)), int(m.group(2)), int(m.group(3)), 0 if m.group(4) else 1)


def newer(a, b):
    return _ver(a) > _ver(b)


# ---------- 新版本提醒 ----------

def check_latest(force=False, timeout=5):
    """返回 GitHub 上最新发布的版本号（失败返回 None）。每 24 小时最多联网一次，结果缓存在 latest.json。"""
    if os.environ.get("PURRGE_NO_UPDATE_CHECK"):
        return None
    try:
        cache = json.loads(LATEST.read_text())
    except (OSError, json.JSONDecodeError):
        cache = {}
    if not force and time.time() - cache.get("checked", 0) < 24 * 3600:
        return cache.get("version")
    try:
        req = urllib.request.Request(RELEASES, headers={"Accept": "application/vnd.github+json", "User-Agent": "purrge"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            ver = json.loads(r.read()).get("tag_name", "").lstrip("v")
    except Exception:          # 没网、限流、仓库还没有发布……都安静地跳过
        ver = cache.get("version")
    try:
        DG_HOME.mkdir(parents=True, exist_ok=True)
        LATEST.write_text(json.dumps({"checked": time.time(), "version": ver}))
    except OSError:
        pass
    return ver


def available():
    """有更新时返回新版本号，否则 None（只读缓存，不联网）。"""
    try:
        ver = json.loads(LATEST.read_text()).get("version")
    except (OSError, json.JSONDecodeError):
        return None
    return ver if ver and newer(ver, VERSION) else None


# ---------- purrge update ----------

def _say(msg):
    print(msg, flush=True)


def _brew_installed():
    brew = shutil.which("brew")
    if not brew:
        return None
    p = subprocess.run([brew, "list", "--versions", "purrge"], capture_output=True, text=True)
    if p.returncode != 0 or not p.stdout.strip():
        return None
    prefix = subprocess.run([brew, "--prefix", "purrge"], capture_output=True, text=True).stdout.strip()
    return brew, Path(prefix)


def _fetch(args, tmp):
    """取新版 runtime 目录。--from <目录> 用本地代码（开发/测试用）；Homebrew 装的走 brew；否则从 GitHub 下载。"""
    if "--from" in args:
        return Path(args[args.index("--from") + 1]).resolve() / "runtime"
    b = _brew_installed()
    if b and "--no-brew" not in args:
        brew, prefix = b
        _say("检测到 Homebrew 安装，正在 brew upgrade…")
        subprocess.run([brew, "update", "--quiet"], capture_output=True)
        subprocess.run([brew, "upgrade", "rabbittux/tap/purrge"])
        return prefix / "libexec" / "runtime"
    _say("正在从 GitHub 下载最新版…")
    tgz = Path(tmp) / "purrge.tar.gz"
    urllib.request.urlretrieve(TARBALL, tgz)
    import tarfile
    with tarfile.open(tgz) as t:
        if hasattr(tarfile, "data_filter"):
            t.extractall(tmp, filter="data")
        else:
            t.extractall(tmp)
    return next(Path(tmp).glob("purrge-*")) / "runtime"


def _new_version(runtime):
    m = re.search(r'VERSION = "([^"]+)"', (runtime / "lib/common.py").read_text(encoding="utf-8"))
    return m.group(1) if m else "?"


def _post_update(python):
    """用新程序完成收尾：重新注册后台任务、更新 AI 说明文件、自检。返回 (成功, 说明)。"""
    p = subprocess.run([python, str(INSTALLED_APP / "lib/dg.py"), "_post_update"], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=180)
    return p.returncode == 0, (p.stdout + p.stderr).strip()[-600:]


def cmd_update(args):
    old = VERSION
    with tempfile.TemporaryDirectory() as tmp:
        try:
            src = _fetch(args, tmp)
        except Exception as e:
            _say(f"✗ 下载新版本失败：{e}。当前版本 {old} 照常可用，稍后再试。")
            return 1
        if not (src / "lib/dg.py").is_file():
            _say("✗ 新版本文件不完整，已取消更新。")
            return 1
        new = _new_version(src)
        if not newer(new, old) and "--force" not in args:
            if not _installed_stale(src):
                _say(f"✓ 已经是最新版本 {old}，不需要更新。")
                return 0
            # Homebrew 已升级但后台运行的 ~/.purrge/app 还是旧程序：按正常更新流程同步（同样备份、自检、失败回滚）
            old = _new_version(INSTALLED_APP)
            _say(f"命令行已是 {new}，后台程序还是 {old}，正在同步…")
        else:
            _say(f"正在更新 Purrge：{old} → {new}")
        if INSTALLED_APP.exists():
            shutil.rmtree(BACKUP, ignore_errors=True)
            shutil.copytree(INSTALLED_APP, BACKUP)
        _replace_app(src)
    ok, info = _post_update(sys.executable)
    if not ok:
        _say("✗ 新版本自检没通过，正在换回旧版本…")
        if BACKUP.exists():
            shutil.rmtree(INSTALLED_APP, ignore_errors=True)
            shutil.copytree(BACKUP, INSTALLED_APP)
            _post_update(sys.executable)
        _say(f"已恢复到 {old}，原有功能不受影响。失败信息：{info}")
        return 1
    try:
        LATEST.unlink()
    except OSError:
        pass
    _say(f"✓ 已更新到 {new}。设置、扫描记录和 AI 引擎都保持不变。")
    return 0


def _replace_app(src):
    if src.resolve() == INSTALLED_APP.resolve():
        return
    shutil.rmtree(INSTALLED_APP, ignore_errors=True)
    shutil.copytree(src, INSTALLED_APP, ignore=shutil.ignore_patterns("__pycache__"))
    try:
        os.chmod(INSTALLED_APP / "bin/purrge", 0o755)
    except OSError:
        pass


def _installed_stale(src):
    """版本号相同但后台运行的 ~/.purrge/app 是旧文件（比如只做了 brew upgrade）。"""
    try:
        return INSTALLED_APP.exists() and _new_version(INSTALLED_APP) != _new_version(src)
    except OSError:
        return False
