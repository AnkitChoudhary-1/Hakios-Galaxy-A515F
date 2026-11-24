#!/usr/bin/env python3
"""Retain live read-only ramoops facts and matching DMA/pstore references."""
from __future__ import annotations

import json
from pathlib import Path
import shutil

from boot_formats import parse_fdt, strings
from phase4_device import BASELINE_SHA256, BOOT, Device
from phase4_support import PROJECT, documents, index_packet, new_packet, pin, require, write_json

REFERENCES = (
    "fs/pstore/ram.c", "fs/pstore/ram_core.c", "include/linux/pstore_ram.h",
    "drivers/scsi/ufs/ufs-exynos.c", "drivers/scsi/ufs/ufs-exynos.h",
    "drivers/scsi/ufs/ufshcd.c", "drivers/scsi/ufs/ufshci.h",
    "arch/arm64/boot/dts/exynos/exynos9610.dts",
)
PARTITIONS = {
    BOOT: BASELINE_SHA256,
    "/dev/block/by-name/recovery": "12412e2008d950260cda627ac7a6b8eac954b49ef9db5573a297f67e4fc85999",
    "/dev/block/by-name/dtbo": "41662c61ff3158448935025477a4e29d445823dab2cddafb18ea649c8ea925d6",
}


def main():
    packet = new_packet("storage-path-audit", __file__)
    device = Device(packet)
    result = {"packet": packet.relative_to(PROJECT).as_posix(), "passed": False,
              "device_reads": True, "device_writes": False, "reboots": 0,
              "source_references": {}, "parameters": {}, "nodes": {}}
    try:
        require(device.mode("initial-state") == "device", "Completed Android is required")
        require(device.text("initial-root", "id").startswith("uid=0(root)"), "Root unavailable")
        require(device.text("initial-model", "getprop ro.product.model") == "SM-A515F", "Wrong phone")
        require(device.text("initial-completed", "getprop sys.boot_completed") == "1", "Boot incomplete")
        result["boot_id_before"] = device.text("initial-boot-id", "cat /proc/sys/kernel/random/boot_id")
        for i, (target, expected) in enumerate(PARTITIONS.items()):
            require(device.text(f"initial-partition-{i}", "sha256sum " + target).split()[0] == expected,
                    "Baseline partition changed: " + target)
        fdt = device.root("live-fdt", "cat /sys/firmware/fdt", limit=1048576)
        tree = parse_fdt(fdt)
        for path, properties in tree.nodes.items():
            if "ramoops" in path or "ramoops" in strings(properties.get("compatible", b"")):
                result["nodes"][path] = {key: value.hex() for key, value in properties.items()}
        for name in ("mem_address", "mem_size", "record_size", "console_size", "ftrace_size", "pmsg_size", "ecc", "mem_type"):
            result["parameters"][name] = device.root("ramoops-" + name,
                "cat /sys/module/ramoops/parameters/" + name, check=False).decode("ascii", "replace").strip()
        device.root("ramoops-platform", "ls -l /sys/bus/platform/devices/ramoops*", check=False)
        device.root("ramoops-bootargs", "cat /proc/cmdline", limit=8192)
        device.root("ramoops-messages", "dmesg | grep -E 'ramoops|persistent_ram|pstore:'", check=False, limit=65536)
        source = Path("//wsl.localhost/A51-KernelBuilder/opt/a51-everline/src")
        for name in REFERENCES:
            target = packet / "references" / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source / name, target)
            result["source_references"][name] = pin(target)
        result["boot_id_after"] = device.text("final-boot-id", "cat /proc/sys/kernel/random/boot_id")
        require(result["boot_id_before"] == result["boot_id_after"], "Android restarted during read-only audit")
        result["passed"] = True
    except Exception as exc:
        result["error"] = str(exc)
    write_json(packet / "result.json", result)
    note = (f"\n\n## P4-037 — Audit recovery log and DMA source contracts ({packet.name})\n\n"
        "Purpose/files: scripts/phase4-audit-storage-path.py; original live FDT, ramoops parameters, filtered "
        "pstore initialization messages, boot arguments and matching complete Android UFS/pstore/DTS references. "
        "Check the rooted SM-A515F baseline partitions and unchanged Android boot before interpreting "
        "the reservation/capacity. No memory/register write, module load, reboot or source modification. "
        f"Verification: passed={result['passed']}; error={result.get('error')}; packet `{result['packet']}`. "
        "Source behavior is reference evidence only; inherited firmware DMA settings and a new recovery "
        "envelope remain unverified. Rollback: discard this new audit selection; keep all original packets "
        "and Android/HakiOS sources.\n")
    documents(packet, {"docs/IMPLEMENTATION-LOG.md":
        (PROJECT / "docs/IMPLEMENTATION-LOG.md").read_text(encoding="utf-8") + note})
    index_packet(packet)
    write_json(PROJECT / "manifests/phase4-storage-path-audit.json", result)
    print(json.dumps(result, indent=2), flush=True)
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
