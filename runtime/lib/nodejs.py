"""Node.js：WorkBuddy / DeepSeek（以及 Windows 上的 Codex）的命令行要用 npm 安装。
电脑上已经有 npm 就直接用，什么都不改；没有时（征得同意后）自动装一份：
  从 nodejs.org 下载官方 LTS 压缩包，核对官方 SHA256 后解压到 ~/.purrge/node，只给 Purrge 用，不改系统、不需要管理员权限。
  不用 Homebrew / winget：前者在不再提供预编译包的 macOS 上会从源码编译并升级其他软件，后者装 Node 需要管理员权限。"""
import hashlib
import json
import os
import platform
import shutil
import sys
import tarfile
import tempfile
import urllib.request
import zipfile
from pathlib import Path

WIN = sys.platform == "win32"
HOME = Path(os.environ.get("PURRGE_HOME", Path.home() / ".purrge")) / "node"
DIST = os.environ.get("PURRGE_NODE_DIST", "https://nodejs.org/dist")   # 测试时可指向本地目录


def bin_dir():
    """私有 Node 的可执行文件目录（Windows 下 node.exe 和 npm 全局命令都在根目录）。"""
    return HOME if WIN else HOME / "bin"


def _private_npm():
    p = bin_dir() / ("npm.cmd" if WIN else "npm")
    return str(p) if p.is_file() else None


def npm():
    """返回可用的 npm 路径：优先电脑上已有的，其次 Purrge 自己装的那份；都没有返回 None。"""
    return shutil.which("npm") or _private_npm()


def env(base=None):
    """调用 npm / AI 命令行时用的环境变量：用的是私有 Node 时，把它加进 PATH，并让 npm -g 装到它自己的目录。"""
    e = dict(os.environ if base is None else base)
    if _private_npm() and not shutil.which("npm", path=e.get("PATH")):
        e["PATH"] = str(bin_dir()) + os.pathsep + e.get("PATH", "")
        e["npm_config_prefix"] = str(HOME)
    return e


def _arch():
    m = platform.machine().lower()
    return "arm64" if m in ("arm64", "aarch64") else "x64"


def _get(url, dest=None, timeout=60):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        if dest is None:
            return r.read()
        with open(dest, "wb") as f:
            shutil.copyfileobj(r, f)


def _latest_lts():
    """nodejs.org 官方版本列表里最新的 LTS 版本号，如 v22.21.0。"""
    for rel in json.loads(_get(f"{DIST}/index.json")):
        if rel.get("lts"):
            return rel["version"]
    raise RuntimeError("没找到 LTS 版本")


def _install_portable(say):
    ver = _latest_lts()
    name = f"node-{ver}-{'win' if WIN else 'darwin'}-{_arch()}"
    fname = name + (".zip" if WIN else ".tar.gz")
    say(f"正在从 nodejs.org 下载 Node.js {ver}（LTS）…")
    sums = _get(f"{DIST}/{ver}/SHASUMS256.txt").decode()
    want = next((l.split()[0] for l in sums.splitlines() if l.strip().endswith("  " + fname)), None)
    if not want:
        raise RuntimeError(f"官方校验清单里没有 {fname}")
    with tempfile.TemporaryDirectory() as tmp:
        pkg = Path(tmp) / fname
        _get(f"{DIST}/{ver}/{fname}", pkg, timeout=600)
        h = hashlib.sha256(pkg.read_bytes()).hexdigest()
        if h != want:
            raise RuntimeError("下载的文件和官方校验值对不上，已放弃安装")
        out = Path(tmp) / "x"
        if WIN:
            with zipfile.ZipFile(pkg) as z:
                z.extractall(out)
        else:
            with tarfile.open(pkg) as t:
                if hasattr(tarfile, "data_filter"):
                    t.extractall(out, filter="data")   # 保留可执行权限和包内的相对软链接（npm）
                else:
                    t.extractall(out)
        top = out / name
        if not top.is_dir():
            raise RuntimeError("压缩包结构不对")
        shutil.rmtree(HOME, ignore_errors=True)
        HOME.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(top), str(HOME))
    return _private_npm()


def ensure(say=print, confirm=None):
    """确保有 npm 可用，返回 npm 路径；用户不同意或安装失败返回 None。
    confirm(问题) → True/False；不传表示直接安装（已在调用方确认过）。"""
    found = npm()
    if found:
        return found
    if confirm and not confirm("需要先安装 Node.js（约 30～50MB，官方 LTS 版本）。现在自动安装吗？[Y/n]："):
        return None
    try:
        p = _install_portable(say)
    except Exception as e:      # 没网、被墙、校验不通过……
        say(f"Node.js 自动安装失败：{e}")
        return None
    if p:
        say(f"Node.js 已安装到 {HOME}（只给 Purrge 使用）")
    return p
