# Phase 4 host checkpoint — 16 November 2026

**Phase 4 IN PROGRESS; device gate UNPASSED.** This checkpoint records the completed host verification and the remaining implementation and physical acceptance work. The assigned collaboration is host-only: no phone query, transfer, write, reboot, flash or payload execution occurred. Current phone screen, USB/ADB state and installed bytes are unknown.

Read root `AGENTS.md`, README, STATE, INDEX, IMPLEMENTATION-LOG and the roadmap before resuming. Work stays under `C:\Users\Ankit\Desktop\A51\hakios-a51` and `/opt/a51-hakios` in `A51-KernelBuilder`. The roadmap's older status paragraphs and dated project milestones are historical; its Phase 4 acceptance criteria remain applicable.

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

Completed readiness wrapper: `runs/20261116T165852846880Z-p4-current-host-readiness`; exit 0, finished `2026-11-16T17:03:57.827602+00:00`. Packet: `evidence/phase-4/host-readiness/20261116T165855086084Z`. It verifies exact packet indexes, current template/source/build correspondence, matching QEMU artifacts, completed wrapper versions, sanitized native output, modeled storage cases, original QEMU bytes, linked symbols, unchanged upstream HEADs, eight selected Phase 3 parent files and stable selection manifests.

| Selection | Packet under `evidence/phase-4/` | Result |
|---|---|---|
| Source capture | `readonly-source-capture/20261116T160051202640Z` | Current bytes, retained revision history and Android references pinned. Earlier provenance gaps remain recorded. |
| Applied adaptation | `readonly-platform-revision/20261116T163741193643Z` | Sixteen adapted files; before/after patches retained. |
| Native protocols | `peripheral-native-tests/20261116T163819181432Z` | 216 cases / 337,511 checks: UFS 74 / 316,791; input 42 / 20,620; reporting 100 / 100. ASan/UBSan and strict compilation passed. |
| Attributed build | `platform-build/20261116T164515848522Z` | Selected revision, templates, adapted files and artifacts matched. |
| Kernel/user QEMU | `platform-qemu/20261116T164742842361Z` | 25 checks passed; actual XNU/PID 1/timer/SPI execution and explicit physical-gate pending reporting. |
| Storage harness | `storage-trial-tests/20261116T164819519944Z` | 244 modeled parser/lifecycle cases passed. These use simulated transports, not a device. |

Build root: `/opt/a51-hakios/experimental/phase4-port/20261114T150320411427Z`. Kernel SHA-256: `3d4a0ae89f4a111c7c4e21ac6bac59e7249d8cae62daa1843ee15f7576be5911` (15,218,432 bytes). User program SHA-256: `4a10d5692244b959ad22482107b3270aa3ed97655b5ace8567e3545dd6404455` (16,736 bytes).

Pinned common HEAD: `63fc2b4633bac3af8e57dadab9f5a8d4cb940438`. Native XNU HEAD: `c54f35ca767986246321eb901baf8f5ff7923f6a`. Local adaptations are retained separately; unchanged HEADs do not assert an unmodified working tree. Checkpoint `result.json` pins the selected inputs; `changes.json`, `before/`, `after/` and `documents.patch` retain this integration. Historical evidence and source captures are not rewritten.

## Failed recording attempt and legacy gate restoration

The initial recording wrapper `runs/20261116T172331315130Z-p4-host-checkpoint-record` exited 1 before creating a checkpoint or changing documents. Static inspection found that `phase4-device-gate.py` retained its disabled warning but both execution guards had been removed. Its intermediate body also added constant-label brightness parsing; the author and timing of that change are not established by this checkpoint.

This integration restores the immediate exception in `run_phase4_cycle()` and the message/exit-2 return at the start of `main()`. It preserves the intermediate body, including the brightness parsing, behind those guards. The gate's exact observed before bytes, guarded after bytes and diff are retained. The historical audit's AST predicate checks both entry points before integration and during replay. No legacy device command is executed, and adding a brightness label check does not establish physical brightness acceptance.

