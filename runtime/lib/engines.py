"""AI 引擎：Claude Code 或 Codex。负责找到命令行工具、安装最新版、检查/拉起登录、调用 AI。
Purrge 本身不依赖任何一家，引擎不可用时 classify.py 会退回规则判断。"""
import json
import os
import platform
import re
import shutil
import subprocess
import tarfile
import tempfile
import urllib.request
from pathlib import Path

HOME = Path.home()
NAMES = {"claude": "Claude Code", "codex": "Codex"}
MODEL_ERRORS = ("not supported", "requires a newer version", "model_not_found", "does not exist", "invalid model")


def _run(cmd, **kw):
    """后台调用：脱离终端运行，避免 CLI 向终端发查询码、抢用户正在输入的内容。"""
    kw.setdefault("start_new_session", True)
    kw.setdefault("stdin", subprocess.DEVNULL) if "input" not in kw else None
    try:
        return subprocess.run(cmd, capture_output=True, text=True, **kw)
    except (OSError, subprocess.TimeoutExpired) as e:
        return subprocess.CompletedProcess(cmd, 127, "", str(e))


def _version(path):
    out = _run([path, "--version"], timeout=20).stdout
    m = re.search(r"(\d+)\.(\d+)\.(\d+)", out)
    return tuple(int(x) for x in m.groups()) if m else (0, 0, 0)


def _candidates(engine):
    found = shutil.which(engine)
    paths = [found] if found else []
    if engine == "claude":
        paths += [HOME / ".local/bin/claude", HOME / ".claude/local/claude", "/opt/homebrew/bin/claude", "/usr/local/bin/claude"]
    else:   # ChatGPT / Codex 桌面版自带的 codex 往往比命令行装的新
        paths += [HOME / ".local/bin/codex", "/opt/homebrew/bin/codex", "/usr/local/bin/codex",
                  "/Applications/ChatGPT.app/Contents/Resources/codex-cli/bin/codex",
                  "/Applications/Codex.app/Contents/Resources/codex-cli/bin/codex",
                  "/Applications/Codex.app/Contents/Resources/codex"]
    seen, out = set(), []
    for p in paths:
        p = str(p)
        if p not in seen and os.path.isfile(p) and os.access(p, os.X_OK):
            seen.add(p)
            out.append(p)
    return out


def find(engine):
    """返回版本最新的那个可执行文件路径，没有就返回 None。"""
    paths = _candidates(engine)
    return max(paths, key=_version) if paths else None


def version_text(path):
    v = _version(path)
    return ".".join(map(str, v)) if v != (0, 0, 0) else "未知版本"


# ---------- 安装 ----------

def install(engine, say=print):
    """安装最新版，成功返回路径。"""
    if engine == "claude":
        say("正在安装最新版 Claude Code（官方安装脚本）…")
        p = subprocess.run("curl -fsSL https://claude.ai/install.sh | bash", shell=True)
        if p.returncode != 0 and shutil.which("npm"):
            say("官方脚本失败，改用 npm 安装…")
            subprocess.run(["npm", "install", "-g", "@anthropic-ai/claude-code@latest"])
        return find("claude")
    say("正在安装最新版 Codex…")
    if shutil.which("npm"):
        subprocess.run(["npm", "install", "-g", "@openai/codex@latest"])
    elif shutil.which("brew"):
        subprocess.run(["brew", "install", "codex"])
    else:
        _install_codex_release(say)
    return find("codex")


def upgrade(engine, path, say=print):
    """把已有的命令行工具升级到最新版。"""
    if engine == "claude":
        subprocess.run([path, "update"])
    elif "node_modules" in os.path.realpath(path) and shutil.which("npm"):
        subprocess.run(["npm", "install", "-g", "@openai/codex@latest"])
    elif os.path.realpath(path).startswith(("/opt/homebrew", "/usr/local/Cellar")) and shutil.which("brew"):
        subprocess.run(["brew", "upgrade", "codex"])
    else:
        _install_codex_release(say)
    return find(engine)


