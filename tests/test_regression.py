"""Purrge 回归测试：锁住现有行为（v0.2.2），重构和新增功能前后都必须全部通过。
运行：python3 -m unittest discover -s tests -v
每个用例都在临时 HOME / PURRGE_HOME 里的独立子进程中运行，不碰真实的 ~/.purrge、废纸篓和后台任务。"""
import json
import os
import stat
import subprocess
import sys
import tempfile
import textwrap
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LIB = ROOT / "runtime" / "lib"
FAKE = {
    # 假的 claude：记录参数，按 stdin 里的候选清单返回一份 AI 判断
    "claude": r'''#!/usr/bin/env python3
import json, os, re, sys
args = sys.argv[1:]
open(os.environ["FAKE_LOG"], "a").write(json.dumps({"bin": "claude", "args": args}) + "\n")
if args[:2] == ["auth", "status"]:
    print(json.dumps({"loggedIn": True})); sys.exit(0)
if "--version" in args:
    print("9.9.9 (Claude Code)"); sys.exit(0)
src = sys.stdin.read()
m = re.search(r"```json\n(.*)\n```", src, re.S)
items = json.loads(m.group(1)) if m else []
out = {"summary": "测试总结", "items": [{"id": it["id"], "tier": "primary", "title": "AI:" + it["id"], "reason": "AI 理由", "category": "测试"} for it in items]}
mode = os.environ.get("FAKE_MODE", "ok")
if mode == "fail":
    sys.stderr.write("boom"); sys.exit(1)
print(json.dumps({"result": "这是结果：" + json.dumps(out, ensure_ascii=False)}, ensure_ascii=False))
''',
    # 假的 codex：默认模型报"不支持"，换成缓存里的模型才成功
    "codex": r'''#!/usr/bin/env python3
import json, os, sys
args = sys.argv[1:]
open(os.environ["FAKE_LOG"], "a").write(json.dumps({"bin": "codex", "args": args}) + "\n")
if "--version" in args:
    print("codex-cli 9.9.9"); sys.exit(0)
if args[:2] == ["login", "status"]:
    sys.exit(0)
model = args[args.index("-m") + 1] if "-m" in args else ""
if model != "good-model":
    sys.stderr.write('ERROR: {"message":"The model is not supported when using Codex"}'); sys.exit(1)
out = args[args.index("-o") + 1]
sys.stdin.read()
open(out, "w").write("OK")
''',
}


FAKE["codebuddy"] = r'''#!/usr/bin/env python3
import json, os, sys
args = sys.argv[1:]
open(os.environ["FAKE_LOG"], "a").write(json.dumps({"bin": "codebuddy", "args": args}) + "\n")
if "--version" in args:
    print("2.173.0"); sys.exit(0)
sys.stdin.read()
print(json.dumps({"type": "result", "result": "OK"}))
'''
FAKE["dsh"] = r'''#!/usr/bin/env python3
import json, os, sys
args = sys.argv[1:]
open(os.environ["FAKE_LOG"], "a").write(json.dumps({"bin": "dsh", "args": args, "key": os.environ.get("DEEPSEEK_API_KEY", "")}) + "\n")
if "--version" in args:
    print("0.2.1"); sys.exit(0)
if "--dump-config" in args:
    pp = args[args.index("--patch") + 1] if "--patch" in args else ""
    if pp and not os.path.exists(pp):
        sys.stderr.write("patch not found"); sys.exit(2)
    off = bool(pp) and "disabled: true" in open(pp).read()
    for t in ("tool-bash", "tool-pwsh", "tool-jobs", "tool-fs"):
        print(f"- id: {t}\n  name: x" + ("\n  disabled: true" if off else ""))
    sys.exit(0)
sys.stdin.read()
print("OK")
'''


