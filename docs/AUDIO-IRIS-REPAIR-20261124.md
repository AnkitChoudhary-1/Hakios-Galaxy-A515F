# Audio and Iris repair — 24 November 2026

The user confirmed that full-quality v2 reached the iOS home screen, but audio was silent, Iris was absent and no SSH app was available. This is a user observation of the installed v2 image, not GPU acceleration, audio playback or a new phase-gate pass. The v2 installation receipt remains preserved.

V3 has been built, checked, exported, installed from explicitly authorized TWRP and rebooted. Home-screen completion, audible speaker output and Iris visibility/launch on v3 require device observation. No automatic device-success claim follows from host compilation or ADB absence.

## Selected inputs and output

- Output: `artifacts/A51-HakiOS-full-quality-audio-iris-v3-boot.img`, 29,712,384 bytes, SHA-256 `b0fa71744861524d40e97eb51214462ca81d9bd601d1a7fa320ca4b1677ad6c0`.
- Kernel: SHA-256 `e228007caf15fda4c3844f3e005199074a10dc5280233434810c41291a3f9ae3`.
- Audio source: SHA-256 `2abab2e6cc4cf3a205f6ccda805a7adef86cbf18125bdb23b2f30138e35db073`.
- Retained GPU source: SHA-256 `2b6d56d74187fd68cf18620dbc90fbcb3fc2702f75c03209c7f8b8612e640a29`.
- Retained UEFI: SHA-256 `038283aa0f0afcda6058e44b7331febd31cbc990bce0456c408bc9be17250ec1`.
- Retained Iris executable: SHA-256 `265ef87ece3b08ec36a620fcb099ad9968d52ccd7b2c7418e47d6b1980876971`. Only metadata/startup registration changed.
- Active WSL source: `/opt/a51-hakios/upstream-a51/hakios`; repair packet: `/opt/a51-hakios/build-repair/audio-iris-20261124`.
- Windows host packet: [audio-iris-20261124-v3](PUBLICATION.md).
- Installation: [device-flash-20261124T032057167732Z](PUBLICATION.md).

The `before/` directory snapshots working v2 inputs before mutation. `inputs.json`, `adaptation.json`, incremental patches, recipe, package manifest and QEMU/native records pin their corresponding source/build identities. These supersede only the supplemental v2 image; earlier storage candidates and phase evidence remain unchanged.

## Audio implementation and limits

Files: `devices/a51/drivers/audio/hakios.a51audio.c` and synchronized `xnu-src/xnu-8796.121.2/bsd/dev/hakios.a51audio.c` in the active WSL checkout.

The TAS2562 book register is accessed after selecting page zero. Clock ratio is 32fs for 16-bit stereo, rather than the previous mismatched 48fs value. Configuration transfers and amplifier power/clock-error readbacks must succeed before registering the audio sink. Hardware or amplifier setup failure leaves the sink unavailable with a diagnostic message.

UAIF2's divider is derived from retained PLL_AUD P/M/S/signed K and AUDIF divider values using the 26 MHz reference; it requires an enabled/stable PLL and an estimated 1.536 MHz bit clock within one percent. UAIF2 selects its internal parent. The driver requests ABOX SysMMU bypass at `0x14920000` and logs before/after CTRL values.

Only RDMA0 feeds SPUS OUT0 → SIFS1 → UAIF2. RDMA7 is stopped. `BUF_OFFSET` is the 4,096-byte DMA period and `STR_POINT` is physical start `0xE9400000`; the sink no longer overwrites period geometry with its producer cursor. It uses the documented STATUS consumer position, bounds available ring capacity and clears consumed samples on subsequent sink callbacks. Initial ring contents are silent; the continuous loud boot square wave was removed. Volume is half the 24-bit register maximum (`0x007fffff`), not a claimed unity value.

Speaker hardware clock, DMA, memory/cache and MMU assumptions still need live validation. Clearing occurs on callbacks, so prolonged idle after playback could repeat stale samples; interruption-based clearing and complete underrun recovery are not implemented. RDMA format was not programmed from a speculative cross-SoC bitfield. Wired headphones, microphone capture and route switching are unavailable in this driver. Old failed-image pstore showing I2C activity does not validate v3 output.

Read-only register references came from the preserved Samsung Android checkout `/opt/a51-everline/src`. Secondary LineageOS Exynos9820 references are pinned to `4bcfb0263b21b553760a3bdce542452db3184820`; these are cross-SoC source references, not A51 measurements. Reference URLs, hashes and fetch errors are retained in the work packet.

## Iris implementation and limits

The preserved Iris bundle is in md0 `/apps/Iris.app`, visible after root switch as `/private/preboot/apps/Iris.app`. Its staged and source plist now specify `CFBundleSupportedPlatforms = [iPhoneOS]` and `MinimumOSVersion = 16.5`.

`scripts/iris-register.c` supplies the static `/redwood/bin/iris-register` helper. It invokes the existing `uicache -p /private/preboot/apps/Iris.app` with twenty retries, three seconds apart, and records child exit status. It removes no app, app data or LaunchServices cache. Persistent diagnostics target `/private/var/mobile/Library/Logs/hakios-iris-registration.log`. A successful utility exit is not proof that SpringBoard displayed or launched the icon.

