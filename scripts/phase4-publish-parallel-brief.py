#!/usr/bin/env python3
"""Publish a fixed four-worker Phase 4 baseline and corrected review disposition.
Run through scripts/run.py. No phone operations or existing worker/source edits.
"""
from __future__ import annotations
import ast
import datetime as dt
import json
import os
from pathlib import Path
import shutil
import subprocess
from phase4_support import PROJECT, command, documents, index_packet, new_packet, pin, require, write_json
from importlib.machinery import SourceFileLoader

FIRST = "parallel/snapshots/20261117T013929281709Z-antigravity-first-handoff"
FIRST_SHA = "024b3c2add18375efca9067684054d789844439b7b005090df359aa5e8a1322a"
CAPTURE = "parallel/snapshots/20261117T030344301526Z-four-worker-inputs"
CAPTURE_SHA = "db5d7d4a81b53639e2b249f8009d2b45b278384d01d730efc038f6b8a654bdec"
FAILED = "evidence/phase-4/parallel-source-freeze/20261117T030344301526Z"
PORT = Path("/opt/a51-hakios/experimental/phase4-port/20261114T150320411427Z")
XNU = PORT / "xnu-src/xnu-8796.121.2"
WORKERS = ("antigravity-phase4", "antigravity-input", "antigravity-review")

def check_index(folder):
    for item in json.loads((folder / "index.json").read_text()):
        rel = Path(item["path"])
        require(not rel.is_absolute() and ".." not in rel.parts, "Unsafe index path")
        require(pin(folder / rel) == {"bytes": item["bytes"], "sha256": item["sha256"]}, "Evidence drift: " + str(folder / rel))

def checked_copy(source, dest, expected):
    require(source.is_file() and not source.is_symlink(), "Not a regular file: " + str(source))
    require(pin(source) == expected, "Input drift: " + str(source))
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, dest)
    require(pin(source) == expected and pin(dest) == expected, "Copy drift: " + str(source))

def validate_snapshot(snapshot, manifest, first=False):
    groups = [(snapshot / "antigravity", manifest["antigravity_files"])] if first else [
        (snapshot / "handoffs" / worker, row["files"]) for worker, row in manifest["workers"].items()]
    if not first:
        groups += [(snapshot / root, manifest[key]) for root, key in
                   (("main-base", "main_files"), ("wsl-adapted", "wsl_files"),
                    ("references", "references"), ("instructions", "instructions"))]
    count = 0
    for root, rows in groups:
        for rel, expected in rows.items():
            require(pin(root / rel) == expected, "Captured file drift: " + str(root / rel))
            count += 1
    return count

def validate_disabled_gate(source):
    tree = ast.parse(source.read_text())
    funcs = {node.name: node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
    body = lambda node: [stmt for stmt in node.body if not (isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant) and isinstance(stmt.value.value, str))]
    require(isinstance(body(funcs["run_phase4_cycle"])[0], ast.Raise), "Legacy cycle guard missing")
    main_body = body(funcs["main"])
    require(any(isinstance(stmt, ast.Return) and isinstance(stmt.value, ast.Constant) and stmt.value.value == 2 for stmt in main_body[:3]), "Legacy main guard missing")

