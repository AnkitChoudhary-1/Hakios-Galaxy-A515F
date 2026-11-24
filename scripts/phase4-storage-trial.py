#!/usr/bin/env python3
"""Package and run bounded storage-only A51 trials with unconditional rollback."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import uuid

from phase4_device import Device
from phase4_storage import RECOVERY_ROUTE, SUPPORT, StorageCycle, cycle, load
from phase4_support import PROJECT, command, documents, index_packet, new_packet, pin, require, write_json
from samsung_boot_dry_run import reconstruct_in_memory

LOADER_SOURCES = ("pack_a51_payload.py", "a51_loader.S", "a51_loader.ld", "xnu_trampoline.S",
                  "xnu_trampoline.h", "a51_recovery_export.S", "hakios_macho.py", "hakios_devicetree.py")


def linux_path(path):
    path = str(Path(path).resolve()).replace("\\", "/")
    require(re.match(r"^[Cc]:/", path), "Expected this workspace on drive C")
    return "/mnt/c" + path[2:]


def select_result(name):
    path = PROJECT / "manifests" / (name + ".json")
    selected = json.loads(path.read_text(encoding="utf-8"))
    packet = cycle.resolve_file(PROJECT, selected["packet"] + "/result.json").parent
    cycle.verify_packet(packet)
    require(json.loads((packet / "result.json").read_text(encoding="utf-8")) == selected,
            "Selected result differs from its retained packet: " + name)
    return selected, {"path": path.relative_to(PROJECT).as_posix(), **pin(path)}


def prepare(packet):
    require(os.name == "nt", "Run this device harness from Windows")
    require(shutil.disk_usage(PROJECT).free >= 384 * 1048576, "Insufficient space for candidate/evidence")
    build, build_pin = select_result("phase4-platform-build")
    require(build["build_verified"] and build["parent_unchanged"], "Unverified platform build")
    adaptation, provenance = cycle.built_platform_adaptation(build)
    for name, expected in adaptation["source_pins"].items():
        require(pin(PROJECT / "prototype/phase4-platform" / name) == expected, "Built driver template changed: " + name)
    qemu, qemu_pin = select_result("phase4-platform-qemu")
    require(qemu["passed"] and qemu["build_packet"] == build["packet"], "QEMU did not execute this build")
    native, native_pin = select_result("phase4-peripheral-native-tests")
    require(native["passed"] and native["suites"]["ufs"]["passed"], "Shared UFS native tests unpassed")
    for name, expected in native["sources"].items():
        # Native test packets pin the exact shared headers/test programs.
        path = PROJECT / "prototype/phase4-platform" / name
        require(pin(path) == expected, "Native test source drift: " + name)
    tests, tests_pin = select_result("phase4-storage-trial-tests")
    require(tests["passed"] and tests["actual_device_operations"] is False and
            tests["sources"] == {name: pin(PROJECT / "scripts" / name) for name in SUPPORT},
            "Storage harness failure models differ from the current source")
    exporter, exporter_pin = select_result("phase4-recovery-export-qemu")
    require(exporter["passed"] and exporter["device_operations"] is False,
            "Exact recovery exporter QEMU execution is unverified")
    for name, expected in exporter["sources"].items():
        require(pin(PROJECT / name) == expected, "Recovery export source changed: " + name)
    baseline = load("phase4_storage_baseline_pins", PROJECT / "scripts/build-xnu-boot-candidate.py")
    rollback = {}
    for role, path in (("template", baseline.TEMPLATE), ("original_boot", baseline.ORIGINAL_BOOT),
                       ("recovery", baseline.RECOVERY), ("dtbo", baseline.DTBO)):
        baseline.pinned(path, role)
        rollback[role] = {"path": path.relative_to(PROJECT.parent).as_posix(), **pin(path)}
    require(re.fullmatch(r"/opt/a51-hakios/experimental/phase4-port/[0-9]{8}T[0-9]{12}Z", build["root"]),
            "Unrecognized platform build directory")
    root = Path("//wsl.localhost/A51-KernelBuilder" + build["root"])
    for name, expected in build["artifacts"].items():
        require(pin(root / name) == expected, "Built artifact drift: " + name)
    nonce = uuid.uuid4().hex
    cmdline = ("rd=md0 -v cpus=1 serial=3 debug=0x104008 hello_wait=3 loader_return_after=20 "
               "hakios_run_nonce=" + nonce + " hakios_kver=p4-a53-drivers "
               "hakios_a51_diag=1 hakios_a51_mmio=1 hakios_a51_probe=16")
    require(len(cmdline) < 608, "Boot arguments exceed the loader ABI")
    sources = packet / "sources/xnu-loader"
    sources.mkdir(parents=True)
    for name in LOADER_SOURCES:
        shutil.copy2(PROJECT / "prototype/xnu-loader" / name, sources / name)
    records = []
    result = command(packet, records, "kernel-symbols", ["wsl", "-d", "A51-KernelBuilder", "--exec",
        "/usr/lib/llvm-18/bin/llvm-nm", build["root"] + "/hakios-kernel"])
    symbols = re.findall(rb"^([0-9a-f]{16}) [A-Za-z] _loader_log$", result.stdout, re.M)
    require(len(symbols) == 1, "Pinned kernel loader_log symbol missing/duplicate")
    log_va = int(symbols[0], 16)
    log_pa = log_va + 0x80000000 - 0xfffffff004000000
    require(0x80000000 <= log_pa <= 0xc0000000 - 131072, "Loader log address outside bounded DRAM")
    work = "/opt/a51-hakios/experimental/storage-trials/" + packet.name
    argv = ["wsl", "-d", "A51-KernelBuilder", "--exec", "env",
            "PATH=/usr/lib/llvm-18/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin", "python3", "-B",
            linux_path(sources / "pack_a51_payload.py"), "--kernel", build["root"] + "/hakios-kernel",
            "--hello", build["root"] + "/userland/hello", "--output", work + "/a51_xnu_loader.bin",
            "--work-dir", work, "--checkpoint", "0", "--cmdline", cmdline, "--pad-to", "36334080",
            "--recovery-envelope"]
    package = command(packet, records, "package", argv, timeout=120)
    metadata_rows = re.findall(rb"^HAKIOS_PACKAGE_METADATA=(.+)$", package.stdout, re.M)
    require(len(metadata_rows) == 1, "Missing/duplicate assembly package metadata")
    metadata = json.loads(metadata_rows[0])
    require(metadata["capture_route"] == RECOVERY_ROUTE and metadata["checkpoint"] == 0,
            "Assembly package did not enable the verified recovery envelope")
    image_path = Path("//wsl.localhost/A51-KernelBuilder" + work) / "a51_xnu_loader.bin"
    image = image_path.read_bytes()
    require(len(image) == 36334080, "Assembly loader does not fit the qualified kernel slot")
    candidate, reconstruction = reconstruct_in_memory(baseline.TEMPLATE.read_bytes(), image)
    require(len(candidate) == 61865984 and candidate[:8] == b"ANDROID!", "Invalid complete Samsung candidate")
    candidate_path = packet / "candidate-boot.img"
    baseline.write_exclusive(candidate_path, candidate)
    shutil.copy2(image_path, packet / "a51_xnu_loader.bin")
    selected = {"schema_version": 1, "kind": "storage", "route": "historical-assembly-loader",
        "packet": packet.relative_to(PROJECT).as_posix(), "host_prepared": True,
        "device_operations": False, "phase_4_gate_passed": False, "nonce": nonce, "cmdline": cmdline,
        "candidate": {"path": candidate_path.relative_to(PROJECT).as_posix(), **pin(candidate_path)},
        "image": {"path": (packet / "a51_xnu_loader.bin").relative_to(PROJECT).as_posix(), **pin(packet / "a51_xnu_loader.bin")},
        "read_hashes": {"single": hashlib.sha256(candidate[:4096]).hexdigest(),
                        "multi": hashlib.sha256(candidate[:65536]).hexdigest()},
        "log_va": log_va, "log_pa": log_pa, "rollback_pins": rollback,
        "capture_route": RECOVERY_ROUTE, "package_metadata": metadata,
        "record_contract": {name: metadata[name] for name in ("entry_pa", "ba_pa", "checkpoint")},
        "platform_build": build_pin, "platform_qemu": qemu_pin, "native_tests": native_pin,
        "harness_tests": tests_pin, "recovery_export_qemu": exporter_pin, "adaptation_provenance": provenance,
        "kernel_artifacts": build["artifacts"], "package_work_directory": work,
        "source_pins": {name: pin(PROJECT / "scripts" / name) for name in SUPPORT},
        "loader_source_pins": {name: pin(sources / name) for name in LOADER_SOURCES},
        "reconstruction": reconstruction}
    selected["snapshot_contract"] = cycle.snapshot_contract(selected)
    write_json(packet / "result.json", selected)
    index_packet(packet)
    write_json(PROJECT / "manifests/phase4-storage-candidate.json", selected)
    return selected, candidate_path, baseline.TEMPLATE, None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cycles", type=int, default=1)
    parser.add_argument("--seconds", type=int, default=180)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    require(1 <= args.cycles <= 3 and 60 <= args.seconds <= 300, "Invalid cycle/deadline bound")
    packet = new_packet("storage-preflight" if args.preflight_only else "storage-trial", __file__)
    for name in SUPPORT:
        shutil.copy2(PROJECT / "scripts" / name, packet / name)
    result = {"packet": packet.relative_to(PROJECT).as_posix(), "passed": False,
              "preflight_only": args.preflight_only, "cycles_requested": args.cycles, "cycles": [],
              "device_operations": False, "storage_gate_passed": False, "phase_4_gate_passed": False}
    try:
        for i in range(1 if args.preflight_only else args.cycles):
            candidate_packet = new_packet("storage-candidate", __file__)
            selected, candidate, baseline, reader = prepare(candidate_packet)
            if args.preflight_only:
                result.update(passed=True, candidate=selected["packet"], host_prerequisites_passed=True)
                break
            trial = packet / ("cycle-" + str(i + 1))
            trial.mkdir()
            write_json(trial / "selected-candidate.json", selected)
            result["device_operations"] = True
            print("Storage cycle " + str(i + 1) + "/" + str(args.cycles) + ": nonce=" + selected["nonce"], flush=True)
            trial_result = StorageCycle(trial, selected, candidate, baseline, Device(trial),
                                        reader_path=reader, seconds=args.seconds).run()
            write_json(trial / "result.json", trial_result)
            index_packet(trial)
            result["cycles"].append({"result": (trial / "result.json").relative_to(PROJECT).as_posix(),
                **pin(trial / "result.json"), "nonce": selected["nonce"], "passed": trial_result["passed"],
                "baseline_verified": trial_result["baseline_verified"], "error": trial_result.get("error"),
                "restoration_error": trial_result.get("restoration_error")})
            if not trial_result["passed"]:
                result["error"] = trial_result.get("error") or trial_result.get("restoration_error") or "Cycle checks failed"
                break
        if not args.preflight_only:
            result["passed"] = len(result["cycles"]) == args.cycles and all(row["passed"] for row in result["cycles"])
            result["storage_gate_passed"] = result["passed"]
    except Exception as exc:
        result["error"] = str(exc)
    write_json(packet / "result.json", result)
    state = json.loads((PROJECT / "state.json").read_text(encoding="utf-8"))
    state["phase_4_storage_preflight" if args.preflight_only else "phase_4_last_storage_trial"] = {
        "result": (packet / "result.json").relative_to(PROJECT).as_posix(), **pin(packet / "result.json"),
        "passed": result["passed"], "error": result.get("error"), "storage_gate_passed": result["storage_gate_passed"]}
    state["phase_4_status"], state["phase_4_device_gate_passed"] = "in_progress", False
    note = (f"\n\n## P4-034 — Storage-only preflight/silicon trial ({packet.name})\n\n"
        "Purpose/files: scripts/phase4-storage-trial.py and phase4_storage.py. Package a fresh nonce in a unique WSL "
        "directory; pin the tested driver/build/QEMU/exporter and independently hash the candidate's first 4KiB/64KiB. "
        "Prestage the baseline, journal mutations, always attempt restoration after any candidate write, verify "
        "fresh rooted Android and all partition pins. Capture the committed binary pmsg record and complete log "
        "in recovery before Android reuses memory; compare the independent raw console, CRC and nonce. "
        "Validate live ramoops geometry and binary-tail extents, actual "
        "boot nonce/arguments, all three single-descriptor DMA protocols/digests, fatal status and cleanup telemetry.\n\n"
        f"Verification: preflight_only={args.preflight_only}; passed={result['passed']}; "
        f"completed_cycles={len(result['cycles'])}; device_operations={result['device_operations']}; error={result.get('error')}. "
        f"Exact commands, intent/progress and original logs: `{result['packet']}`. Storage-only success cannot complete "
        "the display/input or entire Phase 4 gate.\n\nRollback: preserve every failed packet. If baseline readback is "
        "unverified, keep connected recovery and restore the independent pinned baseline as described in "
        "docs/PHASE-4-DEVICE-PATH.md; never reboot an unverified image. Ignore these isolated candidates to use "
        "the preserved Phase 3 sources. No recovery/DTBO or Android source change is part of this test.\n")
    documents(packet, {"state.json": json.dumps(state, indent=2) + "\n",
        "docs/IMPLEMENTATION-LOG.md": (PROJECT / "docs/IMPLEMENTATION-LOG.md").read_text(encoding="utf-8") + note})
    index_packet(packet)
    write_json(PROJECT / ("manifests/phase4-storage-preflight.json" if args.preflight_only else "manifests/phase4-last-storage-trial.json"), result)
    print(json.dumps(result, indent=2), flush=True)
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
