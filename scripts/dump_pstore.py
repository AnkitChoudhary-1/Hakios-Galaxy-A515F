#!/usr/bin/env python3
import sys
from pathlib import Path
import importlib.util

PROJECT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("p4", str(PROJECT / "scripts/phase4-execute-silicon-trial.py"))
p4 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p4)

rc, out, err = p4.adb_root_shell("cat /sys/fs/pstore/console-ramoops-0")
print(f"Console ramoops: rc={rc}, len={len(out)}")
(PROJECT / "artifacts/last_console_ramoops.txt").write_text(out, encoding="utf-8", errors="replace")

rc2, out2, err2 = p4.adb_root_shell("cat /sys/fs/pstore/pmsg-ramoops-0")
print(f"Pmsg ramoops: rc={rc2}, len={len(out2)}")
(PROJECT / "artifacts/last_pmsg_ramoops.txt").write_text(out2, encoding="utf-8", errors="replace")

print("\n=== Console ramoops sample ===")
for line in out.splitlines()[:50]:
    print(line)

print("\n=== Searching for darwin/launchd/xnu/hakios in console ramoops ===")
for line in out.splitlines():
    if any(k in line.lower() for k in ["darwin", "launchd", "xnu", "hakios", "panic", "apfs", "springboard", "backboard"]):
        print(line)
