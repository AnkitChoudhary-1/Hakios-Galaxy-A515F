#!/usr/bin/env python3
import subprocess

SCRIPT = """
path = "/opt/a51-hakios/experimental/phase4-port/20261114T150320411427Z/xnu-src/xnu-8796.121.2/osfmk/console/video_console.c"
with open(path, "r") as f:
    content = f.read()

# Fix the broken if (c == ' \\n ' || poll)
bad_pattern = "if (c == '\\n' || poll)"
# In case it's literal newline:
lines = content.splitlines()
new_lines = []
skip = False
for i, line in enumerate(lines):
    if "if (c == '" in line and not line.endswith("')"):
        # this is the broken multi-line char
        new_lines.append("\t\t\tif (c == 10 || c == 13 || poll) {")
        skip = True
    elif skip and "' || poll) {" in line:
        skip = False
        continue
    else:
        new_lines.append(line)

fixed_content = "\\n".join(new_lines) + "\\n"
with open(path, "w") as f:
    f.write(fixed_content)
print("video_console.c char check fixed to c == 10 || c == 13 || poll!")
"""

def main():
    p = subprocess.run(["wsl", "-d", "A51-KernelBuilder", "python3", "-c", SCRIPT], capture_output=True, text=True)
    print("STDOUT:", p.stdout)
    print("STDERR:", p.stderr)
    return p.returncode

if __name__ == "__main__":
    main()
