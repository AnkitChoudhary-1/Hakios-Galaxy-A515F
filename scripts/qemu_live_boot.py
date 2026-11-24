#!/usr/bin/env python3
"""Direct, standalone QEMU virt runner for Exynos 9611 Darwin XNU kernel and APFS userland."""
from __future__ import annotations

import argparse
import datetime as dt
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import time

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "prototype/xnu-loader"))

from hakios_devicetree import build_exynos9611_device_tree, DeviceTreeReader, DeviceTreeWriter
from hakios_macho import BootArgs, MachOFile

KERNEL_VIRT_BASE = 0xFFFFFFF004000000
PHYS_BASE        = 0x80000000
SLIDE            = PHYS_BASE - KERNEL_VIRT_BASE

def align(n: int, alignment: int = 65536) -> int:
    return (n + alignment - 1) & -alignment

def main():
    if os.name == "nt":
        script = "/mnt/c" + str(Path(__file__).resolve()).replace("\\", "/")[2:]
        return subprocess.call(["wsl", "-d", "A51-KernelBuilder", "--", "python3", "-B", script, *sys.argv[1:]])

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kernel", type=Path,
                        default=Path("/opt/a51-hakios/experimental/phase4-port/20261114T150320411427Z/hakios-kernel"))
    parser.add_argument("--ramdisk", type=Path,
                        default=Path("/opt/a51-hakios/experimental/phase4-port/20261114T150320411427Z/userland/root.apfs"))
    parser.add_argument("--apfs-disk", type=Path,
                        default=Path("/opt/a51-hakios/experimental/phase4-port/20261114T150320411427Z/userland/system.apfs"))
    parser.add_argument("--cmdline", type=str,
                        default="rd=md0 -v cpus=1 serial=3 debug=0x104008 hello_wait=3 loader_return_after=25 virtio_blk=1 root_apfs=rvblk0")
    parser.add_argument("--seconds", type=int, default=35)
    args = parser.parse_args()

    work_dir = Path("/tmp/qemu_live_boot")
    if work_dir.exists():
        shutil.rmtree(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)

    print("===================================================================", flush=True)
    print("=== LIVE EXYNOS 9611 DARWIN XNU QEMU RUNNER ===", flush=True)
    print("===================================================================", flush=True)
    print(f"  Kernel:   {args.kernel} ({args.kernel.stat().st_size} bytes)", flush=True)
    print(f"  Ramdisk:  {args.ramdisk} ({args.ramdisk.stat().st_size} bytes)", flush=True)
    print(f"  APFS Disk:{args.apfs_disk} ({args.apfs_disk.stat().st_size} bytes)", flush=True)
    print(f"  Cmdline:  {args.cmdline}", flush=True)

    # 1. Parse Mach-O kernel
    raw = bytearray(args.kernel.read_bytes())
    macho = MachOFile(raw)
    slot = macho.find_loader_stub_slot()
    if not slot or not macho.entry_point_va:
        print("ERROR: Kernel missing entry point or stub slot", file=sys.stderr)
        return 1

    ranges = [(s.vmaddr + SLIDE, s.vmaddr + SLIDE + s.vmsize) for s in macho.segments if s.vmsize]
    ramdisk_pa = align(max(b for a, b in ranges))
    rd_bytes = args.ramdisk.read_bytes()
    ramdisk_size = align(len(rd_bytes), 4096)
    ba_pa = align(ramdisk_pa + ramdisk_size)
    dt_pa = ba_pa + 0x10000

    # 2. Build Apple Device Tree for QEMU virt
    tree = DeviceTreeReader(build_exynos9611_device_tree(ramdisk_pa=ramdisk_pa,
                                                         ramdisk_size=ramdisk_size,
                                                         timebase_hz=62500000)).root
    writer = DeviceTreeWriter()
    overrides = {
        "/arm-io": {"ranges": struct.pack("<QQQQ", 0, 0x08000000, 0x10000000, 0)},
        "/arm-io/gic": {"reg": struct.pack("<QQQQ", 0, 0x1000, 0x10000, 0x1000)},
        "/arm-io/uart0": {"reg": struct.pack("<QQ", 0x01000000, 0x1000), "compatible": b"arm,pl011\0"},
        "/pram": {"reg": struct.pack("<QQ", 0x8f000000, 0x80000)},
        "/chosen": {"random-seed": os.urandom(64)},
    }

    def emit(node, path):
        writer.begin_node(node["name"])
        values = dict(node["props"], **overrides.get(path, {}))
        for key, value in values.items():
            if key != "name":
                writer.add_prop(key, value)
        for child in node["children"]:
            emit(child, path + "/" + child["name"])
        writer.end_node()

    emit(tree, "")
    dt_blob = writer.finish()
    top = align(dt_pa + len(dt_blob))

    ba = BootArgs(physBase=0x80000000, virtBase=0xFFFFFFF004000000, memSize=0x40000000,
                  topOfKernelData=top, deviceTreeP=dt_pa - SLIDE, deviceTreeLength=len(dt_blob),
                  commandLine=args.cmdline)

    # 3. Compile entry trampoline
    qemu_entry_src = PROJECT / "prototype/phase4-platform/qemu_entry.S"
    entry_elf = work_dir / "entry.elf"
    env = dict(os.environ, PATH="/usr/lib/llvm-18/bin:" + os.environ["PATH"])
    compile_cmd = [
        "clang", "--target=aarch64-none-elf", "-mcpu=cortex-a53", "-nostdlib", "-fuse-ld=lld",
        "-Wl,-Ttext=0x80080000", "-Wl,--build-id=none",
        f"-DQEMU_STACK_PA=0x{top + 0x20000:x}",
        f"-DQEMU_BOOTARGS_PA=0x{ba_pa:x}",
        f"-DQEMU_XNU_ENTRY_PA=0x{macho.entry_point_va + SLIDE:x}",
        str(qemu_entry_src), "-o", str(entry_elf)
    ]
    subprocess.run(compile_cmd, env=env, check=True)

    nm_out = subprocess.check_output(["llvm-nm", str(entry_elf)], env=env, text=True)
    return_pa = int(next(line.split()[0] for line in nm_out.splitlines() if line.endswith(" qemu_loader_return")), 16)
    struct.pack_into("<3Q", raw, slot[0] + 8, return_pa, 0, SLIDE & ((1 << 64) - 1))

    # 4. Prepare QEMU memory devices
    devices = [f"loader,file={entry_elf},cpu-num=0"]
    for i, seg in enumerate(macho.segments):
        if not seg.vmsize:
            continue
        data = bytes(raw[seg.fileoff:seg.fileoff + seg.filesize]) + bytes(seg.vmsize - seg.filesize)
        seg_file = work_dir / f"seg-{i}.bin"
        seg_file.write_bytes(data)
        devices.append(f"loader,file={seg_file},addr=0x{seg.vmaddr + SLIDE:x},force-raw=on")

    for name, pa, data in (("bootargs.bin", ba_pa, ba.pack()),
                            ("devicetree.bin", dt_pa, dt_blob),
                            ("ramdisk.bin", ramdisk_pa, rd_bytes)):
        blob_file = work_dir / name
        blob_file.write_bytes(data)
        devices.append(f"loader,file={blob_file},addr=0x{pa:x},force-raw=on")

    # 5. Launch QEMU
    argv = [
        "qemu-system-aarch64",
        "-M", "virt,gic-version=2,secure=on,virtualization=on",
        "-cpu", "cortex-a53",
        "-smp", "1",
        "-m", "3G",
        "-accel", "tcg,tb-size=384",
        "-display", "none",
        "-serial", "stdio",
        "-monitor", "none",
        "-no-reboot"
    ]
    for d in devices:
        argv += ["-device", d]

    if args.apfs_disk and args.apfs_disk.is_file():
        argv += [
            "-drive", f"file={args.apfs_disk},format=raw,if=none,id=d,readonly=on",
            "-device", "virtio-blk-device,drive=d",
            "-global", "virtio-mmio.force-legacy=false"
        ]

    print("\n--- Starting QEMU Execution ---", flush=True)
    t0 = time.time()
    proc = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=env)
    try:
        stdout, _ = proc.communicate(timeout=args.seconds)
        for line in stdout.splitlines():
            print(line, flush=True)
    except subprocess.TimeoutExpired:
        proc.kill()
        stdout, _ = proc.communicate()
        for line in stdout.splitlines():
            print(line, flush=True)
        print(f"\n[TIMEOUT] QEMU reached deadline ({args.seconds}s)", flush=True)

    elapsed = time.time() - t0
    print(f"\n--- QEMU Exited after {elapsed:.2f}s with code {proc.returncode} ---", flush=True)
    return proc.returncode

if __name__ == "__main__":
    sys.exit(main())
