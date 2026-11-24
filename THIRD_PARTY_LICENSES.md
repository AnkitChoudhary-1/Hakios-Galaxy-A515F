# Licensing and attribution

Existing per-file notices take precedence over the default MIT license for original A51 tools and documentation. Do not remove attribution or apply the default MIT license to XNU/Android-derived code.

| Component included here | Origin | Applicable terms |
| --- | --- | --- |
| Host scripts, documentation and original standalone prototypes | A51 HakiOS contributors | MIT, except any retained third-party notices |
| Common HakiOS snippets/modified hello and integration code | `oosexgang/hakios-xnu-kernel` at `63fc2b4633bac3af8e57dadab9f5a8d4cb940438` | Retain MIT notices where applicable; upstream MIT text in `LICENSES/HakiOS-MIT.txt` |
| XNU-derived modifications in `patches/phase*-xnu.patch` | Apple XNU `xnu-8796.121.2` plus the pinned HakiOS overlays | APSL 2.0 (`LICENSE.APSL`), with existing per-file notices retained |
| Original integration/core files explicitly marked MIT | A51/HakiOS contributors | Their MIT notices; inclusion in an XNU build does not remove them |
| Android diagnostic modules in `diagnostics/` and Linux-derived adaptations | Linux/Android kernel interfaces and A51 contributors | Declared GPL and applicable file notices; GPL 2.0 text in `LICENSES/GPL-2.0.txt` |

The cumulative XNU patches compare an A51 port to the already generated common HakiOS XNU baseline. They distribute source modifications rather than SDK/firmware headers. They are not complete copies of the upstream kernel or its third-party libraries.

Build-time inputs are referenced by their URLs/commits/hashes in `manifests/source-lock.json` and `manifests/dependencies.json`. XNU/HFS and Apple open-source support projects, cctools, SDK headers, QEMU and host compilers have their own terms. Their source archives, binaries and SDK contents are not redistributed here.

Apple's full iOS runtime, framework caches, SpringBoard/Safari, vendor firmware, UEFI vendor blobs and phone backups are excluded. An input appearing in the source/dependency audit does not assert permission to redistribute it. See the retained common project's `THIRD_PARTY_LICENSES.md` when building its other components; their inclusion is outside this A51 source export.

Current `platform/` derives from speedyg2200/hakios-xnu-kernel at the commit pinned in manifests/current-sources.json. `patches/current-xnu.patch` uses pristine Apple XNU at its pinned commit, rather than the earlier prepared phase baseline. `port/current-uefi/` contains Project Silicium/Microsoft Mu/EDK II source overlays; preserve BSD-2-Clause-Patent and all embedded file notices, with upstream license texts alongside the overlays. Refer to their pinned upstream source for excluded resources and dependency terms.
