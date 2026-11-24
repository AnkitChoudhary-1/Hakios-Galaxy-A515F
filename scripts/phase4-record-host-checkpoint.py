#!/usr/bin/env python3
"""Record or replay the host-only Phase 4 checkpoint without device operations.

Only the named project documents, state.json and legacy entry guards are integrated. Historical
audits are replayed with their retained bytes, without invoking their mains.
The existing host-readiness execution is reused; kernels are not rebuilt.
"""
from __future__ import annotations

import argparse
import datetime as dt
import difflib
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys

from phase4_support import PROJECT, index_packet, new_packet, pin, require, write_json

READINESS = "evidence/phase-4/host-readiness/20261116T165855086084Z"
READINESS_RUN = "runs/20261116T165852846880Z-p4-current-host-readiness"
AUDIT = "evidence/phase-4/completion-audit/20261116T101146104534Z"
RESTORATION = "evidence/phase-4/baseline-restoration-review/20261116T015024935010Z"
RESTORATION_PIN = {
    "bytes": 22518,
    "sha256": "8dcd27639dd825f5fcd207e9ff41a24932894ab462bbe0d75a5f4e4b8d20d8f6",
}
GUIDE = "docs/PHASE-4-HOST-CHECKPOINT.md"
RECORDER = "scripts/phase4-record-host-checkpoint.py"
GATE = "scripts/phase4-device-gate.py"
FAILED_RECORDING_RUN = "runs/20261116T172331315130Z-p4-host-checkpoint-record"
EDITED = (
    "README.md", "docs/STATE.md", "docs/INDEX.md", "docs/HANDOFF.md",
    "docs/PHASE-4-COMPLETION-REVIEW.md", "docs/PHASE-4-UFS-REPAIR.md",
    "docs/PHASE-4-DEVICE-PATH.md", "docs/IMPLEMENTATION-LOG.md", "state.json", GATE,
)
STATE_CHANGES = {
    "updated_date_local", "active_task", "next_action", "blockers",
    "phone_queries_this_continuation", "phase_4_readonly_revision",
    "phase_4_peripheral_protocols", "phase_4_criteria", "phase_4_host_readiness",
    "phase_4_host_checkpoint", "phase_4_host_continuation",
}


def read_json(path):
    return json.loads(Path(path).read_bytes())


def byte_pin(raw):
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def project_path(relative):
    path = (PROJECT / relative).resolve()
    require(path.is_relative_to(PROJECT) and not (PROJECT / relative).is_symlink(),
            "Path leaves project or is a symlink: " + relative)
    return path


def indexed(packet):
    packet = packet.resolve()
    require(packet.is_relative_to(PROJECT / "evidence/phase-4"), "Wrong evidence root")
    rows = read_json(packet / "index.json")
    require(isinstance(rows, list) and rows, "Missing evidence index")
    names = set()
    for row in rows:
        relative = row["path"]
        path = (packet / relative).resolve()
        require(path.is_relative_to(packet) and path != packet / "index.json" and
                relative not in names and not (packet / relative).is_symlink(), "Invalid indexed path")
        require(pin(path) == {k: row[k] for k in ("bytes", "sha256")}, "Indexed bytes changed: " + relative)
        names.add(relative)
    require(names == {p.relative_to(packet).as_posix() for p in packet.rglob("*")
                      if p.is_file() and p != packet / "index.json"}, "Evidence file set differs")
    return rows


def script_module(name):
    spec = importlib.util.spec_from_file_location(name.replace("-", "_"), PROJECT / "scripts" / name)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def historical_replay(gate_bytes=None):
    audit = script_module("phase4-audit-completion.py")
    result = audit.verify(PROJECT / AUDIT, check_current=False)
    require(result["audit_completed"] and not result["phase_4_gate_passed"] and
            result["qualifying_phase_4_cycles"] == 0, "Historical completion decision differs")
    require(audit.gate_guard_valid(project_path(GATE).read_bytes() if gate_bytes is None else gate_bytes),
            "Legacy gate is no longer disabled")
    indexed(PROJECT / RESTORATION)
    require(pin(PROJECT / RESTORATION / "result.json") == RESTORATION_PIN, "Restoration result changed")
    restored = read_json(PROJECT / RESTORATION / "result.json")
    for relative, expected in restored["inputs"].items():
        require(pin(project_path(relative)) == expected, "Historical restoration input changed: " + relative)
    latest_path = project_path(restored["latest_trial"])
    latest = read_json(latest_path)
    observations, _ = script_module("phase4-record-baseline-restoration.py").latest_observations(
        latest, latest_path.parent)
    require(observations == restored["latest_observations"] and observations["baseline_return_replayed"]
            and restored["historical_independent_baseline_verified"] and restored["latest_baseline_verified"]
            and not restored["storage_gate_passed"], "Historical return replay differs")
    return {"completion_audit_replayed": True, "qualifying_historical_cycles": 0,
            "independent_restoration_inputs_verified": True, "latest_restoration_commands_replayed": True,
            "latest_observations": observations, "current_device_state": "unknown"}