class Env:
    """一个隔离的运行环境：临时 HOME、PURRGE_HOME、假的 AI 命令行。"""

    def __init__(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name) / "home"
        self.home.mkdir()
        self.bin = Path(self.tmp.name) / "bin"
        self.bin.mkdir()
        self.log = Path(self.tmp.name) / "calls.jsonl"
        self.log.write_text("")
        for name, src in FAKE.items():
            p = self.bin / name
            p.write_text(src)
            p.chmod(p.stat().st_mode | stat.S_IEXEC)
        self.extra = {}

    def run(self, code, check=True):
        env = dict(os.environ, HOME=str(self.home), PURRGE_HOME=str(self.home / ".purrge"), FAKE_LOG=str(self.log),
                   PATH=f"{self.bin}{os.pathsep}{os.environ.get('PATH', '')}", PYTHONDONTWRITEBYTECODE="1", **self.extra)
        prog = "import sys, json\nsys.path.insert(0, %r)\n" % str(LIB) + textwrap.dedent(code)
        p = subprocess.run([sys.executable, "-c", prog], capture_output=True, text=True, env=env, timeout=120)
        if check and p.returncode:
            raise AssertionError(p.stderr[-2000:])
        last = [l for l in p.stdout.splitlines() if l.startswith("@@")]
        return json.loads(last[-1][2:]) if last else None

    def calls(self):
        return [json.loads(l) for l in self.log.read_text().splitlines() if l.strip()]

    def close(self):
        self.tmp.cleanup()


class Base(unittest.TestCase):
    def setUp(self):
        self.e = Env()

    def tearDown(self):
        self.e.close()


class TestCleanSafety(Base):
    """清理只处理勾选项；保护名单、mtime 变化、废纸篓、contents 模式。"""

    def make(self):
        h = self.e.home
        (h / "cache/sub").mkdir(parents=True)
        (h / "cache/a.bin").write_bytes(b"x" * 4096)
        (h / "cache/sub/b.bin").write_bytes(b"x" * 4096)
        (h / "big.mov").write_bytes(b"x" * 8192)
        (h / "keep.mov").write_bytes(b"x" * 8192)
        (h / "changed.mov").write_bytes(b"x" * 8192)
        (h / ".claude").mkdir()
        (h / ".claude/settings.json").write_text("{}")
        (h / "notselected.mov").write_bytes(b"x" * 8192)

    def test_clean(self):
        self.make()
        r = self.e.run(r'''
        import os, time
        from pathlib import Path
        from clean import clean
        H = Path.home()
        m = lambda p: os.stat(p).st_mtime
        items = [
          {"id": "c1", "path": str(H/"cache"), "kind": "cache", "mode": "contents", "tier": "primary"},
          {"id": "c2", "path": str(H/"big.mov"), "kind": "large-file", "mode": "whole", "tier": "optional", "mtimeAtScan": m(H/"big.mov")},
          {"id": "c3", "path": str(H/"keep.mov"), "kind": "large-file", "mode": "whole", "tier": "keep", "mtimeAtScan": m(H/"keep.mov")},
          {"id": "c4", "path": str(H/".claude"), "kind": "cache", "mode": "whole", "tier": "primary"},
          {"id": "c5", "path": str(H/"changed.mov"), "kind": "large-file", "mode": "whole", "tier": "optional", "mtimeAtScan": m(H/"changed.mov") - 100},
          {"id": "c6", "path": str(H/"notselected.mov"), "kind": "large-file", "mode": "whole", "tier": "optional", "mtimeAtScan": m(H/"notselected.mov")},
        ]
        out = clean({"items": items}, ["c1", "c2", "c3", "c4", "c5", "ghost"], log=lambda *a: None)
        st = {x["id"]: x["status"] for x in out["results"]}
        print("@@" + json.dumps({"st": st,
          "cache_dir": (H/"cache").is_dir(), "cache_empty": not any((H/"cache").iterdir()),
          "big_gone": not (H/"big.mov").exists(), "big_in_trash": (H/".Trash/big.mov").exists(),
          "keep": (H/"keep.mov").exists(), "claude": (H/".claude/settings.json").exists(),
          "changed": (H/"changed.mov").exists(), "notselected": (H/"notselected.mov").exists(),
          "keys": sorted(out.keys())}))
        ''')
        self.assertEqual(r["st"], {"c1": "deleted", "c2": "trashed", "c3": "skipped", "c4": "skipped", "c5": "skipped", "ghost": "skipped"})
        self.assertTrue(r["cache_dir"] and r["cache_empty"], "contents 模式保留目录本身、清空内容")
        self.assertTrue(r["big_gone"] and r["big_in_trash"], "需要你决定的项目默认移到废纸篓")
        self.assertTrue(r["keep"] and r["claude"] and r["changed"] and r["notselected"])
        self.assertEqual(r["keys"], ["finishedAt", "freeAfter", "freeBefore", "freedBytes", "results"])

    def test_delete_mode(self):
        self.make()
        r = self.e.run(r'''
        import os
        from pathlib import Path
        from common import load_config, save_config
        from clean import clean
        c = load_config(); c["optionalAction"] = "delete"; save_config(c)
        H = Path.home()
        it = {"id": "c2", "path": str(H/"big.mov"), "kind": "large-file", "mode": "whole", "tier": "optional", "mtimeAtScan": os.stat(H/"big.mov").st_mtime}
        out = clean({"items": [it]}, ["c2"], log=lambda *a: None)
        print("@@" + json.dumps({"st": out["results"][0]["status"], "gone": not (H/"big.mov").exists(), "trash": (H/".Trash/big.mov").exists()}))
        ''')
        self.assertEqual(r, {"st": "deleted", "gone": True, "trash": False})


