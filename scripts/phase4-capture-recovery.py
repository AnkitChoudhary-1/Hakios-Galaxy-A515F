#!/usr/bin/env python3
"""Retain original recovery observations before independent baseline restoration.

This collector uses an explicit ADB executable and serial. It only reads the
phone; it never mounts filesystems, loads modules, writes partitions or reboots.
Unavailable pstore exports remain recorded failures, not payload evidence.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil

from phase4_device import Device
from phase4_support import PROJECT, index_packet, new_packet, pin, require, write_json

ADB = Path(r"C:\Android\platform-tools\adb.exe")
SERIAL = "A51_SERIAL_HERE"


def main():
    packet = new_packet("baseline-recovery-capture", __file__)
    shutil.copy2(PROJECT / "scripts/phase4_device.py", packet / "phase4_device.py")
    os.environ["PATH"] = str(ADB.parent) + os.pathsep + os.environ.get("PATH", "")
    require(Path(shutil.which("adb") or "").resolve() == ADB.resolve(), "Explicit ADB path unavailable")
    device = Device(packet)
    result = {"packet": packet.relative_to(PROJECT).as_posix(),
              "serial": SERIAL, "phone_queries_performed": True,
              "adb_executable": {"path": str(ADB), **pin(ADB)},
              "phone_writes_performed": False, "reboots_performed": False,
              "module_loads_performed": False, "observations": {},
              "original_exports_attributable": "not_evaluated", "passed": False}

    def root(name, remote_command, optional=False):
        raw = device.root(name, remote_command, recovery=True,
                          timeout=30, limit=1048576, check=not optional)
        record = device.records[-1]
        result["observations"][name] = {"available": record["exit_code"] == 0,
                                        "exit_code": record["exit_code"],
                                        "transport_exit_code": record["transport_exit_code"],
                                        "bytes": len(raw)}
        return raw.decode("utf-8", "replace").strip()

    try:
        require(device.mode("state") == "recovery", "Existing recovery is required")
        require(root("root", "id").startswith("uid=0(root)"), "Recovery root unavailable")
        require(root("model", "getprop ro.product.model") == "SM-A515F", "Wrong model")
        result["recovery_boot_id"] = root("boot-id", "cat /proc/sys/kernel/random/boot_id")
        result["boot_hash_observation"] = root("boot-hash", "sha256sum /dev/block/sda12")
        for name, remote_command in (
            ("pstore-listing", "ls -l /sys/fs/pstore"),
            ("pstore-console", "cat /sys/fs/pstore/console-ramoops-0"),
            ("pstore-pmsg", "cat /sys/fs/pstore/pmsg-ramoops-0"),
            ("recovery-fdt", "cat /sys/firmware/fdt"),
            ("ramoops-init", "dmesg | grep -E 'ramoops|persistent_ram|pstore'"),
        ):
            root(name, remote_command, optional=True)
        result["passed"] = True
    except Exception as exc:
        result["error"] = str(exc)
    finally:
        write_json(packet / "result.json", result)
        index_packet(packet)
        print(json.dumps(result, indent=2), flush=True)
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