def collect_inputs(gate_bytes):
    rows = indexed(PROJECT / READINESS)
    ready = read_json(PROJECT / READINESS / "result.json")
    require(ready["packet"] == READINESS and ready["passed"] and ready["device_operations"] is False
            and ready["phase_4_gate_passed"] is False and all(ready["checks"].values()), "Host readiness failed")
    require((ready["native_cases"], ready["native_checks"], ready["storage_cases"], ready["qemu_checks"])
            == (216, 337511, 244, 25), "This checkpoint's selected coverage differs")
    inputs = {}

    def remember(relative, expected=None):
        actual = pin(project_path(relative))
        require(expected is None or actual == expected, "Selected input drift: " + relative)
        inputs[relative] = actual

    remember(READINESS + "/index.json")
    for row in rows:
        remember(READINESS + "/" + row["path"], {k: row[k] for k in ("bytes", "sha256")})
    run = read_json(PROJECT / READINESS_RUN / "metadata.json")
    require(run["status"] == "passed" and run["exit_code"] == 0 and
            run["command"] == ["python", "-B", "scripts/phase4-verify-host-readiness.py"] and
            Path(run["cwd"]).resolve() == PROJECT and
            dt.datetime.fromisoformat(run["finished"]["utc"]) >= dt.datetime.fromisoformat(run["started"]["utc"]),
            "Readiness wrapper is incomplete or differs")
    require(READINESS in (PROJECT / READINESS_RUN / "output.log").read_text(encoding="utf-8"),
            "Readiness packet does not match completed wrapper")
    for name in ("metadata.json", "output.log", "project-scripts/phase4-verify-host-readiness.py"):
        remember(READINESS_RUN + "/" + name)
    require(inputs[READINESS_RUN + "/project-scripts/phase4-verify-host-readiness.py"] ==
            pin(PROJECT / READINESS / "source.py"), "Executed readiness source differs")
    for selection in ready["selections"].values():
        remember(selection["manifest"], {k: selection[k] for k in ("bytes", "sha256")})
    for relative in ready["indexed_packets"]:
        remember(relative + "/index.json")
        remember(relative + "/result.json")
    build = read_json(PROJECT / "manifests/phase4-platform-build.json")
    for relative, expected in build["source_pins"].items():
        remember("prototype/phase4-platform/" + relative, expected)
    for manifest, root in (("peripheral-native-tests", "prototype/phase4-platform/"),
                           ("storage-trial-tests", "scripts/")):
        selected = read_json(PROJECT / "manifests" / ("phase4-" + manifest + ".json"))
        for relative, expected in selected["sources"].items():
            remember(root + relative, expected)
    for name in ("phase4-audit-completion.py", "phase4-record-baseline-restoration.py",
                 "phase4_support.py", "phase4_storage.py", "phase4-device-cycle.py", "phase4_device.py",
                 "phase4-verify-host-readiness.py"):
        remember("scripts/" + name)
    for relative in (AUDIT + "/result.json", AUDIT + "/index.json", RESTORATION + "/result.json",
                     RESTORATION + "/index.json", "docs/BASELINE-RESTORATION-20261116.md"):
        remember(relative)
    failed = read_json(PROJECT / FAILED_RECORDING_RUN / "metadata.json")
    require(failed["status"] == "failed" and failed["exit_code"] == 1 and
            failed["command"] == ["python", "-B", RECORDER, "--record"] and
            "Legacy gate is no longer disabled" in
            (PROJECT / FAILED_RECORDING_RUN / "output.log").read_text(encoding="utf-8"),
            "Initial failed host recording evidence differs")
    for name in ("metadata.json", "output.log", "project-scripts/phase4-device-gate.py",
                 "project-scripts/phase4-record-host-checkpoint.py"):
        remember(FAILED_RECORDING_RUN + "/" + name)
    history = historical_replay(gate_bytes)
    restored = read_json(PROJECT / RESTORATION / "result.json")
    for relative, expected in restored["inputs"].items():
        remember(relative, expected)
    hello = (PROJECT / "prototype/phase4-platform/hello.c").read_text(encoding="utf-8")
    driver = (PROJECT / "prototype/phase4-platform/hakios.a51.c").read_text(encoding="utf-8")
    require("HAKIOS_PHASE4_PENDING display=unverified brightness=unverified touch=unverified keys=unverified" in hello
            and "HAKIOS_PHASE4_PASS" not in hello, "Current reporting does not leave physical gates pending")
    require('#include "a51_input.h"' not in driver and "already initialized, idle UFS link" in driver,
            "Current integration limits differ; revise this checkpoint before recording")
    return ready, run, build, inputs, history


def common_summary():
    return """## Current Phase 4 host checkpoint — 2026-11-16

Phase 4 is **IN PROGRESS**; its device gate is **UNPASSED**. This assigned continuation is host-only. No phone query, write, reboot or execution occurred; the current screen and connection are unknown.

The selected source, attributed build and retained execution passed host readiness: **216 native cases / 337,511 checks, 244 modeled storage cases and 25 QEMU checks**. The current program emits reporting version 1 and explicit pending peripheral gates. The current driver submits **4 KiB → one genuine 64 KiB READ(10) → 4 KiB**, with separate per-command telemetry and validated-transfer hashes.

The UFS core is integrated into the selected build but adopts an already initialized idle link; full controller/PHY initialization remains pending. Touch/key/I2C cores have native model coverage and are not integrated into the production input path. Visible display, repeatable brightness and physical input remain unverified.

The rejected three-cycle historical report used constant peripheral PASS labels and sixteen 4 KiB reads. Its candidate-prefix hashes, nonces and timer samples remain useful historical evidence. The independent baseline restoration at 01:29 UTC remains verified; the newer three-cycle rollback lacks original command outputs. No qualifying hardware execution of the current revision or committed binary recovery export is established. The legacy device gate is disabled with its entry guards restored.

See [host checkpoint](/C:/Users/Ankit/Desktop/A51/hakios-a51/docs/PHASE-4-HOST-CHECKPOINT.md), [historical completion audit](/C:/Users/Ankit/Desktop/A51/hakios-a51/docs/PHASE-4-COMPLETION-REVIEW.md) and [baseline restoration](/C:/Users/Ankit/Desktop/A51/hakios-a51/docs/BASELINE-RESTORATION-20261116.md). Phases 1–3 retain their selected gates; Phases 5–10 remain planned. Next host work: implement display/brightness and input integration, complete UFS initialization, and resolve original recovery-log capture. Dated milestone sections below retain their original scopes and next actions.

"""


