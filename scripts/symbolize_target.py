import subprocess

cmd = ["wsl", "-d", "A51-KernelBuilder", "llvm-nm", "-n", "/opt/a51-hakios/experimental/phase4-port/20261114T150320411427Z/hakios-kernel"]
res = subprocess.run(cmd, capture_output=True, text=True, check=True)

target = 0xfffffff00744acb4
curr = None
for line in res.stdout.splitlines():
    parts = line.strip().split()
    if len(parts) >= 3:
        try:
            addr = int(parts[0], 16)
        except ValueError:
            continue
        if addr <= target:
            curr = parts
        else:
            print("TARGET:", hex(target))
            print("CONTAINED IN:", curr)
            print("NEXT:", parts)
            break

cmd2 = ["wsl", "-d", "A51-KernelBuilder", "llvm-objdump", "-d",
        "--start-address=" + hex(target - 32),
        "--stop-address=" + hex(target + 32),
        "/opt/a51-hakios/experimental/phase4-port/20261114T150320411427Z/hakios-kernel"]
res2 = subprocess.run(cmd2, capture_output=True, text=True)
print("\nDISASSEMBLY:")
print(res2.stdout)
