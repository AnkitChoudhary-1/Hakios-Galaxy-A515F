# HakiOS A51 - current state

## Touch/audio r1 installation — 25 November 2026

R1 was flashed from rooted TWRP on 25 November 2026 after the user explicitly requested proceeding at 1% battery. USB power and Charging were verified before staging and immediately before writing. The full boot backup is retained and independently hashed. One boot write and one reboot succeeded; full-partition SHA-256 readback matched, and recovery/DTBO hashes stayed unchanged. Physical boot completion, touch accuracy, speaker playback, Iris icon/launch and diagnostic persistence remain unverified. Bounded ADB observation: no_adb_boot_confirmation. Phase gates unchanged. Receipt: [installation result](PUBLICATION.md).

Earlier checkpoints below retain their historical scope.

## Latest touch/audio r1 host candidate — 24 November 2026

Latest user report: silent speaker and taps landing in the wrong place. The new r1 candidate corrects DT-based coordinate scaling, checked audio clocks/amp setup and restores full userland/Iris registration plus diagnostics. Fresh build, native/APFS/package and minimal QEMU checks passed. It is not installed yet: ADB sees no device. Physical touch/audio/Iris and diagnostic persistence remain unverified; phase gates unchanged. Read [r1 repair guide](TOUCH-AUDIO-REPAIR-20261124.md). Dated checkpoints below retain their historical scope.

## Audio/Iris v3 installation — 24 November 2026

V2 reached the iOS home screen per user, but audio was silent, Iris absent and SSH unavailable. V3 includes targeted audio clock/DMA/amplifier changes and nondestructive Iris boot registration. Its native checks, APFS/package checks and minimal QEMU PID1 test passed; authorized TWRP installation and full boot-partition readback passed. Recovery/DTBO are unchanged. V3 home-screen/audio/Iris acceptance is pending. Phase 4 and all existing completion gates are unchanged. See [repair details](AUDIO-IRIS-REPAIR-20261124.md).

Older checkpoints below retain their historical scope.

## Authorized device installation — 24 November 2026

The user explicitly authorized installation from connected TWRP. Repaired full-quality v2 was written to boot and independently verified by full-partition SHA-256 before reboot. The user reports “booting in ios.” This is boot progress, not home-screen/GPU/audio acceptance. Recovery/DTBO remain unchanged; the old boot partition is backed up. Bounded ADB observation: no_adb_boot_confirmation. Phase gates are unchanged. Evidence: [installation receipt](PUBLICATION.md).

The host-repair checkpoint below describes the state before this installation.

Updated 24 November 2026 (Asia/Calcutta). The latest supplemental task is the [GPU/audio boot build repair](GPU-AUDIO-BUILD-REPAIR.md). Selected [full-quality repaired v2 image](PUBLICATION.md): 29,700,096 bytes, SHA-256 `9f7fd881143c1ba81a28359ead8000b0d9a953690e67ebac3e0a603dd806ec30`. Contiguous GPU allocation and boot packaging were repaired; latest audio and Iris are included. Host checks passed, and the same rebuilt kernel/UEFI loader reached PID1/uid0 in QEMU. Final md0/md1 startup, phone boot, accelerated GPU behavior and audible audio remain unverified. The earlier working “full-quality” image was not located; its retained recipe was reconstructed.

This repair captured device logs read-only and performed **no phone write, staging, reboot or flashing**. Failed-image stage0 existed; its required **md1 was missing**, correcting an early missing-program inference. The package uses the live UEFI shared page instead of a stale UFS pointer. The first minimal repair is superseded by v2, which preserves Iris. See [final evidence](PUBLICATION.md), [documentation/export verification](PUBLICATION.md) and the repair guide for source pins, failures and rollback.

Phase 4 remains **IN PROGRESS** and its physical peripheral gate is **UNPASSED**. Phases 1–3 retain their selected completion gates; Phases 5–10 remain planned. This supplemental package does not replace the storage candidate or clear its recovery/export blocker. Installation/device validation remain pending.

## Retained 19 November checkpoint

The following checkpoint is historical. Its phase evidence, failed storage trial and verified baseline return remain preserved.

The supplemental [upstream Galaxy A51 port audit](UPSTREAM-A51-PORT-AUDIT.md) passed against the active WSL checkout. Packet [`20261119T112540897049Z`](PUBLICATION.md) pins 65 Git worktrees, the selected 15,048,864-byte ARM64 Mach-O kernel, 2,097,152-byte UEFI image, exact A51 configuration, 15 tool commands, 17 packages, 8,795 SDK files and six retained build runs. Its independent replay passed with 95 ledgered files. This was host-only: no phone query, write, reboot, flashing, IPSW download or phase-gate change occurred. The 136 captured `PORTING.md` excerpts remain upstream assertions, not local proof of iOS 16.5 boot, display, touch, Wi-Fi, GPU or Metal behavior.

