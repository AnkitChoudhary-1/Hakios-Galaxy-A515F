# Current observed status — 24 November 2026

## Current installation — 25 November 2026

R1 was flashed on 25 November 2026 from TWRP with full boot backup and matching full-partition readback. The user explicitly requested proceeding at 1% battery; USB charging was checked before staging and before writing. Recovery/DTBO remained unchanged. Physical boot completion, accurate touch, speaker playback, Iris icon/launch and diagnostic persistence await confirmation. Phase gates remain unchanged. Earlier checkpoints below retain their historical scope.

Latest user report: silent speaker audio and taps landing in the wrong place. The latest installed image pin and Iris observation are unknown while ADB is disconnected. Earlier v3/v4 installation evidence is historical; external v9 source changes are not proof of a tested image.

Implemented in r1: DT-based 0–4095 touch mapping, checked manual gates/Q-channel and PLL transitions, amplifier transfer failure gating, ordinary-memory read-only diagnostics and restored full userland/Iris registration. Sources: platform/devices/a51, patches/current-xnu.patch, scripts/repair-touch-audio.py and scripts/device-diagnostics.c.

Host verified: fresh kernel/loader; 11 audio and 4 Iris native ASan/UBSan cases; all4096 touch coordinates and64 clock patterns; all507 root and12 flashboot entries read back with clean APFS checks; image layout/pins; same kernel/loader reaches Darwin PID1/uid0 in QEMU with raw hello and audio disabled. Validation receipts: validation/touch-audio-r1/. The existing post-link XNU kext symbol-set-only exit2 remains an accepted wrapper limitation.

Candidate r1 has not been installed by this repair. Physical touch accuracy, speaker media playback, Iris icon/launch, diagnostic persistence and GPU acceleration remain unverified. Headphones, capture and route switching remain unavailable. Source audits and compilation are not hardware validation. Phase4 is in progress with its peripheral gate unpassed; storage/recovery-export blockers persist.

The new candidate restores a separate root-tree from the retained verified v3 userland image; it preserves the externally stripped active root. The public export includes authored source, recipes, docs and hashed evidence summaries. Runtime/SDK/firmware/generated phone images and private diagnostics/backups remain local. Read [r1 repair record](TOUCH-AUDIO-REPAIR-20261124.md) for exact pins, prerequisites, limits and rollback.
