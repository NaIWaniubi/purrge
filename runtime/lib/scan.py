"""扫描：已知缓存（知识库）+ 普通应用缓存 + 大文件/大文件夹 → candidates.json。只读，不删除任何东西。"""
import glob
import json
import os
import time

import plat
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from common import (HOME, data_volume, disk_status, du_bytes, expand, is_protected, load_config, load_rules,
                    running_processes)

MB = 1024 * 1024


def _stat(p):
    try:
        st = os.stat(p)
        return st.st_mtime, st.st_atime
    except OSError:
        return None, None


def _last_used(p):
    """文件夹：取最近修改时间（只看第一层，够快）；文件：取访问/修改时间较晚者。"""
    p = Path(p)
    mt, at = _stat(p)
    if p.is_dir():
        try:
            for child in list(os.scandir(p))[:500]:
                try:
                    mt = max(mt or 0, child.stat(follow_symlinks=False).st_mtime)
                except OSError:
                    pass
        except OSError:
            pass
        return mt
    return max(mt or 0, at or 0)


def scan(progress=print):
    cfg, rules = load_config(), load_rules()
    procs = running_processes()
    items, seen = [], set()

    def add(item):
        key = os.path.realpath(item["path"])
        if key in seen:
            return
        seen.add(key)
        items.append(item)

    # 1) 知识库里的已知缓存
    progress("扫描已知缓存目录…")
    known = []
    for rule in rules["rules"]:
        for pattern in rule["paths"]:
            for path in sorted(glob.glob(str(expand(pattern)))):
                if os.path.exists(path):
                    known.append((rule, path))
    with ThreadPoolExecutor(8) as pool:
        sizes = list(pool.map(lambda rp: du_bytes(rp[1]), known))
    for (rule, path), (size, limited) in zip(known, sizes):
        if size < rule.get("minMB", 50) * MB:
            continue
        running = [a for a in rule.get("apps", []) if a in procs]
        add({"path": path, "sizeBytes": size, "kind": "known-cache", "ruleId": rule["id"], "name": rule["name"],
             "mode": rule["mode"], "defaultTier": rule["tier"], "regenerable": rule["regenerable"],
             "impactHint": rule["impact"], "appsRunning": running, "scanLimited": limited,
             "protected": is_protected(path, cfg, rules), "lastUsed": _last_used(path)})

    # 2) ~/Library/Caches 等目录下没被知识库覆盖的大缓存
    progress("扫描应用缓存…")
    generic = []
    for g in rules.get("genericCacheRoots", []):
        root = expand(g["root"])
        try:
            children = [e.path for e in os.scandir(root) if e.is_dir(follow_symlinks=False)]
        except OSError:
            continue
        for c in children:
            if os.path.realpath(c) in seen or any(os.path.realpath(c).startswith(s + os.sep) for s in seen):
                continue
            generic.append((g, c))
    with ThreadPoolExecutor(8) as pool:
        sizes = list(pool.map(lambda gp: du_bytes(gp[1]), generic))
    for (g, path), (size, limited) in zip(generic, sizes):
        rp = os.path.realpath(path)
        size -= sum(x["sizeBytes"] for x in items if os.path.realpath(x["path"]).startswith(rp + os.sep))
        if size < g.get("minMB", 150) * MB:
            continue
        add({"path": path, "sizeBytes": size, "kind": "app-cache", "name": Path(path).name, "mode": "contents",
             "defaultTier": g["tier"], "regenerable": True, "impactHint": g["impact"], "appsRunning": [],
             "scanLimited": limited, "protected": is_protected(path, cfg, rules), "lastUsed": _last_used(path)})

    # 3) 用户目录里的大文件（Spotlight 秒查）
    ls = rules["largeScan"]
    progress("查找大文件…")
    excl = [str(expand(e)) for e in ls.get("excludeUnder", [])]
    out = plat.find_large_files(HOME, ls['fileMinMB'] * MB)
    for path in out:
        if not os.path.isfile(path) or any(path.startswith(e + os.sep) or path == e for e in excl):
            continue
        if "/." in path.replace(str(HOME), "", 1) or any(path.startswith(s + os.sep) for s in seen):
            continue  # 隐藏目录和已列出的缓存里的文件不重复列
        try:
            size = plat.file_bytes(path)
        except OSError:
            continue
        add({"path": path, "sizeBytes": size, "kind": "large-file", "name": Path(path).name, "mode": "whole",
             "defaultTier": "optional", "regenerable": False, "impactHint": "", "appsRunning": [],
             "scanLimited": False, "protected": is_protected(path, cfg, rules), "lastUsed": _last_used(path)})

    # 4) 常用目录下的大文件夹
    progress("统计大文件夹…")
    for root in ls.get("dirRoots", []):
        root = expand(root)
        if not root.is_dir():
            continue
        rows = plat.dir_sizes(root, ls.get("dirDepth", 2))
        if rows is None:
            continue
        big = [(s, pth) for s, pth in rows if s >= ls["dirMinMB"] * MB and Path(pth) != root]
        # 只保留最"深"的大文件夹，避免父子重复
        big.sort(key=lambda r: -len(r[1]))
        chosen = []
        for s, pth in big:
            if any(c.startswith(pth + os.sep) for _, c in chosen):
                continue
            chosen.append((s, pth))
        for s, pth in chosen:
            if any(pth.startswith(e + os.sep) for e in excl):
                continue
            add({"path": pth, "sizeBytes": s, "kind": "large-dir", "name": Path(pth).name, "mode": "whole",
                 "defaultTier": "optional", "regenerable": False, "impactHint": "", "appsRunning": [],
                 "scanLimited": False, "protected": is_protected(pth, cfg, rules), "lastUsed": _last_used(pth)})

    # 大文件夹若已包含其他候选项，就不再整体列出（避免重复计算，也避免把整个项目文件夹当清理目标）
    paths = [os.path.realpath(x["path"]) for x in items]
    items = [x for x, rp in zip(items, paths)
             if x["kind"] != "large-dir" or not any(o != rp and o.startswith(rp + os.sep) for o in paths)]
    for x in items:
        if x["kind"] == "large-dir" and (Path(x["path"]).name in (".git", ".svn", ".hg") or (Path(x["path"]) / ".git").exists()):
            x["defaultTier"] = "keep"
            x["impactHint"] = "版本库/项目仓库，删除会丢失历史记录"

    free, total = disk_status()
    items.sort(key=lambda x: -x["sizeBytes"])
    for i, it in enumerate(items, 1):
        it["id"] = f"c{i:03d}"
        it["mtimeAtScan"] = _stat(it["path"])[0]
    return {"scannedAt": time.time(), "volume": data_volume(), "freeBytes": free, "totalBytes": total,
            "thresholdGB": cfg["thresholdGB"], "items": items}


if __name__ == "__main__":
    import sys
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("candidates.json")
    data = scan()
    out.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"候选 {len(data['items'])} 项 → {out}")
