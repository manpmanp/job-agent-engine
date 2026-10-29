# -*- mode: python ; coding: utf-8 -*-
# Job-search agent engine
# File:    packaging/job_agent.spec
# Purpose: PyInstaller build of the app for people without Python (macOS .app, Windows .exe, Linux binary).
# Author:  manpmanp <manp.node@gmail.com>
# Generated with Claude (Anthropic), under the author's direction and review.
# License: MIT (see LICENSE)
# Version: 0.4.0
# Date:    2026-10-28
#
# Build:  pip install pyinstaller -r requirements.txt && pyinstaller packaging/job_agent.spec
# Output: dist/Job Agent.app (macOS), dist/JobAgent.exe (Windows), dist/JobAgent (Linux)
import os, sys
from PyInstaller.utils.hooks import collect_submodules

ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))
datas = [(os.path.join(ROOT, d), d) for d in
         ("engine/web", "engine/defaults", "engine/templates", "agent", "docs")]
datas += [(os.path.join(ROOT, f), ".") for f in ("requirements.txt", "LICENSE", "README.md")]

a = Analysis([os.path.join(ROOT, "start.py")], pathex=[ROOT], datas=datas,
             hiddenimports=collect_submodules("engine") + ["docx", "openpyxl", "pypdf", "truststore", "certifi"],
             excludes=["tkinter", "playwright"], noarchive=False)
pyz = PYZ(a.pure)

if sys.platform == "darwin":
    exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="JobAgent", console=False)
    coll = COLLECT(exe, a.binaries, a.datas, name="JobAgent")
    app = BUNDLE(coll, name="Job Agent.app", bundle_identifier="local.job-agent-engine",
                 info_plist={"CFBundleShortVersionString": "0.4.2", "LSUIElement": False})
else:
    exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], name="JobAgent",
              console=(sys.platform != "win32"), onefile=True)
