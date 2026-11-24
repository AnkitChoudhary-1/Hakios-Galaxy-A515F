#!/usr/bin/env python3
"""Retain an immutable, repeatable storage-repair checkpoint before edits."""
from __future__ import annotations

import json
import shutil

from phase4_support import PROJECT, documents, index_packet, new_packet, pin, require, write_json

FILES = (
    "prototype/phase4-platform/a51_ufs_readonly.h",
    "prototype/phase4-platform/hakios.a51.c",
    "prototype/phase4-platform/hakios.a51.h",
    "prototype/phase4-platform/hello.c",
    "prototype/phase4-platform/tests/ufs_model.c",
    "diagnostics/storage-reader/Makefile",
    "diagnostics/storage-reader/hakios_storage_reader.c",
    "scripts/phase4-build-storage-reader.py",
    "scripts/phase4_storage.py",
    "scripts/phase4-storage-trial.py",
    "scripts/phase4-test-storage-trial.py",
    "scripts/phase4-revise-platform.py",
    "scripts/phase4-build-platform.py",
    "scripts/phase4-test-peripherals.py",
    "scripts/phase4-qemu-platform.py",
    "scripts/phase4-device-cycle.py",
    "scripts/phase4_device.py",
    "scripts/phase4_support.py",
    "scripts/phase4-checkpoint-storage.py",
    "prototype/xnu-loader/xnu_trampoline.S",
    "prototype/xnu-loader/xnu_trampoline.h",
    "prototype/xnu-loader/a51_recovery_export.S",
    "prototype/xnu-loader/pack_a51_payload.py",
    "README.md", "docs/STATE.md", "docs/INDEX.md", "docs/IMPLEMENTATION-LOG.md", "state.json",
    "manifests/phase4-readonly-revision.json",
    "manifests/phase4-platform-adaptation.json",
    "manifests/phase4-platform-build.json",
    "manifests/phase4-platform-qemu.json",
    "manifests/phase4-peripheral-native-tests.json",
    "manifests/phase4-storage-reader.json",
    "manifests/phase4-storage-trial-tests.json",
    "manifests/phase4-last-storage-trial.json",
)


def main():
    packet = new_packet("storage-repair-checkpoint", __file__)
    selection = PROJECT / "manifests/phase4-storage-repair-checkpoint.json"
    previous = selection.read_bytes() if selection.exists() else None
    result = {"packet": packet.relative_to(PROJECT).as_posix(), "captured": False,
              "device_operations": False, "files": {}}
    try:
        if previous is not None:
            (packet / "previous-selection.json").write_bytes(previous)
            result["previous_selection"] = pin(packet / "previous-selection.json")
        for rel in FILES:
            target = packet / "before" / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(PROJECT / rel, target)
            result["files"][rel] = pin(target)
        require(all(pin(PROJECT / rel) == expected for rel, expected in result["files"].items()),
                "Concurrent change during storage checkpoint")
        result["captured"] = True
    except Exception as exc:
        result["error"] = str(exc)
    write_json(packet / "result.json", result)
    if result["captured"]:
        require((selection.read_bytes() if selection.exists() else None) == previous,
                "Storage checkpoint selection changed concurrently")
        write_json(selection, result)
    note = (f"\n\n## P4-035 — Retain storage repair inputs ({packet.name})\n\n"
        "Purpose/files: scripts/phase4-checkpoint-storage.py; indexed before bytes for the driver, "
        "userland checks, native model, Android reader, cycle parser/harness, selections and documentation. "
        "Coverage now includes the recovery exporter, shared record format and assembly packager; "
        "the previous checkpoint retains the checkpoint script before this expansion. "
        "This supplements the already retained WSL revision without changing historical packets. "
        f"Verification: captured={result['captured']}; error={result.get('error')}; packet `{result['packet']}`. "
        "No build or device operation occurred. Rollback: restore only this packet's indexed before files "
        "after checking pins; keep all hardware evidence and Android images. The repeatable checkpoint "
        "retains an earlier selection instead of overwriting its evidence. Phase 4 remains in progress.\n")
    documents(packet, {"docs/IMPLEMENTATION-LOG.md":
        (PROJECT / "docs/IMPLEMENTATION-LOG.md").read_text(encoding="utf-8") + note})
    index_packet(packet)
    print(json.dumps({k: v for k, v in result.items() if k != "files"}, indent=2), flush=True)
    return 0 if result["captured"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