## Historical hardware observations and failed attempts

The rejected report `silicon-execution/20261116T091954739903Z` contains three nonce-bound cycles. Offline audit `evidence/phase-4/completion-audit/20261116T101146104534Z` independently replays candidate-prefix 4 KiB and aggregate 64 KiB hashes and three timer samples per cycle. Its captured producer used sixteen one-block commands and constant peripheral labels. It has zero qualifying Phase 4 cycles. The current source/build proof does not retroactively attribute those older candidates to the current revision.

Independent restoration review `evidence/phase-4/baseline-restoration-review/20261116T015024935010Z` remains byte-pinned (22,518 bytes, SHA-256 `8dcd27639dd825f5fcd207e9ff41a24932894ab462bbe0d75a5f4e4b8d20d8f6`). Its original inputs and the latest retry's command frames are replayed offline. Historical restoration at `2026-11-16T01:29:42.290650+00:00` verified baseline boot hash `eb30609a62999e3282ac81e0a5e56411ef12ec1a39c107171bf3e01209c7cb67`, rooted completed Android UUID `b674c765-6e77-43ed-815f-a8c1e6c4a042`, recovery/DTBO pins and staging absence. This establishes that historical return only. The later three-cycle report lacks original rollback outputs for independent replay.

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

From `C:\Users\Ankit\Desktop\A51\hakios-a51`, replay this document/state checkpoint and the original historical evidence without rebuilding or operating a phone:

```powershell
python -B scripts/run.py --label p4-host-checkpoint-replay -- python -B scripts/phase4-record-host-checkpoint.py --verify-review evidence/phase-4/host-checkpoint/20261116T172916769408Z
```

The verifier checks retained packet/index/input hashes, exact current after copies, both disabled legacy entry guards, untouched state fields, append-only log history and historical audit/restoration bytes. It reuses the completed readiness proof at its recorded time; it does not re-query live WSL source trees. Run the existing readiness verifier when a new live-tree correspondence check is warranted.

For changed implementation inputs, use the existing host entry points in order, through `scripts/run.py`: `phase4-test-peripherals.py`, `phase4-build-platform.py`, `phase4-qemu-platform.py`, `phase4-test-storage-trial.py`, then `phase4-verify-host-readiness.py`. Each retains exact arguments/output/status/times and source versions. Do not rebuild or rerun unchanged passing inputs solely because physical acceptance is missing. Follow each adaptation's pinned patch history and read upstream AGENTS before source edits. Failed-run packets remain evidence.

The device/recovery commands in [PHASE-4-DEVICE-PATH.md](PHASE-4-DEVICE-PATH.md) and [PHASE-4-UFS-REPAIR.md](PHASE-4-UFS-REPAIR.md) are historical/future device procedures, outside this assignment. They were not executed here. The historical baseline is verified; current phone status is unknown.

## Rollback

Checkpoint: `evidence/phase-4/host-checkpoint/20261116T172916769408Z`. Verify its index and `changes.json` before restoring files. For each of the nine pre-existing document/state files listed there, require the current bytes to match its `after` hash (otherwise reconcile later work), then copy only its exact `before/<path>` bytes back to the same project path. `docs/IMPLEMENTATION-LOG.md` is restored from its complete before copy; this checkpoint retains the removed entry in its after evidence.

The tenth pre-existing file is `scripts/phase4-device-gate.py`. Keep its restored entry guards disabled during a host-only rollback. Its unguarded before snapshot is inspection evidence; restoring it as runnable code would re-enable the legacy device actions. The intermediate body is already preserved in the guarded after version.

The new guide and recorder have `before=null`. If withdrawing them, first retain their current bytes in a new rollback packet and remove only those two exact project files. Preserve this original checkpoint and all runs/evidence; do not modify its index or place unindexed rollback files inside it. No recursive deletion, Git reset, WSL source rollback or phone restoration is involved. Existing Android projects, backups, Phase 3, recovery, DTBO, partition layout and userdata were outside this integration's write set.