class TestClassify(Base):
    """AI 判断：保护名单强制 keep、用户文件不进首要清理、AI 失败退回规则。"""

    CAND = r'''
    cand = {"items": [
      {"id": "c001", "path": "/x/cache", "sizeBytes": 10, "kind": "cache", "name": "缓存", "defaultTier": "primary", "regenerable": True, "protected": False},
      {"id": "c002", "path": "/x/big.mov", "sizeBytes": 10, "kind": "large-file", "name": None, "defaultTier": "optional", "regenerable": False, "protected": False},
      {"id": "c003", "path": "/x/prot", "sizeBytes": 10, "kind": "cache", "name": "受保护", "defaultTier": "primary", "regenerable": True, "protected": True},
    ]}
    '''

    def test_ai(self):
        r = self.e.run(textwrap.dedent(self.CAND) + textwrap.dedent(r'''
        from common import load_config, save_config
        import shutil
        c = load_config(); c.update(aiEngine="claude", claudePath=shutil.which("claude")); save_config(c)
        from classify import classify
        rv = classify(cand, log=lambda *a: None)
        print("@@" + json.dumps({"by": rv["judgedBy"], "engine": rv.get("engine"), "summary": rv["summary"], "tiers": {x["id"]: x["tier"] for x in rv["items"]}, "title": rv["items"][0]["title"]}))
        '''))
        self.assertEqual(r["by"], "ai")
        self.assertEqual(r["engine"], "Claude Code")
        self.assertEqual(r["tiers"], {"c001": "primary", "c002": "optional", "c003": "keep"})
        self.assertEqual(r["title"], "AI:c001")
        claude = [c for c in self.e.calls() if c["bin"] == "claude" and "-p" in c["args"]][0]["args"]
        for need in ("-p", "--tools", "--no-session-persistence", "--max-turns"):
            self.assertIn(need, claude)
        self.assertEqual(claude[claude.index("--tools") + 1], "", "Claude 必须关掉全部工具")

    def test_fallback(self):
        self.e.extra["FAKE_MODE"] = "fail"
        r = self.e.run(textwrap.dedent(self.CAND) + textwrap.dedent(r'''
        from common import load_config, save_config
        import shutil
        c = load_config(); c.update(aiEngine="claude", claudePath=shutil.which("claude")); save_config(c)
        from classify import classify
        rv = classify(cand, log=lambda *a: None)
        print("@@" + json.dumps({"by": rv["judgedBy"], "tiers": {x["id"]: x["tier"] for x in rv["items"]}}))
        '''))
        self.assertEqual(r, {"by": "rules", "tiers": {"c001": "primary", "c002": "optional", "c003": "keep"}})

    def test_no_engine(self):
        r = self.e.run(textwrap.dedent(self.CAND) + textwrap.dedent(r'''
        from classify import classify
        rv = classify(cand, log=lambda *a: None)
        print("@@" + json.dumps({"by": rv["judgedBy"], "n": len(rv["items"])}))
        '''))
        self.assertEqual(r, {"by": "rules", "n": 3})


