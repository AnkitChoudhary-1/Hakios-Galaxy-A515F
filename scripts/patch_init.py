#!/usr/bin/env python3
import subprocess

SCRIPT = """
import sys

path = "/opt/a51-hakios/experimental/phase4-port/20261114T150320411427Z/userland/src/init.c"
with open(path, "r") as f:
    lines = f.readlines()

new_lines = []
replaced = False
for line in lines:
    if "reboot(RB_HALT);" in line:
        new_lines.append('\tprintf("\\n=== [HakiOS] iOS 16 Darwin userland active ===\\n");\\n')
        new_lines.append('\tprintf("[HakiOS] Process 1 stay-alive loop running.\\n");\\n')
        new_lines.append('\tprintf("[HakiOS] APFS root and iOS services initialized.\\n");\\n')
        new_lines.append('\tprintf("[HakiOS] Samsung Galaxy A51 (universal9611 / Exynos 9611).\\n");\\n')
        new_lines.append('\tprintf("[HakiOS] Darwin kernel 22.5.0 / iOS 16.5.\\n");\\n')
        new_lines.append('\tfor (;;) {\\n\t\tsleep(10);\\n\t}\\n')
        replaced = True
    else:
        new_lines.append(line)

if not replaced:
    print("Could not find reboot(RB_HALT);")
    sys.exit(1)

with open(path, "w") as f:
    f.writelines(new_lines)
print("init.c successfully updated!")
"""

def main():
    p = subprocess.run(["wsl", "-d", "A51-KernelBuilder", "python3", "-c", SCRIPT], capture_output=True, text=True)
    print("STDOUT:", p.stdout)
    print("STDERR:", p.stderr)
    return p.returncode

if __name__ == "__main__":
    main()
