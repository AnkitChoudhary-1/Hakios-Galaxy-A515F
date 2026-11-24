# A51 GPU/audio build repair — 24 November 2026

Selected output: [A51-HakiOS-full-quality-gpu-audio-fixed-v2-boot.img](PUBLICATION.md), **29,700,096 bytes**, SHA-256 `9f7fd881143c1ba81a28359ead8000b0d9a953690e67ebac3e0a603dd806ec30`. Its [manifest](PUBLICATION.md) and [checksum](PUBLICATION.md) accompany it. Host packaging checks and execution of the same rebuilt kernel/UEFI loader in QEMU passed. This image has **not been flashed or booted on the phone**; home-screen behavior, GPU execution and audible audio remain unverified.

The user identified the previous working image by a name resembling “full-quality.” That original image was not located. This repair reconstructs the retained full-quality boot recipe and preserves the latest files; it does not claim byte identity with the earlier image. Phase statuses and device acceptance gates are unchanged.

## Diagnosis

The retained failed device log is [console-ramoops-0](PUBLICATION.md). This repair session read device logs but performed no phone write, staging, reboot, flashing, repartitioning or recovery/DTBO change. Source assessments alone do not establish hardware behavior.

1. **GPU allocation:** successful Mali reset/core startup is followed by `a51gpu: the memory ... is not in one piece` and `no memory for the tables or the job: stopping`. Ordinary `kmem_alloc()` does not guarantee physical contiguity for GPU page tables/job buffers.
2. **Missing md1:** the failed assembly-loader blob includes the original valid 4 MiB `flashboot.apfs`, including executable `/sbin/launchd` (stage0), but omits the latest `root.apfs`. `userland/src/stage0.c` mounts **md1** and executes `/redwood/sbin/init`; absence of that disk causes startup to halt. An early missing-startup-program inference was incorrect and was corrected after filesystem inspection. [diagnosis.json](PUBLICATION.md) records exact equality of the flashboot range `[0x3870:0x403870]` and absence of latest root bytes.
3. **Stale UFS pointer:** the raw loader copied `ufs_shared_pa=0xa1553000`; XNU read magic `ffffffffffffffff`. The restored UEFI route retains the firmware's live shared page and supplies its address dynamically.
4. **Stripes:** `prototype/xnu-loader/a51_loader.S` intentionally paints loader milestones. The stripes alone do not establish physical GPU damage or successful accelerated rendering.
5. **Audio:** DMA/amp diagnostics already appear in the failed log. They demonstrate code execution, not audible playback. The latest source was preserved and explicitly recompiled.

## Implementation and preserved inputs

Linux checkout: `/opt/a51-hakios/upstream-a51/hakios`, WSL distribution `A51-KernelBuilder`. Isolated outputs: `/opt/a51-hakios/build-repair/gpu-audio-20261124`. Existing Android projects, backups, failed images and tuning modules were preserved.

| Component | Change/status |
|---|---|
| `devices/a51/drivers/gpu/hakios.a51gpu.c` | Use `kmem_alloc_contig(..., PAGE_MASK, 0, 0, ...)`; retain physical-contiguity guard, free failed allocation and clear `*phys`. |
| XNU `bsd/dev/hakios.a51gpu.c` | Synchronize repaired source and compile fresh object. Existing ACPM/clock/thermal edits remain. |
| Audio and XNU copy | Preserve latest GPIO drive strength, clocks/gates, DMA priming before transmitter, FIFO settings and TAS format/diagnostics. Force fresh object without changing source bytes. |
| Kernel/loader | Fresh kernel and `xnuloader/loader.efi`; existing firmware unchanged. |
| Boot package | BootShim + UEFI firmware + XNUP; `resident=flashboot.apfs` is md0, `ramdisk=root.apfs` is md1. Retain separate Android ramdisk/DTB. |
| Root APFS | Latest bytes unchanged; independent checks agree on 504 entries. |
| Boot APFS | All 12 entries, including stage0 and Iris, match original files/modes/owners. Regenerated metadata differs. |
| Command line | Retain prior tuning and `a51gpu=8 a51audio=4`, omit stale shared pointer, generate epoch. Exact arguments: [recipe.json](PUBLICATION.md). |

Prior CPU/GPU/memory clock requests, `ufs_write=1`, `var_store=1`, `fbscale=2` and `fb_ca_hz=120` were retained, not newly validated. Conservative command-line budget: 601/607 bytes. The panel target remains 60 Hz; `fb_ca_hz=120` does not prove 120 Hz output. This package is separate from the Phase 4 read-only storage candidate and does not change its contract/gate.

