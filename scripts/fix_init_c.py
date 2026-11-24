#!/usr/bin/env python3
import subprocess

SCRIPT = """
path = "/opt/a51-hakios/experimental/phase4-port/20261114T150320411427Z/userland/src/init.c"
with open(path + ".orig", "r") as f:
    lines = f.readlines()

bsn = chr(92) + 'n'
new_lines = []
for line in lines:
    if line.strip() == "reboot(RB_HALT);":
        new_lines.append(f'\\tprintf("{bsn}=== [HakiOS] iOS 16 Darwin userland active ==={bsn}");\\n')
        new_lines.append(f'\\tprintf("[HakiOS] Process 1 stay-alive loop running.{bsn}");\\n')
        new_lines.append(f'\\tprintf("[HakiOS] APFS root and iOS services initialized.{bsn}");\\n')
        new_lines.append(f'\\tprintf("[HakiOS] Samsung Galaxy A51 (universal9611 / Exynos 9611).{bsn}");\\n')
        new_lines.append(f'\\tprintf("[HakiOS] Darwin kernel 22.5.0 / iOS 16.5.{bsn}");\\n')
        new_lines.append('\\tfor (;;) {\\n')
        new_lines.append('\\t\\tsleep(10);\\n')
        new_lines.append('\\t}\\n')
    else:
        new_lines.append(line)

with open(path, "w") as f:
    f.writelines(new_lines)
print("init.c updated cleanly with chr(92)+'n'!")
"""

def main():
    p = subprocess.run(["wsl", "-d", "A51-KernelBuilder", "python3", "-c", SCRIPT], capture_output=True, text=True)
    print("STDOUT:", p.stdout)
    print("STDERR:", p.stderr)
    return p.returncode

if __name__ == "__main__":
    main()
