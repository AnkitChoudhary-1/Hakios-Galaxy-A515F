#!/usr/bin/env python3
"""Run Darwin XNU with virtio-blk and APFS root mount in Exynos QEMU emulator."""
import os
import subprocess
import sys
import time
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
ARTIFACTS_QEMU = PROJECT / "artifacts/qemu"
ARTIFACTS_QEMU.mkdir(parents=True, exist_ok=True)

WSL_PROJECT = "/mnt/c/Users/Ankit/Desktop/A51/hakios-a51"
WSL_REPO = "/opt/a51-hakios/experimental/phase4-port/20261114T150320411427Z"
WSL_KERNEL = f"{WSL_REPO}/hakios-kernel"
WSL_ROOT_APFS = f"{WSL_REPO}/userland/root.apfs"
WSL_SYSTEM_APFS = f"{WSL_REPO}/userland/system.apfs"
WSL_FDT = f"{WSL_PROJECT}/evidence/phase-4/live-inventory/20261114T162645749263Z/live-fdt.stdout.bin"
WSL_PAYLOAD = f"{WSL_PROJECT}/artifacts/qemu/qemu_a51_payload.bin"
WSL_FIRMWARE = f"{WSL_PROJECT}/artifacts/qemu/qemu_firmware.elf"

def run():
    print("=== [1/3] Packing XNU Kernel + root.apfs Payload ===", flush=True)
    cmdline = "rd=md0 -v cpus=1 serial=3 debug=0x104008 hello_wait=3 loader_return_after=30 virtio_blk=1 root_apfs=rvblk0"
    pack_cmd = [
        "wsl", "-d", "A51-KernelBuilder", "--", "bash", "-c",
        f"python3 {WSL_PROJECT}/prototype/xnu-loader/pack_a51_payload.py "
        f"--kernel {WSL_KERNEL} "
        f"--hello {WSL_ROOT_APFS} "
        f"--output {WSL_PAYLOAD} "
        f"--checkpoint 0 "
        f"--cmdline '{cmdline}' "
        f"--pad-to 36334080 "
        f"--recovery-envelope"
    ]
    res = subprocess.run(pack_cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print("Pack error:\n", res.stderr, flush=True)
        return 1
    print(res.stdout, flush=True)

    print("=== [2/3] Compiling QEMU firmware trampoline ===", flush=True)
    compile_cmd = [
        "wsl", "-d", "A51-KernelBuilder", "--", "bash", "-c",
        f"clang --target=aarch64-none-elf -mcpu=cortex-a53 -nostdlib -fuse-ld=lld -Wl,--build-id=none "
        f"-Wl,-Ttext=0x40200000 -DQEMU_IMAGE_BASE=0x80080000 "
        f"{WSL_PROJECT}/prototype/phase4-loader/qemu_firmware.S "
        f"-o {WSL_FIRMWARE}"
    ]
    res = subprocess.run(compile_cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print("Compile error:\n", res.stderr, flush=True)
        return 1
    print(f"Firmware built at {WSL_FIRMWARE}", flush=True)

    print("=== [3/3] Launching QEMU virt (Cortex-A53 + GICv2 + FDT + virtio-blk system.apfs) ===", flush=True)
    qemu_cmd = [
        "wsl", "-d", "A51-KernelBuilder", "--", "bash", "-c",
        f"qemu-system-aarch64 -M virt,gic-version=2,secure=on,virtualization=on "
        f"-cpu cortex-a53 -smp 1 -m 3G -accel tcg,tb-size=384 "
        f"-display none -serial stdio -monitor none -no-reboot "
        f"-device loader,file={WSL_FIRMWARE},cpu-num=0 "
        f"-device loader,file={WSL_PAYLOAD},addr=0x80080000,force-raw=on "
        f"-device loader,file={WSL_FDT},addr=0x8a100000,force-raw=on "
        f"-drive file={WSL_SYSTEM_APFS},format=raw,if=none,id=d,readonly=on "
        f"-device virtio-blk-device,drive=d "
        f"-global virtio-mmio.force-legacy=false"
    ]
    t0 = time.time()
    proc = subprocess.Popen(qemu_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    try:
        # Give QEMU at most 60 seconds
        stdout, _ = proc.communicate(timeout=60)
        for line in stdout.splitlines():
            print(line, flush=True)
    except subprocess.TimeoutExpired:
        proc.kill()
        stdout, _ = proc.communicate()
        for line in stdout.splitlines():
            print(line, flush=True)
        print("\n[TIMEOUT] QEMU did not terminate within 60 seconds.", flush=True)

    elapsed = time.time() - t0
    print(f"\n=== QEMU run finished in {elapsed:.2f}s with exit code {proc.returncode} ===", flush=True)
    return proc.returncode

if __name__ == "__main__":
    sys.exit(run())
