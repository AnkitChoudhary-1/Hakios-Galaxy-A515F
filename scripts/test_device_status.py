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
print(f"insmod: rc={rc}, out={out.strip()}, err={err.strip()}")

rc, out, err = p4.adb_root_shell("dmesg | tail -n 20")
print(f"dmesg tail:\n{out}")

rc, out, err = p4.adb_root_shell("cat /proc/hakios_dram_log")
print(f"cat /proc/hakios_dram_log: rc={rc}, len={len(out)}")
(PROJECT / "artifacts/hakios_dram_log.txt").write_text(out, encoding="utf-8", errors="replace")

print("\n--- FIRST 40 LINES OF DRAM LOG ---")
for line in out.splitlines()[:40]:
    print(line)

print("\n--- LAST 40 LINES OF DRAM LOG ---")
for line in out.splitlines()[-40:]:
    print(line)
