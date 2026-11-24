# Phase 4 UFS repair and recovery checkpoint — current through 19 November 2026

## Current contiguous single-PRDT checkpoint — 19 November

The authoritative current host-only result is `evidence/phase-4/host-readiness/20261119T121143895035Z/result.json`, produced by completed wrapper `runs/20261119T064135755192Z-phase4-contiguous-prdt-host-readiness-final`. It passed **240 native cases / 337,535 checks, 244 modeled storage cases and 25 QEMU checks**. It records `device_operations=false` and `phase_4_gate_passed=false`. This verifies source/build/QEMU/preflight correspondence only; it is not A51 UFS execution evidence.

The selected 64 KiB path issues one genuine sixteen-block READ(10) into a kernel-owned contiguous buffer and reports exactly one full 128-byte FMP PRDT: `prdt_count == 1` and `prdt_bytes == 128`. The parser rejects any different count or length. Current native, QEMU and storage-harness evidence supports this contract, but the path remains **unverified on A51 hardware**. Historical 4 KiB success and sixteen separate 4 KiB aggregates do not verify this implementation.

All four shared `hakios.a51.h` copies were rechecked at 6,650 bytes with SHA-256 `a1af295eca6cdbfa85fb941865d02ded4e73db82d77ff084320109664db08127`; the completed record is `runs/20261119T064801749702Z-phase4-final-header-copy-hashes`.

The device-cycle provenance validator now replays from the build's `initial_adaptation_packet`, accepts at most 64 unique ordered revision packets, checks each retained before/after link and requires the final revision to equal the build's `adaptation_packet`. The 119 passing failure-model tests reject duplicate, reordered, omitted, broken, post-build and drifted revision histories. These are host models and do not qualify a physical gate.

Storage-only preflight `evidence/phase-4/storage-preflight/20261119T082444878694Z/result.json` passed with `preflight_only=true`, an empty cycle list and `device_operations=false`. It prepared nonce `52ff74e2e759496782bae1528f358bb3` in candidate packet `evidence/phase-4/storage-candidate/20261119T082444932365Z` (61,865,984-byte boot image SHA-256 `7ea55347547b813317ccfc3af19e2f33f938c103bb91d3b2aca05b1e5b1b338a`). The candidate was **not staged, installed, flashed, booted or executed**. The two preceding failed storage preflights remain preserved: `20261119T054240862766Z` rejected an invalid/duplicate revision chain, and `20261119T063642154956Z` rejected a revision not retained before the selected build.

Read-only device preflight `evidence/phase-4/live-inventory/20261119T082617776063Z/result.json` passed with `inventory_valid=true`. It verified connected completed rooted Android, the pinned boot image and unchanged boot UUID, battery 97%, `/dev/block/sda12` at 61,865,984 bytes, 4,096-byte UFS logical blocks, boot start sector 222,336 and UFS LBA 27,792. `runs/20261119T082659324006Z-phase4-device-preflight-rollback-pins` matched the pinned boot, recovery and DTBO hashes. The unavailable GPIO debugfs query was retained and was not a required predicate. These preflight operations were device reads only; no staging, write, reboot, module load, candidate execution or SELinux change occurred.

One explicitly authorized cycle later ran through `runs/20261119T083427970875Z-phase4-storage-repair-silicon-authorized`. Trial `evidence/phase-4/storage-trial/20261119T083428785023Z/cycle-1/result.json` used nonce `594d0e8f3eb44839b334dbc1ebed0617` and candidate SHA-256 `2d51ab7ff204b7c2e2d842ceee167c31044838d380c360815a33210d91d0919b`. It failed its 180-second recovery deadline with a recorded wait of 181.172 seconds. Recovery subsequently connected, but `/sys/fs/pstore` was empty and both console and pmsg reads returned framed remote exit 1 with zero bytes. No nonce-bound storage record or transfer telemetry exists, so this trial does not prove that the current single-PRDT path executed on silicon.

The same cycle restored the baseline on attempt 0, verified the boot-partition readback before reboot, returned to completed rooted Android with boot UUID `17436b89-c1dd-4512-9cb0-6fe3174af88c`, rechecked the boot/recovery/DTBO pins and removed all staging files. Phase 4 therefore remains **IN PROGRESS** with its physical gate **UNPASSED**. Investigate recovery/export persistence before another candidate. Any later boot-partition trial requires a fresh candidate, matching host checks and new explicit authorization. Display, brightness, touch and key gates also remain outside this storage checkpoint.

## Earlier host checkpoint — 16 November

