#!/usr/bin/env python3
"""Record retained baseline restoration and a completed retry; no device actions."""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
import re
import shutil

from phase4_storage import cycle
from phase4_support import PROJECT, documents, index_packet, new_packet, pin, require, write_json

BASELINE = "eb30609a62999e3282ac81e0a5e56411ef12ec1a39c107171bf3e01209c7cb67"
PARTITION_PINS = {
    "/dev/block/sda12": BASELINE,
    "/dev/block/by-name/recovery": "12412e2008d950260cda627ac7a6b8eac954b49ef9db5573a297f67e4fc85999",
    "/dev/block/by-name/dtbo": "41662c61ff3158448935025477a4e29d445823dab2cddafb18ea649c8ea925d6",
}
OLD_TRIAL = "evidence/phase-4/storage-trial/20261115T213856233327Z/cycle-1/result.json"
FIRST_CAPTURE = "evidence/phase-4/baseline-recovery-capture/20261116T010624908001Z"
CAPTURE = "evidence/phase-4/baseline-recovery-capture/20261116T010854001746Z"
RETURN = "evidence/phase-4/baseline-return-verification/20261116T011720900876Z"
RUNS = {
    "staged_hash": "20261116T011108211252Z-p4-independent-recovery-staged-hash",
    "write": "20261116T011122003038Z-p4-independent-recovery-restore-boot",
    "readback": "20261116T011457478817Z-p4-independent-recovery-boot-readback",
    "reboot": "20261116T011526544710Z-p4-independent-recovery-return-android",
}
SUMMARIES = ("README.md", "docs/STATE.md", "docs/INDEX.md", "docs/HANDOFF.md",
             "docs/PHASE-4-DEVICE-PATH.md", "docs/PHASE-4-COMPLETION-REVIEW.md")
GUIDE = "docs/BASELINE-RESTORATION-20261116.md"
UFS_GUIDE = "docs/PHASE-4-UFS-REPAIR.md"
LINK_ROOT = "/C:/Users/Ankit/Desktop/A51/hakios-a51/"
HOSTS = {
    "native": "evidence/phase-4/peripheral-native-tests/20261116T010350110512Z",
    "build": "evidence/phase-4/platform-build/20261115T213458578092Z",
    "qemu": "evidence/phase-4/platform-qemu/20261116T010427975972Z",
    "storage_models": "evidence/phase-4/storage-trial-tests/20261115T212706751122Z",
    "exporter": "evidence/phase-4/recovery-export-qemu/20261115T215525223262Z",
    "preflight": "evidence/phase-4/storage-preflight/20261116T012234119779Z",
}


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def retained_packet(relative):
    packet = PROJECT / relative
    cycle.verify_packet(packet)
    return read_json(packet / "result.json")


