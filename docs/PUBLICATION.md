# Publication scope and provenance

The user explicitly requested publishing all HakiOS project code to `AnkitChoudhary-1/Hakios-Galaxy-A515F`. A new empty clone was prepared for this destination. The earlier `hakios-SM-A515F` publication checkout, its remote/history and the active build trees remain preserved.

Included: current common/device HakiOS source/build tools, all authored project source families, Iris native source and web simulator, cumulative native XNU adaptations, earlier port patches, comprehensive Markdown documentation, source/dependency manifests, license/attribution texts and selected source-bound v3 host/native/QEMU receipts.

Excluded: compiled executables/images/APFS archives, private raw evidence and run trees, full device inventory/log dumps, personal serials/MAC addresses, phone/partition backups, vendor firmware, Apple runtime/SDK files, full separately downloaded upstream dependency checkouts and unrelated Android kernel projects. Dependencies are represented by pinned revisions/provenance, with local adaptations exported as source/patches. The public repository is a source snapshot, not an installable runtime bundle.

`PUBLICATION-MANIFEST.json` records exported hashes, original source hashes, transformations, executable modes, selected binary exclusions and scan results. Source snapshots sanitize personal device identifiers and repair links into absent local evidence to this scope document. Original local evidence hashes remain authoritative; sanitized publication content is a separate artifact.

Historical documentation and upstream README/bring-up claims may describe old scopes or unvalidated assertions. [PUBLIC-STATUS.md](PUBLIC-STATUS.md) states the current distinction between implementation, host checks, user reports and unknown hardware behavior. The user-reported v2 home screen is not independent telemetry or proof of GPU acceleration; the v3 flash receipt is not audible playback or Iris launch acceptance.

GitHub connector metadata verified the destination and access. Native Git is used for the bulk source commit/push because the connector exposes individual object/file operations rather than a bulk checkout upload. The push is the user-requested publication; it does not open an upstream PR or change firmware.

The final scope check additionally exports locally changed/new Mu-Silicium, A51 board and Mu_Basecore source as `port/current-uefi/` overlays, with nested submodule pins and original/exported hashes. Binary logo/DTB changes are excluded. XNU patch applicability and resulting hashes were independently checked on isolated pristine source.


Source was published to the requested repository on main at initial commit `24c2b1b5e1b6d6bea0144fd5380f3b8ffe6053c2`, independently verified against remote main. A subsequent documentation commit records this receipt; it does not change the v3 image or any hardware acceptance gate. Speaker audio and Iris acceptance remain pending.