This historical checkpoint is superseded by the 19 November host selection above. See [PHASE-4-HOST-CHECKPOINT.md](PHASE-4-HOST-CHECKPOINT.md) for its then-current genuine-read implementation, explicit pending reporting, exact host evidence and integration limits. Phase 4 remained **IN PROGRESS**, with its device gate **UNPASSED**. No phone operation occurred in that continuation; current screen/connection were unknown. Device commands below remain retained procedures, not evidence that a new trial ran.

Phase 4 remains **IN PROGRESS**. The pinned baseline was independently restored and verified, and the latest retry also returned to completed rooted Android with matching boot/recovery/DTBO hashes and staging cleanup. The repaired **64 KiB UFS read remains unverified on hardware**: the retry missed its recovery deadline and captured no usable storage result. The corrected exporter's A51 execution and recovery survival remain unknown. See [restoration and retry evidence](BASELINE-RESTORATION-20261116.md).

## Newer chunked-read evidence — 16 November completion audit

Three later candidates have matching recorded 64 KiB aggregate hashes through sixteen separate 4 KiB READ(10)s. Their aggregate report rewrites the first command's block/byte counts; it does not verify the single 64 KiB READ(10) repair. The template captured by that audit differed from the genuine-read repair. The selected current revision restores a genuine sixteen-block command and truthful reporting; its hardware execution remains unverified. No driver source was changed in this audit. Text logs were recovered via Android early_probe/console; the committed binary export remains unverified. Phase 4 stays unpassed because physical display, brightness and input tests are missing. See [current review](PHASE-4-COMPLETION-REVIEW.md).

## What the retained silicon evidence establishes

The older storage trial is `evidence/phase-4/storage-trial/20261115T193839789423Z/cycle-1/`. Its original `capture-pstore-console.stdout.bin` contains:

| Observation | Result and limit |
|---|---|
| Single READ(10), LBA 27792, one 4096-byte block | `rc=0`, `ocs=0`, 88 microseconds; SHA-256 `acab1ef7cace1fe3538dd58e5a82b15d89dd6923d551c4bba668eeca3027be3f` matches the independent candidate bytes. |
| Multi READ(10), same LBA, sixteen blocks | `rc=-5`, `ocs=15`, 97 microseconds; no valid digest. |
| Multi terminal registers | `IS=0x20000`, `doorbell=1`, `HCS=0x109`; the reported lifecycle is quarantined and the reread is skipped. |
| DMA monitors | `0x1010404:0x2:0x1010101:0`; the second word is a monitor count, not a decoded error code. |
| Write submission guard | `rc=-30`, one rejection, `doorbell=0`. |
| Return | That older trial restored the pinned baseline and returned to rooted Android. Its overall result still failed the saved-loader-record contract. |

`IS=0x20000` is **SYSTEM_BUS_FATAL_ERROR**. OCS 15 is the diagnostic's incomplete sentinel, not a SCSI CHECK CONDITION. The original five-second timeout did not expose this distinction. The current driver notices fatal interrupts immediately and records terminal/vendor telemetry before cleanup. No valid SCSI sense response is available from an uncompleted DMA command.

The old DMA buffer began at `0x83e54000`, which is 4 KiB aligned and crosses a 64 KiB boundary during a full transfer. Requiring a contiguous, 64 KiB-aligned buffer is a bounded experiment. Its effect on silicon is **unverified**; neither this address observation nor passing model tests establish the bus-fatal root cause.

Older display, brightness and physical-input PASS labels were superseded by source review. This storage repair does not qualify those gates. Timers, earlier nonces and earlier rollback remain historical evidence; they cannot establish the latest trial's return.

## Implemented driver and exporter changes

[a51_ufs_readonly.h](../prototype/phase4-platform/a51_ufs_readonly.h) and [hakios.a51.c](../prototype/phase4-platform/hakios.a51.c) retain one genuine READ(10) for the full 64 KiB request. A single zeroed 128-byte FMP bypass PRDT spans the contiguous kernel-owned buffer; response/PRDT UTRD fields use the matching Exynos byte units. Writes are rejected before pointer access or MMIO. Readiness commands precede **4 KiB → 64 KiB → 4 KiB**. Hashes require completion, zero OCS, a valid response, zero status/residual/sense and successful lifecycle restoration. Failed cleanup permanently quarantines the buffers until reset. The driver does not divide a failed read into smaller reads to satisfy the gate.

The recovery exporter had a separate, reproducible alignment defect. The production trampoline disables the MMU and data cache without clearing `SCTLR_EL1.A`; its persistent header is 12 bytes long. Old 64-bit stores at pmsg+12 and pmsg+44 were consequently misaligned. [a51_recovery_export.S](../prototype/xnu-loader/a51_recovery_export.S) now uses naturally aligned 32-bit stores for the same binary format.

