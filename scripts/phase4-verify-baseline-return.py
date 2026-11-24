#!/usr/bin/env python3
"""Bounded baseline verification; optional cleanup of a recorded trial's files."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import re
import time
import uuid

from phase4_device import BASELINE_SHA256, BOOT, Device
from phase4_support import PROJECT, index_packet, new_packet, pin, require, write_json

ADB = Path(r"C:\Android\platform-tools\adb.exe")
PINS = {
    BOOT: BASELINE_SHA256,
    "/dev/block/by-name/recovery": "12412e2008d950260cda627ac7a6b8eac954b49ef9db5573a297f67e4fc85999",
    "/dev/block/by-name/dtbo": "41662c61ff3158448935025477a4e29d445823dab2cddafb18ea649c8ea925d6",
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--previous-boot-id", action="append", required=True)
    parser.add_argument("--seconds", type=int, default=240)
    parser.add_argument("--cleanup-trial-result", type=Path)
    args = parser.parse_args()
    require(1 <= args.seconds <= 240, "Return deadline must be at most 240 seconds")
    require(all(str(uuid.UUID(value)) == value for value in args.previous_boot_id), "Invalid prior boot UUID")
    packet = new_packet("baseline-return-verification", __file__)
    shutil.copy2(PROJECT / "scripts/phase4_device.py", packet / "phase4_device.py")
    os.environ["PATH"] = str(ADB.parent) + os.pathsep + os.environ.get("PATH", "")
    require(Path(shutil.which("adb") or "").resolve() == ADB.resolve(), "Explicit ADB path unavailable")
    device = Device(packet)
    result = {"packet": packet.relative_to(PROJECT).as_posix(),
              "previous_boot_ids": args.previous_boot_id, "passed": False,
              "baseline_verified": False, "phone_queries_performed": True,
              "phone_writes_performed": False, "reboots_performed": False,
              "adb_executable": {"path": str(ADB), **pin(ADB)}, "partition_hashes": {}}
    staging_paths = []
    if args.cleanup_trial_result:
        trial = json.loads(args.cleanup_trial_result.read_text(encoding="utf-8"))
        nonce = trial.get("nonce", "")
        require(re.fullmatch(r"[0-9a-f]{32}", nonce), "Invalid recorded trial nonce")
        staging_paths = [f"/data/local/tmp/hakios-p4-baseline-{nonce}.img",
                         f"/data/local/tmp/hakios-p4-{nonce}.img"]
        require(trial.get("serial") == "A51_SERIAL_HERE" and
                trial.get("candidate_write_attempted") is True and
                trial.get("staging_paths") == staging_paths,
                "Trial does not authorize these exact staging paths")
        shutil.copy2(args.cleanup_trial_result, packet / "trial-result.json")
        result["cleanup_trial_result"] = {"path": str(args.cleanup_trial_result), **pin(args.cleanup_trial_result)}
        result["cleanup_staging_paths"] = staging_paths
    started = time.monotonic()
    deadline = started + args.seconds
    try:
        poll = 0
        while True:
            remaining = deadline - time.monotonic()
            require(remaining > 0, "Completed rooted Android return deadline expired")
            mode = device.adb(f"wait-state-{poll:03}", ["get-state"],
                              timeout=min(8, remaining), check=False).decode("ascii", "replace").strip()
            if mode == "device":
                try:
                    completed = device.text(f"wait-completed-{poll:03}", "getprop sys.boot_completed",
                                            timeout=min(8, max(0.1, deadline - time.monotonic())))
                    if completed == "1":
                        break
                except Exception as exc:
                    result["last_wait_error"] = str(exc)
            poll += 1
            time.sleep(min(2, max(0, deadline - time.monotonic())))
        require(device.text("root", "id").startswith("uid=0(root)"), "Android root unavailable")
        require(device.text("model", "getprop ro.product.model") == "SM-A515F", "Wrong Android model")
        require(device.text("boot-target", "readlink -f /dev/block/by-name/boot") == BOOT, "Wrong boot device")
        require(device.text("boot-size", "blockdev --getsize64 " + BOOT) == "61865984", "Wrong boot size")
        boot_id = device.text("boot-id-before", "cat /proc/sys/kernel/random/boot_id")
        require(str(uuid.UUID(boot_id)) == boot_id and boot_id not in args.previous_boot_id,
                "Fresh Android boot UUID unverified")
        result["android_boot_id"] = boot_id
        for i, (target, expected) in enumerate(PINS.items()):
            value = device.text(f"partition-hash-{i}", "sha256sum " + target).split()
            require(value == [expected, target], "Partition pin differs: " + target)
            result["partition_hashes"][target] = value[0]
        require(device.text("boot-completed-after", "getprop sys.boot_completed") == "1", "Android boot incomplete")
        require(device.text("boot-id-after", "cat /proc/sys/kernel/random/boot_id") == boot_id, "Android rebooted during verification")
        result["baseline_verified"] = True
        if staging_paths:
            for i, path in enumerate(staging_paths):
                device.root(f"staging-before-{i}", "ls -ld " + path, check=False)
            result["phone_writes_performed"] = True
            result["staging_cleanup_attempted"] = True
            write_json(packet / "progress.json", result)
            device.root("remove-recorded-staging", "rm -f " + " ".join(staging_paths))
            condition = " && ".join("test ! -e " + path + " && test ! -L " + path for path in staging_paths)
            require(device.text("staging-absent", "if " + condition +
                                "; then printf HAKIOS_STAGING_ABSENT; else exit 1; fi") == "HAKIOS_STAGING_ABSENT",
                    "Recorded staging paths remain")
            result["staging_cleanup_verified"] = True
        result["passed"] = True
    except Exception as exc:
        result["error"] = str(exc)
    finally:
        result["observation_seconds"] = round(time.monotonic() - started, 3)
        write_json(packet / "result.json", result)
        index_packet(packet)
        print(json.dumps(result, indent=2), flush=True)
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