class TestEngines(Base):
    def test_codex_readonly_and_model_fallback(self):
        (self.e.home / ".codex").mkdir()
        (self.e.home / ".codex/models_cache.json").write_text(json.dumps({"models": [
            {"slug": "bad-model", "visibility": "list", "priority": 1}, {"slug": "good-model", "visibility": "list", "priority": 2}]}))
        r = self.e.run(r'''
        import engines, shutil
        cfg = {"aiEngine": "codex", "codexPath": shutil.which("codex"), "codexModel": ""}
        print("@@" + json.dumps(list(engines.test(cfg, log=lambda *a: None))))
        ''')
        self.assertEqual(r, [True, "good-model", ""])
        ex = [c["args"] for c in self.e.calls() if c["bin"] == "codex" and "exec" in c["args"]]
        self.assertTrue(all(a[a.index("--sandbox") + 1] == "read-only" and "--ephemeral" in a for a in ex), "Codex 必须只读、不留会话")

    def test_names_and_find(self):
        r = self.e.run(r'''
        import engines
        print("@@" + json.dumps({"names": engines.NAMES, "claude": bool(engines.find("claude")), "codex": bool(engines.find("codex")),
              "logged": [engines.logged_in("claude", engines.find("claude")), engines.logged_in("codex", engines.find("codex"))]}))
        ''')
        self.assertEqual(r["names"]["claude"], "Claude Code")
        self.assertEqual(r["names"]["codex"], "Codex")
        self.assertTrue(r["claude"] and r["codex"])
        self.assertEqual(r["logged"], [True, True])

    def test_unknown_engine(self):
        r = self.e.run(r'''
        import engines
        try:
            engines.ask({"aiEngine": ""}, "hi"); print("@@" + json.dumps("no-error"))
        except engines.AIError:
            print("@@" + json.dumps("AIError"))
        ''')
        self.assertEqual(r, "AIError")


class TestNewEngines(Base):
    def test_workbuddy_no_tools(self):
        r = self.e.run(r'''
        import engines, shutil
        print("@@" + json.dumps(list(engines.test({"aiEngine": "workbuddy", "workbuddyPath": shutil.which("codebuddy")}, log=lambda *a: None))))
        ''')
        self.assertEqual(r, [True, "", ""])
        a = [c["args"] for c in self.e.calls() if c["bin"] == "codebuddy" and "-p" in c["args"]][0]
        self.assertEqual(a[a.index("--tools") + 1], "", "WorkBuddy 必须关掉全部工具")
        self.assertIn("--no-session-persistence", a)

    def test_deepseek_patch_and_key(self):
        r = self.e.run(r'''
        import engines, shutil
        cfg = {"aiEngine": "deepseek", "deepseekPath": shutil.which("dsh")}
        no_key = engines.test(cfg, log=lambda *a: None)
        engines.save_deepseek_key("sk-test")
        import os, stat
        mode = oct(os.stat(engines.SECRETS).st_mode & 0o777)
        print("@@" + json.dumps({"no_key": list(no_key), "ok": list(engines.test(cfg, log=lambda *a: None)), "mode": mode}))
        ''')
        self.assertFalse(r["no_key"][0])
        self.assertEqual(r["ok"], [True, "", ""])
        self.assertEqual(r["mode"], "0o600")
        run = [c for c in self.e.calls() if c["bin"] == "dsh" and "-" in c["args"]][0]
        self.assertIn("--patch", run["args"]); self.assertEqual(run["key"], "sk-test")

    def test_deepseek_refuses_without_patch(self):
        r = self.e.run(r'''
        import engines, shutil
        engines.DSH_PATCH = engines.Path("/nonexistent.yml")
        engines.save_deepseek_key("sk-test")
        print("@@" + json.dumps(list(engines.test({"aiEngine": "deepseek", "deepseekPath": shutil.which("dsh")}, log=lambda *a: None))))
        ''')
        self.assertFalse(r[0]); self.assertIn("工具", r[2])
        self.assertFalse([c for c in self.e.calls() if c["bin"] == "dsh" and "-" in c["args"]], "工具没关掉时绝不能真正调用")

    def test_installer_choice_compat(self):
        r = self.e.run(r'''
        import installer
        res = {}
        for ans in ("", "1", "2", "3", "4", "codex", "9"):
            installer.ask = lambda prompt, default="", a=ans: a or default
            installer.has_tty = lambda: True
            res[ans or "回车"] = installer.choose_engine([])
        print("@@" + json.dumps(res))
        ''')
        self.assertEqual(r, {"回车": "claude", "1": "claude", "2": "codex", "3": "workbuddy", "4": "deepseek", "codex": "codex", "9": "claude"})


