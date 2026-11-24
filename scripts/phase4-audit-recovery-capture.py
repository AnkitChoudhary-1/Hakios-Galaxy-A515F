#!/usr/bin/env python3
"""Audit an early, bounded GNSS capture route; return to unchanged Android.

No partition writes, firmware changes, memory writes or module loads. Reboots
are journaled and all three baseline partition hashes are checked on return.
"""
from __future__ import annotations

import json
import os
import time

from phase4_device import BASELINE_SHA256, BOOT, Device
from phase4_storage import RAMOOPS_COMMAND, validate_gnss_reservation, validate_ramoops_parameters
from phase4_support import PROJECT, documents, index_packet, new_packet, require, write_json

PINS = {
    BOOT: BASELINE_SHA256,
    "/dev/block/by-name/recovery": "12412e2008d950260cda627ac7a6b8eac954b49ef9db5573a297f67e4fc85999",
    "/dev/block/by-name/dtbo": "41662c61ff3158448935025477a4e29d445823dab2cddafb18ea649c8ea925d6",
}


def main():
    packet = new_packet("recovery-capture-audit", __file__)
    device = Device(packet)
    result = {"packet": packet.relative_to(PROJECT).as_posix(), "passed": False,
              "device_operations": True, "partition_writes": 0, "memory_writes": 0,
              "module_loads": 0, "reboots_attempted": 0, "baseline_verified": False}
    reboot_attempted = False

    def intent(name):
        result["reboots_attempted"] += 1
        with (packet / "intent.jsonl").open("ab") as stream:
            stream.write((json.dumps({"operation": name, "category": "reboots"}) + "\n").encode())
            stream.flush()
            os.fsync(stream.fileno())
        write_json(packet / "progress.json", result)

    def wait(label, recovery):
        started = time.monotonic()
        for i in range(90):
            mode = device.mode(f"{label}-{i:02}")
            if recovery and mode == "recovery":
                return
            if not recovery and mode == "device":
                try:
                    if device.text(f"{label}-completed-{i:02}", "getprop sys.boot_completed", timeout=10) == "1":
                        return
                except Exception:
                    pass
            require(time.monotonic() - started < 180, label + ": reconnection deadline expired")
            time.sleep(2)
        raise ValueError(label + ": polling bound expired")

    def hashes(label, recovery=False):
        for i, (target, expected) in enumerate(PINS.items()):
            actual = device.text(f"{label}-hash-{i}", "sha256sum " + target, recovery=recovery).split()
            require(actual and actual[0] == expected, label + ": partition hash differs: " + target)

    try:
        require(device.mode("initial-state") == "device", "Completed baseline Android is required")
        require(device.text("initial-root", "id").startswith("uid=0(root)"), "Android root unavailable")
        require(device.text("initial-model", "getprop ro.product.model") == "SM-A515F", "Wrong phone model")
        require(device.text("initial-completed", "getprop sys.boot_completed") == "1", "Android boot incomplete")
        result["boot_id_before"] = device.text("initial-boot-id", "cat /proc/sys/kernel/random/boot_id")
        hashes("initial")
        result["gnss_android"] = validate_gnss_reservation(device.root("android-fdt", "cat /sys/firmware/fdt", limit=1048576))
        device.root("android-memory-config", "zcat /proc/config.gz | grep -E 'DEVMEM|DEVKMEM|MODULES|IKCONFIG'", check=False)
        reboot_attempted = True
        intent("reboot-recovery")
        device.adb("reboot-recovery", ["reboot", "recovery"], timeout=20, check=False)
        wait("recovery-return", True)
        require(device.text("recovery-root", "id", recovery=True).startswith("uid=0(root)"), "Recovery root unavailable")
        require(device.text("recovery-model", "getprop ro.product.model", recovery=True) == "SM-A515F", "Wrong recovery model")
        result["recovery_kernel"] = device.text("recovery-kernel", "uname -r", recovery=True)
        result["recovery_boot_id"] = device.text("recovery-boot-id", "cat /proc/sys/kernel/random/boot_id", recovery=True)
        require(result["recovery_boot_id"] != result["boot_id_before"], "Recovery did not start a fresh boot")
        hashes("recovery", True)
        result["ramoops_recovery"] = validate_ramoops_parameters(device.root(
            "recovery-ramoops-parameters", RAMOOPS_COMMAND, recovery=True, limit=4096))
        device.root("recovery-ramoops-init", "dmesg | grep -E 'ramoops|persistent_ram|pstore'",
                    recovery=True, check=False, limit=65536)
        result["gnss_recovery"] = validate_gnss_reservation(device.root("recovery-fdt", "cat /sys/firmware/fdt", recovery=True, limit=1048576))
        for label, command in (
            ("memory-config", "zcat /proc/config.gz | grep -E 'DEVMEM|DEVKMEM|MODULES|IKCONFIG'"),
            ("memory-devices", "ls -l /dev/mem /dev/kmem"),
            ("tools", "command -v dd; command -v devmem; command -v busybox; command -v insmod; command -v rmmod"),
            ("version", "getprop ro.twrp.version"),
        ):
            raw = device.root("recovery-" + label, command, recovery=True, check=False)
            result[label] = raw.decode("utf-8", "replace").strip()
        # Fixed first sixteen GNSS bytes only: no original reusable log mapping.
        device.root("recovery-memory-read", "test -c /dev/mem && dd if=/dev/mem bs=16 skip=263192576 count=1",
                    recovery=True, check=False, limit=4096, timeout=10)
        result["audit_completed"] = True
    except Exception as exc:
        result["error"] = str(exc)
    finally:
        if reboot_attempted:
            try:
                mode = device.mode("return-state")
                if mode not in ("device", "recovery"):
                    wait("return-recovery", True)
                    mode = "recovery"
                if mode == "recovery":
                    hashes("pre-return", True)
                    intent("return-baseline-android")
                    device.adb("return-baseline-android", ["reboot"], timeout=20, check=False)
                wait("android-return", False)
                hashes("final")
                require(device.text("final-root", "id").startswith("uid=0(root)"), "Returned Android root unavailable")
                result["boot_id_after"] = device.text("final-boot-id", "cat /proc/sys/kernel/random/boot_id")
                require(result["boot_id_after"] not in (result["boot_id_before"], result.get("recovery_boot_id")), "Fresh Android return unverified")
                result["baseline_verified"] = True
            except Exception as exc:
                result["return_error"] = str(exc)
        result["passed"] = bool(result.get("audit_completed") and result["baseline_verified"] and
                                "error" not in result and "return_error" not in result)
        write_json(packet / "result.json", result)
        note = (f"\n\n## P4-036 — Audit capture in recovery ({packet.name})\n\n"
                "Purpose/files: scripts/phase4-audit-recovery-capture.py. Audit the recovery kernel, memory interfaces, "
                "fixed live GNSS reservation, exact ramoops geometry and bounded first-16-byte read before Android can overwrite a future payload record. "
                "Journal both reboots; verify unchanged baseline boot/recovery/DTBO hashes and completed rooted Android return. "
                f"Verification: audit_passed={result['passed']}; baseline_verified={result['baseline_verified']}; "
                f"error={result.get('error')}; return_error={result.get('return_error')}; packet `{result['packet']}`. "
                "No partition/memory write, module load or experimental payload. Interface availability alone does not verify "
                "a future log capture. Rollback: return to the pinned unchanged Android; preserve the audit packet.\n")
        documents(packet, {"docs/IMPLEMENTATION-LOG.md": (PROJECT / "docs/IMPLEMENTATION-LOG.md").read_text(encoding="utf-8") + note})
        index_packet(packet)
        write_json(PROJECT / "manifests/phase4-recovery-capture-audit.json", result)
        print(json.dumps(result, indent=2), flush=True)
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