def main():
    if os.name == "nt":
        script = "/mnt/c" + str(Path(__file__).resolve()).replace("\\", "/")[2:]
        return subprocess.call(["wsl.exe", "-d", "A51-KernelBuilder", "--exec", "python3", "-B", script])
    packet = new_packet("parallel-workflow", __file__)
    result = {"schema_version": 1, "packet": packet.relative_to(PROJECT).as_posix(),
              "baseline_selected": False, "brief_ready": False, "live_worker_freeze_succeeded": False,
              "device_operations": False, "existing_worker_writes": False,
              "main_driver_changes": False, "wsl_source_changes": False, "phase_4_gate_passed": False}
    records = []
    try:
        require(not (PROJECT / "parallel/BRIEF.md").exists(), "Preserve the existing brief; reconcile before publishing")
        first, capture = PROJECT / FIRST, PROJECT / CAPTURE
        require(pin(first / "MANIFEST.json")["sha256"] == FIRST_SHA, "Reviewed first manifest drift")
        require(pin(capture / "MANIFEST.json")["sha256"] == CAPTURE_SHA, "Captured manifest drift")
        fm = json.loads((first / "MANIFEST.json").read_text())
        cm = json.loads((capture / "MANIFEST.json").read_text())
        checked = validate_snapshot(first, fm, first=True) + validate_snapshot(capture, cm)
        check_index(PROJECT / FAILED)
        failed = json.loads((PROJECT / FAILED / "result.json").read_text())
        require(failed["frozen"] is False and "Worker changed during freeze" in failed["error"], "Unexpected original freeze result")
        for rel, expected in cm["main_files"].items():
            require(pin(PROJECT / rel) == expected, "Current main baseline drift: " + rel)
        for key, expected in cm["wsl_files"].items():
            label, rel = key.split("/", 1)
            require(pin((XNU if label == "native" else PORT) / rel) == expected, "Current adapted baseline drift: " + key)
        validate_disabled_gate(PROJECT / "scripts/phase4-device-gate.py")
        snapshot = PROJECT / "parallel/snapshots" / (packet.name + "-four-worker-baseline")
        snapshot.mkdir(parents=True, exist_ok=False)
        selected = {"schema_version": 2, "created_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
                    "scope": "fixed source slices and complete captured handoffs; not full dependency checkouts",
                    "snapshot": snapshot.relative_to(PROJECT).as_posix(),
                    "reviewed_first_source": {"path": FIRST, "manifest_sha256": FIRST_SHA},
                    "historical_capture_source": {"path": CAPTURE, "manifest_sha256": CAPTURE_SHA,
                        "live_consistency_passed": False, "original_failed_packet": FAILED},
                    "workers": {}, "main_files": cm["main_files"], "wsl_files": cm["wsl_files"],
                    "references": cm["references"], "instructions": cm["instructions"],
                    "common_head": cm["common_head"], "native_head": cm["native_head"],
                    "current_artifacts": cm["current_artifacts"], "unselected_live_worker_drift": {}}
        for worker in WORKERS:
            source = first / "antigravity" if worker == "antigravity-phase4" else capture / "handoffs" / worker
            rows = fm["antigravity_files"] if worker == "antigravity-phase4" else cm["workers"][worker]["files"]
            selected["workers"][worker] = {"fixed_origin": FIRST + "/antigravity" if worker == "antigravity-phase4" else CAPTURE + "/handoffs/" + worker, "files": rows}
            for rel, expected in rows.items():
                checked_copy(source / rel, snapshot / "handoffs" / worker / rel, expected)
            drift = []
            for rel, expected in rows.items():
                live = PROJECT / "parallel" / worker / rel
                actual = pin(live) if live.is_file() else None
                if actual != expected:
                    drift.append({"path": rel, "selected": expected, "observed_live": actual})
            selected["unselected_live_worker_drift"][worker] = drift
        for root, key in (("main-base", "main_files"), ("wsl-adapted", "wsl_files"),
                          ("references", "references"), ("instructions", "instructions")):
            for rel, expected in selected[key].items():
                checked_copy(capture / root / rel, snapshot / root / rel, expected)
        extras = {}
        for root_name in ("wsl-metadata", "wsl-instructions"):
            root = capture / root_name
            if root.is_dir():
                for source in sorted(root.rglob("*")):
                    if source.is_file():
                        rel = source.relative_to(capture).as_posix()
                        extras[rel] = pin(source)
                        checked_copy(source, snapshot / rel, extras[rel])
        selected["metadata_files"] = extras
        processes_module = SourceFileLoader("p4_freeze_helpers", str(PROJECT / "scripts/phase4-freeze-parallel.py")).load_module()
        process_rows = processes_module.inspect_processes()
        for label, tree in (("common", PORT), ("native", XNU)):
            head = command(packet, records, label + "-head", ["git", "-C", str(tree), "rev-parse", "HEAD"], timeout=30).stdout.decode().strip()
            require(head == selected[label + "_head"], "Current HEAD drift: " + label)
        for rel, expected in selected["current_artifacts"].items():
            require(pin(PORT / rel) == expected, "Selected artifact drift: " + rel)
        win = command(packet, records, "windows-build-processes",
            ["powershell.exe", "-NoProfile", "-Command",
             "Get-CimInstance Win32_Process | Where-Object { $_.Name -match '^(python|pythonw|wsl|wslhost|make|ninja|clang|adb|heimdall|odin).*' } | Select-Object Name,ProcessId,ParentProcessId,CreationDate | ConvertTo-Json -Depth 3"],
            timeout=30, check=False)
        round_id = "phase4-" + packet.name
        roles = ("main", "display-brightness", "touch-keys", "source-review")
        private = {}
        for role in roles:
            wr = PROJECT / "parallel" / round_id / role
            lr = Path("/opt/a51-hakios/parallel") / round_id / role
            require(wr.resolve().is_relative_to((PROJECT / "parallel").resolve()) and lr.resolve().is_relative_to(Path("/opt/a51-hakios/parallel").resolve()), "Private path escapes")
            require(not wr.exists() and not lr.exists(), "Private path already exists")
            wr.mkdir(parents=True)
            lr.mkdir(parents=True)
            (wr / "scripts").mkdir()
            checked_copy(snapshot / "main-base/scripts/run.py", wr / "scripts/run.py", selected["main_files"]["scripts/run.py"])
            (wr / "TASK.md").write_text("Read the central parallel/BRIEF.md for the " + role + " role. Use only this private output root and its separately listed WSL root. Existing worker folders and fixed snapshots remain read-only.\n", encoding="utf-8")
            private[role] = {"windows": "C:/Users/Ankit/Desktop/A51/hakios-a51/parallel/" + round_id + "/" + role,
                             "wsl_project_alias": str(wr), "wsl_build": str(lr),
                             "logger": str(wr / "scripts/run.py"), "logger_pin": pin(wr / "scripts/run.py")}
        old_audit = json.loads((capture / "PATH-AUDIT.json").read_text())
        audit = {**old_audit, "audited_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
                 "same_physical_project": str(PROJECT.resolve()) == "/mnt/c/Users/Ankit/Desktop/A51/hakios-a51",
                 "wsl_processes": process_rows, "windows_process_query_exit_code": win.returncode,
                 "worker_full_builds_allowed": False, "private_roots": private,
                 "private_roots_are_distinct": len({v["wsl_build"] for v in private.values()}) == 4}
        require(audit["same_physical_project"] and audit["native_inside_common"], "Unexpected shared build paths")
        write_json(packet / "path-audit.json", audit)
        write_json(snapshot / "PATH-AUDIT.json", audit)
        write_json(snapshot / "MANIFEST.json", selected)
        validate_snapshot(snapshot, selected)
        for rel, expected in extras.items():
            require(pin(snapshot / rel) == expected, "Metadata drift")
        manifest_pin = pin(snapshot / "MANIFEST.json")
        brief = f"""# HakiOS A51 Phase 4: four-worker brief
Published {selected['created_utc']}. Main/Codex coordinates this round. Phase 4 is IN PROGRESS; all physical peripheral acceptance remains UNPASSED.

## Fixed inputs and existing work
Read AGENTS.md, README, STATE, IMPLEMENTATION-LOG, INDEX, MODIFICATION-GUIDE and hakios-assessment/ROADMAP.md before work. Current user Phase 4 instructions supersede dated Phase 1/host-only scope text. Handoff runbooks are proposals, not new device authorization.

Fixed Windows snapshot: C:/Users/Ankit/Desktop/A51/hakios-a51/{selected['snapshot']}
WSL alias: {snapshot}
MANIFEST.json SHA-256: {manifest_pin['sha256']}
Full per-file sizes/hashes and original paths are in MANIFEST.json; verify these before work and cite them in every handoff. These are source slices, not a full XNU/dependency checkout.
"""
        brief += "\n| Input | Selected version | HANDOFF.md SHA-256 | Disposition |\n|---|---|---|---|\n"
        for worker, disposition in (("antigravity-phase4", "Changes required; original reviewed revision only"),
                                     ("antigravity-input", "Preliminary changes required; new model claims awaiting independent reproduction"),
                                     ("antigravity-review", "Supported concerns with source/evidence corrections below")):
            row = selected["workers"][worker]
            brief += f"| {worker} | {row['fixed_origin']} | {row['files']['HANDOFF.md']['sha256']} | {disposition} |\n"
        brief += f"""
The original first snapshot MANIFEST hash is {FIRST_SHA}. The later capture MANIFEST hash is {CAPTURE_SHA}; its final live-consistency check FAILED because display source changed. That failed result at {FAILED} is preserved. This round independently verifies and selects fixed captured bytes; it does not relabel that earlier freeze as successful. Live drift is listed under unselected_live_worker_drift and is not covered by old tests. Existing antigravity-phase4, antigravity-input and antigravity-review folders remain read-only.

Main baseline: main-base/. Adapted WSL slices: wsl-adapted/common/ and wsl-adapted/native/. Matching references: references/android/ and references/xnu/. The main implementation baseline and adapted files matched current pins at publication; later main changes receive new packets rather than changing this snapshot.
Common HEAD: {selected['common_head']}
Native HEAD: {selected['native_head']}
Selected kernel SHA-256: {selected['current_artifacts']['hakios-kernel']['sha256']}
Selected user SHA-256: {selected['current_artifacts']['userland/hello']['sha256']}
Retain 216 main native cases / 337,511 checks, 244 storage models and 25 QEMU checks when those input pins match. The first worker's independently reproduced 230 cases / 337,647 checks are host-only evidence. Prototype-folder binaries are not substitutes for selected WSL artifacts.

## Roles and private outputs
"""
        brief += "\n| Worker | Owned work | Windows private outputs | WSL private build/output |\n|---|---|---|---|\n"
        ownership = {"main": "UFS/read-only storage, recovery/original logs, shared integration, central docs/state, build and all phone tests",
                     "display-brightness": "Display/brightness corrections and measured diagnostic interface proposals",
                     "touch-keys": "Melfas touch, power/volume keys, queue/debounce and sustained event interface proposals",
                     "source-review": "Independent review of fixed source/patch/evidence and targeted private verification"}
        for role in roles:
            brief += f"| {role} | {ownership[role]} | {private[role]['windows']} | {private[role]['wsl_build']} |\n"
        brief += """
Use source/, patches/, verification/, logs/ and HANDOFF.md inside your own private Windows root. Keep Linux objects/models/caches/TMPDIR under your assigned WSL root. The coordinator created only empty private build roots and a byte-identical private copy of the project logger. Invoke that private scripts/run.py with --label <role>-<unique-purpose> --cwd <private-source-or-build> -- <exact argv>. This records commands/output/exit/times under your private runs/ without central state changes. Do not execute copied device scripts or builders from a snapshot.

## Display and brightness task
Continue supported first-handoff work; avoid rewriting tested unchanged helpers. Remove unsupported 0xCA000000 assumptions and all drawing before framebuffer ownership, bounds, cache attributes and scanout address translation are established. A declared DRAM range or observed DPP base does not certify ownership; SYSMMU can make a DMA base an IOVA. Derive DECON/DPP/DSIM offsets from the matching cal_9610 references and either preserve a proven inherited configuration or return an explicit unsupported/readiness error. SetFramebufferAddress must not report success without real supported scanout programming.
Fix DSIM full-FIFO timeout, completion/error propagation and failure cleanup. Never report transfer success from an absent mapping or FIFO availability alone. Cache/release mappings using the matching XNU API/attributes; no per-query unbounded mapping. Bound every pattern write to a verified framebuffer span.
Support the detected A51 panel through its matching sequence/table and restore the original level after a bounded visible brightness sequence with usable dwell/timestamps. Both matching S6E3FA9 and EA8076 sources use DCS 0x51 with TWO parameter bytes/10-bit brightness-table fields. Do not implement the reviewer's unsupported EA8076 one-byte fallback.
Provide targeted models for disabled/wrong DECON, ownership/address/stride failures, FIFO timeout without writes, completion/error failures, panel sequence/dwell and repeated mapping lifetime. Physical observations remain pending.

## Touch and power/volume keys task
Use the separate fixed input candidate, retaining its useful attention helper, counters and tested decoder. Correct the packet transaction: Melfas page 2 register 0x04 is EVENT_FORMAT, 0x10 is PACKET_INFO, and 0x11 is PACKET_DATA. Confirm format/event size against source; the input HANDOFF prose contradicts its actual format-10 decoder. Do not infer physical sensor scaling from model constants.
The candidate touch ISR passes NULL,0 and does not drain I2C. Define a bounded IRQ/deferred-drain or timed polling lifecycle; acknowledge/mask the GPIO source and honor the existing GIC handler contract before returning. No unlocked ISR mutation of manager/queue shared with sysctl, and no blocking I2C/mutex work in an unsafe interrupt context. Debouncing needs delayed/rescheduled sampling even when there are no more edges. Record queue overflow/loss and propagate decoder/I2C/push failures.
Provide continuous sequenced press/move/release/contact and all three key transitions, including nonzero first finger IDs, repeated presses, long holds, bounce, no-edge debounce and bus failures. MelfasTouch_Poll remains a stub and must not count as a physical event path. Remove unrelated display ABI/address edits from the input deliverable.

## Independent source/evidence review task
Review fixed bases and the next two private candidates only after their exact changed-file hashes and patches are supplied. Check patch reconstruction/source/compiler/binary correspondence, every readiness/failure path, mapping lifetime/ownership/SYSMMU, IRQ queue synchronization/acknowledgement and meaningful sustained reporting. Distinguish inherited configuration, models, QEMU, Android observations and actual HakiOS physical success. Correct unsupported panel/patch/DRAM recommendations listed below. Keep review outputs private; do not modify sources, peer folders or central state. Cite exact retained paths, hashes and lines; label unproved risks as risks rather than observed panics/corruption.

## Shared interfaces and integration rules
Display owns a51_display.h and drivers/display/*. Input owns a51_input.h and drivers/input/*. Main owns a51_ufs_readonly.h, storage/recovery helpers, gic_v2_irq.c, hakios.a51.c, hakios.a51.h, hello.c, build manifests and reporting grammar. Workers may propose narrowly scoped hunks for shared files in their private patches; no whole-file promotion or unrelated subsystem edits. Supply proposed ABI sizes/version/flags/error meanings and lifecycle callbacks separately, so main can merge one common ABI and serialized MMIO/queue ownership.
Keep reporting version 1 and HAKIOS_PHASE4_PENDING. Add diagnostic observations with exact errors, time/sequence/contact/key state and dropped-event counters; do not add peripheral PASS strings. Both legacy phase4-device-gate.py entry guards remain disabled. Do not run phase4-resume-audit.py.
Actual adaptation destinations are recorded in main-base/manifests/phase4-platform-adaptation.json. New kernel headers require common drivers/core and native bsd/dev placements; common userland/src is required only where user code includes them. Existing a51_input.h placements are already present. Main records patches and manifests, tests combined sources privately, then performs attributed full build/QEMU validation before promotion.

## Shared Windows/WSL build audit
C:/Users/Ankit/Desktop/A51/hakios-a51 and /mnt/c/Users/Ankit/Desktop/A51/hakios-a51 refer to the SAME physical files. Main common tree is /opt/a51-hakios/experimental/phase4-port/20261114T150320411427Z; native XNU is nested at xnu-src/xnu-8796.121.2. The legacy helpers use this shared source/BUILD tree, output symlinks, shared Theos/toolchains and central manifests.
PATH-AUDIT.json records resolved selected symlinks and current process observations. Separate worker directories alone do not isolate a full XNU build. Worker full builds remain DISALLOWED until the coordinator verifies a complete source/dependency copy with every output/cached/generated/symlink path confined to a private root. Private model/C++ object builds with explicit -o, TMPDIR and cache paths are allowed. Shared tools/dependency sources are read-only. Main serializes full builds and device operations. Do not run the input handoff's generic /opt/a51-hakios && ninja command.

## Review corrections retained
Repeated sysctl mapping and unowned framebuffer rendering are supported source defects; exact leaked size and actual kernel panic/live corruption are not measured hardware findings. Dynamic allocator ownership and DMA/SYSMMU/cache lifetimes must be established before rendering.
Removing the incorrect legacy DECON address offset is useful, but replacing it with an assumed physical DPP base without translation/ownership validation is insufficient.
Both matching A51 brightness sources contradict the one-byte EA8076 recommendation. Default git apply already strips one prefix; the first unified original/work patch reconstructed the candidate in private staging. The alternative absolute-path patch failed. Explicit -p1 is optional for that unified patch, not a newly required fix.
Queue concurrency was conditional for the first candidate and is an actual unlocked ISR path in the separate input candidate. Standalone C++ compilations or sanitized host mocks do not establish full-kernel integration or peripherals.

## Handoff and physical acceptance
Every handoff must provide base MANIFEST hash, changed-file before/after sizes/hashes, relative a/ b/ patches, exact logged compiler/test argv and outputs, binaries and input versions, supported results, unresolved blockers, mapping/DMA/IRQ cleanup/rollback, and a proposed bounded physical test sequence for main. Reuse unchanged matching proofs; execute targeted regressions for changes and failures.
Only main/Codex in this chat issues any phone operation, including read-only ADB; worker runbooks confer no permission. Main binds each tested combined candidate to exact source/build hashes and a fresh nonce, captures original logs and recovery/return evidence, and coordinates visible display/orientation, repeatable brightness, actual touch press/move/release/multitouch, repeated power/volume transitions and independent known-image/larger-image read-only storage comparisons. Compilation, QEMU, snapshots and printed PASS labels cannot pass these gates. Keep Phase 4 incomplete until the actual physical acceptance evidence passes.
"""
        review = f"""# Independent Phase 4 review: coordinator disposition
17 November 2026. Reviewed fixed report and handoff in {selected['snapshot']}/handoffs/antigravity-review/. No phone operation, peer-folder edit or driver promotion occurred.

Disposition: supported concerns with corrections. Direct first-candidate integration remains blocked as already recorded in P4-044. Its unchanged 230 native cases / 337,647 checks and four C++ compilations retain the coordinator's independently reproduced proof; they are synthetic host evidence.

| Finding | Coordinator disposition |
|---|---|
| Hardcoded framebuffer / rendering | Supported blocker: matching A51 DTS does not establish 0xCA000000 ownership; the other-device address cannot authorize rendering. DRAM membership is insufficient. Actual corruption was not observed. |
| Per-sysctl mapping | Supported source-lifetime defect; repeated calls do not release/cache this mapping. The exact leak size, time to exhaustion and inevitable panic were not measured. |
| Missing DPP/IDMA | Supported architecture gap. The old legacy DECON offset is wrong; DPP DMA base registers require matching SYSMMU/address/ownership/format/stride analysis before use. Reading a base does not automatically yield a usable physical framebuffer. |
| DSIM FIFO timeout | Supported and already reproduced by the coordinator: full FIFO exhaustion falls through. A timeout check alone does not complete packet completion/error/cleanup handling. |
| EA8076 brightness fallback | Recommendation rejected: matching ea8076_a51_lcd_ctrl.c sets bl_reg[1] from brightness_table bits 8..9 and bl_reg[2] from bits 0..7, then writes all three bytes including 0x51. S6E3FA9 does the same. type_of_ddi is not proof of one-byte brightness. |
| Unified patch requires explicit -p1 | Correction: git apply defaults to stripping one prefix. Coordinator staging reconstructed exact candidate hashes with the original/work unified patch. The separate absolute-path patch failed. |
| Adaptation headers | New a51_display.h destinations must be added if integrated. Existing a51_input.h already has common drivers/core, native bsd/dev and common userland/src placements. Use actual manifest entries. |
| Queue concurrency | Conditional future concern in first worker; present unlocked ISR access in separate input candidate now makes it a concrete integration blocker. |
| Missing brief | Confirmed and remedied by this publication; earlier failed freeze and unselected newer edits are preserved. |

Matching complete reference files are retained under the fixed snapshot references/ with exact hashes in MANIFEST.json and in the earlier supplement evidence/phase-4/antigravity-first-review-supplement/20261117T022721584880Z. Original reviewer documents are preserved unchanged. Main does not execute the review's runbooks as authorization.
"""
        result.update(baseline_selected=True, brief_ready=True, snapshot=selected["snapshot"],
                      snapshot_manifest=manifest_pin, verified_captured_files=checked,
                      workers={worker: {"handoff": row["files"]["HANDOFF.md"], "fixed_origin": row["fixed_origin"]} for worker,row in selected["workers"].items()},
                      unselected_live_drift={worker:[row["path"] for row in rows] for worker,rows in selected["unselected_live_worker_drift"].items()},
                      private_roots=private, path_audit=pin(packet/"path-audit.json"),
                      retained_failed_freeze=FAILED, worker_full_builds_allowed=False,
                      selected_artifacts=selected["current_artifacts"])
        state = json.loads((PROJECT / "state.json").read_text())
        require(state["phase_4_device_gate_passed"] is False, "Unexpected Phase 4 physical completion flag")
        state["phase_4"] = "in_progress"
        state["phase_4_parallel_workflow"] = {**result, "brief": "parallel/BRIEF.md", "independent_review": "docs/PHASE-4-INDEPENDENT-REVIEW.md"}
        state["next_action"] = "Reproduce the new input models, review corrected private handoffs and continue main UFS/recovery; test combined sources before integration and physical acceptance."
        current_state = f"""# HakiOS A51 - current state
Updated 17 November 2026 (Asia/Calcutta). Phase 4 is IN PROGRESS; its physical peripheral gate is UNPASSED. Phases 1-3 retain selected completion gates; Phases 5-10 remain planned.

The [four-worker brief](/C:/Users/Ankit/Desktop/A51/hakios-a51/parallel/BRIEF.md) is ready with fixed source/evidence inputs, per-file hashes, interfaces and four distinct private Windows/WSL output roots. Main owns storage, recovery, shared integration, central documentation and all phone operations; peers own display/brightness, touch/keys and independent review.

The first Antigravity candidate still needs changes before integration; 230 host cases / 337,647 checks and all four C++ compilations are independently retained. The separate input handoff has source blockers (wrong packet register, null-data ISR, synchronization, debounce and sustained reporting); its added test claims await independent reproduction. The independent report supports critical source concerns but needs corrections for EA8076 two-byte brightness, default patch stripping, ownership/IOVA and unmeasured hardware consequences. See [first review](/C:/Users/Ankit/Desktop/A51/hakios-a51/docs/PHASE-4-ANTIGRAVITY-FIRST-REVIEW.md) and [independent disposition](/C:/Users/Ankit/Desktop/A51/hakios-a51/docs/PHASE-4-INDEPENDENT-REVIEW.md).

Earlier live freeze {FAILED} FAILED when display files changed. Its result and bytes remain intact. New selection {result['packet']} internally verifies fixed historical copies and current main/adapted/artifact pins; live worker drift is recorded and unselected. Existing peer folders and all main/WSL driver sources are preserved.

Retained main host proof: 216 native cases / 337,511 checks, 244 storage models and 25 QEMU checks, reusable only for matching pins. UFS adopts an initialized idle link; controller/PHY initialization, current genuine 64 KiB known-image execution and binary recovery persistence remain unfinished. Actual display, brightness, touch and key gates remain unpassed.

The dated read-only Android inventory at evidence/phase-4/main-resume/20261117T002159343005Z and storage-path audit at evidence/phase-4/storage-path-audit/20261117T002742491892Z remain verified observations. No fresh phone operation occurred during handoff/brief work. Both disabled legacy device-gate entry guards are preserved; historical inventory fields are unchanged.

Next: reproduce added input tests, continue UFS/recovery, review corrected worker handoffs, then test supported combined sources before integration and coordinated physical acceptance. Compilation, QEMU and PASS text cannot establish peripheral success.
"""
        note = f"""
\n## P4-045 - Publish fixed four-worker inputs and brief ({packet.name})

Purpose/files: scripts/phase4-freeze-parallel.py and new scripts/phase4-publish-parallel-brief.py; parallel/BRIEF.md; fixed selected snapshot {selected['snapshot']}; distinct new private roots/logger copies; manifests/phase4-parallel-workflow.json; current STATE/state.json, README/INDEX and this append-only log. Existing worker folders and main/WSL implementation sources are preserved read-only. All existing progress is retained.

Failed installation: the first long publisher installation command was rejected before process launch with Windows os error 206 (filename or extension too long); no script/document/source write occurred. The same prepared code was installed using smaller logged staged pieces and syntax-checked before installation.

Failed attempt: runs/20261117T030338287089Z-p4-freeze-four-worker-inputs exited 1 at its final live-consistency check: {failed['error']}. Original packet {FAILED} and captured manifest {CAPTURE_SHA} remain unchanged. Logged inspection runs/20261117T030540315799Z-p4-inspect-freeze-worker-drift confirmed later display edits. This publication verifies internally fixed captured bytes and chooses the originally reviewed first worker revision; newer live edits are recorded as unselected, not attributed to old tests.

Verification: {checked} captured files checked; new snapshot MANIFEST hash {manifest_pin['sha256']}; current main/adapted files, upstream heads and selected WSL artifacts match at publication. PATH-AUDIT records Windows/WSL path identity, nested native tree, shared output symlinks/processes and four distinct private roots. Worker full XNU builds remain disabled; explicit private model/object builds are allowed. No phone operation, source promotion or physical gate success.

Limitations/next: slices are not full dependency checkouts. Added input model claims remain pending reproduction; source blockers are assigned in the brief. Main continues UFS/read-only storage and recovery logging while peers correct supported candidates. Retain the selected main native/build/QEMU proof for matching pins.

Rollback: preserve packet/index/after bytes and later changes; restore only central files still matching their recorded after hashes from exact before copies, or withdraw newly created selection/brief/private roots after retaining them. Do not restore whole source trees, edit existing peers, re-enable legacy guards, delete prior evidence or change phone state. Keep append-only history.

## P4-046 - Record independent-review support and corrections ({packet.name})

Purpose/files: docs/PHASE-4-INDEPENDENT-REVIEW.md and the brief. Retain original report/HANDOFF unchanged with hashes. Supported source concerns: unowned framebuffer rendering, repeated mapping lifetime, missing DPP fetch path, DSIM full-FIFO fallthrough and missing workflow brief.

Verification/evidence: reuse coordinator's unchanged independently reproduced first-candidate models/compilations and retained matching Android/XNU references. EA8076 and S6E3FA9 both build two brightness parameter bytes from the 10-bit table. Default git apply strips one prefix and the unified patch already reconstructed the candidate in private staging. Existing a51_input.h adaptation placements are retained. Unreserved DRAM is not ownership; a DPP base may be an IOVA; exact leak size and actual panic/corruption were not measured.

Limitations/rollback: review changes documentation only, does not accept unsafe recommendations or integrate drivers. Separate input ISR concurrency is now a concrete source blocker; added input tests await execution. Preserve this report and withdraw its central selection only after checking later work. No phone operations or physical acceptance.
"""
        top = "## Phase 4 four-worker workflow - 17 November 2026\n\nPhase 4 remains IN PROGRESS; physical gates are UNPASSED. The [fixed four-worker brief](/C:/Users/Ankit/Desktop/A51/hakios-a51/parallel/BRIEF.md) is ready. Existing handoffs and progress are preserved; first/display and input candidates need changes, and [independent-review corrections](/C:/Users/Ankit/Desktop/A51/hakios-a51/docs/PHASE-4-INDEPENDENT-REVIEW.md) are recorded. See [current state](/C:/Users/Ankit/Desktop/A51/hakios-a51/docs/STATE.md). Older scopes below are historical.\n\n"
        replacements = {"parallel/BRIEF.md": brief, "docs/PHASE-4-INDEPENDENT-REVIEW.md": review,
                        "state.json": json.dumps(state, indent=2) + "\n", "docs/STATE.md": current_state,
                        "manifests/phase4-parallel-workflow.json": json.dumps(result, indent=2) + "\n",
                        "docs/IMPLEMENTATION-LOG.md": (PROJECT/"docs/IMPLEMENTATION-LOG.md").read_text() + note}
        for rel in ("README.md", "docs/INDEX.md"):
            text = (PROJECT/rel).read_text()
            start = text.index("## Phase 4 handoff review - 17 November 2026")
            end = text.index("## Retained Phase 4 host checkpoint", start)
            replacements[rel] = text[:start] + top + text[end:]
        before = {rel: pin(PROJECT/rel) if (PROJECT/rel).exists() else None for rel in replacements}
        write_json(packet/"before-file-pins.json", before)
        write_json(packet/"result.json", result)
        documents(packet, replacements)
        for rel, text in replacements.items():
            require((PROJECT/rel).read_bytes() == text.encode("utf-8"), "Document publication mismatch: " + rel)
        validate_disabled_gate(PROJECT/"scripts/phase4-device-gate.py")
        index_packet(packet)
        print(json.dumps({k:v for k,v in result.items() if k not in ("private_roots","workers")}, indent=2), flush=True)
        return 0
    except Exception as exc:
        result["error"] = str(exc)
        write_json(packet/"result.json", result)
        index_packet(packet)
        print(json.dumps(result, indent=2), flush=True)
        return 1

if __name__ == "__main__":
    raise SystemExit(main())
