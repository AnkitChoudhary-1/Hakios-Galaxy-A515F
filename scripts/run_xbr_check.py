#!/usr/bin/env python3
import sys
from pathlib import Path
import importlib.util

PROJECT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("p4", str(PROJECT / "scripts/phase4-execute-silicon-trial.py"))
p4 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p4)

p4.adb_root_shell("rmmod early_probe")
rc, out, err = p4.adb_root_shell("insmod /data/local/tmp/early_probe.ko")
print(f"insmod: rc={rc}, err={err.strip()}")

rc, out, err = p4.adb_root_shell("dmesg | grep XBR")
print(out)