class TestConfig(Base):
    def test_defaults(self):
        r = self.e.run(r'''
        from common import load_config
        print("@@" + json.dumps(load_config()))
        ''')
        for k, v in {"thresholdGB": 15, "intervalMinutes": 30, "cooldownHours": 6, "optionalAction": "trash", "protect": [], "aiEngine": ""}.items():
            self.assertEqual(r[k], v, k)

    def test_migrate_v01(self):
        (self.e.home / ".purrge").mkdir()
        (self.e.home / ".purrge/config.json").write_text(json.dumps({"thresholdGB": 20, "claudePath": "/x/claude", "aiModel": "m1"}))
        r = self.e.run(r'''
        from common import load_config
        print("@@" + json.dumps(load_config()))
        ''')
        self.assertEqual((r["aiEngine"], r["claudeModel"], r["thresholdGB"], "aiModel" in r), ("claude", "m1", 20, False))


class TestCLI(Base):
    def cli(self, *args):
        env = dict(os.environ, HOME=str(self.e.home), PURRGE_HOME=str(self.e.home / ".purrge"), FAKE_LOG=str(self.e.log),
                   PATH=f"{self.e.bin}{os.pathsep}{os.environ.get('PATH', '')}")
        return subprocess.run([sys.executable, str(LIB / "dg.py"), *args], capture_output=True, text=True, env=env, timeout=60)

    def test_version_help(self):
        self.assertIn("by RabbittuX", self.cli("version").stdout)
        out = self.cli().stdout
        for cmd in ("install", "scan", "status", "engine", "config", "review", "uninstall"):
            self.assertIn(cmd, out)

    def test_config_set(self):
        out = self.cli("config", "thresholdGB", "20").stdout
        self.assertEqual(json.loads(out)["thresholdGB"], 20)
        self.assertEqual(json.loads((self.e.home / ".purrge/config.json").read_text())["thresholdGB"], 20)

    def test_status(self):
        s = json.loads(self.cli("status").stdout)
        for k in ("free", "total", "thresholdGB", "belowThreshold", "monitor", "intervalMinutes", "lastRun", "ai"):
            self.assertIn(k, s)


class TestScanAndServer(Base):
    def test_scan_shape(self):
        (self.e.home / "Library/Caches/Big").mkdir(parents=True)
        r = self.e.run(r'''
        from scan import scan
        c = scan(progress=lambda *a: None)
        print("@@" + json.dumps({"keys": sorted(c.keys()), "items": c["items"][:3]}))
        ''')
        self.assertTrue({"items", "freeBytes", "totalBytes"} <= set(r["keys"]))

    def test_server(self):
        r = self.e.run(r'''
        import threading, time, urllib.request
        from pathlib import Path
        from common import new_run_dir
        d = new_run_dir()
        (d / "review.json").write_text(json.dumps({"items": [{"id": "c1", "path": str(Path.home()), "kind": "cache"}], "summary": "", "judgedBy": "rules"}))
        from server import serve
        threading.Thread(target=serve, args=(d,), kwargs={"open_browser": False, "log": lambda *a: None}, daemon=True).start()
        for _ in range(50):
            if (d / "review-url.txt").exists(): break
            time.sleep(0.1)
        url = (d / "review-url.txt").read_text(); base = url.split("/?")[0]; tok = url.split("token=")[1]
        def call(p, body=None, token=tok):
            req = urllib.request.Request(base + p, data=json.dumps(body).encode() if body is not None else None, headers={"X-DG-Token": token, "Content-Type": "application/json"})
            try:
                return json.loads(urllib.request.urlopen(req).read())
            except urllib.error.HTTPError as e:
                return {"http": e.code}
        print("@@" + json.dumps({"page": urllib.request.urlopen(url).status, "review": sorted(call("/api/review").keys()),
              "bad": call("/api/review", token="nope"), "reveal_unknown": call("/api/reveal", {"id": "zzz"})}))
        ''')
        self.assertEqual(r["page"], 200)
        self.assertEqual(r["review"], ["config", "freeBytes", "review", "totalBytes"])
        self.assertEqual(r["bad"], {"http": 403})
        self.assertEqual(r["reveal_unknown"], {"ok": False})


if __name__ == "__main__":
    unittest.main()