The packaged `userland/root/etc/rc.jobs` starts the helper in the background. `userland/rc.jobs.audio-iris` retains that safe selectable job recipe, and `userland/build.sh` compiles/copies the helper in future builds. Select `RC_JOBS=rc.jobs.audio-iris` for a full userland rebuild; the default job selection remains the upstream recipe. Working init, libraries and all other packaged startup jobs were preserved. The earlier destructive `rc.jobs.iris` is not selected.

## Verification, failures and rebuild

Eleven actual-source clock/ring cases and four Iris retry/failure cases passed native ASan/UBSan checks. LaunchServices and hardware are not emulated. Android v2 image header/ID, shim + UEFI + XNUP layout, entry hashes and the 61,865,984-byte boot partition fit were checked. Both APFS images passed fsck and matching tree readback: 505 md1 entries and 12 md0 entries. The rebuilt kernel/loader reached Darwin PID 1 / uid 0 in QEMU virt with a raw hello ramdisk and `a51audio=0`; this does not exercise final md0/md1 startup or A51 peripherals.

The first kernel wrapper invocation linked successfully but failed its stale v2 audio-source hash assertion. Updating the expected hash corrected the wrapper. The first helper compilation failed because libmini's main declaration requires the third `envp` argument; the corrected signature compiled. An unsigned free-space guard and volume comment were corrected before final tests/build/package. Existing XNU kext symbol-set checks reported exit 2 after the kernel linked; the retained build wrapper accepts the linked kernel, so this is a known build-check limitation. A secondary `abox_dma.c` URL returned HTTP 404; a later correct `abox_rdma.c` fetch succeeded. The first Windows export invocation used a project-relative path twice because `run.py` sets its child cwd to `hakios-a51`; `scripts/export-audio-iris.py` corrected it before export. Failed runs remain intact.

Historical commands, from the Windows workspace root:

```powershell
python hakios-a51/scripts/run.py --label audio-iris-native -- wsl -d A51-KernelBuilder -- python3 /mnt/c/Users/Ankit/Desktop/A51/hakios-a51/scripts/test-audio-iris.py
python hakios-a51/scripts/run.py --label audio-iris-kernel -- wsl -d A51-KernelBuilder -- python3 /mnt/c/Users/Ankit/Desktop/A51/hakios-a51/scripts/repair-audio-iris.py kernel
python hakios-a51/scripts/run.py --label audio-iris-userland -- wsl -d A51-KernelBuilder -- python3 /mnt/c/Users/Ankit/Desktop/A51/hakios-a51/scripts/repair-audio-iris.py userland
python hakios-a51/scripts/run.py --label audio-iris-loader -- wsl -d A51-KernelBuilder -- python3 /mnt/c/Users/Ankit/Desktop/A51/hakios-a51/scripts/repair-audio-iris.py loader
python hakios-a51/scripts/run.py --label audio-iris-package -- wsl -d A51-KernelBuilder -- python3 /mnt/c/Users/Ankit/Desktop/A51/hakios-a51/scripts/repair-audio-iris.py package
python hakios-a51/scripts/run.py --label audio-iris-qemu -- wsl -d A51-KernelBuilder -- python3 /mnt/c/Users/Ankit/Desktop/A51/hakios-a51/scripts/repair-audio-iris.py qemu
```

Do not rerun `prepare` over the existing work packet; it deliberately refuses an existing snapshot. For a fresh rebuild, restore or materialize pinned v2 inputs in an isolated checkout, choose a new packet and adjust the workspace-specific constants. Export refuses to replace an existing artifact. These scripts depend on retained licensed runtime/SDK, UEFI and prepared object inputs, not included in the public source repository.

## Installation and rollback

`scripts/flash-audio-iris.py` reuses the retained v2 procedure with only candidate name/hash/length and latest-receipt path changed. It validates serial/model/root/TWRP, boot alias/size, battery and recovery/DTBO pins; takes an independently hashed full boot backup; verifies both staged image and Android fallback; writes boot only and verifies the entire partition before reboot. The image replaces a prefix and preserves the original partition tail.

V3 full-partition readback: `654f17114d8009a49a7d050b08c1d9c8beae50e6dbd52d75c7bb02cbcfceec61`. The v2 full-partition backup is `boot-before.img` in the v3 installation packet, SHA-256 `7431a547bd7f7756a6ed86934ba474b491e11733de87e810a334581780c7f931`. V2 reached the home screen per user, with silent audio/missing Iris. The older v2 installation's `boot-before.img` is the failed striped image and must not be described as a working baseline.

Android fallback: `everline-ksu/artifacts/A51-PixelOS-Everline-KernelSU-Next-boot.img`, SHA-256 `eb30609a62999e3282ac81e0a5e56411ef12ec1a39c107171bf3e01209c7cb67`. Restoration requires the same verified connected recovery, exact boot target/size, pinned input and full readback before reboot. V3 needed no rollback. The installed build has no host ADB/SSH observation channel while iOS runs; absence of ADB cannot prove boot success or failure. Return to recovery for retained logs if needed.

The user explicitly authorized this supplemental flash; the original Phase 1 prohibition does not undo that authorization. No phase-completion gate changes follow from this installation.