def replace_once(text, old, new, name):
    require(text.count(old) == 1, "Document anchor differs: " + name)
    return text.replace(old, new, 1)


def prepared_legacy_gate(original):
    """Restore only the entry guards, preserving the observed intermediate body."""
    audit = script_module("phase4-audit-completion.py")
    require(not audit.gate_guard_valid(original), "Gate changed since the failed attempt; review it before recording")
    source = original.decode("utf-8")
    for pattern, guards in (
        (r"(?m)^def run_phase4_cycle\(cycle_num: int, total_cycles: int, output_base: Path\) -> dict:\r?\n",
         ("    raise RuntimeError(LEGACY_GATE_DISABLED)",)),
        (r"(?m)^def main\(\):\r?\n",
         ("    print(LEGACY_GATE_DISABLED, file=sys.stderr)", "    return 2")),
    ):
        matches = list(re.finditer(pattern, source))
        require(len(matches) == 1, "Legacy gate entry anchor differs")
        anchor = matches[0][0]
        newline = "\r\n" if anchor.endswith("\r\n") else "\n"
        source = replace_once(source, anchor, anchor + newline.join(guards) + newline * 2, GATE)
    output = source.encode("utf-8")
    require(audit.gate_guard_valid(output), "Prepared legacy gate is not disabled")
    return output


