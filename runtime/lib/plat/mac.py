"""macOS 实现（与 v0.2.2 行为完全一致，代码从 common / scan / clean / server / dg 原样搬来）。"""
import os
import shutil
import subprocess
import time
from pathlib import Path

NAME = "macOS"
FILE_MANAGER = "访达"


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


def dir_sizes(root, depth, timeout=900):
    """root 下各层目录的占用 [(字节, 路径)]，深度 depth。"""
    try:
        p = subprocess.run(["du", "-kx", "-d", str(depth), str(root)], capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return None
    rows = []
    for line in p.stdout.splitlines():
        kb, _, path = line.partition("\t")
        try:
            rows.append((int(kb) * 1024, path))
        except ValueError:
            pass
    return rows


def find_large_files(home, min_bytes):
    """Spotlight 秒查大文件。"""
    try:
        return subprocess.run(["mdfind", "-onlyin", str(home), f"kMDItemFSSize > {min_bytes}"],
                              capture_output=True, text=True, timeout=120).stdout.splitlines()
    except (OSError, subprocess.TimeoutExpired):
        return []


def file_bytes(path):
    return os.stat(path).st_blocks * 512


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


def to_trash(path, home):
    trash = Path(home) / ".Trash"
    trash.mkdir(exist_ok=True)
    name = Path(path).name
    dest = trash / name
    if dest.exists():
        dest = trash / f"{Path(name).stem} {time.strftime('%H.%M.%S')}{Path(name).suffix}"
    shutil.move(str(path), str(dest))
    return dest


def reveal(path, folder):
    # 文件夹直接打开浏览内容；文件（以及 .app 这类包）在所在文件夹里选中
    subprocess.run(["open", path] if folder else ["open", "-R", path], capture_output=True)


def is_package(path):
    return path.endswith((".app", ".photoslibrary"))


def notify(title, text):
    subprocess.run(["osascript", "-e", f'display notification "{text}" with title "{title}"'], capture_output=True)


def show_alert(app_dir, free_txt, total_txt, th_txt, used_frac):
    """原生提醒窗（NSAlert，带图标和用量条）；失败时退回系统对话框。返回 scan / later。"""
    try:
        p = subprocess.run(["osascript", "-l", "JavaScript", str(Path(app_dir) / "lib/alert.js"), free_txt, total_txt, th_txt,
                            str(used_frac), str(Path(app_dir) / "assets/icon-256.png")], capture_output=True, text=True,
                           timeout=3600)
        if p.returncode == 0 and p.stdout.strip() in ("scan", "later"):
            return p.stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        pass
    msg = f"主人，磁盘只剩 {free_txt} 了，已经低于你定的 {th_txt} 啦。\\n要我帮你翻翻哪些能清掉吗？删哪些，你说了算。"
    p = subprocess.run(["osascript", "-e", f'display dialog "{msg}" with title "Purrge" buttons {{"等会儿再说", "帮我看看"}} '
                        f'default button "帮我看看" giving up after 120'], capture_output=True, text=True)
    return "scan" if "帮我看看" in p.stdout else "later"


def monitor_file(label):
    return Path.home() / "Library/LaunchAgents" / f"{label}.plist"


def install_monitor(label, python, script, interval_minutes, log_path, path_env):
    plist = monitor_file(label)
    plist.parent.mkdir(parents=True, exist_ok=True)
    plist.write_text(f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>{label}</string>
  <key>ProgramArguments</key><array><string>{python}</string><string>{script}</string><string>check</string></array>
  <key>StartInterval</key><integer>{int(interval_minutes) * 60}</integer>
  <key>RunAtLoad</key><true/>
  <key>StandardOutPath</key><string>{log_path}</string>
  <key>StandardErrorPath</key><string>{log_path}</string>
  <key>EnvironmentVariables</key><dict><key>PATH</key><string>{path_env}</string></dict>
</dict></plist>
""", encoding="utf-8")
    uid = os.getuid()
    subprocess.run(["launchctl", "bootout", f"gui/{uid}/{label}"], capture_output=True)
    subprocess.run(["launchctl", "bootstrap", f"gui/{uid}", str(plist)], capture_output=True)


def uninstall_monitor(label):
    subprocess.run(["launchctl", "bootout", f"gui/{os.getuid()}/{label}"], capture_output=True)
    monitor_file(label).unlink(missing_ok=True)


def monitor_loaded(label):
    return subprocess.run(["launchctl", "print", f"gui/{os.getuid()}/{label}"], capture_output=True).returncode == 0


def full_disk_access():
    probe = Path.home() / "Library/Safari"
    try:
        list(os.scandir(probe))
        return True
    except PermissionError:
        return False
    except OSError:
        return None


def default_python():
    return shutil.which("python3") or "/usr/bin/python3"
