# HakiOS for Galaxy A51 (SM-A515F)

## Current installation — 25 November 2026

R1 was flashed on 25 November 2026 from TWRP with full boot backup and matching full-partition readback. The user explicitly requested proceeding at 1% battery; USB charging was checked before staging and before writing. Recovery/DTBO remained unchanged. Physical boot completion, accurate touch, speaker playback, Iris icon/launch and diagnostic persistence await confirmation. Phase gates remain unchanged. Earlier checkpoints below retain their historical scope.

Experimental A51 HakiOS source, Iris app source, build tools and documentation. The latest r1 candidate corrects touch coordinate mapping, checks speaker clock/amplifier setup, and restores full userland/Iris startup with diagnostics.

Host builds, native checks, image/APFS verification and minimal Darwin QEMU boot pass. The latest installed build is user-reported to have inaccurate touch and silent audio. The new candidate awaits TWRP installation and physical testing; audible speaker output and Iris launch are unverified.

Start with [current status](docs/PUBLIC-STATUS.md), [build scope](docs/PUBLIC-BUILD.md), [r1 repair record](docs/TOUCH-AUDIO-REPAIR-20261124.md) and [publication scope](docs/PUBLICATION.md). Exact source/dependency identities are in manifests/current-sources.json; PUBLICATION-MANIFEST.json pins exported files. The cumulative XNU patch must be applied to its pristine pinned baseline. Earlier repairs/experiments and phase records are preserved with their original scope.

This source export requires separately supplied SDK/runtime/firmware inputs to build a phone image. Generated images, vendor firmware, private logs and device backups remain local. Physical peripheral acceptance and Phase4 remain incomplete.