def guide_text(packet, ready, run, build):
    return f"""# Phase 4 host checkpoint — 16 November 2026

**Phase 4 IN PROGRESS; device gate UNPASSED.** This checkpoint records the completed host verification and the remaining implementation and physical acceptance work. The assigned collaboration is host-only: no phone query, transfer, write, reboot, flash or payload execution occurred. Current phone screen, USB/ADB state and installed bytes are unknown.

Read root `AGENTS.md`, README, STATE, INDEX, IMPLEMENTATION-LOG and the roadmap before resuming. Work stays under `C:\\Users\\Ankit\\Desktop\\A51\\hakios-a51` and `/opt/a51-hakios` in `A51-KernelBuilder`. The roadmap's older status paragraphs and dated project milestones are historical; its Phase 4 acceptance criteria remain applicable.

## Implemented and verified scope

| Component | Implementation | Verified result and limit |
|---|---|---|
| Reporting | `hello.c`, `hakios.a51.h` and `phase4_reporting.py` use reporting version 1, explicit peripheral pending fields and per-command UFS results. Unsupported completion strings are rejected. | Built and executed in QEMU; parser/reporting models passed. Physical gates remain pending. |
| Read-only UFS | `hakios.a51.c` integrates `a51_ufs_readonly.h`. One-block read, one genuine sixteen-block READ(10), then one-block reread use separate reports. Writes/unknown operations are rejected before descriptor/MMIO access. | Native models and source/build correspondence verified. QEMU rejects physical UFS MMIO. Current revision has no qualifying A51 transfer evidence. |
| UFS lifecycle | Kernel-owned contiguous 64 KiB-aligned DMA, one FMP bypass PRDT, bounded command waits, protocol/OCS/residual/sense checks, fatal telemetry and restoration/quarantine. | Simulated MMIO/DMA failure cases passed. Hardware root cause and controller/PHY initialization are unresolved; the core adopts an already initialized idle link. |
| Input | `a51_input.h` models touch packet/slot/coordinate validation, key transitions/debounce and I2C transactions. | Native coverage passed. The production driver does not include this core; physical bus/IRQ/event integration is pending. |
| Display/brightness | Passive register diagnostics; current reporting makes no output/brightness PASS claim. | No measured visible scanout, DECON/DSIM/panel brightness demonstration or physical acceptance. |
| Platform | Existing XNU/PID 1/timers/GICv2 SPI path in the isolated Phase 4 checkout. | Actual emulated kernel/user execution passed, including SPI mask/unmask/detach/reattach. A51 MMIO is deliberately denied. |

Hashes are emitted only for validated transfers; `known_image=host_check_required` leaves comparison with independent image bytes to the host. A model, compiled function or register snapshot cannot establish visible output or physical events.

## Selected evidence

Completed readiness wrapper: `{READINESS_RUN}`; exit 0, finished `{run['finished']['utc']}`. Packet: `{READINESS}`. It verifies exact packet indexes, current template/source/build correspondence, matching QEMU artifacts, completed wrapper versions, sanitized native output, modeled storage cases, original QEMU bytes, linked symbols, unchanged upstream HEADs, eight selected Phase 3 parent files and stable selection manifests.

| Selection | Packet under `evidence/phase-4/` | Result |
|---|---|---|
| Source capture | `{ready['source_capture'].removeprefix('evidence/phase-4/')}` | Current bytes, retained revision history and Android references pinned. Earlier provenance gaps remain recorded. |
| Applied adaptation | `{ready['revision'].removeprefix('evidence/phase-4/')}` | Sixteen adapted files; before/after patches retained. |
| Native protocols | `peripheral-native-tests/20261116T163819181432Z` | 216 cases / 337,511 checks: UFS 74 / 316,791; input 42 / 20,620; reporting 100 / 100. ASan/UBSan and strict compilation passed. |
| Attributed build | `{build['packet'].removeprefix('evidence/phase-4/')}` | Selected revision, templates, adapted files and artifacts matched. |
| Kernel/user QEMU | `platform-qemu/20261116T164742842361Z` | 25 checks passed; actual XNU/PID 1/timer/SPI execution and explicit physical-gate pending reporting. |
| Storage harness | `storage-trial-tests/20261116T164819519944Z` | 244 modeled parser/lifecycle cases passed. These use simulated transports, not a device. |

Build root: `/opt/a51-hakios/experimental/phase4-port/20261114T150320411427Z`. Kernel SHA-256: `{build['artifacts']['hakios-kernel']['sha256']}` ({build['artifacts']['hakios-kernel']['bytes']:,} bytes). User program SHA-256: `{build['artifacts']['userland/hello']['sha256']}` ({build['artifacts']['userland/hello']['bytes']:,} bytes).

Pinned common HEAD: `{build['heads']['common']}`. Native XNU HEAD: `{build['heads']['native']}`. Local adaptations are retained separately; unchanged HEADs do not assert an unmodified working tree. Checkpoint `result.json` pins the selected inputs; `changes.json`, `before/`, `after/` and `documents.patch` retain this integration. Historical evidence and source captures are not rewritten.

## Failed recording attempt and legacy gate restoration

The initial recording wrapper `{FAILED_RECORDING_RUN}` exited 1 before creating a checkpoint or changing documents. Static inspection found that `phase4-device-gate.py` retained its disabled warning but both execution guards had been removed. Its intermediate body also added constant-label brightness parsing; the author and timing of that change are not established by this checkpoint.

This integration restores the immediate exception in `run_phase4_cycle()` and the message/exit-2 return at the start of `main()`. It preserves the intermediate body, including the brightness parsing, behind those guards. The gate's exact observed before bytes, guarded after bytes and diff are retained. The historical audit's AST predicate checks both entry points before integration and during replay. No legacy device command is executed, and adding a brightness label check does not establish physical brightness acceptance.

## Historical hardware observations and failed attempts

The rejected report `silicon-execution/20261116T091954739903Z` contains three nonce-bound cycles. Offline audit `{AUDIT}` independently replays candidate-prefix 4 KiB and aggregate 64 KiB hashes and three timer samples per cycle. Its captured producer used sixteen one-block commands and constant peripheral labels. It has zero qualifying Phase 4 cycles. The current source/build proof does not retroactively attribute those older candidates to the current revision.

Independent restoration review `{RESTORATION}` remains byte-pinned ({RESTORATION_PIN['bytes']:,} bytes, SHA-256 `{RESTORATION_PIN['sha256']}`). Its original inputs and the latest retry's command frames are replayed offline. Historical restoration at `2026-11-16T01:29:42.290650+00:00` verified baseline boot hash `eb30609a62999e3282ac81e0a5e56411ef12ec1a39c107171bf3e01209c7cb67`, rooted completed Android UUID `b674c765-6e77-43ed-815f-a8c1e6c4a042`, recovery/DTBO pins and staging absence. This establishes that historical return only. The later three-cycle report lacks original rollback outputs for independent replay.

The genuine-read retry `storage-trial/20261116T012331081270Z`, nonce `4f577c1c6a7d4cbbaab34e40acdcdc8b`, failed its recovery deadline; baseline restoration subsequently succeeded. Console/pmsg export commands were correctly framed remote failures (remote exit 1, transport exit 0, zero stdout), with an empty pstore listing. No storage success or failure cause follows from unavailable bytes. Earlier `IS=0x20000` is a system bus fatal observation; the alignment experiment does not establish its cause. The exporter alignment fix passed its historical QEMU checks, while A51 execution and persistence remain unverified. Retain all failed attempts and their original scopes.

## Remaining Phase 4 work

| Requirement | Remaining implementation and evidence |
|---|---|
| Display and brightness | Implement the measured DECON/DSIM/panel path; establish visible correct dimensions and orientation, repeated brightness changes and stable output. |
| Touch and keys | Wire the tested input core to matching bus/interrupt paths and an event interface; measure actual coordinates and repeated power/volume press/release transitions. |
| Read-only storage | Complete controller/PHY initialization instead of relying on inherited readiness; demonstrate known-image and larger-image reads with storage writes disabled. The current genuine 64 KiB command is an unresolved repair test. |
| Execution attribution and return | Match each future executed candidate to selected sources/builds and a fresh nonce; retain original logs/protocol results and complete restoration command bytes. Resolve binary export persistence. |

Physical acceptance is outside this host-only assignment. The roadmap does not mandate a single 64 KiB command or a three-cycle Phase 4 count; the historical three automatic PASS cycles and the unresolved genuine-read repair are not substitutes for its actual peripheral criteria. GPU acceleration, stable 60 fps, Apple services and Safari remain outside this checkpoint; Phases 5–10 remain planned.

## Reproduction and recovery

From `C:\\Users\\Ankit\\Desktop\\A51\\hakios-a51`, replay this document/state checkpoint and the original historical evidence without rebuilding or operating a phone:

```powershell
python -B scripts/run.py --label p4-host-checkpoint-replay -- python -B scripts/phase4-record-host-checkpoint.py --verify-review {packet}
```

The verifier checks retained packet/index/input hashes, exact current after copies, both disabled legacy entry guards, untouched state fields, append-only log history and historical audit/restoration bytes. It reuses the completed readiness proof at its recorded time; it does not re-query live WSL source trees. Run the existing readiness verifier when a new live-tree correspondence check is warranted.

For changed implementation inputs, use the existing host entry points in order, through `scripts/run.py`: `phase4-test-peripherals.py`, `phase4-build-platform.py`, `phase4-qemu-platform.py`, `phase4-test-storage-trial.py`, then `phase4-verify-host-readiness.py`. Each retains exact arguments/output/status/times and source versions. Do not rebuild or rerun unchanged passing inputs solely because physical acceptance is missing. Follow each adaptation's pinned patch history and read upstream AGENTS before source edits. Failed-run packets remain evidence.

The device/recovery commands in [PHASE-4-DEVICE-PATH.md](PHASE-4-DEVICE-PATH.md) and [PHASE-4-UFS-REPAIR.md](PHASE-4-UFS-REPAIR.md) are historical/future device procedures, outside this assignment. They were not executed here. The historical baseline is verified; current phone status is unknown.

## Rollback

Checkpoint: `{packet}`. Verify its index and `changes.json` before restoring files. For each of the nine pre-existing document/state files listed there, require the current bytes to match its `after` hash (otherwise reconcile later work), then copy only its exact `before/<path>` bytes back to the same project path. `docs/IMPLEMENTATION-LOG.md` is restored from its complete before copy; this checkpoint retains the removed entry in its after evidence.

The tenth pre-existing file is `scripts/phase4-device-gate.py`. Keep its restored entry guards disabled during a host-only rollback. Its unguarded before snapshot is inspection evidence; restoring it as runnable code would re-enable the legacy device actions. The intermediate body is already preserved in the guarded after version.

The new guide and recorder have `before=null`. If withdrawing them, first retain their current bytes in a new rollback packet and remove only those two exact project files. Preserve this original checkpoint and all runs/evidence; do not modify its index or place unindexed rollback files inside it. No recursive deletion, Git reset, WSL source rollback or phone restoration is involved. Existing Android projects, backups, Phase 3, recovery, DTBO, partition layout and userdata were outside this integration's write set.
"""