Reproduction `evidence/phase-4/recovery-export-qemu/20261115T215423978011Z/` passes with alignment checking off and aborts with it on: ESR `0x96000061`, FAR `0xf9e9000c`, ELR `0x40201144`. Corrected execution `20261115T215525223262Z` passes both settings with the MMU/data cache off and instruction cache on. This confirms the exporter defect and emulated fix. It does not prove that this defect caused the latest phone return failure, or that the corrected exporter survives an A51 recovery boot.

## Historical selected host verification — 01:22 checkpoint

| Selection | Evidence |
|---|---|
| Native shared UFS model | `peripheral-native-tests/20261116T010350110512Z`: 74 UFS cases, 316,791 checks; input models are separate. |
| Driver adaptation | `readonly-platform-revision/20261115T213418804741Z`: indexed before/after files and prior source-history gaps. |
| Isolated XNU/userland build | `platform-build/20261115T213458578092Z`: passed; foreign writable UFS driver disabled. |
| Kernel/userland QEMU integration | `platform-qemu/20261116T010427975972Z`: passed; physical A51 MMIO deliberately denied. |
| Storage lifecycle/parser models | `storage-trial-tests/20261115T212706751122Z`: 118 modeled cases. |
| Corrected exporter execution | `recovery-export-qemu/20261115T215525223262Z`: 74 cases, 78,166,826 checks across both alignment settings. |
| Corrected host-only preflight | `storage-preflight/20261116T012234119779Z`: host prerequisites passed, no device operations. Candidate packet `storage-candidate/20261116T012234144534Z` was not installed. |

All entries are under `evidence/phase-4/`. The isolated build root is `/opt/a51-hakios/experimental/phase4-port/20261114T150320411427Z` in `A51-KernelBuilder`. Reuse unchanged passing suites when their source pins match. Rebuild and rerun matching checks only for changed inputs or unresolved failures.

## Failed trials and verified baseline restoration

### Latest authorized trial — 19 November

Trial: `evidence/phase-4/storage-trial/20261119T083428785023Z/cycle-1/result.json`; wrapper: `runs/20261119T083427970875Z-phase4-storage-repair-silicon-authorized`; nonce: `594d0e8f3eb44839b334dbc1ebed0617`. The 61,865,984-byte candidate is `evidence/phase-4/storage-candidate/20261119T083428836110Z/candidate-boot.img`, SHA-256 `2d51ab7ff204b7c2e2d842ceee167c31044838d380c360815a33210d91d0919b`. The independent baseline was staged and hashed before the candidate. Candidate write and partition readback succeeded, followed by the bounded reboot attempt.

The result remains `passed=false` and `storage_gate_passed=false`: recovery was not reached within the 180-second deadline, and the recorded return wait was 181.172 seconds. Recovery subsequently connected with UUID `68c27e9a-201a-499e-bfb7-055160c09975`. Its pstore listing was `total 0`; console and pmsg reads were transport exit 0, framed remote exit 1 and zero stdout bytes. The generic stored `capture_error` does not change those original command records. No nonce record, UFS command status, PRDT count/length, transfer digest, timer sample or write-guard telemetry was recovered. Candidate execution and the current single-PRDT path therefore remain unproven.

Restoration succeeded on attempt 0. `restore-baseline-0-readback` matched baseline SHA-256 `eb30609a62999e3282ac81e0a5e56411ef12ec1a39c107171bf3e01209c7cb67` before reboot. Final Android completed with root and boot UUID `17436b89-c1dd-4512-9cb0-6fe3174af88c`; boot, recovery and DTBO hashes matched their pins, and all three temporary staging paths were absent. The operation record contains three file-write attempts, two boot-partition writes, two reboots, four removals, zero module operations and zero security changes. This was the one authorized cycle; another cycle must not run without new explicit authorization.

### Prior completed retry — 16 November

Trial: `evidence/phase-4/storage-trial/20261116T012331081270Z/cycle-1/result.json`; nonce `4f577c1c6a7d4cbbaab34e40acdcdc8b`; candidate SHA-256 `f645571cbb877aab9b5a9d7dbae4902bb720f51e15e1b3967b04aa6ec9a27964` (61,865,984 bytes). The candidate did not reach recovery before the 240-second configured deadline, with a 242-second recorded wait. Recovery subsequently became available for restoration. Original `restore-baseline-0-readback` output matches the pinned baseline before `return-baseline-android`; `final-completed=1`, root, fresh Android UUID `b674c765-6e77-43ed-815f-a8c1e6c4a042`, all partition hashes and exact staging absence were verified. The failed trial retains `passed=false` and `storage_gate_passed=false` while `baseline_restored=true` and `baseline_verified=true`.

