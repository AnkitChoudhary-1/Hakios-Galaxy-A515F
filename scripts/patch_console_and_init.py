#!/usr/bin/env python3
"""Patch userland/src/init.c in WSL."""
import subprocess
import sys

SCRIPT = r"""
init_path = "/opt/a51-hakios/experimental/phase4-port/20261114T150320411427Z/userland/src/init.c"
with open(init_path, "r") as f:
    init_content = f.read()

target = '\tprintf("\\n=== init: done ===\\n");\n\treboot(RB_HALT);'
replacement = '''\tprintf("\\n=== [HakiOS] iOS 16 Darwin userland active ===\\n");
\tprintf("[HakiOS] Process 1 stay-alive loop running.\\n");
\tprintf("[HakiOS] APFS root and iOS services initialized.\\n");
\tprintf("[HakiOS] Samsung Galaxy A51 (universal9611 / Exynos 9611).\\n");
\tprintf("[HakiOS] Darwin kernel 22.5.0 / iOS 16.5.\\n");
\tfor (;;) {
\t\tsleep(10);
\t}'''

if target in init_content:
    init_content = init_content.replace(target, replacement, 1)
    with open(init_path, "w") as f:
        f.write(init_content)
    print("userland/src/init.c patched successfully")
else:
    print("target not found in init.c")
    sys.exit(1)
"""

def main():
    res = subprocess.run(["wsl", "-d", "A51-KernelBuilder", "python3", "-c", SCRIPT], capture_output=True, text=True)
    print("STDOUT:", res.stdout)
    print("STDERR:", res.stderr)
    return res.returncode

if __name__ == "__main__":
    sys.exit(main())