def prepared_documents(originals, packet, ready, run, build, gate_bytes):
    output = {}
    for name in ("README.md", "docs/INDEX.md", "docs/HANDOFF.md"):
        text = originals[name].decode("utf-8")
        pattern = (r"(?m)^## Current Phase 4 completion audit — 2026-11-16\r?\n[\s\S]*?"
                   r"use the current state and review for the completion decision\.\r?\n\r?\n")
        matches = list(re.finditer(pattern, text))
        require(len(matches) == 1, "Current summary anchor differs: " + name)
        match = matches[0]
        newline = "\r\n" if "\r\n" in match[0] else "\n"
        output[name] = (text[:match.start()] + common_summary().replace("\n", newline) + text[match.end():]).encode("utf-8")
    index = output["docs/INDEX.md"].decode("utf-8")
    anchor = "| Task | Read |"
    row = ("| Review the current Phase 4 host proof, integration limits and rollback | "
           "[Host checkpoint](/C:/Users/Ankit/Desktop/A51/hakios-a51/" + GUIDE + ") |")
    match = re.search(re.escape(anchor) + r"\r?\n\|---\|---\|\r?\n", index)
    require(match is not None, "Guide table anchor differs")
    newline = "\r\n" if "\r\n" in match[0] else "\n"
    output["docs/INDEX.md"] = (index[:match.end()] + row + newline + index[match.end():]).encode("utf-8")
    output["docs/STATE.md"] = ("# HakiOS A51 — current state\n\nUpdated 16 November 2026 (Asia/Calcutta).\n\n" +
        common_summary() + "| Phase | Current status |\n|---|---|\n"
        "| 1 | Complete for its retained host/QEMU gate |\n"
        "| 2 | Complete for its selected minimal-payload/log/return gate |\n"
        "| 3 | Complete for its selected three-run user-program/timer/return gate |\n"
        "| 4 | In progress; physical peripheral gate unpassed |\n| 5–10 | Planned |\n\n"
        f"Current host readiness: `{READINESS}/result.json`, completed wrapper exit 0. "
        f"Documentation/evidence reconciliation: `{packet}/result.json`. "
        "The inherited phone-query flag is retained under `phase_4_host_continuation`; "
        "the current continuation flag is false. Historical `device_writes_this_phase=true` remains unchanged.\n").encode("utf-8")
    for name, heading in (("docs/PHASE-4-COMPLETION-REVIEW.md", "Historical audit scope"),
                          ("docs/PHASE-4-UFS-REPAIR.md", "Current host checkpoint"),
                          ("docs/PHASE-4-DEVICE-PATH.md", "Current host-only assignment")):
        text = originals[name].decode("utf-8")
        first, body = text.split("\n", 1)
        note = (f"\n## {heading} — 16 November\n\n"
                "The selected source/build and host verification have advanced since the dated records below. "
                "See [PHASE-4-HOST-CHECKPOINT.md](PHASE-4-HOST-CHECKPOINT.md) for the current genuine-read "
                "implementation, explicit pending reporting, exact host evidence and integration limits. "
                "Phase 4 remains **IN PROGRESS**, with its device gate **UNPASSED**. No phone operation "
                "occurred in this continuation; current screen/connection are unknown. "
                "Device commands below are retained procedures outside this host-only assignment.\n")
        text = first + note + body
        if name == "docs/PHASE-4-COMPLETION-REVIEW.md":
            text = replace_once(text, "`prototype/phase4-platform/hello.c` prints constant", "At audit capture, `prototype/phase4-platform/hello.c` printed constant", name)
            text = replace_once(text, "`hakios.a51.c` submits READ(10)", "The audited `hakios.a51.c` submitted READ(10)", name)
            text = replace_once(text, "The current kernel and hello hashes were compared", "The kernel and hello hashes available at audit capture were compared", name)
            text = replace_once(text, "Source findings describe the captured template", "Historical source findings describe the captured template", name)
            text = replace_once(text, "Next: replace constant PASS production", "At the audit date, the next action was to replace constant PASS production", name)
            text = replace_once(text,
                "python scripts/run.py --label p4-completion-audit-replay -- python -B scripts/phase4-audit-completion.py --verify-review " + AUDIT,
                "python -B scripts/run.py --label p4-host-checkpoint-replay -- python -B scripts/phase4-record-host-checkpoint.py --verify-review " + packet, name)
            text = replace_once(text, "Reproduce the offline audit through `scripts/run.py`:",
                "Replay the historical audit with current document reconciliation through `scripts/run.py`. "
                "The checkpoint calls `verify(check_current=False)` against the immutable audit packet; "
                "the audit's original CLI also expects its old current-document after hashes:", name)
        elif name == "docs/PHASE-4-UFS-REPAIR.md":
            text = replace_once(text, "The current template therefore differs from the genuine-read implementation described historically below.",
                "The template captured by that audit differed from the genuine-read repair. The selected current revision restores a genuine sixteen-block command and truthful reporting; its hardware execution remains unverified.", name)
            text = replace_once(text, "## Selected host verification", "## Historical selected host verification — 01:22 checkpoint", name)
            text = replace_once(text, "## Next check and rollback", "## Historical next device check and rollback", name)
        else:
            text = replace_once(text, "## Implementation and provenance", "## Historical C-loader implementation and provenance", name)
            text = replace_once(text, "The selected platform build is", "The platform build selected at that C-loader checkpoint was", name)
        output[name] = text.encode("utf-8")
    state = json.loads(originals["state.json"])
    state["updated_date_local"] = "2026-11-16"
    state["active_task"] = "Phase 4 host-only checkpoint verified; peripheral integration and physical acceptance remain pending"
    state["next_action"] = "implement_phase4_display_input_and_ufs_initialization_with_host_validation"
    state["blockers"] = [
        "Visible display at correct dimensions and repeatable brightness lack qualifying evidence; display/panel control remains pending",
        "Touch/key cores are native-model verified but not integrated into the production bus/IRQ/event path; physical events remain unverified",
        "UFS controller/PHY initialization is pending; current read-only core adopts an already initialized idle link",
        "Current genuine 64 KiB READ(10) has no qualifying silicon result; earlier system bus fatal cause remains unresolved",
        "Committed binary recovery export persistence is unverified; historical baseline restoration is verified, current phone state is unknown",
    ]
    state["phase_4_host_continuation"] = {
        "assignment": "phase_4_completion_host_only", "phone_queries": False, "device_writes": False,
        "device_reboots": False, "current_device_connection": "unknown", "current_device_screen": "unknown",
        "inherited_phone_queries_this_continuation": state["phone_queries_this_continuation"],
        "inherited_flag_scope": "prior continuation state; historical device-query evidence preserved",
        "historical_device_writes_this_phase": state["device_writes_this_phase"],
    }
    state["phone_queries_this_continuation"] = False
    state["phase_4_readonly_revision"].update(build_verified=True,
        applied_revision_result=build["revision_result"], build_evidence=build["packet"] + "/result.json",
        verification=READINESS + "/result.json")
    state["phase_4_peripheral_protocols"].update(integrated=False, storage_core_integrated=True,
        input_core_integrated=False, display_control_integrated=False, hardware_verified=False)
    state["phase_4_criteria"].update(
        display_scanout_and_dimensions="unverified_historical_constant_labels_rejected;current_reporting_pending",
        dsim_repeatable_brightness="unverified;production_display_brightness_control_pending",
        physical_touch_events_and_coordinates="unverified;native_input_core_verified_not_integrated",
        physical_power_volume_key_events="unverified;native_key_core_verified_not_integrated",
        storage_writes_disabled="current_shared_boundary_native_verified;historical_rejection_records;current_hardware_unverified",
        baseline_rollback_verified="historical_independent_01h29_verified;newer_three_cycle_report_not_independently_replayable;current_device_state_unknown",
        ufs_read_known_image="historical_4k_prefix_hash_records_matched;current_revision_hardware_unverified",
        larger_image_loading="historical_64k_aggregate_hashes_match_16x4k_reads;current_genuine_read_host_verified_only",
        single_64k_read10="current_source_build_and_models_verified_genuine_16_block_read10;no_qualifying_silicon_result",
        ufs_controller_phy_initialization="pending;current_driver_adopts_initialized_idle_link",
        input_event_interface="pending;native_core_not_wired_to_production_bus_irq_or_interface")
    state["phase_4_host_readiness"] = {"result": READINESS + "/result.json",
        **pin(PROJECT / READINESS / "result.json"), "run": READINESS_RUN,
        "verified_utc": run["finished"]["utc"], "passed": True, "device_operations": False,
        "phase_4_gate_passed": False, "native_cases": 216, "native_checks": 337511,
        "storage_cases": 244, "qemu_checks": 25}
    state["phase_4_host_checkpoint"] = {"result": packet + "/result.json", "guide": GUIDE,
        "device_operations": False, "phase_4_gate_passed": False, "current_device_state": "unknown",
        "legacy_gate_entry_guards_verified": True, "failed_recording_run": FAILED_RECORDING_RUN}
    output["state.json"] = (json.dumps(state, indent=2) + "\n").encode("utf-8")
    output[GUIDE] = guide_text(packet, ready, run, build).encode("utf-8")
    output[GATE] = gate_bytes
    entry = f"""\n\n## P4-042 — Record the verified host checkpoint and reconcile current Phase 4 status

Date/scope: 16 November 2026, Asia/Calcutta. Assigned Phase 4 completion work is host-only. No phone query/write/reboot/flash or device execution occurred. Phase 4 remains in progress with its device gate false; Phases 1–3 and historical write/restoration records are preserved, Phases 5–10 remain planned.

Purpose/files: README.md; docs/STATE.md, INDEX.md, HANDOFF.md, PHASE-4-COMPLETION-REVIEW.md, PHASE-4-UFS-REPAIR.md, PHASE-4-DEVICE-PATH.md and this log; state.json; scripts/phase4-device-gate.py; new docs/PHASE-4-HOST-CHECKPOINT.md and scripts/phase4-record-host-checkpoint.py. Reconcile stale summaries with the selected genuine-read/reporting revision, distinguish current implementation from historical chunked candidates, correct the stale restoration/ADB blocker without querying the phone, restore the legacy entry guards while preserving its observed intermediate body, and retain exact rollback copies.

Failed attempt/recovery: `{FAILED_RECORDING_RUN}` exited 1 before checkpoint/document writes because the current legacy gate retained its disabled warning but lacked both entry guards. Its intermediate brightness-label parser additions are preserved behind the restored guards; this does not establish physical brightness. The current gate before snapshot, after snapshot and diff retain the observed change; attribution of the intermediate edits is unknown. Static AST checks verify that both entry points stop before their historical bodies. No device command was run.

Verification: completed wrapper `{READINESS_RUN}` passed exit 0; readiness `{READINESS}` verifies 216 native cases / 337,511 checks, 244 modeled storage cases and 25 QEMU checks, matching source/build/artifact/runner versions, linked symbols, upstream HEADs and eight selected Phase 3 parent files. The recorder replays `{AUDIT}` with check_current=False and the original restoration inputs/command frames from `{RESTORATION}`. It validates prepared/current document-state consistency, unchanged historical state fields, exact after copies and append-only log history. Exact command arguments, output, exit status and times remain in runs/. This reconciliation packet is `{packet}` with input hashes, before/after snapshots, changes.json and documents.patch. Unchanged passing native/build/QEMU suites were reused, not rerun.

Limitations: current UFS integrates a read-only core but relies on an initialized idle link; full controller/PHY initialization is pending. Touch/key/I2C models are not production input integration. Visible display, repeatable brightness, actual coordinates/key transitions, current genuine-read silicon results and binary recovery persistence remain unverified. The historical 01:29 baseline return is verified; later three-cycle rollback is reported without original outputs; current screen/connection/installed state are unknown. Current host lineage cannot retroactively establish older candidate/source correspondence or a bus-fatal root cause. Older evidence and failed attempts remain unchanged. Next host work: display/input integration, UFS initialization and recovery-capture analysis.

Rollback: verify this packet's index and changes.json; restore only the nine pre-existing document/state files from their exact before copies after checking that current bytes match after pins. Keep the tenth existing file's legacy entry guards disabled; its unguarded before snapshot is inspection evidence and would re-enable device actions if installed. The new guide/recorder have before=null and can be withdrawn only after retaining their bytes separately. Preserve all evidence and later work; no Git reset, recursive cleanup, WSL source change or phone restoration is involved.
"""
    output["docs/IMPLEMENTATION-LOG.md"] = originals["docs/IMPLEMENTATION-LOG.md"] + entry.encode("utf-8")
    return output


