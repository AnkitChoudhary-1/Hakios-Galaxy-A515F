import subprocess
import time
import sys

print("Auto-restore watcher started. Waiting for device in adb...", flush=True)
while True:
    try:
        res = subprocess.run(["adb", "devices"], capture_output=True, text=True)
        lines = res.stdout.splitlines()
        for line in lines:
            if "A51_SERIAL_HERE" in line and ("device" in line or "recovery" in line):
                print(f"Device detected: {line.strip()}", flush=True)
                print("Running restore-baseline-boot.py...", flush=True)
                ret = subprocess.run([sys.executable, "scripts/restore-baseline-boot.py"])
                if ret.returncode == 0:
                    print("Restoration successful! Rebooting device into Android OS...", flush=True)
                    subprocess.run(["adb", "reboot"])
                    sys.exit(0)
    except Exception as e:
        print(f"Error: {e}", flush=True)
    time.sleep(1)