| File | SHA-256 |
|---|---|
| Repaired GPU source | `2b6d56d74187fd68cf18620dbc90fbcb3fc2702f75c03209c7f8b8612e640a29` |
| Included audio source, unchanged | `bab89d13130474c6d8155a33aefdf772969920e50976d383fed7ec172dd48e4f` |
| Rebuilt kernel, 15,090,648 bytes | `58ba933c022831b1fdf77fc4b7544161911f27899afcd6b8251f5bb635922860` |
| Rebuilt loader, 72,704 bytes | `3d5c32f4278ef190c18e089af8d12fa065091d1c07277e6748b73686fd9ec45a` |
| Retained firmware, 2,097,152 bytes | `038283aa0f0afcda6058e44b7331febd31cbc990bce0456c408bc9be17250ec1` |
| Latest root APFS | `5f3f9963ece021dc1d02b15cf3f37f36592d47ce1ebb0146acc3b4e03dd9b834` |
| Regenerated boot APFS | `8febc9201a14d3226a81b9d9effd13026350b737c6d958aae1e6449e388687e9` |

The [final packet](PUBLICATION.md) retains before/after sources, input hashes, root/device/XNU/Mu-Silicium Git HEADs and existing dirty binary patches, [GPU adaptation](PUBLICATION.md), [included audio diff against older restored source](PUBLICATION.md), recipes and original build/test logs. Existing dirty work was preserved; no reset or upstream commit occurred. The supplemental GPU edit is retained as a patch. Audited dependencies were reused; no new dependency download occurred.

## Verification and limits

- **Build:** both drivers freshly compiled and kernel linked. GPU object imports `_kmem_alloc_contig_guard` and `_kmem_free_guard`. Existing build judge permits only its known symbolset/`check_all_exports` failures; this is not a warning-free upstream build claim.
- **Allocator:** the actual extracted helper passed four ASan/UBSan modeled cases: contiguous 16 KiB, rounded small allocation, allocation failure and fragmented mapping cleanup. [Result](PUBLICATION.md). No Mali MMIO was tested.
- **QEMU:** [result](PUBLICATION.md) and [serial](PUBLICATION.md) show `Hello from user space on Darwin!`, process 1 and uid 0 with exact final kernel/loader. Fresh hello remained alive until the intentional 35-second timeout, exit 124. Raw hello ramdisk, `a51audio=0 cpus=1 hello_wait=120`: this does not execute final md0/md1 stage0 startup or A51 peripherals.
- **Filesystems:** independent `apfsck` and kernel APFS reader passed; original flashboot contents, including Iris executable and Info.plist, match the rebuilt tree.
- **Samsung image:** Android header v2, 2048-byte pages, independently verified SHA1 image ID, exact section/XNUP equality, command-line/firmware reservation bounds, fit within 61,865,984-byte boot partition.
- **Export:** Windows image matches WSL manifest; failed-image/raw-loader and Android rollback pins unchanged. [Final documentation/export verification](PUBLICATION.md) checks retained inputs, source/output hashes, documentation links and unchanged historical phase state.

This is host build/package readiness and generic kernel/loader execution. Phone boot, home-screen completion, GPU acceleration, audible playback, persistence and recovery for the new image remain unknown. Apple services/Safari support is not established. No physical phase gate changed.

## Commands and reproducibility

Run from `C:\Users\Ankit\Desktop\A51`. `scripts/run.py` retains exact arguments, timestamps, full output and status. Historical actions:

```powershell
python hakios-a51\scripts\run.py --label gpu-audio-repair-prepare -- wsl -d A51-KernelBuilder -- python3 /mnt/c/Users/Ankit/Desktop/A51/hakios-a51/scripts/repair-gpu-audio-build.py prepare
python hakios-a51\scripts\run.py --label gpu-audio-repaired-kernel-fresh-drivers -- wsl -d A51-KernelBuilder -- python3 /mnt/c/Users/Ankit/Desktop/A51/hakios-a51/scripts/repair-gpu-audio-build.py kernel
python hakios-a51\scripts\run.py --label gpu-audio-resident-uefi-loader -- wsl -d A51-KernelBuilder -- python3 /mnt/c/Users/Ankit/Desktop/A51/hakios-a51/scripts/repair-gpu-audio-build.py loader
python hakios-a51\scripts\run.py --label gpu-contiguous-allocator-regression -- wsl -d A51-KernelBuilder -- python3 /mnt/c/Users/Ankit/Desktop/A51/hakios-a51/scripts/repair-gpu-audio-build.py test
python hakios-a51\scripts\run.py --label gpu-audio-repaired-kernel-qemu-fresh-hello -- wsl -d A51-KernelBuilder -- python3 /mnt/c/Users/Ankit/Desktop/A51/hakios-a51/scripts/repair-gpu-audio-build.py qemu
python hakios-a51\scripts\run.py --label gpu-audio-full-quality-preserve-app-package -- wsl -d A51-KernelBuilder -- python3 /mnt/c/Users/Ankit/Desktop/A51/hakios-a51/scripts/repair-gpu-audio-build.py package
python hakios-a51\scripts\run.py --label gpu-audio-final-image-export -- python scripts/export-gpu-audio-repair.py
```