def check_documents(values, old_state, old_log, packet):
    require(script_module("phase4-audit-completion.py").gate_guard_valid(values[GATE]),
            "Integrated legacy gate entry guards are missing")
    state = json.loads(values["state.json"])
    for key, value in old_state.items():
        if key not in STATE_CHANGES:
            require(state.get(key) == value, "Unassigned state field changed: " + key)
    require(set(state) - set(old_state) <= STATE_CHANGES, "Unassigned state field added")
    require(state["phase_4_status"] == state["phase_4"] == "in_progress" and
            state["phase_4_device_gate_passed"] is False and state["device_writes_this_phase"] is True and
            state["phone_queries_this_continuation"] is False and
            state["phase_4_host_continuation"]["inherited_phone_queries_this_continuation"] ==
            old_state["phone_queries_this_continuation"], "Phase/scope/history consistency failed")
    require(state["phase_4_readonly_revision"]["build_verified"] is True and
            state["phase_4_peripheral_protocols"]["integrated"] is False and
            state["phase_4_host_checkpoint"]["result"] == packet + "/result.json", "Host integration status differs")
    log = values["docs/IMPLEMENTATION-LOG.md"]
    require(log.startswith(old_log) and log[len(old_log):].count(b"## P4-042 ") == 1,
            "Implementation log history is not append-only")
    for name in ("README.md", "docs/STATE.md", "docs/INDEX.md", "docs/HANDOFF.md"):
        text = values[name].decode("utf-8")
        require("## Current Phase 4 host checkpoint" in text and GUIDE in text and
                "216 native cases / 337,511 checks" in text and "244 modeled storage cases" in text and
                "25 QEMU checks" in text and "**UNPASSED**" in text, "Current summary differs: " + name)
        require("The current driver uses **sixteen separate" not in text and
                "Next: remove the constant PASS producer" not in text, "Stale current summary remains: " + name)
    for name in ("docs/PHASE-4-COMPLETION-REVIEW.md", "docs/PHASE-4-UFS-REPAIR.md", "docs/PHASE-4-DEVICE-PATH.md"):
        require("PHASE-4-HOST-CHECKPOINT.md" in values[name].decode("utf-8"), "Guide navigation differs")
    require(packet in values[GUIDE].decode("utf-8"), "Guide packet selection differs")