The original capture error `Recovery console export failed or was unframed` is generic. Both console and pmsg reads were actually framed correctly: transport exit 0, remote exit 1, zero stdout bytes; `/sys/fs/pstore` listed `total 0`. These exports were unavailable. No new UFS completion, hash or fatal result is established, and neither the DMA failure's cause nor exporter execution can be inferred. Original commands and byte pins are retained in [the restoration review](BASELINE-RESTORATION-20261116.md).

### Independent restoration of the prior failed trial

The independent staged-hash/write/readback/reboot and Android verification records establish restoration before the retry. They supersede the earlier unverified device status without changing the historical failed result below. Recovery UUID `412c0f92-31a3-4ad9-93d8-9c33a9e000d5`; returned Android UUID `d08d8255-bc1a-4168-b3d5-0f038d70617c`.

Historical failed trial: `evidence/phase-4/storage-trial/20261115T213856233327Z/cycle-1/`; nonce `25f9798aa52d4763abae651571919914`. Candidate SHA-256 is `d66684414b9fddbed52748bf400fa47c42bcb74597d899a9f62d0aae705a8230`, 61,865,984 bytes. The candidate write occurred; recovery did not reconnect within the trial deadline or either bounded restoration wait. The result retains `candidate_write_attempted=true`, `baseline_restored=false`, `baseline_verified=false`. No new UFS result was captured from this trial.

Pre-trial Android UUID: `48abbf0d-a033-433c-b45e-53f9faf8734e`. Both exact staging paths below were subsequently removed and their absence verified in `evidence/phase-4/baseline-return-verification/20261116T011720900876Z/`. They are retained here as historical names:

```text
/data/local/tmp/hakios-p4-baseline-25f9798aa52d4763abae651571919914.img
/data/local/tmp/hakios-p4-25f9798aa52d4763abae651571919914.img
```

### Recovery procedure for a future unverified return

The [independent pinned-baseline recovery procedure](PHASE-4-DEVICE-PATH.md) applies. Connect USB and enter the existing recovery: hold Power + Volume Down, then switch to Power + Volume Up as the screen goes black. Leave recovery open without wiping or installing anything through its UI.

Use serial `A51_SERIAL_HERE` and `C:\Android\platform-tools\adb.exe`. Verify recovery mode, root, model, `/dev/block/sda12`, exact 61,865,984-byte boot size and unchanged recovery/DTBO pins. Capture original recovery pstore exports before reboot if they are available. The independent baseline is `C:\Users\Ankit\Desktop\A51\everline-ksu\artifacts\A51-PixelOS-Everline-KernelSU-Next-boot.img`, SHA-256 `eb30609a62999e3282ac81e0a5e56411ef12ec1a39c107171bf3e01209c7cb67`. Verify the host and staged bytes before the single boot write. Require matching boot readback **before rebooting**, then fresh completed rooted Android, unchanged recovery/DTBO and recorded cleanup of the two trial staging paths. Preserve every original failed-trial record.

## Historical next device check and rollback

Investigate recovery/export persistence before another storage candidate. Compare the retained recovery FDT/ramoops initialization, candidate layout, exporter reachability and reset path; absence of exported bytes alone does not identify a cause. After any relevant change passes matching checks, the future storage-only commands use a fresh nonce and current selections through `scripts/run.py`:

```powershell
python scripts/run.py --label p4-storage-repair-preflight -- python -B scripts/phase4-storage-trial.py --preflight-only
python scripts/run.py --label p4-storage-repair-silicon -- python -B scripts/phase4-storage-trial.py --cycles 1
```

Before using the second command, the fresh Android/root/partition checks must pass. The trial must independently match all three image hashes, validate each genuine DMA completion, reject writes before the doorbell, capture the nonce-bound binary record/log and verify the baseline return. A new multi-block failure requires analysis of its original fatal/vendor telemetry; the three-cycle whole-Phase-4 qualification remains pending after storage and all other gates qualify.

This reconciliation's indexed document before/after copies and diff are in `evidence/phase-4/baseline-restoration-review/20261116T015024935010Z/`. Earlier documentation rollback copies are indexed in `storage-repair-review/20261115T220257860822Z/before/`. The pre-exporter-change source checkpoint is `storage-repair-checkpoint/20261115T215121900466Z`; driver adaptation has its own indexed before/after packet. Restore only relevant pinned source/document files, rebuild matching changed inputs and retain all evidence. Source rollback does not restore a phone partition. Preserve Phase 3, Android projects, backups, recovery, DTBO, partition tables and userdata.
