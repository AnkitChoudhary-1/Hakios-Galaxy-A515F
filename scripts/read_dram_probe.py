#!/usr/bin/env python3
import subprocess
import sys

push_res = subprocess.run(["adb", "push", "artifacts/early_probe.ko", "/data/local/tmp/early_probe.ko"], capture_output=True, text=True)
print("Push output:", push_res.stdout.strip())

ksu_cmd = """/data/adb/ksu/bin/ksud debug su -g << 'EOF'
setenforce 0
rmmod early_probe 2>/dev/null
insmod /data/local/tmp/early_probe.ko
dmesg | grep -E -i "hakios|klog" | tail -n 60
EOF
"""
res = subprocess.run(["adb", "shell", "su", "-c", ksu_cmd], capture_output=True, text=True, errors="replace")
print("STDOUT:")
print(res.stdout)
print("STDERR:")
print(res.stderr)