def _install_codex_release(say):
    """没有 npm / Homebrew 时，直接从 GitHub 官方发布页下载 codex 到 ~/.local/bin。"""
    arch = "aarch64" if platform.machine() == "arm64" else "x86_64"
    url = f"https://github.com/openai/codex/releases/latest/download/codex-{arch}-apple-darwin.tar.gz"
    dest = HOME / ".local/bin/codex"
    with tempfile.TemporaryDirectory() as tmp:
        tgz = Path(tmp) / "codex.tar.gz"
        urllib.request.urlretrieve(url, tgz)
        with tarfile.open(tgz) as t:
            t.extractall(tmp, filter="data") if hasattr(tarfile, "data_filter") else t.extractall(tmp)
        binary = next(p for p in Path(tmp).rglob("codex*") if p.is_file() and p.suffix != ".gz")
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(binary, dest)
        os.chmod(dest, 0o755)
    say(f"已安装到 {dest}")


# ---------- 登录 ----------

def logged_in(engine, path):
    if engine == "claude":
        p = _run([path, "auth", "status", "--json"], timeout=30)
        try:
            return bool(json.loads(p.stdout).get("loggedIn"))
        except (json.JSONDecodeError, AttributeError):
            return None          # 老版本没有 auth 命令，留给后面的连接测试判断
    return _run([path, "login", "status"], timeout=30).returncode == 0


def login(engine, path):
    """在当前终端里拉起官方登录流程（会打开浏览器）。"""
    cmd = [path, "auth", "login"] if engine == "claude" else [path, "login"]
    return subprocess.run(cmd).returncode == 0


# ---------- 调用 AI ----------

def codex_models():
    """账号可用的模型（Codex 本地缓存的列表，按推荐顺序）。"""
    try:
        data = json.loads((HOME / ".codex/models_cache.json").read_text(encoding="utf-8"))
        ms = [m for m in data.get("models", []) if m.get("visibility") == "list"]
        return [m["slug"] for m in sorted(ms, key=lambda m: m.get("priority", 99))]
    except (OSError, json.JSONDecodeError, KeyError):
        return []


class AIError(Exception):
    pass


def _ask_once(engine, path, prompt, model, timeout):
    if engine == "claude":
        cmd = [path, "-p", "--output-format", "json", "--max-turns", "1", "--tools", "", "--no-session-persistence"]
        if model:
            cmd += ["--model", model]
        p = _run(cmd, input=prompt, timeout=timeout)
        if p.returncode != 0 and not p.stdout.strip():
            raise AIError((p.stderr or p.stdout)[-400:])
        try:
            return json.loads(p.stdout).get("result", "")
        except json.JSONDecodeError:
            return p.stdout
    # Codex：只读沙箱、不留会话，在空目录里运行，避免读到别的项目说明
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "answer.txt"
        cmd = [path, "exec", "--skip-git-repo-check", "--sandbox", "read-only", "--ephemeral", "--color", "never",
               "-o", str(out), "-"]
        if model:
            cmd[2:2] = ["-m", model]
        p = _run(cmd, input=prompt, timeout=timeout, cwd=tmp)
        text = out.read_text(encoding="utf-8") if out.exists() else ""
        if p.returncode != 0 or not text.strip():
            msg = re.findall(r'"message":"([^"]+)"', p.stderr) or [p.stderr[-400:]]
            raise AIError(msg[-1])
        return text


def ask(cfg, prompt, timeout=600, log=print):
    """按配置调用 AI，返回文本。Codex 模型不可用时自动换账号能用的模型，并记住它。"""
    engine = cfg.get("aiEngine")
    if engine not in NAMES:
        raise AIError("没有配置 AI 引擎")
    path = cfg.get(f"{engine}Path") or find(engine)
    if not path or not os.path.exists(path):
        raise AIError(f"找不到 {NAMES[engine]}")
    model = cfg.get(f"{engine}Model") or ""
    tried = [model]
    try:
        return _ask_once(engine, path, prompt, model, timeout), model
    except AIError as e:
        if engine != "codex" or not any(k in str(e).lower() for k in MODEL_ERRORS):
            raise
        last = e
    for m in codex_models():
        if m in tried:
            continue
        tried.append(m)
        log(f"模型 {tried[-2] or '默认'} 不可用，换 {m} 再试…")
        try:
            return _ask_once(engine, path, prompt, m, timeout), m
        except AIError as e:
            last = e
            if not any(k in str(e).lower() for k in MODEL_ERRORS):
                raise
    raise last


def test(cfg, log=print):
    """发一句很短的话，确认 AI 能正常回复。返回 (成功, 用上的模型, 错误信息)。"""
    try:
        text, model = ask(cfg, "只回复两个字母：OK。不要执行任何命令。", timeout=180, log=log)
        return bool(text.strip()), model, ""
    except AIError as e:
        return False, "", str(e)
