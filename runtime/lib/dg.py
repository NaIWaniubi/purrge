"""purrge 命令行入口。
  setup [--threshold GB]   一键安装：复制运行时、写配置、注册后台监控
  run [--no-open]          扫描 → AI 判断 → 打开审查页面（审查完成后才会清理）
  check                    后台监控调用：低于阈值时弹窗询问
  config [key value]       查看/修改配置，如：config thresholdGB 20
  status                   当前磁盘与监控状态
  uninstall                移除后台监控（--purge 同时删除配置和记录）
"""
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (APP_DIR, CONFIG, DG_HOME, disk_status, human, latest_run, load_config, new_run_dir,  # noqa: E402
                    save_config)

LABEL = "com.rabbittux.purrge"
PLIST = Path.home() / "Library/LaunchAgents" / f"{LABEL}.plist"
INSTALLED_APP = DG_HOME / "app"
STATE = DG_HOME / "state.json"


def notify(title, text):
    subprocess.run(["osascript", "-e", f'display notification "{text}" with title "{title}"'], capture_output=True)


def migrate_from_disk_guard():
    """旧版叫 disk-guard：停掉旧的后台任务，并把设置和扫描记录搬到新目录（旧目录原样保留）。"""
    old_home, old_label = Path.home() / ".disk-guard", "com.diskguard.monitor"
    old_plist = Path.home() / "Library/LaunchAgents" / f"{old_label}.plist"
    if old_plist.exists():
        subprocess.run(["launchctl", "bootout", f"gui/{os.getuid()}/{old_label}"], capture_output=True)
        old_plist.unlink()
    if (old_home / "config.json").exists() and not CONFIG.exists():
        DG_HOME.mkdir(parents=True, exist_ok=True)
        shutil.copy2(old_home / "config.json", CONFIG)
        if (old_home / "runs").is_dir() and not (DG_HOME / "runs").exists():
            shutil.copytree(old_home / "runs", DG_HOME / "runs")
        return str(old_home)
    return None


def cmd_setup(args):
    migrated = migrate_from_disk_guard()
    cfg = load_config()
    if "--threshold" in args:
        cfg["thresholdGB"] = float(args[args.index("--threshold") + 1])
    claude = shutil.which("claude") or str(Path.home() / ".local/bin/claude")
    cfg["claudePath"] = claude if os.path.exists(claude) else ""
    # 运行时复制到固定位置（插件目录随版本变化，后台监控要用稳定路径）
    if APP_DIR.resolve() != INSTALLED_APP.resolve():
        if INSTALLED_APP.exists():
            shutil.rmtree(INSTALLED_APP)
        shutil.copytree(APP_DIR, INSTALLED_APP, ignore=shutil.ignore_patterns("__pycache__"))
    os.chmod(INSTALLED_APP / "bin/purrge", 0o755)
    save_config(cfg)
    install_monitor(cfg)
    free, total = disk_status()
    print(json.dumps({
        "ok": True, "thresholdGB": cfg["thresholdGB"], "intervalMinutes": cfg["intervalMinutes"],
        "free": human(free), "total": human(total), "claude": cfg["claudePath"] or "未找到（AI 判断将改用规则）",
        "app": str(INSTALLED_APP), "config": str(CONFIG), "monitor": str(PLIST),
        "fullDiskAccess": has_full_disk_access(),
        **({"migratedFrom": migrated + "（旧目录可以手动删除）"} if migrated else {})}, ensure_ascii=False, indent=1))


