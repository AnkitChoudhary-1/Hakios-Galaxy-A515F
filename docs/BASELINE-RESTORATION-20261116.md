# Baseline restoration and storage retry — 16 November 2026

The independent pinned baseline was restored and verified. The repaired 64 KiB UFS read is still unverified on hardware. The latest retry also restored the pinned boot image and returned to completed rooted Android with unchanged recovery/DTBO and verified staging cleanup.

## Independent restoration evidence

The prior failed trial `evidence/phase-4/storage-trial/20261115T213856233327Z/cycle-1/result.json` remains byte-for-byte unchanged, including its original restoration failure. The independent restoration supersedes that historical device status; it does not turn the failed storage trial into a pass. Recovery UUID: `412c0f92-31a3-4ad9-93d8-9c33a9e000d5`. Verified returned Android UUID: `d08d8255-bc1a-4168-b3d5-0f038d70617c`.

Recovery model/root/boot target/61,865,984-byte size and recovery/DTBO pins were checked. The independently pinned Everline KernelSU boot image was staged and hashed, written only to `/dev/block/sda12`, read back to SHA-256 `eb30609a62999e3282ac81e0a5e56411ef12ec1a39c107171bf3e01209c7cb67` before reboot, and checked again in completed rooted Android. Both exact staging paths from nonce `25f9798aa52d4763abae651571919914` were removed and their absence verified. Recovery, DTBO, partition layout, Android sources/backups and userdata were preserved.

- Corrected original recovery capture: `evidence/phase-4/baseline-recovery-capture/20261116T010854001746Z/`.
- Final Android/root/partition/staging verification: `evidence/phase-4/baseline-return-verification/20261116T011720900876Z/`.
- staged_hash: `runs/20261116T011108211252Z-p4-independent-recovery-staged-hash/`.
- write: `runs/20261116T011122003038Z-p4-independent-recovery-restore-boot/`.
- readback: `runs/20261116T011457478817Z-p4-independent-recovery-boot-readback/`.
- reboot: `runs/20261116T011526544710Z-p4-independent-recovery-return-android/`.

The first collector packet `baseline-recovery-capture/20261116T010624908001Z` incorrectly interpreted ADB transport success as remote-file availability. It is retained and superseded by the framed capture. Both missing pstore exports have transport exit 0 but remote exit 1; recovery's pstore listing was empty. These are unavailable exports, not payload success.

## Latest completed retry

Trial: `evidence/phase-4/storage-trial/20261116T012331081270Z/cycle-1/result.json`; nonce `4f577c1c6a7d4cbbaab34e40acdcdc8b`; original wrapper: `runs/20261116T012330314346Z-p4-storage-repair-silicon/`.

Candidate SHA-256: `f645571cbb877aab9b5a9d7dbae4902bb720f51e15e1b3967b04aa6ec9a27964`. Trial passed: `false`; latest baseline verified: `true`; storage gate: `false`. Error: `Candidate did not reach recovery before the deadline`; capture error: `Recovery console export failed or was unframed`. Wrapper exit 1 at `2026-11-16T01:29:42.290650+00:00`; recorded candidate return wait: 242 seconds. Recovery UUID `5a057f7e-193f-428a-8309-60bb6a3a2710`; completed rooted Android UUID `b674c765-6e77-43ed-815f-a8c1e6c4a042`.

The generic capture error does not establish missing framing: the original console and pmsg acquisitions were framed correctly with remote exit 1, transport exit 0 and zero stdout bytes. `/sys/fs/pstore` listed `total 0`. Exports were unavailable; no new UFS completion/hash/fatal result or hardware root cause can be inferred. Original staged baseline/hash, boot readback before reboot, `final-completed=1`, root/model/target/size, fresh UUID, all three partition hashes and final exact staging absence are replayed by this recorder.

Investigate the failed recovery log capture before another storage candidate. The retry was already active in a separate local process when this continuation resumed. No overlapping device operation was launched. This recorder performs host reads/documentation only. Retained input hashes, before/after documents and the exact diff are in `evidence/phase-4/baseline-restoration-review/20261116T015024935010Z/`.

## Selected host checks

| Check | Retained passing evidence |
|---|---|
| Native shared UFS model, 74 cases/316,791 checks | `evidence/phase-4/peripheral-native-tests/20261116T010350110512Z/` |
| Isolated kernel/userland build | `evidence/phase-4/platform-build/20261115T213458578092Z/` |
| Kernel/userland QEMU integration | `evidence/phase-4/platform-qemu/20261116T010427975972Z/` |
| Storage lifecycle/parser models, 118 cases | `evidence/phase-4/storage-trial-tests/20261115T212706751122Z/` |
| Corrected exporter, 74 cases with both alignment settings | `evidence/phase-4/recovery-export-qemu/20261115T215525223262Z/` |
| Host-only preflight | `evidence/phase-4/storage-preflight/20261116T012234119779Z/` |

The source pins and packet indexes for these unchanged checks are verified and reused. Passing host/QEMU checks do not establish A51 DMA completion, exporter execution or recovery persistence.

## Scripts, verification and rollback

`scripts/phase4-capture-recovery.py` uses the explicit ADB path/serial and framed remote exit codes for read-only recovery capture. Optional missing exports stay failures. `scripts/phase4-verify-baseline-return.py` bounds Android reconnection, checks a fresh UUID/completed boot/root/model/target/size and all partition pins, and optionally removes only a recorded trial's exact staging files after baseline verification. Neither script installs a storage candidate. Their retained executions establish this restoration's evidence.

This documentation recorder verifies packet indexes, the unchanged original failed result, original restore hashes and strict staged-hash/write/readback/reboot timing, plus the original latest retry's framing, final boot/root/hash/UUID and exact staging cleanup. It requires a completed trial wrapper before updating current summaries, preserves the selected retry, and checks original document pins captured from the same bytes used to construct replacements immediately before writing. Phase 4 remains in progress. The retained wrapper snapshots reproduce this review's exact source and arguments:

```powershell
python scripts/run.py --label p4-baseline-restoration-reconciliation -- python -B scripts/phase4-record-baseline-restoration.py --latest-trial-result evidence/phase-4/storage-trial/20261116T012331081270Z/cycle-1/result.json --latest-run runs/20261116T012330314346Z-p4-storage-repair-silicon
```

This command adds the review once; after it passes, replay from the retained input/source snapshots in an isolated copy rather than overwriting current documents or historical evidence.

For documentation rollback, verify this review packet's `document-changes.json` and restore its indexed `before/` bytes for only the listed files; remove the new guide/recorder if undoing this addition. Preserve all original device/run evidence. A documentation rollback does not change a phone partition. Independent device restoration remains documented in `docs/PHASE-4-DEVICE-PATH.md`.
