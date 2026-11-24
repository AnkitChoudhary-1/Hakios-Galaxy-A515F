# Current observed status — 24 November 2026

Implemented: v2 contiguous GPU allocation and full boot packaging; v3 TAS2562 book/clock-ratio checks, retained-clock divider calculation, DMA geometry/bounds and sink failure gating; Iris bundle metadata and bounded boot registration. Current sources are in `platform/` and `apps/Iris/`.

Host verified for v3: eleven actual-source audio cases and four Iris retry/failure cases under ASan/UBSan; kernel/helper/loader linking; Android v2 image header/layout/entry pins; both APFS disks with 505 md1 and 12 md0 matching entries; QEMU virt Darwin PID1/uid0 using the same kernel and loader, raw hello ramdisk and audio disabled. The existing XNU kext symbol-set check exit2 after linking remains a build-check limitation.

Device observed: user reported v2 iOS home screen, silent audio, missing Iris and no SSH app. V3 was written from user-authorized TWRP to boot with backup, verified full-partition readback and reboot; recovery/DTBO hashes were unchanged. No ADB connection appeared during the bounded post-reboot observation. V3 home-screen completion, audible speaker media and Iris icon/launch are pending; ADB absence proves neither success nor failure.

Unavailable or unknown: wired headphones, microphone capture and route switching in this speaker driver; complete idle/underrun ring handling; verified GPU acceleration/Metal, Safari and Apple services; live v3 clock/DMA/MMU/cache behavior. Compilation and source audits are not hardware validation.

Phases 1–3 retain their previously selected gates. Phase 4 is in progress and its physical peripheral gate is unpassed. The failed storage experiment and independently verified Android restoration remain historical evidence; this supplemental repair does not clear storage/recovery-export blockers.
