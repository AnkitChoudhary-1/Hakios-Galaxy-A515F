# Touch and speaker repair r1 — 24 November 2026

## Current installation — 25 November 2026

R1 was flashed on 25 November 2026 from TWRP with full boot backup and matching full-partition readback. The user explicitly requested proceeding at 1% battery; USB charging was checked before staging and before writing. Recovery/DTBO remained unchanged. Physical boot completion, accurate touch, speaker playback, Iris icon/launch and diagnostic persistence await confirmation. Phase gates remain unchanged. Earlier checkpoints below retain their historical scope.

The user reports silent speaker audio and taps landing in the wrong place in the latest installed build. The currently installed image cannot be pinned while ADB is disconnected. Earlier recovery captured v4, but later source was changed externally to a v9 hardware experiment; neither later source nor filenames prove a hardware-tested image. Iris visibility in the latest build is unknown.

## Selected candidate and evidence

`artifacts/A51-HakiOS-full-quality-touch-audio-r1-boot.img`: 29,720,576 bytes, SHA-256 `2f22fbb6f0cacae5afb17488d4bcdc6b6bd3b64a6fd046721bfee43880544ea7`. Evidence: `evidence/build-repair/touch-audio-20261124-r1`. WSL work: `/opt/a51-hakios/build-repair/touch-audio-20261124-r1`.

Implemented: fixed touch scaling, checked clock/amplifier initialization, cached driver diagnostics, and restored full userland/Iris startup jobs. Host verified: fresh kernel/loader build, APFS contents and boot package, native regressions and minimal QEMU PID1/uid0. Not installed by this repair yet. Physical touch accuracy, audible speaker audio, Iris visibility/launch and diagnostic persistence remain unverified. All phase gates remain unchanged.

## Changes and source basis

Samsung's A51 DT specifies `melfas,max_x_y = <4095 4095>`. Its vendor driver takes these inclusive maxima from DT rather than chip resolution metadata. Both HakiOS input copies now use 4096 coordinate counts; chip resolution remains diagnostic only. Zero/one ranges fail safely. `kern.hakios_a51touch` exposes range and last raw/normalized sample for recovery diagnostics.

Audio restores the retained v3 ring/status/amplifier safeguards, correcting v9's gate/Q-channel control from Samsung `ra.c` and `cmucal-sfr.c`: manual gates set bits20/21, clear automatic gating bit28; QCH low bits6 request clocks with ENABLE0/REQ1/PM_IGNORE1. Unrelated register fields are preserved and readbacks checked. The reference-supported 48k PLL plan is retained with bounded transition checks; it is an estimate from register fields, not a measured BCLK. Amplifier transfer failures prevent sink registration and are logged. Ring startup is silent, 32fs remains consistent with 16-bit stereo, DMA status/address checks remain enforced. The GPU source and UEFI firmware are pinned unchanged. Headphones, recording and route switching remain unavailable.

The external v9 sources/binaries/configuration and Git changes were captured under `before/` before mutation. Its assumed ramoops memory writes and unchecked/loud boot experiment were replaced; startup diagnostics use ordinary kernel memory through read-only `kern.hakios_a51audio`. The Samsung reference checkout has no usable Git metadata: `references.json` records unknown commit and exact file hashes, not an invented upstream pin.

The stripped active userland root was preserved. A separate `root-tree` was restored from the retained verified v3 `root.apfs`, retaining modes and symlinks. All506 baseline entries matched independent readback. The v3 Iris helper binary matches its baseline image; its retained source matches the source tested here. A newly compiled static ARM64 diagnostics helper adds one entry; all507 final entries and all12 flashboot entries pass readback/APFS consistency. Only Iris registration and diagnostics are queued in this candidate's rc.jobs. The current Iris app is packaged separately in md0. The diagnostic helper snapshots both sysctls and app presence at20/40/60 seconds and calls existing var_store save. Archive persistence and extraction still need hardware validation; a helper exit status alone does not prove persisted data.

## Verification and failed attempts