The latest authoritative host-only checkpoint is [host-readiness/20261119T121143895035Z](PUBLICATION.md), produced by `runs/20261119T064135755192Z-phase4-contiguous-prdt-host-readiness-final`. It passed **240 native cases / 337,535 checks, 244 modeled storage cases and 25 QEMU checks** with `device_operations=false` and `phase_4_gate_passed=false`. These results verify matching source, build, QEMU and preflight evidence; they do not establish A51 peripheral execution.

The selected storage repair uses one genuine sixteen-block, 64 KiB READ(10) into a contiguous kernel-owned DMA buffer. A valid result must report `prdt_count == 1` and `prdt_bytes == 128`. That contract is verified in native/QEMU/harness checks but remains **unverified on A51 hardware**. Historical 4 KiB reads and sixteen-command 64 KiB aggregates do not qualify the current path.

The revision validator starts from the build's `initial_adaptation_packet`, accepts at most 64 unique ordered revisions, checks every retained before/after link and requires the final revision to equal `adaptation_packet`. The 119 current device-cycle failure models reject duplicate, reordered, omitted, broken, post-build and drifted histories. All four shared header copies match at 6,650 bytes and SHA-256 `a1af295eca6cdbfa85fb941865d02ded4e73db82d77ff084320109664db08127`.

Storage preflight [20261119T082444878694Z](PUBLICATION.md) passed host prerequisites only. It prepared nonce `52ff74e2e759496782bae1528f358bb3` in candidate packet `evidence/phase-4/storage-candidate/20261119T082444932365Z`; the 61,865,984-byte image has SHA-256 `7ea55347547b813317ccfc3af19e2f33f938c103bb91d3b2aca05b1e5b1b338a`. That preflight completed zero cycles and performed no device operation. Its candidate was not staged, installed, flashed, booted or executed. Failed storage preflights `20261119T054240862766Z` and `20261119T063642154956Z`, plus failed device preflights `20261118T213751189140Z` and `20261118T213926739261Z`, remain preserved with their original errors.

The current read-only A51 preflight passed. [Live inventory 20261119T082617776063Z](PUBLICATION.md) verified serial `A51_SERIAL_HERE`, model `SM-A515F`, completed rooted Android, `/dev/block/sda12`, 61,865,984 boot bytes, the pinned baseline hash, an unchanged boot UUID, UFS logical block size 4,096, boot start sector 222,336 and absolute UFS LBA 27,792. Battery was 97%. Run `runs/20261119T082659324006Z-phase4-device-preflight-rollback-pins` independently matched boot, recovery and DTBO SHA-256 pins. GPIO debugfs was unavailable but non-required; `inventory_valid=true`. This session performed device reads only: no staging, write, reboot, module load, candidate execution or SELinux change occurred.

Exactly one explicitly authorized storage cycle then ran through `runs/20261119T083427970875Z-phase4-storage-repair-silicon-authorized`. [Trial 20261119T083428785023Z](PUBLICATION.md) used nonce `594d0e8f3eb44839b334dbc1ebed0617` and a fresh 61,865,984-byte candidate with SHA-256 `2d51ab7ff204b7c2e2d842ceee167c31044838d380c360815a33210d91d0919b`. The candidate write and readback completed, but the cycle failed because recovery was not reached within the 180-second deadline; the recorded wait was 181.172 seconds. Recovery subsequently connected with boot ID `68c27e9a-201a-499e-bfb7-055160c09975`.

Recovery listed `/sys/fs/pstore` as `total 0`; both console and pmsg exports were correctly framed remote exit 1 with zero payload bytes. No nonce-bound record, UFS completion, PRDT telemetry, transfer digest, timer result or write-guard result was recovered. The current single-PRDT UFS path therefore remains **unverified on A51 hardware**.

Rollback succeeded on attempt 0. Baseline readback matched SHA-256 `eb30609a62999e3282ac81e0a5e56411ef12ec1a39c107171bf3e01209c7cb67` before reboot, rooted Android completed boot with UUID `17436b89-c1dd-4512-9cb0-6fe3174af88c`, recovery and DTBO retained their pinned hashes, and all temporary staging paths were absent. No module or SELinux change occurred. This consumed the single-cycle authorization; no additional device cycle is authorized. Investigate recovery/export persistence before preparing any later candidate, and require new explicit authorization before another boot-partition write. Physical visible display, repeatable brightness, touch coordinates, power/volume keys and combined reporting also remain unpassed. `phase4-resume-audit.py` was not run.


## Requested source published — 24 November 2026

Current HakiOS source, audio/Iris v3 changes, UEFI source overlays, build tools and documentation were published to [Hakios-Galaxy-A515F](https://github.com/AnkitChoudhary-1/Hakios-Galaxy-A515F) on main at initial commit `24c2b1b5e1b6d6bea0144fd5380f3b8ffe6053c2`. Native remote main and the GitHub connector independently confirmed the commit. All 1515 staged files matched the reviewed bytes. XNU patch application and all 269 result hashes passed. Publication receipts are under evidence/publication/requested-20261124. This is a source export; binaries and private/proprietary inputs remain local. V3 screen/audio/Iris acceptance remains pending, and no phase gate changed. A follow-up documentation commit records this first-publication receipt.
