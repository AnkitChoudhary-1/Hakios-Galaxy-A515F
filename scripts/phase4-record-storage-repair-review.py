#!/usr/bin/env python3
"""Record the 16 November storage-repair checkpoint without device operations.

This dated review requires its retained before files and exact incident inputs.
Run once through scripts/run.py; its result never qualifies a hardware gate.
"""
import argparse
import datetime as dt
import difflib
import hashlib
import json
import re
import shutil
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
PACKET = "evidence/phase-4/storage-repair-review/20261115T220257860822Z"
OLD = "evidence/phase-4/storage-trial/20261115T193839789423Z/cycle-1"
LAST = "evidence/phase-4/storage-trial/20261115T213856233327Z/cycle-1"
PREFLIGHT = "evidence/phase-4/storage-preflight/20261115T215622069350Z"
READY = "evidence/phase-4/storage-candidate/20261115T215622093064Z"
FAILED_EXPORT = "evidence/phase-4/recovery-export-qemu/20261115T215423978011Z"
GUIDE = "docs/PHASE-4-UFS-REPAIR.md"
SCRIPT = "scripts/phase4-record-storage-repair-review.py"
PINNED_BOOT = "eb30609a62999e3282ac81e0a5e56411ef12ec1a39c107171bf3e01209c7cb67"


def require(value, message):
    if not value:
        raise RuntimeError(message)


def read_json(relative):
    return json.loads((PROJECT / relative).read_text(encoding="utf-8"))


def pin(path):
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1048576), b""):
            size += len(chunk)
            digest.update(chunk)
    return {"bytes": size, "sha256": digest.hexdigest()}