def install_monitor(cfg):
    PLIST.parent.mkdir(parents=True, exist_ok=True)
    py = shutil.which("python3") or "/usr/bin/python3"
    PLIST.write_text(f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>{LABEL}</string>
  <key>ProgramArguments</key><array><string>{py}</string><string>{INSTALLED_APP}/lib/dg.py</string><string>check</string></array>
  <key>StartInterval</key><integer>{int(cfg['intervalMinutes']) * 60}</integer>
  <key>RunAtLoad</key><true/>
  <key>StandardOutPath</key><string>{DG_HOME}/monitor.log</string>
  <key>StandardErrorPath</key><string>{DG_HOME}/monitor.log</string>
  <key>EnvironmentVariables</key><dict><key>PATH</key><string>/usr/local/bin:/opt/homebrew/bin:{Path(cfg.get('claudePath') or '/usr/bin').parent}:/usr/bin:/bin:/usr/sbin:/sbin</string></dict>
</dict></plist>
""", encoding="utf-8")
    uid = os.getuid()
    subprocess.run(["launchctl", "bootout", f"gui/{uid}/{LABEL}"], capture_output=True)
    subprocess.run(["launchctl", "bootstrap", f"gui/{uid}", str(PLIST)], capture_output=True)


def has_full_disk_access():
    probe = Path.home() / "Library/Safari"
    try:
        list(os.scandir(probe))
        return True
    except PermissionError:
        return False
    except OSError:
        return None


def _state():
    try:
        return json.loads(STATE.read_text())
    except (OSError, json.JSONDecodeError):
        return {}


def ask_user(free):
    """弹出原生提醒窗（NSAlert，带图标和用量条）；失败时退回系统对话框。返回 scan / later。"""
    cfg = load_config()
    _, total = disk_status()
    th = f"{cfg['thresholdGB']:g} GB"
    try:
        p = subprocess.run(["osascript", "-l", "JavaScript", str(APP_DIR / "lib/alert.js"), human(free), human(total), th,
                            str(1 - free / total), str(APP_DIR / "assets/icon-256.png")], capture_output=True, text=True,
                           timeout=3600)
        if p.returncode == 0 and p.stdout.strip() in ("scan", "later"):
            return p.stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        pass
    msg = f"主人，磁盘只剩 {human(free)} 了，已经低于你定的 {th} 啦。\\n要我帮你翻翻哪些能清掉吗？删哪些，你说了算。"
    p = subprocess.run(["osascript", "-e", f'display dialog "{msg}" with title "Purrge" buttons {{"等会儿再说", "帮我看看"}} '
                        f'default button "帮我看看" giving up after 120'], capture_output=True, text=True)
    return "scan" if "帮我看看" in p.stdout else "later"


def cmd_check(args):
    cfg = load_config()
    free, _ = disk_status()
    st = _state()
    low = free < cfg["thresholdGB"] * 1024 ** 3
    print(time.strftime("%F %T"), "free", human(free), "threshold", cfg["thresholdGB"], "GB", "low" if low else "ok")
    if not low and "--force" not in args:
        return
    if time.time() - st.get("lastPrompt", 0) < cfg["cooldownHours"] * 3600 and "--force" not in args:
        return
    st["lastPrompt"] = time.time()
    STATE.write_text(json.dumps(st))
    choice = ask_user(free)
    if choice == "scan":
        subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "run"], start_new_session=True,
                         stdout=open(DG_HOME / "run.log", "a"), stderr=subprocess.STDOUT)


def cmd_run(args):
    if "--background" in args:   # 供 Claude Code 命令调用：立即返回，扫描完成后自动打开审查页面
        rest = [a for a in args if a != "--background"]
        log = open(DG_HOME / "run.log", "a")
        subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "run", *rest], start_new_session=True,
                         stdout=log, stderr=subprocess.STDOUT)
        print("已开始扫描（约 1 分钟：扫描 10 秒 + AI 判断 30～60 秒），完成后会自动在浏览器打开审查页面。"
              f"进度日志：{DG_HOME / 'run.log'}")
        return
    from classify import classify
    from scan import scan
    from server import serve
    run_dir = new_run_dir()
    notify("Purrge", "收到！正在帮你翻找能清理的东西，翻完会把清单拿给你看～")
    t0 = time.time()
    cand = scan()
    (run_dir / "candidates.json").write_text(json.dumps(cand, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"扫描完成：{len(cand['items'])} 项，用时 {time.time() - t0:.0f}s")
    review = classify(cand)
    (run_dir / "review.json").write_text(json.dumps(review, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"判断完成（{'AI' if review['judgedBy'] == 'ai' else '规则'}），打开审查页面…")
    serve(run_dir, open_browser="--no-open" not in args)


def cmd_review(args):
    from server import serve
    run = latest_run()
    if not run or not (run / "review.json").exists():
        print("还没有扫描记录，请先运行 run")
        return
    serve(run, open_browser="--no-open" not in args)


def cmd_config(args):
    cfg = load_config()
    if len(args) >= 2:
        key, val = args[0], args[1]
        if key in ("threshold", "阈值"):
            key = "thresholdGB"
        old = cfg.get(key)
        cfg[key] = type(old)(val) if isinstance(old, (int, float)) and not isinstance(old, bool) else val
        if isinstance(old, (int, float)):
            cfg[key] = float(val) if "." in str(val) else int(val)
        save_config(cfg)
        if key == "intervalMinutes" and PLIST.exists():
            install_monitor(cfg)
    print(json.dumps(cfg, ensure_ascii=False, indent=1))


def cmd_status(args):
    cfg = load_config()
    free, total = disk_status()
    loaded = subprocess.run(["launchctl", "print", f"gui/{os.getuid()}/{LABEL}"], capture_output=True).returncode == 0
    run = latest_run()
    print(json.dumps({"free": human(free), "total": human(total), "thresholdGB": cfg["thresholdGB"],
                      "belowThreshold": free < cfg["thresholdGB"] * 1024 ** 3, "monitor": "运行中" if loaded else "未安装",
                      "intervalMinutes": cfg["intervalMinutes"], "lastRun": run.name if run else None},
                     ensure_ascii=False, indent=1))


def cmd_uninstall(args):
    subprocess.run(["launchctl", "bootout", f"gui/{os.getuid()}/{LABEL}"], capture_output=True)
    PLIST.unlink(missing_ok=True)
    if "--purge" in args:
        shutil.rmtree(DG_HOME, ignore_errors=True)
    print("已移除后台监控" + ("，并删除了配置和记录" if "--purge" in args else "（配置和记录保留在 ~/.purrge）"))


def main():
    cmds = {"setup": cmd_setup, "run": cmd_run, "check": cmd_check, "review": cmd_review, "config": cmd_config,
            "status": cmd_status, "uninstall": cmd_uninstall}
    if len(sys.argv) < 2 or sys.argv[1] not in cmds:
        print(__doc__)
        return
    DG_HOME.mkdir(parents=True, exist_ok=True)
    cmds[sys.argv[1]](sys.argv[2:])


if __name__ == "__main__":
    main()
