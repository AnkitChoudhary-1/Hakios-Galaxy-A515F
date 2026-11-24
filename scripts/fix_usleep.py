#!/usr/bin/env python3
import subprocess

SCRIPT = """
path = "/opt/a51-hakios/experimental/phase4-port/20261114T150320411427Z/userland/src/init.c"
with open(path, "r") as f:
    content = f.read()

content = content.replace("sleep(10);", "usleep(5000000);")

with open(path, "w") as f:
    f.write(content)
print("init.c sleep replaced with usleep(5000000)")
"""

def main():
    p = subprocess.run(["wsl", "-d", "A51-KernelBuilder", "python3", "-c", SCRIPT], capture_output=True, text=True)
    print("STDOUT:", p.stdout)
    print("STDERR:", p.stderr)
    return p.returncode

if __name__ == "__main__":
    main()
