"""purrge 公共工具：路径、配置、磁盘空间、目录大小。"""
import json
import os
import shutil
import subprocess
import time
from pathlib import Path

HOME = Path.home()
DG_HOME = Path(os.environ.get("PURRGE_HOME", HOME / ".purrge"))
APP_DIR = Path(__file__).resolve().parent.parent          # runtime/
RULES = APP_DIR / "rules" / "registry.json"
WEB_DIR = APP_DIR / "web"
CONFIG = DG_HOME / "config.json"
RUNS = DG_HOME / "runs"

DEFAULT_CONFIG = {
    "thresholdGB": 15,          # 剩余空间低于这个值就提醒
    "intervalMinutes": 30,      # 后台检查频率
    "cooldownHours": 6,         # 提醒过一次后，多久内不再打扰
    "optionalAction": "trash",  # "需你决定"的项目：trash=移到废纸篓（可找回）delete=直接删除
    "protect": [],              # 额外的保护路径（永不清理）
    "claudePath": "",           # setup 时自动探测
    "aiModel": "",              # 留空用默认模型
    "language": "zh",
}


def expand(p):
    return Path(os.path.expandvars(os.path.expanduser(p)))


def load_config():
    cfg = dict(DEFAULT_CONFIG)
    if CONFIG.is_file():
        try:
            cfg.update(json.loads(CONFIG.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError):
            pass
    return cfg


def save_config(cfg):
    DG_HOME.mkdir(parents=True, exist_ok=True)
    CONFIG.write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_rules():
    return json.loads(RULES.read_text(encoding="utf-8"))


def data_volume():
    return "/System/Volumes/Data" if os.path.isdir("/System/Volumes/Data") else "/"


def disk_status():
    """返回 (可用字节, 总字节)。口径与 df 一致（不含 APFS 可清除空间）。"""
    st = os.statvfs(data_volume())
    return st.f_bavail * st.f_frsize, st.f_blocks * st.f_frsize


def du_bytes(path, timeout=600):
    """目录实际占用（du -sk，跨卷不统计）。权限不足的部分会被跳过，返回 (字节, 是否有受限子目录)。"""
    try:
        p = subprocess.run(["du", "-skx", str(path)], capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return 0, True
    out = p.stdout.strip().split("\t")[0] if p.stdout.strip() else "0"
    try:
        kb = int(out)
    except ValueError:
        kb = 0
    return kb * 1024, bool(p.stderr.strip())


def running_processes():
    try:
        out = subprocess.run(["ps", "-axo", "comm="], capture_output=True, text=True).stdout
    except OSError:
        return set()
    names = set()
    for line in out.splitlines():
        line = line.strip()
        if line:
            names.add(os.path.basename(line))
            names.add(line)
    return names


def human(n):
    n = float(n)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(n) < 1024 or unit == "TB":
            return f"{n:.1f}{unit}" if unit in ("GB", "TB") else f"{n:.0f}{unit}"
        n /= 1024


def is_protected(path, cfg, rules):
    path = Path(path).resolve()
    for raw in list(rules.get("protected", [])) + list(cfg.get("protect", [])):
        prot = expand(raw)
        try:
            prot = prot.resolve()
        except OSError:
            pass
        if path == prot or prot in path.parents or path in prot.parents:
            return True
    return False


def new_run_dir():
    d = RUNS / time.strftime("%Y%m%d-%H%M%S")
    d.mkdir(parents=True, exist_ok=True)
    # 只保留最近 10 次
    runs = sorted(p for p in RUNS.iterdir() if p.is_dir())
    for old in runs[:-10]:
        shutil.rmtree(old, ignore_errors=True)
    return d


def latest_run():
    if not RUNS.is_dir():
        return None
    runs = sorted(p for p in RUNS.iterdir() if p.is_dir())
    return runs[-1] if runs else None