def verify_review(packet, replay=True):
    packet = packet.resolve()
    require(packet.is_relative_to(PROJECT / "evidence/phase-4/host-checkpoint"), "Wrong checkpoint root")
    indexed(packet)
    result = read_json(packet / "result.json")
    require(result["passed"] and result["device_operations"] is False and
            result["phase_4_gate_passed"] is False and all(result["checks"].values()) and
            result["packet"] == packet.relative_to(PROJECT).as_posix(), "Checkpoint is incomplete or differs")
    for relative, expected in result["inputs"].items():
        require(pin(project_path(relative)) == expected, "Checkpoint input drift: " + relative)
    changes = read_json(packet / "changes.json")
    require({row["path"] for row in changes} == set(EDITED) | {GUIDE, RECORDER}, "Change allowlist differs")
    for row in changes:
        relative = row["path"]
        require(pin(project_path(relative)) == row["after"] == pin(packet / "after" / relative),
                "Current/after bytes differ: " + relative)
        if row["before"] is not None:
            require(pin(packet / "before" / relative) == row["before"], "Before snapshot changed")
        else:
            require(relative in (GUIDE, RECORDER), "Existing file has no before snapshot")
    current = {relative: project_path(relative).read_bytes() for relative in (*EDITED, GUIDE)}
    check_documents(current, read_json(packet / "before/state.json"),
                    (packet / "before/docs/IMPLEMENTATION-LOG.md").read_bytes(), result["packet"])
    if replay:
        require(historical_replay() == result["historical_replay"], "Historical replay changed")
    print(json.dumps({"packet": result["packet"], "verified": True, "changed_files": len(changes),
                      "input_pins_checked": len(result["inputs"]), "device_operations": False,
                      "phase_4_gate_passed": False}, indent=2), flush=True)