`scripts/run.py` retains exact commands/output/status/times. Prepare first failed because the Samsung directory was not a Git repository, before source mutation; the resumed preparation verified the preserved snapshots and recorded HEAD unknown. Kernel build compiled the audio/input/GPU objects freshly and linked a fresh Mach-O. Its existing post-link kext symbol-set-only error2 is accepted by upstream make-kernel.sh in this configuration; no new compile/link failure occurred. Native ASan/UBSan tests passed11 audio cases,4 Iris retry/failure cases, all4096 touch values with clipping/metadata regression and64 gate/QCH bit-preservation patterns. Minimal QEMU uses this kernel/loader with audio disabled and raw hello; it cannot validate md0/md1 iOS startup or A51 peripherals.

Runs: `touch-audio-r1-prepare`, `prepare-resume`, `kernel`, `userland`, `native-tests`, `loader`, `package`, `verify`, `qemu`, `export`, `documentation` under runs/ with UTC prefixes. Root/boot recipes, source adaptations, Samsung references, kernel/build receipts, tests, image manifest and QEMU serial/result are retained in the evidence packet. Export preserves every older artifact and checks candidate bytes against the package manifest.

## Rebuild, installation and rollback

Run consequential actions through `scripts/run.py`. In WSL, `scripts/repair-touch-audio.py` supports prepare, kernel, userland, loader, package, verify, test and qemu. Preparation is intentionally single-use; preserve this work directory and choose a new revision for a fresh rebuild. `test-touch-audio.py` tests actual helpers; `export-touch-audio.py` exports checked bytes and evidence. Full runtime/SDK/firmware inputs remain separate and are not supplied by a source-only GitHub export.

The user's explicit build/flash authorization overrides the older host-only phase restriction for this supplemental repair. `flash-touch-audio.py install` requires the exact serial/model, rooted TWRP, boot target/size, battery, image/rollback hashes and recovery/DTBO pins. It backs up the full current boot and independently hashes it, stages checked images, writes boot only and verifies the complete partition before reboot. Failure uses the pinned Android fallback with readback. Later hardware observations must be recorded separately. Preserve before-image backups; an older striped image is not a known-good rollback. No repartition, recovery or DTBO write is authorized here.

Source rollback: use this repair's before snapshots/patches after checking current hashes and preserving intervening work. The separate full root-tree requires no rollback of the active root. Device fallback: `everline-ksu/artifacts/A51-PixelOS-Everline-KernelSU-Next-boot.img`, SHA-256 `eb30609a62999e3282ac81e0a5e56411ef12ec1a39c107171bf3e01209c7cb67`; checked installation verifies its full61865984 bytes. Publishing uses a normal follow-up commit in the requested repository and preserves earlier commits.


## Authorized r1 installation — 25 November 2026

R1 was flashed from rooted TWRP on 25 November 2026 after the user explicitly requested proceeding at 1% battery. USB power and Charging were verified before staging and immediately before writing. The full boot backup is retained and independently hashed. One boot write and one reboot succeeded; full-partition SHA-256 readback matched, and recovery/DTBO hashes stayed unchanged. Physical boot completion, touch accuracy, speaker playback, Iris icon/launch and diagnostic persistence remain unverified. Bounded ADB observation: no_adb_boot_confirmation. Phase gates unchanged. Receipt: [installation result](PUBLICATION.md).

Full partition: `fe0b641497b0c7622b76d6a0ca9e59c989aefcffec0e234c489748b1e0e857ca`. Before-image full partition: `2f305fb82ff0df52c339f4f621ddf5372521321b1fc6610a15da7ea6d61176df`. These hashes identify image bytes plus the retained partition tail. The earlier host-only/no-installation paragraphs describe the preceding checkpoint.

Initial attempt `20261124T233514923243Z-touch-audio-r1-install` stopped at the 30% battery check before staging or any write. The user then requested “just flash it anyway.” The r1 wrapper adds an explicit --allow-low-battery option; the default 30% check remains. The override verifies battery range, Charging/Full status and USB online at preflight and immediately before writing. All serial/model/root/partition/image/fallback/backup/readback checks remain. Successful run: `20261124T233948796103Z-touch-audio-r1-install-user-battery-override`. Observation: `20261124T234041342882Z-touch-audio-r1-observe`.

Changed files: scripts/flash-touch-audio.py (opt-in override), scripts/record-touch-audio-install.py (independent receipt verification and reconciliation), STATE/INDEX/README, this guide, implementation log and state.json. No build or image byte changed. No rollback was needed. Keep the full boot backup; its previous image had reported touch/audio failures. For a known Android fallback use the pinned image already described above, through exact-model recovery with full readback before reboot.
