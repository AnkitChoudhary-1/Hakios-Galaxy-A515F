#!/usr/bin/env python3
import sys
from pathlib import Path
import importlib.util

PROJECT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("p4", str(PROJECT / "scripts/phase4-execute-silicon-trial.py"))
p4 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p4)

rc, out, err = p4.adb_root_shell("cat /proc/iomem")
for line in out.splitlines():
    if any(h in line.lower() for h in ["ca00", "caa0", "cb40", "system ram", "framebuffer", "decon", "display"]):
        print(line)
