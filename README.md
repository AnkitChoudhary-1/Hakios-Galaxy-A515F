# HakiOS — Samsung Galaxy A51 SM-A515F

Experimental HakiOS/Darwin port and Iris app source for Samsung Galaxy A51 (Exynos 9611). This repository contains the current platform source snapshot, authored research/build tools, earlier port adaptations and comprehensive implementation documentation.

On 24 November 2026, the user reported that the installed full-quality v2 image reached the iOS home screen, with silent audio and no Iris icon. V3 adds targeted audio clock/amplifier/DMA changes and nondestructive Iris registration. V3 was built, checked and flashed from TWRP with full boot-partition readback; its home-screen, speaker and Iris acceptance is pending. These observations do not establish GPU acceleration or working Apple services. Phase 4's physical gate remains unpassed.

Read [current status](docs/PUBLIC-STATUS.md), [build instructions](docs/PUBLIC-BUILD.md), [publication scope](docs/PUBLICATION.md) and the [audio/Iris repair record](docs/AUDIO-IRIS-REPAIR-20261124.md). The historical [implementation log](docs/IMPLEMENTATION-LOG.md) retains failed attempts, evidence limits and rollback instructions.

- `platform/`: current common HakiOS source, build recipes and A51 drivers.
- `apps/Iris/`: Objective-C/UIKit source, metadata, build script and web simulator.
- `scripts/`, `prototype/`, `diagnostics/`, `drivers/`, `userland/`: authored host tools and earlier research/platform code.
- `patches/current-xnu.patch`: cumulative current native changes against pinned Apple XNU.
- `port/`, older `patches/`: preserved earlier experimental port snapshots.
- `manifests/current-sources.json`: exact upstream/dependency commits and changed-file identities.
- `validation/audio-iris-v3/`: selected host build/native/QEMU receipts with their limits.

No installable image, proprietary runtime/SDK, vendor firmware, phone backup or personal raw device logs are distributed here. Local paths in historical scripts must be configured before use. This source snapshot requires separately supplied dependencies and licensed runtime inputs to reproduce the phone package.

Upstream source and individual files retain their licenses and attribution; see `LICENSE`, `LICENSE.APSL`, `LICENSES/` and `THIRD_PARTY_LICENSES.md`.
