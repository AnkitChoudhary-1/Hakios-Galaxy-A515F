# iOS 16.5 / HakiOS on Galaxy A51 — AI handoff plan

Updated 19 November 2026, Asia/Calcutta.

## Current decision

Continue only with **host-side and read-only investigation**. Do not write the boot partition, install a loader, reboot into a candidate, repartition the phone, or emit an installable device image from this plan.

Phase 4 remains **IN PROGRESS** and `phase_4_device_gate_passed` remains `false`. The previously authorized single storage cycle was consumed. It failed to produce a persistent recovery record, then restored and verified the Android baseline. **No additional device cycle is authorized. Any later boot-partition write requires new, explicit user authorization for one identified candidate and one bounded trial.**

The exact first task is [IOS165-A51-WP5A: recovery/export-persistence host investigation](#first-exact-next-task-ios165-a51-wp5a). There is no reliable basis for promising that a complete iOS 16.5 environment will boot today.

## Objective

Determine, with retained evidence, whether the audited upstream Galaxy A51 HakiOS port can be turned into a lawful, reproducible and recoverable boot path that:

1. identifies the role and compatibility of the selected UEFI and XNU artifacts;
2. boots an attributable A51-specific loader/kernel path;
3. mounts a compatible Darwin/HakiOS root filesystem and starts a defined first user process;
4. preserves useful logs across failure or reset;
5. returns to the pinned Android or recovery baseline through a verified procedure; and
6. only then evaluates display, input, storage, Wi-Fi and graphics claims on this device.

The first realistic software target is a **minimal Darwin/HakiOS user space associated with the iPhoneOS 16.5 SDK**, not an unsupported claim that a stock iOS 16.5 IPSW can simply be downloaded and booted on Samsung hardware.

## Non-goals

- This document does not authorize flashing, partition writes, repartitioning, loader installation, candidate booting or a phone reboot.
- It does not provide executable flashing commands.
- It does not discard or rewrite the existing Phase 1–4 evidence.
- It does not treat an iPhoneOS SDK as an iOS installation image or root filesystem.
- It does not claim that an Apple IPSW is compatible with the Exynos 9611, Samsung boot chain or A51 peripherals.
- It does not authorize bypassing activation, code signing, encryption, entitlement, licensing or platform security requirements.
- It does not establish display, touch, keys, Wi-Fi, GPU, Metal, Safari, Apple services or a complete iOS home screen.
- It does not mark a phase complete from compilation, artifact structure, QEMU execution or upstream documentation alone.

## Required reading order

Another AI must read these records before changing code, configuration or evidence:

1. Root [`AGENTS.md`](../AGENTS.md) for workspace boundaries and evidence rules.
2. Project [`README.md`](../README.md).
3. Authoritative current [`STATE.md`](STATE.md) and [`state.json`](../state.json).
4. This plan.
5. [`INDEX.md`](INDEX.md) and [`HANDOFF.md`](HANDOFF.md).
6. [`UPSTREAM-A51-PORT-AUDIT.md`](UPSTREAM-A51-PORT-AUDIT.md).
7. [`PHASE-4-UFS-REPAIR.md`](PHASE-4-UFS-REPAIR.md), especially the latest failed trial and verified restoration.
8. [`PHASE-4-DEVICE-PATH.md`](PHASE-4-DEVICE-PATH.md) for retained recovery constraints; its commands are historical procedures, not authorization.
9. [`IMPLEMENTATION-LOG.md`](IMPLEMENTATION-LOG.md), with attention to P4-049 through P4-051 and P1-012.
10. The ten-phase [`ROADMAP.md`](ROADMAP.md). Its older status paragraphs are historical; `STATE.md` controls current status.
11. Local `AGENTS.md` files inside any upstream checkout before modifying that checkout.

## Status vocabulary

Use these words consistently:

| Status | Meaning |
|---|---|
| Implemented | Source or documentation exists. It may not have executed successfully. |
| Verified | The stated behavior was observed and is backed by retained evidence for the named environment. |
| Planned | Work is described but has not been implemented or executed. |
| Unavailable | A required input or interface was checked and was not accessible in the tested context. |
| Unknown | The project has no adequate evidence yet. |

Never promote an upstream assertion, enabled configuration symbol, successful compile, valid file format, QEMU result or result from a different artifact into local A51 verification.

## Verified inputs and evidence

### Current project/device state

- Phase 4 is `in_progress`; its physical device gate is false.
- Earlier project evidence records A51 XNU milestones in Phases 2–3. That evidence must not be transferred to the newly audited upstream kernel/UEFI or to a complete iOS 16.5 userspace.
- The current storage implementation has host evidence for one sixteen-block, 64 KiB READ(10) with one PRDT entry. It lacks a qualifying nonce-bound A51 recovery record.
- The last authorized trial is `evidence/phase-4/storage-trial/20261119T083428785023Z`. It exceeded its 180-second recovery deadline, later reached recovery, found `/sys/fs/pstore` empty and recovered neither console nor pmsg bytes.
- Rollback from that trial succeeded on attempt 0. Baseline boot SHA-256 is `eb30609a62999e3282ac81e0a5e56411ef12ec1a39c107171bf3e01209c7cb67`; recovery is `12412e2008d950260cda627ac7a6b8eac954b49ef9db5573a297f67e4fc85999`; DTBO is `41662c61ff3158448935025477a4e29d445823dab2cddafb18ea649c8ea925d6`. Rooted Android completed with boot UUID `17436b89-c1dd-4512-9cb0-6fe3174af88c`, and temporary staging paths were absent.
- The single-cycle authorization is consumed and `additional_cycle_authorized=false` in `state.json`.

### Audited upstream A51 port

The source under review is the audited checkout corresponding to [`speedyg2200/hakios-xnu-kernel`, branch `a51-port`](https://github.com/speedyg2200/hakios-xnu-kernel/tree/a51-port). The local active checkout is `/opt/a51-hakios/upstream-a51/hakios` in WSL distribution `A51-KernelBuilder`.

Selected host evidence:

| Input | Verified host identity |
|---|---|
| Audit packet | `evidence/phase-1/upstream-a51-port/20261119T112540897049Z` |
| Main HakiOS commit | `14b7cdbe502f9ca5e1481cf1e6c7890fe8d3343a` |
| A51 device commit | `0773636aea5de1c246e2cb3a72b2cb824c5b7316` |
| UEFI source commit | `26fe9a2844e0c2c852dca79cb173091744ba8aae` |
| XNU overlay commit | `c54f35ca767986246321eb901baf8f5ff7923f6a` |
| Kernel | 15,048,864-byte ARM64 Mach-O, SHA-256 `38ea0ee0c6bf38bbc0c3a5ac2f60b28dd2bdbf1a058a3130a2bdd79750093f33` |
| UEFI | 2,097,152-byte firmware image, SHA-256 `038283aa0f0afcda6058e44b7331febd31cbc990bce0456c408bc9be17250ec1` |
| Kernel configuration | SHA-256 `72b228f50e0c78e6a19bc42932d057901a2d4e92792fb7649a8df490ad61f30d`, 384 parsed symbols |
| iPhoneOS 16.5 SDK source | Commit `0222fd5413cf4b9af096f37b4621afa2688572f7`; 8,795 files; tree SHA-256 `94e4bca9629203156f99d7be9572e66dc304b930ed76ae6e06879adf9669e38d` |

The final audit documentation validation is `runs/20261119T113719208726Z-upstream-a51-port-final-documentation-validation-corrected`. It passed with 95 packet files, 75 local links, four selected file pins, three selected runs and 11 host-only flags verified false.

### Evidence boundary

The audit verifies repository pins, generated overlays, selected artifact structure, configuration, toolchain, packages, SDK tree and retained build provenance. It performed no phone query, write, reboot, flash, IPSW download, root-filesystem assembly or peripheral execution.

The captured upstream `PORTING.md` statements about an iOS 16.5 home screen, display, touch/buttons, Wi-Fi and Mali/Panfrost OpenGL ES are **upstream assertions**. They are not local proof. In particular, an OpenGL or Panfrost path is not evidence of Apple Metal support.

## Unknowns and blockers

1. **Boot-chain relationship:** it is not yet proven how the 2 MiB UEFI firmware, Mach-O kernel, Samsung boot image, device tree, boot arguments and any initramfs/root filesystem are assembled and handed off on this exact A51 path.
2. **Artifact pairing:** structural validity and matching source pins do not prove that the selected UEFI and kernel are a mutually compatible runtime pair.
3. **Samsung acceptance:** the audited artifacts have not been wrapped, accepted or executed on this device as a new candidate.
4. **Persistent failure evidence:** the latest actual trial produced no pstore, console, pmsg or nonce-bound record. Another risky boot is unjustified until this path is understood or replaced.
5. **Darwin root filesystem:** no compatible, reproducible root filesystem with a defined PID 1 has been assembled and verified for this port.
6. **Complete iOS 16.5 user space:** the iPhoneOS SDK is not a bootable operating system. Availability, licensing, architecture compatibility, dependencies, code-signing requirements and device assumptions for Apple-distributed user-space components remain unresolved.
7. **Device drivers:** the newly audited branch's display, touch, keys, Wi-Fi and GPU claims have not been reproduced locally. Phase 4's current physical display/input/storage gates also remain unpassed.
8. **Graphics terminology:** OpenGL ES acceleration through Panfrost would not establish Metal compatibility or the performance of SpringBoard/Safari.
9. **Recovery route:** recovery eventually connected after the last deadline, but the time bound, reset behavior and reliable log collection route are not established.
10. **Schedule:** these blockers prevent a defensible estimate for a complete iOS 16.5 boot. No AI should promise a same-day result.

## Work plan

All work packages below are host-only unless a later section explicitly says otherwise. Each package must retain inputs, commands, outputs, failures and a pass/fail result. A package is not complete merely because code compiles.

### WP0 — Replay and freeze the upstream audit

Purpose: confirm that the selected checkout and inputs have not drifted before analysis begins.

Actions:

- Replay `scripts/verify-upstream-a51-port.py` through `scripts/run.py` against the selected immutable packet.
- Record current WSL distribution, checkout path, commits, dirty-overlay expectations, artifact hashes, configuration hash, SDK commit/tree hash and tool identities.
- If any input differs, preserve the failed replay and create a fresh audit packet. Never rewrite the selected packet.
- Check for active build or QEMU processes before using shared outputs.

Deliverable: a passing replay tied to exact current bytes, or an explicit drift report. This does not establish bootability.

### WP1 — Determine boot-chain and artifact roles

Purpose: replace assumptions about “the kernel” and “the UEFI” with an exact chain of responsibility.

Build a source-cited matrix that answers:

- What Samsung firmware loads first, from which partition/container and at what architectural state.
- Whether the UEFI image is directly packaged, embedded by another stage or only a host build product.
- Which component loads the Mach-O kernel, device tree, boot arguments, ramdisk/root filesystem and trust metadata.
- Required load addresses, alignment, memory ownership, CPU exception level, MMU/cache state, interrupt state and secondary-core behavior.
- Which configuration or source path selects `a51Pkg` and which generated overlays belong to that build.
- How failure logs are committed before reset and how recovery is expected to discover them.
- Which artifact is responsible for return/reset to Android or recovery.

Required output: `docs/IOS-16.5-A51-BOOT-CHAIN.md`, a machine-readable artifact-role manifest and citations to exact source bytes. Mark every unresolved edge as unknown. Do not infer a device path from filenames.

Pass gate: every selected artifact has a documented producer, consumer, format, hash, expected load/entry contract and failure behavior. Any incompatible or missing edge blocks packaging.

### WP2 — Identify lawful, compatible Darwin user-space inputs

Purpose: decide what “iOS 16.5” can honestly mean for this project.

Classify candidate inputs into:

- open-source Darwin components that can be built and redistributed under their licenses;
- HakiOS-provided programs and libraries;
- SDK headers, stubs and build metadata that support compilation but are not runtime files;
- user-supplied proprietary files whose possession, use and redistribution must be lawful and whose compatibility remains unproved; and
- unavailable components that block a complete Apple user experience.

For every runtime file, record provenance, license/redistribution status, architecture, minimum OS/ABI, linked libraries, interpreter/dynamic-loader path, expected services, signing state and SHA-256. Never place proprietary bytes in Git or a public evidence packet. Do not provide or automate security-bypass instructions. If the right to use an input is unclear, stop and document it as unavailable pending user/legal confirmation.

Decision output:

- **Target A:** minimal open Darwin/HakiOS root filesystem capable of starting a defined PID 1; or
- **Target B:** broader Apple user space, only if lawful inputs and all runtime dependencies can be demonstrated.

Target A must be completed first. A stock IPSW download is not an accepted shortcut and cannot be called compatible without evidence.

### WP3 — Define deterministic root-filesystem construction

Purpose: produce a reviewable filesystem design before producing any device candidate.

The specification must define:

- filesystem or ramdisk format and size budget;
- ARM64 ABI and kernel/user ABI assumptions;
- exact PID 1 and launch sequence;
- dynamic loader, libc and required shared libraries;
- device nodes, mounts, console/log path and read-only versus writable areas;
- ownership, permissions and configuration files;
- how drivers expose display, input, storage and network services;
- failure behavior when a required service is missing;
- deterministic file ordering, timestamps, metadata and full manifest/hash generation; and
- how the image is tested without a phone.

Prefer a minimal read-only root with temporary writable memory filesystems until storage-write safety is independently proven. Host validation must reject missing dependencies, wrong architecture, path traversal, duplicate paths, unexpected proprietary files, non-deterministic output and size overflow.

Pass gate: two clean host builds produce byte-identical root-filesystem output and manifests; a compatible emulator or host harness reaches the defined PID 1 where technically applicable. This still does not pass a device gate.

### WP4 — Verify UEFI, kernel, configuration and root-filesystem compatibility

Purpose: prove that all selected pieces describe one coherent boot attempt.

Checks must include:

- exact source/build/run association for UEFI and kernel;
- Mach-O entry/load-command bounds and expected boot-argument ABI;
- UEFI firmware-volume integrity and actual loader path;
- device-tree source, overlays/fixups and final consumption path;
- physical/virtual load ranges, reserved-memory overlap and ownership;
- expected exception level, page size, MMU/cache and interrupt transitions;
- initramfs/root-device support and the selected filesystem format;
- required kernel symbols/configuration versus actually linked code;
- console, fault envelope, watchdog/reset and persistent log exporter;
- absence of stale generated overlays or post-build source drift; and
- exact compatibility matrix among UEFI, kernel, configuration, root filesystem and packaging template.

Pass gate: all compatibility checks and meaningful negative/mutation tests pass against the exact selected bytes. A compile, clean link or valid parser result alone is insufficient.

### WP5 — Design and verify persistent recovery logging

Purpose: make the next failure diagnosable before risking another candidate.

Investigate the complete producer-to-consumer path:

- loader/kernel record layout, checksum/commit sequence and nonce binding;
- physical address, alignment, total size and reserved-memory ownership;
- cache clean, memory barrier, MMU-off and reset behavior;
- whether Samsung firmware or either kernel clears or reuses the region;
- recovery kernel configuration for pstore, ramoops, console and pmsg;
- recovery DT/DTBO reservation and ramoops node geometry;
- recovery mount/discovery timing and exact exported filenames;
- capacity and truncation behavior for binary and text records; and
- an alternative retrieval channel if RAM persistence cannot be made reliable without unsafe assumptions.

Use the existing failed trial as a test fixture. Reconstruct why an empty `/sys/fs/pstore` is consistent with each possible failure mode, and add host tests that reject incorrect address, geometry, alignment, commit, checksum, nonce, cache-transition and configuration combinations.

Pass gate: source/configuration evidence and host tests establish a single coherent persistence design, or explicitly conclude that the current pstore route is unavailable and select a safer alternative. Do not request another device trial merely to discover which undocumented assumption was wrong.

### WP6 — Validate packaging without emitting or installing a device image

Purpose: check container/layout compatibility while keeping this phase non-mutating.

- Model the proposed artifact placement in memory from pinned inputs.
- Verify partition-size bounds, headers, offsets, padding, hashes, AVB-related fields and the exact list of changed regions.
- Require the selected UEFI, kernel, root filesystem and logging configuration identities in one manifest.
- Run mutation tests for truncation, stale input, wrong target/model, offset overlap, oversized payload, missing rollback image and mismatched evidence.
- Produce reports and manifests only. Do not retain an installable `.img`, Odin archive or other device-ready payload during this work package.

Pass gate: the dry-run is deterministic, all changed regions are explained, rollback inputs are pinned and negative tests reject every modeled mismatch. Packaging success is not execution evidence.

## Read-only device-preflight gate

This gate may run only after WP0–WP6 have passed or have explicit blocking conclusions. It permits bounded reads from the phone in its current mode. It does not authorize a reboot, mode transition, staging, module load, security-policy change or partition write.

Required observations:

- exact serial `A51_SERIAL_HERE` and model `SM-A515F`;
- current Android completion/root state and boot UUID;
- boot, recovery and DTBO hashes matching the selected rollback pins;
- boot partition identity, byte size, start sector and logical block size;
- sufficient battery/power and stable transport;
- absence of stale staging paths or unexpected partition drift;
- current recovery/pstore configuration facts obtainable without changing device state; and
- matching host source, build, QEMU, root-filesystem, logging and dry-run manifests.

Stop and fail the preflight on any identity, size, hash, geometry, source, build, evidence or transport mismatch. Preserve the failed packet. If a required recovery-persistence fact cannot be learned read-only, mark it unknown and design a separately scoped diagnostic; do not silently convert preflight into a boot trial.

A passing read-only preflight means only that the prerequisites were current at that moment. It does not authorize a write.

## Authorization boundary for any later device trial

Before any boot-partition write, obtain a new user instruction that explicitly authorizes:

- the exact device and target partition;
- one named candidate identified by byte size and SHA-256;
- exactly one bounded cycle;
- the selected baseline/rollback hashes;
- the maximum wait/attempt limits; and
- automatic restoration under the documented stop conditions.

General instructions such as “continue,” “go on,” “boot it” or approval of this plan are not authorization for a future boot-partition write. If the candidate, source, configuration, logging design or rollback input changes, the authorization does not carry forward.

## One bounded future trial design

This is a design specification, not an executable procedure.

### Preconditions

- WP0–WP6 pass against the exact candidate inputs.
- Read-only device preflight passes immediately before the trial.
- A fresh per-run nonce is embedded in every expected log/report path.
- Candidate, baseline boot, recovery and DTBO bytes are independently hashed and available.
- The persistent log route has a documented producer/consumer contract and capacity.
- Recovery and Android return deadlines are fixed before starting.
- The user has provided the explicit authorization described above.

### Single-cycle sequence

1. Create an immutable trial packet and journal intended mutations before each operation.
2. Stage and verify the independent baseline needed for recovery.
3. Change only the authorized boot target; do not touch recovery, DTBO, userdata or partition layout.
4. Verify candidate readback before attempting a boot.
5. Attempt exactly one boot within the fixed deadline.
6. Capture raw loader/kernel/recovery output before Android or another boot can overwrite it.
7. Stop after the single attempt regardless of apparent progress.
8. Restore the baseline, verify its readback before reboot and return to Android or recovery.
9. Recheck boot, recovery and DTBO hashes, Android completion/root state, a fresh boot UUID and staging-file absence.

### Required evidence

- wrapper metadata with exact argv, UTC/IST times, exit status and complete output;
- device serial/model and partition identity/geometry;
- nonce, candidate/baseline sizes and SHA-256 values;
- before/write/readback/boot/capture/rollback state transitions;
- unedited raw binary and text logs, including empty outputs and remote exit codes;
- loader/UEFI/XNU/root-filesystem identities recovered from the device record;
- entry state, last committed stage, fault syndrome/registers and reset reason where available;
- proof that storage writes stayed disabled except for the explicitly authorized boot restoration path;
- final baseline readback and Android/recovery return evidence; and
- photographs or video only as supplementary evidence for visible display/input behavior, never as a substitute for attributable machine logs.

### Immediate stop conditions

Stop before the candidate write if the serial, model, partition, size, start sector, baseline hash, recovery hash, DTBO hash, candidate hash, source/build identity, battery/power, transport, logging contract or rollback input differs.

After a candidate write, stop further experimentation and restore the baseline if readback differs, the deadline expires, recovery/log capture is unavailable, an unexpected partition changes, the device repeatedly disconnects, the device temperature/power state becomes unsafe or any unplanned mutation occurs. Do not attempt a second candidate boot in the same authorization.

### Verified rollback gate

Rollback is verified only when:

- the restored boot partition readback equals the pinned baseline SHA-256;
- recovery and DTBO still equal their pins;
- Android or the designated recovery environment completes startup;
- the device identity and a fresh boot UUID are recorded;
- temporary staging files are absent; and
- all attempted operations and failures are retained.

Merely issuing a restore operation, observing a logo or reconnecting ADB does not pass rollback.

## Acceptance gates

| Gate | Evidence required | Insufficient evidence |
|---|---|---|
| A. Upstream reproducibility | Pinned source/dependencies, clean replay, artifact and SDK identities | Repository claims or branch name |
| B. Coherent boot chain | Source-cited artifact roles, entry/memory/log/reset contract | Valid Mach-O/UEFI structure or compilation |
| C. Root filesystem readiness | Deterministic compatible image, dependency manifest and defined PID 1 | iPhoneOS SDK or downloaded IPSW alone |
| D. Recoverable trial readiness | Proven logging design, rollback pins, dry-run and read-only preflight | Historical recovery access or an empty pstore |
| E. Minimal A51 execution | Nonce-bound local device record from exact artifacts plus verified rollback | QEMU, another kernel, another phone or upstream screenshots |
| F. Minimal Darwin boot | A51 mounts the selected root and reaches its defined PID 1 with attributable logs | XNU entry or kernel banner alone |
| G. Complete iOS 16.5 claim | Lawful compatible Apple user space reaches the specifically defined UI/services with reproducible local evidence | SDK-based build, home-screen assertion or partial HakiOS shell |
| H. Phase 4 peripherals | Correct display dimensions/input coordinates, repeatable brightness/keys and matching read-only storage data on A51 | Enabled config symbols, model tests or upstream `PORTING.md` |

Compilation alone cannot pass any device-execution, user-space or peripheral gate. QEMU verifies only the behavior exercised by the selected emulation.

## Evidence and command rules

- Run every consequential command through `scripts/run.py`; retain its exact arguments, output, exit status, timestamps and script snapshots.
- Use fresh UTC-stamped immutable evidence directories. For the first task, use `evidence/phase-4/recovery-export-analysis/<UTC-stamp>/`. Continue using existing phase-specific roots for later work; do not move historical packets or invent a new completed phase.
- Each packet needs a manifest containing relative path, byte size and SHA-256 for every retained file except the manifest itself.
- Preserve failed and partial packets. Never overwrite a selected result or “clean up” evidence that explains a failure.
- Pin source commits, dirty-overlay expectations, configurations, build outputs, SDK/runtime inputs and tool versions.
- Redact credentials and private tokens. Avoid retaining unrelated personal data from device logs.
- Record implementation/configuration changes in `IMPLEMENTATION-LOG.md` with purpose, files, verification, limitations, next action and rollback.
- Update `STATE.md` and `state.json` only when verified evidence, an explicit blocker or a gate actually changes. Do not change them for planning text alone.
- Keep upstream checkouts clean. Retain local adaptations as reviewable patches with exact before/after hashes and provenance.
- Never run the older state-writing `scripts/phase4-resume-audit.py` as part of this investigation.

## First exact next task: IOS165-A51-WP5A

**Name:** Host/read-only recovery and export-persistence investigation.

**Authorization:** host filesystem and source reads only. If the phone is already connected in Android, only commands already proven to be bounded reads may be used. No reboot, recovery transition, staging, module load, SELinux change, candidate generation, image emission or partition write.

**Inputs:**

- `docs/STATE.md`, `state.json` and `docs/PHASE-4-UFS-REPAIR.md`;
- trial `evidence/phase-4/storage-trial/20261119T083428785023Z`;
- candidate packet `evidence/phase-4/storage-candidate/20261119T083428836110Z` as historical bytes only;
- loader/exporter source, especially `prototype/xnu-loader/a51_recovery_export.S`;
- current recovery image, recovery kernel configuration, DT/DTBO and retained live ramoops observations;
- scripts that parse/capture pstore and storage-trial evidence; and
- upstream A51 UEFI/kernel source paths responsible for reset and log publication.

**Work:**

1. Replay and index every original last-trial output without altering it.
2. Trace the record from producer writes through commit/checksum/cache maintenance/reset to recovery discovery and export.
3. Extract the recovery kernel's pstore/ramoops/pmsg/console configuration and the effective DT/DTBO reservation geometry.
4. Compare producer address/size/alignment with the recovery consumer and with all reserved-memory owners.
5. Enumerate failure hypotheses: producer never ran, record not committed, wrong physical address, overlap, alignment fault, cache not cleaned, reset cleared RAM, firmware reused memory, recovery lacked the driver/configuration, DT geometry differed, capture occurred too late or parser rejected valid bytes.
6. Tie every hypothesis to evidence that confirms, rejects or leaves it unknown.
7. Add host-only negative tests for the remaining geometry, checksum, commit, nonce, cache-state and configuration cases.
8. Decide whether the pstore route is supportable. If not, design an alternative attributable logging channel without implementing a device write.

**Deliverables:**

- `docs/IOS-16.5-A51-RECOVERY-EXPORT-ANALYSIS.md`;
- an immutable packet under `evidence/phase-4/recovery-export-analysis/<UTC-stamp>/`;
- a producer/consumer geometry table and failure-hypothesis matrix;
- exact replay/test commands retained through `scripts/run.py`; and
- a clear `ready_for_new_trial`, `not_ready` or `route_unavailable` result. `ready_for_new_trial` still does not authorize a write.

**Pass gate:** all relevant selected bytes are pinned; recovery configuration and reservation geometry are known; host tests cover the selected contract and its negative cases; and the last empty pstore result has a defensible explanation or the current route is explicitly rejected. If this cannot be achieved without a device state change, stop and request a separately scoped user decision.

## Handoff checklist

Before ending a continuation, the next AI must report:

- exact work package and authorization boundary followed;
- files changed and why;
- commands/runs and selected evidence packets;
- what is implemented, verified, planned, unavailable and unknown;
- all failed attempts retained;
- whether phone reads, writes, reboots, module/security changes or candidate execution occurred;
- current baseline/rollback state if the phone was touched;
- phase and device-gate status, with no inference from compilation;
- the single next safe task; and
- whether new user authorization is required.

Current handoff answer: begin IOS165-A51-WP5A. Do not promise a same-day complete iOS 16.5 boot, do not create an installable candidate and do not write the device.