These are **not idempotent**. Preparation refuses an existing work directory and requires original allocation code; packaging refuses an existing `flashboot-full-quality` directory; export refuses existing packet/image names. Preserve those guards and retained packets. For another repair, copy/adapt scripts with new work/image/evidence names, pin current inputs and adapt the preparation diff to those exact bytes. To replay the original repair, use an isolated checkout, retained repository HEADs/pre-existing patches, two GPU before snapshots and `gpu-contiguous.patch`; preserve audio/app pins and synchronize sources. Record adaptations before building. Kernel timestamps and command-line epoch mean rebuild hashes can differ. The selected retained artifact is the exact pinned output of this repair.

## Failed attempts and selected final run

| Wrapper run | Outcome/correction |
|---|---|
| `20261124T023425488316Z-gpu-audio-repaired-kernel` | Linked, then rejected stale audio object. Next run synchronized/touched and freshly compiled both drivers, preserving audio bytes. |
| `20261124T023805627686Z-gpu-audio-repaired-kernel-qemu` | Old hello reached PID1 then deliberately exited/panicked. Fresh source rebuild passed bounded execution. |
| `20261124T023558298206Z-gpu-audio-full-quality-package`, `20261124T023943964864Z-gpu-audio-fixed-image-export` | Minimal package restored loader/disks but omitted Iris. Superseded by v2. |
| `20261124T024131524351Z-gpu-audio-full-quality-preserve-app-package`, `20261124T024201239807Z-gpu-audio-final-image-export` | Final v2 preserved all 12 original entries; packaging/export passed. |

Superseded `artifacts/A51-HakiOS-full-quality-gpu-audio-fixed-boot.img` remains at SHA-256 `bbac344415456754166cf21a14cf149f0ad4ac6969524b7bb71d7598409f06a8` with separate `gpu-audio-20261124-fixed` packet. Select **v2**. Successful kernel/loader/allocator/QEMU runs: `20261124T023511591809Z-gpu-audio-repaired-kernel-fresh-drivers`, `20261124T023545196071Z-gpu-audio-resident-uefi-loader`, `20261124T023748735422Z-gpu-contiguous-allocator-regression`, `20261124T023848536023Z-gpu-audio-repaired-kernel-qemu-fresh-hello`. All original wrapper metadata/output is retained in `runs/`.

## Rollback and handoff

Compare current after hashes before restoring GPU before snapshots at both paths. Preserve user audio and other dirty work. Old kernel/loader/build-resource snapshots are in the packet; use isolated rebuild outputs to avoid mixed objects. Documentation/state before copies are under `evidence/build-repair/20261124T022342Z/before/workspace`; restore only after checking later edits. Retain append-only implementation entries, failed/final images, patches and command logs.

No device rollback was needed because this repair made no device mutation. Preserved Android rollback: `../everline-ksu/artifacts/A51-PixelOS-Everline-KernelSU-Next-boot.img`, SHA-256 `eb30609a62999e3282ac81e0a5e56411ef12ec1a39c107171bf3e01209c7cb67`. Original failed image/raw loader remain at `d061a034c7e683a486b8fb6e5997d35e628f0237ccea58bc99da0ed990f4673b` and `b96009c9dd7180292fff543a309a38be6a2a0c60c8264bae6c3ee7ebf7ae9f40`.

The request authorized repair/build work, not a phone installation. The prior storage-cycle authorization remains consumed. Any later physical trial needs a concrete device/logging/rollback plan and explicit authorization. Do not run old storage trials as part of this repair. Require attributable new boot logs and physical display/audio observations before changing hardware claims or gates.


## Subsequent authorized installation — 24 November 2026

The user explicitly authorized installation from connected TWRP. Repaired full-quality v2 was written to boot and independently verified by full-partition SHA-256 before reboot. The user reports “booting in ios.” This is boot progress, not home-screen/GPU/audio acceptance. Recovery/DTBO remain unchanged; the old boot partition is backed up. Bounded ADB observation: no_adb_boot_confirmation. Phase gates are unchanged. Evidence: [installation receipt](PUBLICATION.md).

The earlier no-device-write statements describe the completed host repair, before the new flash request. The installed image remains the same pinned v2 artifact. The full-partition hash is `7431a547bd7f7756a6ed86934ba474b491e11733de87e810a334581780c7f931`: image bytes followed by the preserved original partition tail. A backup of the former 61,865,984-byte boot partition is retained as `boot-before.img` in the installation packet. The pinned Android rollback was staged and verified before writing; rollback was not needed. One candidate write and one reboot completed. Both temporary staged images were removed before reboot. No recovery/DTBO, repartitioning, module or security change occurred.

The initial install run failed its backup-length check before staging or a partition write: exec-out quoting produced a shell error. Binary `exec-out cat /dev/block/sda12` corrected the capture. The failed packet and run are preserved. The installation script records exact arguments, raw outputs, remote exit frames and durable write/reboot intent. On partial/failed write or readback it restores the preverified Android rollback and verifies it while retaining recovery.

Commands: `python scripts/run.py --label gpu-audio-v2-authorized-twrp-install-binary-backup -- python scripts/flash-gpu-audio-repair.py install`, then `observe --seconds 60` through the wrapper. These are historical installation commands, not an instruction for another device cycle.