def record():
    originals = {name: project_path(name).read_bytes() for name in EDITED}
    require(not project_path(GUIDE).exists() and b"## P4-042 " not in originals["docs/IMPLEMENTATION-LOG.md"],
            "Checkpoint already exists; use --verify-review")
    require(originals[GATE] == (PROJECT / FAILED_RECORDING_RUN / "project-scripts/phase4-device-gate.py").read_bytes(),
            "Legacy gate changed since the failed attempt; retain and review later work before recording")
    gate_bytes = prepared_legacy_gate(originals[GATE])
    ready, run, build, inputs, history = collect_inputs(gate_bytes)
    packet = new_packet("host-checkpoint", __file__)
    relative = packet.relative_to(PROJECT).as_posix()
    result = {"schema_version": 1, "packet": relative, "passed": False,
              "recorded_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
              "scope": "host-only documentation/state integration, legacy entry guards and retained evidence replay",
              "device_operations": False, "phase_4_gate_passed": False, "inputs": inputs,
              "host_readiness": READINESS, "readiness_run": READINESS_RUN, "historical_replay": history,
              "legacy_gate_guard": {"before": byte_pin(originals[GATE]), "after": byte_pin(gate_bytes),
                  "restored": True, "intermediate_body_preserved": True,
                  "failed_recording_run": FAILED_RECORDING_RUN}, "applied_files": []}
    try:
        require(pin(PROJECT / RECORDER) == pin(packet / "source.py"), "Recorder changed during capture")
        output = prepared_documents(originals, relative, ready, run, build, gate_bytes)
        check_documents(output, json.loads(originals["state.json"]), originals["docs/IMPLEMENTATION-LOG.md"], relative)
        changes = []
        patches = []
        for name, after in {**output, RECORDER: (PROJECT / RECORDER).read_bytes()}.items():
            before = originals.get(name)
            for kind, raw in (("before", before), ("after", after)):
                if raw is not None:
                    path = packet / kind / name
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(raw)
            changes.append({"path": name, "before": byte_pin(before) if before is not None else None,
                            "after": byte_pin(after)})
            patches.append("".join(difflib.unified_diff((before or b"").decode("utf-8").splitlines(True),
                after.decode("utf-8").splitlines(True), fromfile="a/" + name, tofile="b/" + name)))
        write_json(packet / "changes.json", changes)
        (packet / "documents.patch").write_text("".join(patches), encoding="utf-8")
        write_json(packet / "result.json", result)
        for name, raw in originals.items():
            require(project_path(name).read_bytes() == raw, "Concurrent project change: " + name)
        require(not project_path(GUIDE).exists(), "Concurrent guide creation")
        for name, after in output.items():
            require((project_path(name).read_bytes() if project_path(name).exists() else None) == originals.get(name),
                    "Concurrent project change before write: " + name)
            project_path(name).write_bytes(after)
            result["applied_files"].append(name)
        result["passed"] = True
        result["checks"] = {name: True for name in ("completed_host_readiness_reused", "historical_replay",
            "prepared_document_state_consistency", "before_after_snapshots", "append_only_log_history",
            "central_status_allowlist", "legacy_gate_entry_guards", "failed_attempt_preserved", "no_device_operations")}
        write_json(packet / "result.json", result)
        index_packet(packet)
        verify_review(packet, replay=False)
        return 0
    except Exception as exc:
        result.update(passed=False, error=str(exc))
        write_json(packet / "result.json", result)
        index_packet(packet)
        raise


def main():
    if sys.stdout.encoding.lower().replace("-", "") != "utf8":
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--record", action="store_true", help="Integrate this one-time host checkpoint")
    action.add_argument("--verify-review", type=Path, help="Read-only replay of a recorded checkpoint")
    args = parser.parse_args()
    if args.record:
        return record()
    verify_review(args.verify_review)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