def latest_observations(latest, packet):
    """Replay the original command bytes, including framing and restoration order."""
    rows = read_json(packet / "commands.json")
    records = {row["name"]: row for row in rows}
    require(len(records) == len(rows), "Duplicate latest command name")
    inputs = [(packet / "commands.json").relative_to(PROJECT).as_posix()]

    def command(name, remote_exit=0, framed=True):
        require(name in records, "Missing original latest command: " + name)
        row = records[name]
        require(row["argv"][:3] == ["adb", "-s", latest["serial"]] and
                row["exit_code"] == remote_exit and row["transport_exit_code"] == 0 and
                row["framed_remote_exit"] is framed, "Latest command status differs: " + name)
        for kind in ("stdout", "stderr"):
            path = packet / (name + "." + kind + ".bin")
            require(pin(path) == row[kind], "Latest command output pin differs: " + name)
            inputs.append(path.relative_to(PROJECT).as_posix())
        raw = (packet / (name + ".stdout.bin")).read_bytes()
        if framed:
            path = packet / (name + ".frame.bin")
            frame = path.read_bytes()
            footer = re.search(rb"\nHAKIOS_REMOTE_EXIT:([0-9]{1,3})\n$", frame)
            require(footer and int(footer[1]) == remote_exit and frame[:footer.start()] == raw,
                    "Latest remote framing differs: " + name)
            inputs.append(path.relative_to(PROJECT).as_posix())
        return raw.decode("utf-8").strip()

    require(command("capture-pstore-files") == "total 0", "Latest pstore was not empty")
    for name in ("capture-pstore-console", "capture-pstore-pmsg"):
        require(command(name, remote_exit=1) == "", "Unexpected latest export bytes")
    require(command("capture-boot-id") == latest["recovery_boot_id"], "Latest recovery UUID differs")
    observed = {"recovery_exports": "unavailable_framed_remote_exit_1_transport_exit_0_zero_stdout",
                "pstore_listing": "total 0", "baseline_return_replayed": False}
    if latest["baseline_restored"] and latest["baseline_verified"]:
        staged = "/tmp/hakios-p4-baseline-" + latest["nonce"] + "-0.img"
        require(command("stage-baseline-0-hash").split() == [BASELINE, staged], "Wrong latest staged baseline")
        command("restore-baseline-0")
        require(records["restore-baseline-0"]["argv"][-1].startswith(
            "{ dd if=" + staged + " of=/dev/block/sda12 bs=4096 conv=fsync; };"), "Wrong latest boot write")
        require(command("restore-baseline-0-readback").split() == [BASELINE, "/dev/block/sda12"],
                "Wrong latest baseline readback")
        command("return-baseline-android", framed=False)
        require(records["return-baseline-android"]["argv"] == ["adb", "-s", latest["serial"], "reboot"],
                "Wrong latest Android reboot")
        ordered = ("stage-baseline-0-hash", "restore-baseline-0", "restore-baseline-0-readback",
                   "return-baseline-android", "final-root")
        for earlier, later in zip(ordered, ordered[1:]):
            require(dt.datetime.fromisoformat(records[earlier]["finished"]) <
                    dt.datetime.fromisoformat(records[later]["started"]), "Latest restoration order differs")
        require(command("final-root").startswith("uid=0(root)"), "Latest Android root unverified")
        require(command("final-model") == "SM-A515F", "Wrong latest Android model")
        require(command("final-boot-target") == "/dev/block/sda12" and
                command("final-boot-size") == "61865984", "Wrong latest boot target/size")
        require(command("final-completed") == "1", "Latest Android boot incomplete")
        for role, target in zip(("template", "recovery", "dtbo"), PARTITION_PINS):
            require(command("final-hash-" + role).split() == [PARTITION_PINS[target], target],
                    "Wrong latest final partition hash: " + role)
        boot_id = command("final-boot-id")
        require(cycle.UUID.fullmatch(boot_id) and boot_id == latest["boot_id_after"] and
                boot_id not in (latest["boot_id_before"], latest["recovery_boot_id"]), "Latest Android UUID not fresh")
        expected_staging = ["/data/local/tmp/hakios-p4-baseline-" + latest["nonce"] + ".img",
                            "/data/local/tmp/hakios-p4-" + latest["nonce"] + ".img", staged]
        require(latest["staging_paths"] == expected_staging, "Latest staging paths differ")
        for remote in expected_staging:
            matches = [row for row in rows if row["name"].startswith("remove-") and
                       ("test ! -e " + remote + " && test ! -L " + remote) in row["argv"][-1] and
                       dt.datetime.fromisoformat(row["started"]) >
                       dt.datetime.fromisoformat(records["final-boot-id"]["finished"])]
            require(len(matches) == 1, "Latest final staging absence unverified: " + remote)
            command(matches[0]["name"])
        require(latest["checks"].get("all_staging_absent") and
                latest["checks"].get("baseline_boot_root_and_unchanged_recovery_dtbo"), "Latest return checks differ")
        observed.update(baseline_return_replayed=True, android_boot_id=boot_id,
                        partition_hashes=PARTITION_PINS, staging_cleanup_verified=True)
    return observed, inputs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--latest-trial-result", type=Path, required=True)
    parser.add_argument("--latest-run", type=Path, required=True)
    args = parser.parse_args()
    latest_path = args.latest_trial_result.resolve()
    require(latest_path.is_relative_to(PROJECT / "evidence/phase-4/storage-trial"), "Wrong trial root")
    run_path = args.latest_run.resolve()
    require(run_path.is_relative_to(PROJECT / "runs"), "Wrong run root")
    run = read_json(run_path / "metadata.json")
    require(run["status"] in ("passed", "failed") and "finished" in run, "Retry is still running")
    require("scripts/phase4-storage-trial.py" in run["command"] and
            Path(run["cwd"]).resolve() == PROJECT, "Wrong retry command/workspace")
    # Pins come from the exact bytes used to construct replacements, before any
    # validation or rendering can give another writer time to change them.
    originals = {name: (PROJECT / name).read_bytes() if (PROJECT / name).exists() else None
                 for name in (*SUMMARIES, UFS_GUIDE, GUIDE, "state.json", "docs/IMPLEMENTATION-LOG.md")}
    before = {name: {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()} if raw is not None else None
              for name, raw in originals.items()}
    require(originals[GUIDE] is None, "Restoration guide already exists; review newer state")

    def original_text(name):
        require(originals[name] is not None, "Missing current document: " + name)
        return originals[name].decode("utf-8").replace("\r\n", "\n")

    latest = retained_packet(latest_path.parent.relative_to(PROJECT).as_posix())
    trial_root = retained_packet(latest_path.parent.parent.relative_to(PROJECT).as_posix())
    require(latest["case"] == "storage" and latest["serial"] == "A51_SERIAL_HERE" and
            latest["candidate_write_attempted"] and not latest["passed"] and
            not latest["storage_gate_passed"] and not trial_root["passed"] and run["exit_code"] == 1,
            "This review requires the retained failed storage retry")
    observed, command_inputs = latest_observations(latest, latest_path.parent)
    first_capture = retained_packet(FIRST_CAPTURE)
    capture = retained_packet(CAPTURE)
    returned = retained_packet(RETURN)
    old_pin = {"bytes": 2361, "sha256": "2f6b211c418feccaeafb15b196766c362199b0894091c6163b044f1d7d6ae080"}
    require(pin(PROJECT / OLD_TRIAL) == old_pin, "Historical failed result changed")
    require(capture["passed"] and not capture["phone_writes_performed"], "Recovery capture is invalid")
    require(capture["recovery_boot_id"] == "412c0f92-31a3-4ad9-93d8-9c33a9e000d5" and
            first_capture["recovery_boot_id"] == capture["recovery_boot_id"], "Wrong independent recovery UUID")
    for name in ("pstore-console", "pstore-pmsg"):
        observation = capture["observations"][name]
        require(not observation["available"] and observation["exit_code"] == 1 and
                observation["transport_exit_code"] == 0, "Missing export was misclassified")
        require(first_capture["observations"][name]["available"], "Superseded collector status differs")
    require(returned["passed"] and returned["baseline_verified"] and returned["staging_cleanup_verified"],
            "Independent Android baseline/cleanup was not verified")
    require(returned["cleanup_trial_result"]["sha256"] == old_pin["sha256"], "Wrong cleaned trial")
    require(returned["partition_hashes"] == PARTITION_PINS, "Wrong independent partition pins")
    require(returned["android_boot_id"] == "d08d8255-bc1a-4168-b3d5-0f038d70617c", "Wrong Android return")
    restore_runs = {}
    for role, name in RUNS.items():
        path = PROJECT / "runs" / name
        metadata = read_json(path / "metadata.json")
        require(metadata["status"] == "passed" and metadata["exit_code"] == 0, "Failed restore step: " + role)
        restore_runs[role] = metadata
    for role in ("staged_hash", "readback"):
        require((PROJECT / "runs" / RUNS[role] / "output.log").read_text(encoding="utf-8").split()[0] == BASELINE,
                "Wrong restore hash: " + role)
    require(restore_runs["staged_hash"]["finished"]["utc"] < restore_runs["write"]["started"]["utc"] and
            restore_runs["write"]["finished"]["utc"] < restore_runs["readback"]["started"]["utc"] and
            restore_runs["readback"]["finished"]["utc"] < restore_runs["reboot"]["started"]["utc"],
            "Required stage/write/readback/reboot order is unverified")
    write_args = restore_runs["write"]["command"]
    require(write_args[-4:] == ["if=/tmp/hakios-p4-baseline-manual-restore.img", "of=/dev/block/sda12",
                               "bs=4096", "conv=fsync"], "Unexpected restoration write")
    hosts = {role: retained_packet(path) for role, path in HOSTS.items()}
    for role, host in hosts.items():
        require(host.get("build_verified" if role == "build" else "passed") and
                not host.get("device_operations", False), "Host selection failed: " + role)
    require(hosts["native"]["suites"]["ufs"]["cases"] == 74 and
            len(hosts["storage_models"]["cases"]) == 118 and
            all(case["passed"] for case in hosts["storage_models"]["cases"]) and
            hosts["exporter"]["report"]["cases"] == 74 and
            hosts["exporter"]["report"]["alignment_modes"] == [0, 1], "Host coverage differs")
    for role, root in (("native", "prototype/phase4-platform"), ("storage_models", "scripts"), ("exporter", "")):
        for name, expected in hosts[role]["sources"].items():
            require(pin(PROJECT / root / name) == expected, "Retained host source changed: " + name)
    for name, retained in (("phase4-capture-recovery.py", CAPTURE), ("phase4-verify-baseline-return.py", RETURN)):
        require(pin(PROJECT / "scripts" / name) == pin(PROJECT / retained / "source.py"),
                "Helper differs from its executed snapshot: " + name)
    current_verified = latest["baseline_restored"] and latest["baseline_verified"]
    require(current_verified and observed["baseline_return_replayed"],
            "This restoration review requires verified original latest-return commands")
    storage_verified = latest.get("storage_gate_passed", False)
    packet = new_packet("baseline-restoration-review", __file__)
    for name in ("phase4-capture-recovery.py", "phase4-verify-baseline-return.py"):
        shutil.copy2(PROJECT / "scripts" / name, packet / name)
    inputs = [OLD_TRIAL, FIRST_CAPTURE + "/result.json", FIRST_CAPTURE + "/index.json",
              CAPTURE + "/result.json", CAPTURE + "/index.json", RETURN + "/result.json",
              RETURN + "/index.json", latest_path.relative_to(PROJECT).as_posix(),
              (latest_path.parent / "index.json").relative_to(PROJECT).as_posix(),
              (latest_path.parent.parent / "result.json").relative_to(PROJECT).as_posix(),
              (latest_path.parent.parent / "index.json").relative_to(PROJECT).as_posix(),
              (run_path / "metadata.json").relative_to(PROJECT).as_posix()]
    inputs.extend(command_inputs)
    for path in HOSTS.values():
        inputs.extend([path + "/result.json", path + "/index.json"])
    for name in RUNS.values():
        inputs.extend(["runs/" + name + "/metadata.json", "runs/" + name + "/output.log"])
    result = {"packet": packet.relative_to(PROJECT).as_posix(), "passed": True, "device_operations": False,
              "historical_independent_baseline_verified": True, "historical_staging_cleanup_verified": True,
              "latest_baseline_verified": bool(current_verified), "storage_gate_passed": bool(storage_verified),
              "phase_4_gate_passed": False, "latest_trial": latest_path.relative_to(PROJECT).as_posix(),
              "latest_nonce": latest["nonce"], "latest_observations": observed,
              "host_selections": HOSTS, "document_input_pins": before,
              "inputs": {name: pin(PROJECT / name) for name in inputs}}
    write_json(packet / "result.json", result)
    current_sentence = ("The latest retry also restored the pinned boot image and returned to completed rooted "
                        "Android with unchanged recovery/DTBO and verified staging cleanup.")
    next_action = "Investigate the failed recovery log capture before another storage candidate."
    summary = ("Phase 4 is **IN PROGRESS**. The independent baseline restoration succeeded on 16 November: "
        "boot readback passed before reboot, completed rooted Android returned, recovery/DTBO hashes matched, and "
        "both prior failed-trial staging files were removed. " + current_sentence + "\n\n"
        "The repaired **64 KiB UFS read remains unverified on hardware**. The latest retry " + latest["nonce"] +
        " did not produce an attributable completed storage result. The older original capture verifies a 4 KiB "
        "read/hash match followed by a 64 KiB system bus fatal error (`IS=0x20000`, `rc=-5`, incomplete `OCS=15`). "
        "One genuine READ(10), contiguous 64 KiB-aligned DMA, immediate fatal telemetry and bounded cleanup are "
        "implemented. The exporter alignment fix passes both QEMU alignment settings; its A51 execution and log "
        "survival remain unverified.\n\n"
        "Retained build/native/QEMU/preflight checks pass; these do not qualify hardware completion. " + next_action +
        " The latest recovery pstore listing was empty; both framed export reads returned remote exit 1 with "
        "transport exit 0 and no export bytes. See [baseline restoration and retry evidence](" + LINK_ROOT + GUIDE +
        ") and [UFS repair](" + LINK_ROOT + UFS_GUIDE + "). "
        "Display, brightness, physical input and the whole Phase 4 gate remain unpassed.")
    replacements = {}
    for name in SUMMARIES:
        text = original_text(name)
        marker = "## Current Phase 4 storage repair — 2026-11-16\n\n"
        require(text.count(marker) == 1, "Summary marker changed: " + name)
        prefix, rest = text.split(marker, 1)
        paragraphs = rest.split("\n\n")
        require(len(paragraphs) >= 3 and paragraphs[2].startswith("Current driver build/QEMU"),
                "Summary content changed: " + name)
        text = prefix + marker + summary + "\n\n" + "\n\n".join(paragraphs[3:])
        if name == "docs/PHASE-4-COMPLETION-REVIEW.md":
            text = text.replace("**Decision: hardware completion gate unpassed; latest baseline return unverified.**",
                                "**Decision: hardware completion gate unpassed; latest baseline return " +
                                ("verified." if current_verified else "unverified.") + "**")
        if name == "docs/INDEX.md":
            table = "| Task | Read |\n|---|---|\n"
            require(text.count(table) == 1, "Guide index table changed")
            text = text.replace(table, table + "| Review the verified baseline restoration and failed storage retry | "
                "[16 November restoration evidence](" + LINK_ROOT + GUIDE + ") and [UFS repair](" +
                LINK_ROOT + UFS_GUIDE + ") |\n", 1)
        replacements[name] = text

    ufs = original_text(UFS_GUIDE)
    opening, body = ufs.split("## What the retained silicon evidence establishes", 1)
    require("boot baseline restoration is unverified" in opening, "UFS checkpoint opening changed")
    ufs = (opening.split("\n\n", 1)[0] + "\n\nPhase 4 remains **IN PROGRESS**. The pinned baseline "
        "was independently restored and verified, and the latest retry also returned to completed rooted Android "
        "with matching boot/recovery/DTBO hashes and staging cleanup. The repaired **64 KiB UFS read remains "
        "unverified on hardware**: the retry missed its recovery deadline and captured no usable storage result. "
        "The corrected exporter's A51 execution and recovery survival remain unknown. See [restoration and retry "
        "evidence](" + LINK_ROOT + GUIDE + ").\n\n## What the retained silicon evidence establishes" + body)
    for old, new in (
        ("peripheral-native-tests/20261115T211247479020Z", HOSTS["native"].removeprefix("evidence/phase-4/")),
        ("platform-qemu/20261115T213735963581Z", HOSTS["qemu"].removeprefix("evidence/phase-4/")),
        ("storage-preflight/20261115T215622069350Z", HOSTS["preflight"].removeprefix("evidence/phase-4/")),
        ("storage-candidate/20261115T215622093064Z", hosts["preflight"]["candidate"].removeprefix("evidence/phase-4/")),
    ):
        require(ufs.count(old) == 1, "UFS host selection changed: " + old)
        ufs = ufs.replace(old, new)
    start = "## Latest failed trial and required recovery\n\n"
    end = "## Next hardware check and rollback\n\n"
    require(ufs.count(start) == 1 and ufs.count(end) == 1, "UFS recovery sections changed")
    prefix, rest = ufs.split(start, 1)
    historical, next_section = rest.split(end, 1)
    historical = historical.replace("Latest attempted trial:", "Historical failed trial:", 1)
    historical = historical.replace("No restoration process remains active. ", "", 1)
    historical = historical.replace("Preserve these exact staging paths until restoration and Android verification permit cleanup:",
        "Both exact staging paths below were subsequently removed and their absence verified in `" + RETURN +
        "/`. They are retained here as historical names:", 1)
    procedure = "The [independent pinned-baseline recovery procedure]"
    require(procedure in historical, "UFS independent procedure changed")
    historical = historical.replace(procedure, "### Recovery procedure for a future unverified return\n\n" + procedure, 1)
    current_retry = ("## Failed trials and verified baseline restoration\n\n"
        "### Latest completed retry — 16 November\n\n"
        "Trial: `" + result["latest_trial"] + "`; nonce `" + latest["nonce"] + "`; candidate SHA-256 `" +
        latest["candidate"]["sha256"] + "` (61,865,984 bytes). The candidate did not reach recovery before the "
        "240-second configured deadline, with a 242-second recorded wait. Recovery subsequently became available for restoration. Original `" +
        "restore-baseline-0-readback` output matches the pinned baseline before `return-baseline-android`; "
        "`final-completed=1`, root, fresh Android UUID `" + latest["boot_id_after"] + "`, all partition hashes "
        "and exact staging absence were verified. The failed trial retains `passed=false` and "
        "`storage_gate_passed=false` while `baseline_restored=true` and `baseline_verified=true`.\n\n"
        "The original capture error `Recovery console export failed or was unframed` is generic. Both console "
        "and pmsg reads were actually framed correctly: transport exit 0, remote exit 1, zero stdout bytes; "
        "`/sys/fs/pstore` listed `total 0`. These exports were unavailable. No new UFS completion, hash or "
        "fatal result is established, and neither the DMA failure's cause nor exporter execution can be "
        "inferred. Original commands and byte pins are retained in [the restoration review](" + LINK_ROOT +
        GUIDE + ").\n\n### Independent restoration of the prior failed trial\n\n"
        "The independent staged-hash/write/readback/reboot and Android verification records establish "
        "restoration before the retry. They supersede the earlier unverified device status without changing "
        "the historical failed result below. Recovery UUID `" + capture["recovery_boot_id"] + "`; returned "
        "Android UUID `" + returned["android_boot_id"] + "`.\n\n" + historical)
    next_section = next_section.replace(
        "After independent restoration succeeds, run one storage-only trial with a fresh nonce and matching current selections through `scripts/run.py`:",
        "Investigate recovery/export persistence before another storage candidate. Compare the retained recovery "
        "FDT/ramoops initialization, candidate layout, exporter reachability and reset path; absence of exported "
        "bytes alone does not identify a cause. After any relevant change passes matching checks, the future "
        "storage-only commands use a fresh nonce and current selections through `scripts/run.py`:", 1)
    rollback = "Documentation rollback copies are indexed in"
    require(rollback in next_section, "UFS rollback section changed")
    next_section = next_section.replace(rollback,
        "This reconciliation's indexed document before/after copies and diff are in `" + result["packet"] +
        "/`. Earlier documentation rollback copies are indexed in", 1)
    replacements[UFS_GUIDE] = prefix + current_retry + "## Next check and rollback\n\n" + next_section
    guide = ("# Baseline restoration and storage retry — 16 November 2026\n\n"
        "The independent pinned baseline was restored and verified. The repaired 64 KiB UFS read is still "
        "unverified on hardware. " + current_sentence + "\n\n"
        "## Independent restoration evidence\n\n"
        "The prior failed trial `" + OLD_TRIAL + "` remains byte-for-byte unchanged, including its original "
        "restoration failure. The independent restoration supersedes that historical device status; it does not "
        "turn the failed storage trial into a pass. Recovery UUID: `" + capture["recovery_boot_id"] + "`. "
        "Verified returned Android UUID: `" + returned["android_boot_id"] + "`.\n\n"
        "Recovery model/root/boot target/61,865,984-byte size and recovery/DTBO pins were checked. The independently "
        "pinned Everline KernelSU boot image was staged and hashed, written only to `/dev/block/sda12`, read back "
        "to SHA-256 `" + BASELINE + "` before reboot, and checked again in completed rooted Android. Both exact "
        "staging paths from nonce `25f9798aa52d4763abae651571919914` were removed and their absence verified. "
        "Recovery, DTBO, partition layout, Android sources/backups and userdata were preserved.\n\n"
        "- Corrected original recovery capture: `" + CAPTURE + "/`.\n"
        "- Final Android/root/partition/staging verification: `" + RETURN + "/`.\n" +
        "".join("- " + role + ": `runs/" + name + "/`.\n" for role, name in RUNS.items()) + "\n"
        "The first collector packet `baseline-recovery-capture/20261116T010624908001Z` incorrectly interpreted "
        "ADB transport success as remote-file availability. It is retained and superseded by the framed capture. "
        "Both missing pstore exports have transport exit 0 but remote exit 1; recovery's pstore listing was empty. "
        "These are unavailable exports, not payload success.\n\n"
        "## Latest completed retry\n\n"
        "Trial: `" + result["latest_trial"] + "`; nonce `" + latest["nonce"] + "`; original wrapper: `" +
        run_path.relative_to(PROJECT).as_posix() + "/`.\n\n"
        "Candidate SHA-256: `" + latest["candidate"]["sha256"] + "`. Trial passed: `" +
        str(latest["passed"]).lower() + "`; latest baseline verified: `" + str(bool(current_verified)).lower() +
        "`; storage gate: `" + str(bool(storage_verified)).lower() + "`. Error: `" + str(latest.get("error")) +
        "`; capture error: `" + str(latest.get("capture_error")) + "`. Wrapper exit 1 at `" +
        run["finished"]["utc"] + "`; recorded candidate return wait: 242 seconds. Recovery UUID `" +
        latest["recovery_boot_id"] + "`; completed rooted Android UUID `" + latest["boot_id_after"] + "`.\n\n"
        "The generic capture error does not establish missing framing: the original console and pmsg "
        "acquisitions were framed correctly with remote exit 1, transport exit 0 and zero stdout bytes. "
        "`/sys/fs/pstore` listed `total 0`. Exports were unavailable; no new UFS completion/hash/fatal result "
        "or hardware root cause can be inferred. Original staged baseline/hash, boot readback before reboot, "
        "`final-completed=1`, root/model/target/size, fresh UUID, all three partition hashes and final exact "
        "staging absence are replayed by this recorder.\n\n" + next_action +
        " The retry was already active in a separate local process when this continuation resumed. No overlapping "
        "device operation was launched. This recorder performs host reads/documentation only. Retained input "
        "hashes, before/after documents and the exact diff are in `" + result["packet"] + "/`.\n\n"
        "## Selected host checks\n\n"
        "| Check | Retained passing evidence |\n|---|---|\n"
        "| Native shared UFS model, 74 cases/316,791 checks | `" + HOSTS["native"] + "/` |\n"
        "| Isolated kernel/userland build | `" + HOSTS["build"] + "/` |\n"
        "| Kernel/userland QEMU integration | `" + HOSTS["qemu"] + "/` |\n"
        "| Storage lifecycle/parser models, 118 cases | `" + HOSTS["storage_models"] + "/` |\n"
        "| Corrected exporter, 74 cases with both alignment settings | `" + HOSTS["exporter"] + "/` |\n"
        "| Host-only preflight | `" + HOSTS["preflight"] + "/` |\n\n"
        "The source pins and packet indexes for these unchanged checks are verified and reused. Passing "
        "host/QEMU checks do not establish A51 DMA completion, exporter execution or recovery persistence.\n\n"
        "## Scripts, verification and rollback\n\n"
        "`scripts/phase4-capture-recovery.py` uses the explicit ADB path/serial and framed remote exit codes for "
        "read-only recovery capture. Optional missing exports stay failures. `scripts/phase4-verify-baseline-return.py` "
        "bounds Android reconnection, checks a fresh UUID/completed boot/root/model/target/size and all partition pins, "
        "and optionally removes only a recorded trial's exact staging files after baseline verification. Neither "
        "script installs a storage candidate. Their retained executions establish this restoration's evidence.\n\n"
        "This documentation recorder verifies packet indexes, the unchanged original failed result, original "
        "restore hashes and strict staged-hash/write/readback/reboot timing, plus the original latest retry's "
        "framing, final boot/root/hash/UUID and exact staging cleanup. It requires a completed trial wrapper "
        "before updating current summaries, preserves the selected retry, and checks original document pins "
        "captured from the same bytes used to construct replacements immediately before writing. Phase 4 "
        "remains in progress. The retained wrapper snapshots reproduce this review's exact source and arguments:\n\n"
        "```powershell\npython scripts/run.py --label p4-baseline-restoration-reconciliation -- python -B "
        "scripts/phase4-record-baseline-restoration.py --latest-trial-result " + result["latest_trial"] +
        " --latest-run " + run_path.relative_to(PROJECT).as_posix() + "\n```\n\n"
        "This command adds the review once; after it passes, replay from the retained input/source snapshots "
        "in an isolated copy rather than overwriting current documents or historical evidence.\n\n"
        "For documentation rollback, verify this review packet's `document-changes.json` and restore its indexed "
        "`before/` bytes for only the listed files; remove the new guide/recorder if undoing this addition. Preserve "
        "all original device/run evidence. A documentation rollback does not change a phone partition. Independent "
        "device restoration remains documented in `docs/PHASE-4-DEVICE-PATH.md`.\n")
    replacements[GUIDE] = guide
    state = json.loads(originals["state.json"])
    require(state["phase_4_last_storage_trial"]["result"] ==
            (latest_path.parent.parent / "result.json").relative_to(PROJECT).as_posix(), "Newer trial selection exists")
    require(pin(latest_path.parent.parent / "result.json") ==
            {key: state["phase_4_last_storage_trial"][key] for key in ("bytes", "sha256")}, "Selected retry pin differs")
    for key, role in (("phase_4_peripheral_protocols", "native"), ("phase_4_build", "build"),
                      ("phase_4_qemu", "qemu"), ("phase_4_storage_preflight", "preflight")):
        require(state[key]["result"] == HOSTS[role] + "/result.json", "Newer host selection exists: " + role)
    state.update(updated_date_local=dt.datetime.now(dt.timezone(dt.timedelta(hours=5, minutes=30))).date().isoformat(),
                 active_task=next_action, phase_4_status="in_progress", phase_4_device_gate_passed=False)
    state["phase_4_baseline_restoration_review"] = {"result": result["packet"] + "/result.json",
        **pin(packet / "result.json"), "guide": GUIDE, "historical_independent_baseline_verified": True,
        "latest_baseline_verified": bool(current_verified), "storage_gate_passed": bool(storage_verified)}
    state["phase_4_criteria"]["baseline_rollback_verified"] = (
        "verified_latest_retry_return_" if current_verified else "latest_retry_return_unverified_") + latest["nonce"]
    state["phase_4_criteria"]["status"] = ("in_progress_storage_capture_and_display_input_pending" if current_verified
                                            else "in_progress_requires_baseline_recovery_before_next_candidate")
    state["phase_4_criteria"]["larger_image_loading"] = (
        "historical_64k_system_bus_fatal_current_repair_unverified_missing_recovery_exports")
    state["phase_4_criteria"]["recovery_export_persistence"] = "unverified_empty_latest_pstore_" + latest["nonce"]
    state["phase_4_storage_repair_review"]["latest_status_scope"] = "historical_at_original_review"
    state["phase_4_storage_repair_review"]["current_device_status_superseded_by"] = result["packet"] + "/result.json"
    state["phase_4_device_status"] = {"status": "baseline_restored_verified" if current_verified
                                      else "baseline_restoration_unverified", "serial": latest["serial"],
        "latest_cycle": result["latest_trial"], "nonce": latest["nonce"], "candidate": latest["candidate"],
        "baseline_restored": latest["baseline_restored"], "baseline_verified": latest["baseline_verified"],
        "boot_id_before": latest.get("boot_id_before"), "boot_id_after": latest.get("boot_id_after"),
        "recovery_boot_id": latest.get("recovery_boot_id"), "staging_paths": latest.get("staging_paths", []),
        "staging_cleanup_verified": latest["checks"].get("all_staging_absent", False),
        "baseline_sha256": BASELINE, "physical_recovery_requested": not current_verified,
        "adb_mode": "device" if current_verified else "unknown",
        "observation_scope": "latest_completed_retained_trial; no live query in this review",
        "observed_utc": run["finished"]["utc"], "storage_gate_passed": False,
        "recovery_exports": observed["recovery_exports"], "device_write_or_reboot_this_review": False}
    replacements["state.json"] = json.dumps(state, indent=2) + "\n"
    note = ("\n\n## P4-040 — Independent baseline restoration and completed retry reconciliation\n\n"
        "Purpose/files: scripts/phase4-{capture-recovery,verify-baseline-return,record-baseline-restoration}.py, "
        "docs/BASELINE-RESTORATION-20261116.md, README.md, docs/{STATE,INDEX,HANDOFF,PHASE-4-DEVICE-PATH,"
        "PHASE-4-COMPLETION-REVIEW,PHASE-4-UFS-REPAIR}.md, state.json and this log. Record the previously undocumented independent "
        "restoration, superseded collector error and current retry without rewriting historical failed evidence.\n\n"
        "Verification: original recovery/Android packets and restore hashes/timestamps checked; historical failed "
        "result unchanged; independent boot baseline/root/fresh Android/partition pins and exact old staging cleanup "
        "verified. Latest retry " + latest["nonce"] + ": trial_passed=" + str(latest["passed"]) +
        "; baseline_verified=" + str(bool(current_verified)) + "; storage_gate_passed=" + str(bool(storage_verified)) +
        ". No new hardware operation or repeated host suite was performed by this recorder. "
        "The first collector confused transport exit 0 with remote availability; both missing pstore exports are "
        "correctly remote exit 1 in the superseding framed packet. The latest retry also had correctly framed "
        "remote exit 1/transport exit 0/zero-byte exports and an empty pstore listing; its generic capture error "
        "does not establish a framing failure. Original latest staged baseline hash/write/readback before "
        "reboot, completed rooted Android, model/target/size, fresh UUID, partition pins and final exact staging "
        "absence are independently replayed. Current native/QEMU/preflight selections and unchanged model/exporter "
        "source pins were checked and reused. Concurrent document protection now pins the original bytes at "
        "read time, including state/log/guide, and compares those pins before writing. Original run commands "
        "and full logs are linked in the new guide; input pins/document before-after/diff: `" + result["packet"] + "`.\n\n"
        "Limitations/next action: the corrected 64 KiB single READ(10) and exporter hardware behavior remain "
        "unverified; no attributable new UFS completion was captured. " + next_action +
        " Phase 4/display/input gates remain unpassed.\n\nRollback: restore only this packet's indexed before "
        "documents/state after checking their pins; remove the newly added guide/recorder if undoing this review. "
        "Preserve historical failed trials, recovery/Android evidence, source fixes and all Android projects/backups. "
        "Documentation rollback does not restore a phone partition.\n")
    require("## P4-040 —" not in original_text("docs/IMPLEMENTATION-LOG.md"), "Restoration entry already recorded")
    replacements["docs/IMPLEMENTATION-LOG.md"] = original_text("docs/IMPLEMENTATION-LOG.md") + note
    require(set(replacements) == set(before), "A replacement lacks its original document pin")
    for name, expected in before.items():
        require((pin(PROJECT / name) if (PROJECT / name).exists() else None) == expected,
                "Concurrent document change: " + name)
    documents(packet, replacements)
    index_packet(packet)
    print(json.dumps({key: value for key, value in result.items() if key not in ("inputs", "document_input_pins")}
                     | {"input_files": len(result["inputs"]), "document_files": len(replacements)}, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