def write_text(relative, text):
    path = PROJECT / relative
    newline = "\r\n" if path.exists() and b"\r\n" in path.read_bytes() else "\n"
    path.write_bytes(text.replace("\n", newline).encode("utf-8"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--adb-run", required=True, help="Retained empty ADB observation")
    args = parser.parse_args()
    folder = PROJECT / PACKET
    require(not (folder / "result.json").exists(), "Dated review already recorded")
    before = read_json(PACKET + "/before-index.json")
    for relative, expected in before.items():
        require(pin(PROJECT / relative) == expected, "Current before bytes changed: " + relative)
        require(pin(folder / "before" / relative) == expected, "Rollback copy changed: " + relative)

    inputs = {}

    def capture(relative, expected=None):
        actual = pin(PROJECT / relative)
        if expected is not None:
            require(actual == {k: expected[k] for k in ("bytes", "sha256")}, "Pin changed: " + relative)
        inputs[relative] = actual

    latest = read_json(LAST + "/result.json")
    old = read_json(OLD + "/result.json")
    require(latest["nonce"] == "25f9798aa52d4763abae651571919914", "Wrong incident")
    require(latest["candidate_write_attempted"] is True and latest["baseline_verified"] is False
            and latest["baseline_restored"] is False, "Restoration status changed")
    require(old["baseline_verified"] is True and old["passed"] is False, "Historical result changed")
    require(read_json("manifests/phase4-last-storage-trial.json")["packet"] == LAST.rsplit("/", 1)[0],
            "A newer hardware selection must be reviewed instead")
    for relative in (LAST + "/result.json", OLD + "/result.json", OLD + "/capture-pstore-console.stdout.bin"):
        capture(relative)
    capture(latest["candidate"]["path"], latest["candidate"])
    capture(old["candidate"]["path"], old["candidate"])
    original = (PROJECT / OLD / "capture-pstore-console.stdout.bin").read_bytes()
    with (PROJECT / old["candidate"]["path"]).open("rb") as stream:
        single_hash = hashlib.sha256(stream.read(4096)).hexdigest()
    single = re.findall(rb"HAKIOS_UFS_TRANSFER name=single[^\r\n]*", original)
    multi = re.findall(rb"HAKIOS_UFS_TRANSFER name=multi[^\r\n]*", original)
    terminal = re.findall(rb"HAKIOS_UFS_TERMINAL name=multi[^\r\n]*", original)
    guard = re.findall(rb"HAKIOS_STORAGE_WRITE_GUARD[^\r\n]*", original)
    require(len(single) == len(multi) == len(terminal) == len(guard) == 1, "Original diagnostic ambiguity")
    require(b"rc=0 ocs=0" in single[0] and single_hash.encode() in single[0], "Independent single hash mismatch")
    require(b"rc=-5 ocs=15" in multi[0] and b"blocks=16" in multi[0]
            and b"sha256=unavailable" in multi[0], "Historical multi result mismatch")
    require(b"is=0x20000 dbr=0x1" in terminal[0], "Bus-fatal observation mismatch")
    require(b"rc=-30 rejected=1 doorbell=0x0 pass=1" in guard[0], "Write guard mismatch")

    candidate = read_json(READY + "/result.json")
    preflight = read_json(PREFLIGHT + "/result.json")
    require(preflight["host_prerequisites_passed"] is True and preflight["device_operations"] is False
            and preflight["candidate"] == READY, "Current preflight mismatch")
    capture(READY + "/result.json")
    capture(PREFLIGHT + "/result.json")
    capture(candidate["candidate"]["path"], candidate["candidate"])
    with (PROJECT / candidate["candidate"]["path"]).open("rb") as stream:
        prefix = stream.read(65536)
    require(candidate["read_hashes"] == {"single": hashlib.sha256(prefix[:4096]).hexdigest(),
            "multi": hashlib.sha256(prefix).hexdigest()}, "Prepared independent hashes changed")
    for key in ("platform_build", "platform_qemu", "native_tests", "harness_tests", "recovery_export_qemu"):
        selection = candidate[key]
        capture(selection["path"], selection)
        selected = read_json(selection["path"])
        require(selected.get("passed", selected.get("build_verified")) is True, "Failed host selection: " + key)
        capture(selected["packet"] + "/result.json")
    for relative, expected in candidate["source_pins"].items():
        capture("scripts/" + relative, expected)
    for relative, expected in candidate["loader_source_pins"].items():
        capture("prototype/xnu-loader/" + relative, expected)
    native = read_json("manifests/phase4-peripheral-native-tests.json")
    for relative, expected in native["sources"].items():
        capture("prototype/phase4-platform/" + relative, expected)
    exporter = read_json("manifests/phase4-recovery-export-qemu.json")
    for relative, expected in exporter["sources"].items():
        capture(relative, expected)
    require(exporter["report"]["cases"] == 74 and exporter["report"]["checks"] == 78166826
            and exporter["report"]["alignment_modes"] == [0, 1], "Exporter execution mismatch")
    harness = read_json("manifests/phase4-storage-trial-tests.json")
    require(harness["case_count"] == len(harness["cases"]) == 118, "Harness selection mismatch")
    trace_path = FAILED_EXPORT + "/alignment-1-exceptions.log"
    trace = (PROJECT / trace_path).read_text(encoding="utf-8")
    require("0x96000061" in trace and "0xf9e9000c" in trace and "0x40201144" in trace,
            "Alignment reproduction mismatch")
    capture(trace_path)
    capture(FAILED_EXPORT + "/result.json")

    adb = read_json(args.adb_run + "/metadata.json")
    require(adb["exit_code"] == 0 and adb["command"][-2:] == ["devices", "-l"], "Wrong ADB observation")
    adb_output = (PROJECT / args.adb_run / "output.log").read_text(encoding="utf-8")
    require("List of devices attached" in adb_output and "A51_SERIAL_HERE" not in adb_output,
            "Phone connection changed; review fresh identity before documenting")
    capture(args.adb_run + "/metadata.json")
    capture(args.adb_run + "/output.log")
    local_date = dt.datetime.now(dt.timezone(dt.timedelta(hours=5, minutes=30))).date().isoformat()
    guide_link = "[UFS repair and required recovery](" + (PROJECT / GUIDE).as_posix() + ")"
    summary = (
        "## Current Phase 4 storage repair — " + local_date + "\n\n"
        "Phase 4 is **IN PROGRESS**. The latest installed storage candidate did not return to recovery; "
        "**boot baseline restoration is unverified**. The phone is absent from the retained ADB observation. "
        "Restore and verify the independent pinned baseline before installing another candidate.\n\n"
        "An older original silicon capture verifies a 4 KiB read and independent SHA-256 match, "
        "then a 64 KiB system bus fatal error (`IS=0x20000`, `rc=-5`, incomplete `OCS=15`). "
        "A genuine single-command 64 KiB read, a contiguous 64 KiB-aligned DMA buffer, fatal-error "
        "telemetry and bounded cleanup are implemented. The DMA alignment explanation remains unverified on hardware. "
        "The separate recovery-exporter alignment defect is reproduced and fixed; 74 QEMU cases pass with "
        "alignment checking both off and on. The corrected exporter is packaged on the host and has not run on this A51.\n\n"
        "Current driver build/QEMU, 74-case UFS native tests, 118-case storage models and corrected host preflight pass. "
        "These do not qualify hardware completion. Older display/brightness/physical-input PASS labels were "
        "superseded by source review. See " + guide_link + " for exact selections, failed-trial nonce, recovery pins and commands."
    )
    for relative in ("README.md", "docs/INDEX.md"):
        text = (PROJECT / relative).read_text(encoding="utf-8")
        start = text.index("## Current Phase 4 hardware investigation")
        end = text.index("\nPhase 1 and Phase 2 remain COMPLETE.", start)
        write_text(relative, text[:start] + summary + "\n" + text[end:])
    text = (PROJECT / "docs/STATE.md").read_text(encoding="utf-8")
    historical = text.index("## Historical state")
    write_text("docs/STATE.md", "# Current state\n\n" + summary + "\n\n"
               "Phases 1–3 retain their selected completion evidence. Phase 5 remains planned. "
               "No overall Phase 4 completion percentage is justified.\n\n" + text[historical:])
    text = (PROJECT / "docs/HANDOFF.md").read_text(encoding="utf-8")
    start = text.index("\nPhase 2 is **COMPLETE**")
    end = text.index("\n## Inspect before resuming", start)
    text = text[:start] + "\n\n" + summary + "\n\nPhases 1–3 are complete for their selected gates. "
    text += "The current user authorized the Phase 4 UFS repair. Older scope/next-action sections below "
    text += "retain their historical context; the current recovery requirement takes precedence.\n" + (PROJECT / "docs/HANDOFF.md").read_text(encoding="utf-8")[end:]
    text = text.replace("## Next authorized scope", "## Historical authorization and next-scope notes", 1)
    write_text("docs/HANDOFF.md", text)
    text = (PROJECT / "docs/PHASE-4-DEVICE-PATH.md").read_text(encoding="utf-8")
    end = text.index("\n## Implementation and provenance")
    write_text("docs/PHASE-4-DEVICE-PATH.md", text.split("\n", 1)[0] + "\n\n" + summary + "\n\n"
               "The corrected C-loader selections and trial commands below describe their original checkpoint. "
               "The storage repair uses the historical Phase 3 assembly route with the corrected exporter. "
               "Use the storage-specific guide for current selections; the independent recovery procedure below still applies.\n"
               + text[end:].replace("## Selected evidence", "## Historical corrected C-loader selections", 1)
               .replace("## Exact rebuild and execution commands", "## Historical C-loader rebuild and execution commands", 1))
    text = (PROJECT / "docs/PHASE-4-COMPLETION-REVIEW.md").read_text(encoding="utf-8")
    write_text("docs/PHASE-4-COMPLETION-REVIEW.md", "# Phase 4 completion review — storage repair checkpoint\n\n"
               + summary + "\n\n**Decision: hardware completion gate unpassed; latest baseline return unverified.**\n\n"
               "## Historical reviews (superseded where they conflict with the checkpoint above)\n\n" + text)

    state = read_json("state.json")
    state.update(updated_date_local=local_date, active_task="Restore pinned baseline, then qualify the genuine 64 KiB UFS repair",
                 phase_4_status="in_progress", phase_4_device_gate_passed=False, device_writes_this_phase=True,
                 next_phase=5, next_phase_status="planned", next_action="independent_pinned_baseline_recovery_and_verified_android_return")
    state["blockers"] = [
        "Latest installed candidate did not reconnect; baseline restoration/readback remains unverified and ADB is absent",
        "64 KiB READ(10) has no qualifying silicon completion/hash; prior capture reports system bus fatal IS=0x20000",
        "64 KiB DMA alignment experiment and corrected exporter hardware return remain unverified",
        "Actual display/brightness and physical touch/key events still lack qualifying evidence",
        "Three consecutive whole-Phase-4 qualifying runs remain pending"]
    state["phase_4_criteria"].update(
        storage_writes_disabled="historical_silicon_write_guard_minus30_doorbell_zero_current_boundary_native_verified",
        baseline_rollback_verified="latest_trial_unverified_25f9798aa52d4763abae651571919914_historical_returns_preserved",
        ufs_read_known_image="historical_4k_single_independent_hash_verified_current_repair_hardware_pending",
        larger_image_loading="unpassed_64k_system_bus_fatal_ocs15_alignment_hypothesis_pending",
        status="in_progress_requires_baseline_recovery_before_next_candidate")
    state["phase_4_readonly_revision"] = {"result": "evidence/phase-4/readonly-platform-revision/20261115T213418804741Z/result.json",
                                          "applied": True, "build_verified": True, "hardware_verified": False}
    state["phase_4_device_status"] = {"status": "baseline_restoration_unverified", "serial": latest["serial"],
        "adb_observation": args.adb_run + "/metadata.json", "adb_mode": "absent", "screen": "unknown",
        "latest_cycle": LAST + "/result.json", "nonce": latest["nonce"], "candidate": latest["candidate"],
        "baseline_restored": False, "baseline_verified": False, "boot_id_before": latest["boot_id_before"],
        "staging_paths": latest["staging_paths"], "baseline_sha256": PINNED_BOOT,
        "physical_recovery_requested": True, "device_write_or_reboot_this_review": False}
    state["phase_4_storage_repair_review"] = {"result": PACKET + "/result.json", "guide": GUIDE,
        "host_checks_passed": True, "storage_gate_passed": False, "phase_4_gate_passed": False,
        "latest_baseline_verified": False, "confirmed_exporter_fix_scope": "qemu_both_alignment_settings",
        "dma_alignment_fix_scope": "implemented_hardware_hypothesis", "device_operations": False}
    state["android_kernelsu_restore"]["historical_snapshot_superseded_by_phase_4_device_status"] = True
    write_text("state.json", json.dumps(state, indent=2) + "\n")
    log = (PROJECT / "docs/IMPLEMENTATION-LOG.md").read_text(encoding="utf-8")
    write_text("docs/IMPLEMENTATION-LOG.md", log + "\n\n## P4-039 — UFS repair and unverified-return reconciliation (" + local_date + ")\n\n"
        "Purpose/files: docs/PHASE-4-UFS-REPAIR.md, README.md, docs/{STATE,INDEX,HANDOFF,PHASE-4-DEVICE-PATH,PHASE-4-COMPLETION-REVIEW}.md, state.json and scripts/phase4-record-storage-repair-review.py. "
        "Reconcile stale summaries with the original single-read/bus-fatal evidence, current host checks and failed latest restoration. "
        "Retain the implemented single-command FMP/64 KiB DMA repair and distinguish its hardware hypothesis from the exporter alignment defect. "
        "The old exporter abort is independently reproduced at ESR 0x96000061/FAR 0xf9e9000c; aligned 32-bit stores preserve the binary format and pass 74 QEMU cases/78,166,826 checks with both alignment settings. "
        "The patched exporter has not run on the A51.\n\n"
        "Verification: this recorded review checks all eight before/rollback pins, matching candidate/source/host selections, independent old 4 KiB and prepared 4 KiB/64 KiB hashes, original fatal/write-guard lines, 118 harness cases and the actual alignment-abort trace. "
        "Current build/QEMU/native/exporter/preflight evidence is reused; no unchanged suite was rerun. Latest nonce 25f9798aa52d4763abae651571919914 failed recovery and both bounded restoration waits. "
        "ADB observation " + args.adb_run + " lists no phone. Report, input pins, document diff and after pins are in " + PACKET + ".\n\n"
        "Limitations/next action: baseline_restored=false and baseline_verified=false remain the latest trial's recorded status. "
        "Physical recovery and independent pinned boot readback are required before another candidate; no new phone write/reboot/build/publication occurred in this documentation review. "
        "Capture original pstore, verify recovery/model/target/size/pins, stage and verify the baseline, restore boot, verify readback before reboot, then require fresh completed rooted Android and known staging cleanup. "
        "Phase 4 and the genuine 64 KiB gate remain unpassed; storage-only success cannot qualify display/input.\n\n"
        "Rollback: verify and restore only " + PACKET + "/before-index.json document/state bytes, remove the newly added guide/review script if undoing this review, and preserve all original evidence. "
        "Exporter before bytes are retained in storage-repair-checkpoint/20261115T215121900466Z; the driver has its indexed adaptation history. "
        "Source/document rollback does not restore a phone partition. Preserve Phase 3, Android projects/backups, recovery, DTBO and userdata.\n")

    after = {}
    for relative in list(before) + [GUIDE, SCRIPT]:
        path = PROJECT / relative
        target = folder / "after" / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
        after[relative] = pin(path)
    patch = []
    for relative in before:
        patch.extend(difflib.unified_diff((folder / "before" / relative).read_text(encoding="utf-8").splitlines(True),
                     (PROJECT / relative).read_text(encoding="utf-8").splitlines(True), fromfile="before/" + relative,
                     tofile="after/" + relative))
    (folder / "documents.patch").write_text("".join(patch), encoding="utf-8")
    for name, value in (("input-pins.json", inputs), ("after-index.json", after)):
        (folder / name).write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    result = {"schema_version": 1, "packet": PACKET, "reviewed_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "passed": True, "scope": "host evidence and documentation reconciliation", "device_operations": False,
        "source_or_binary_changes": False, "input_pin_count": len(inputs), "after_file_count": len(after),
        "before_files_verified": len(before), "single_hash_independently_verified": single_hash,
        "prior_bus_fatal_is": "0x20000", "confirmed_exporter_alignment_fix": "qemu_only",
        "dma_alignment_hardware_verified": False, "latest_trial": LAST + "/result.json",
        "baseline_verified": False, "storage_gate_passed": False, "phase_4_gate_passed": False,
        "next_action": state["next_action"]}
    (folder / "result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
