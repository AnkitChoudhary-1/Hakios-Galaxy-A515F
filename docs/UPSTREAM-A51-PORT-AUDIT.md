# Upstream Galaxy A51 port audit

Completed 19 November 2026, Asia/Calcutta. This is a supplemental, host-only Phase 1 audit of the active upstream checkout at `/opt/a51-hakios/upstream-a51/hakios` in the `A51-KernelBuilder` WSL distribution. It does not replace the original [Phase 1 acceptance report](PHASE-1-RESULTS.md), change any phase gate, or establish execution on the Galaxy A51.

## Selected evidence

- Audit packet: [`evidence/phase-1/upstream-a51-port/20261119T112540897049Z`](PUBLICATION.md)
- Result: [`result.json`](PUBLICATION.md), 1,525 bytes, SHA-256 `c334883dd2cc9b2dc733c825daa00f68f2a70f8d7cb4832ecad42690124172a1`
- Ledger: [`manifest.json`](PUBLICATION.md), 20,570 bytes, SHA-256 `e10e6e429657be04479cc6380c46e650ea2b420f2ae45e95f2a44e2c68440bf2`; it pins 95 other packet files by path, size and SHA-256.
- Syntax run: `runs/20261119T112522350706Z-upstream-a51-port-audit-syntax`
- Capture run: `runs/20261119T112541210265Z-upstream-a51-port-host-audit`
- Independent replay: `runs/20261119T112631731926Z-upstream-a51-port-audit-verification`

The capture reports `passed=true`, `issues=[]`, `device_operations=false`, `phone_queries=false`, `phone_writes=false`, `phone_reboots=false`, `flashing=false` and `ipsw_downloaded=false`. The replay compared the packet ledger with the live checkout, artifacts, configuration, toolchain, SDK, retained runs and claim source and also exited 0.

## Verified host facts

| Area | Verified result |
|---|---|
| Repository inventory | 65 Git worktrees were enumerated. Every configured commit and clean/overlay expectation matched. The only dirty trees are the three expected generated overlays: `Mu-Silicium`, `Mu-Silicium/Mu_Basecore` and `xnu-src/xnu-8796.121.2`. Binary patches and working-tree inventories for those overlays are retained in the packet. |
| Main source pins | HakiOS `14b7cdbe502f9ca5e1481cf1e6c7890fe8d3343a`; A51 device source `0773636aea5de1c246e2cb3a72b2cb824c5b7316`; HakiOS UEFI source `26fe9a2844e0c2c852dca79cb173091744ba8aae`; generated Mu-Silicium `e51cd877e31c8fbb322032dc4cb6715e83d25ad3`; Mu Basecore `cfb93724a06ff86ff5ba971413368a7809ee42a5`; generated XNU overlay `c54f35ca767986246321eb901baf8f5ff7923f6a`. |
| Kernel artifact | `hakios-kernel`, 15,048,864 bytes, SHA-256 `38ea0ee0c6bf38bbc0c3a5ac2f60b28dd2bdbf1a058a3130a2bdd79750093f33`. Its parser identifies a 64-bit ARM64 Mach-O executable with 25 load commands, consistent command bounds and valid segment file ranges. |
| UEFI artifact | `Mu-Silicium/Build/a51Pkg/RELEASE_CLANGPDB/FV/SILICIUM_UEFI.fd`, 2,097,152 bytes, SHA-256 `038283aa0f0afcda6058e44b7331febd31cbc990bce0456c408bc9be17250ec1`. One firmware volume was found with a valid header checksum, block map and file range. |
| Kernel configuration | `.config` SHA-256 `72b228f50e0c78e6a19bc42932d057901a2d4e92792fb7649a8df490ad61f30d`; 384 symbols parsed. Selected enabled symbols include `CONFIG_HAKIOS_A51GPU`, `CONFIG_HAKIOS_A51INPUT`, `CONFIG_HAKIOS_A51WIFI`, `CONFIG_HAKIOS_UFS` and `CONFIG_HAKIOS_WIFI_STATION`. Configuration is build intent, not hardware acceptance evidence. |
| Toolchain and packages | All 15 required version commands exited 0, and all 17 audited Debian packages were installed. Executable identities, command output, virtual-environment packages and package versions are retained in `toolchain.json`. |
| iPhoneOS 16.5 SDK | Repository commit `0222fd5413cf4b9af096f37b4621afa2688572f7`, clean worktree; 8,795 files and 210,522,742 bytes with tree digest `94e4bca9629203156f99d7be9572e66dc304b930ed76ae6e06879adf9669e38d`. This is an SDK input, not an iOS installation image. |
| NASM adaptation | Installed and retained `extdep_state.yaml` copies both match SHA-256 `e191bc0a4c46e0317f42fd9080021b885617a69dc854f1955388defcee71b587`; NASM and NDISASM resolve to `/usr/bin/nasm` and `/usr/bin/ndisasm`. |
| Retained build provenance | Six prior runs are copied and pinned: UEFI clean-integrity, overlay application, NASM adaptation, UEFI build, XNU build and repository-status audit. |

## Upstream claims and evidence boundary

The packet preserves the exact upstream `devices/a51/PORTING.md` bytes and 136 keyword-matched excerpts. Those excerpts include upstream assertions of an iOS 16.5 home screen on an A51, later touch/button operation, Mali/Panfrost OpenGL ES acceleration and Wi-Fi connectivity. They are deliberately classified as `upstream_assertions_not_local_hardware_validation`.

This audit did not reproduce any of those device results. It did not boot the kernel or UEFI on the phone, acquire or assemble a Darwin root filesystem, download an IPSW, test display or input, join Wi-Fi, run a GPU workload, or verify Metal. The captured source itself distinguishes its Mali/OpenGL path from Apple Metal in at least one section. Source text, enabled configuration symbols and successful host builds are not substitutes for original local device logs and acceptance checks.

The audit therefore supports only this conclusion: the selected upstream A51 checkout and its retained host build products are internally pinned and reproducible enough for further review. It does not prove that stock iOS 16.5 can be downloaded and booted directly, that the current artifacts are safe to install, or that the upstream feature claims hold on this device.

## Audit implementation

- `scripts/audit-upstream-a51-port.py`: 41,428 bytes, SHA-256 `f0e3b7fbaee3a0c614deff1890926f1a939302977da619ba8855d6c30a982163`. It creates a new packet only under `evidence/phase-1/upstream-a51-port/`, preserves partial failed packets, redacts URL credentials, records working-tree patches and inventories, parses the Mach-O and UEFI structures, and captures toolchain, SDK, run and claim provenance.
- `scripts/verify-upstream-a51-port.py`: 8,430 bytes, SHA-256 `f15f6dccd2a07a3069961ce6f3873b6ca8de6cddbde2776663767317e736e99a`. It rejects packets outside the selected evidence root, verifies the manifest has no missing or unlisted files, and recomputes the live host inputs without contacting the phone.

Both scripts must be run through `scripts/run.py`. To create a fresh packet, choose a new UTC directory name; the capture script refuses to overwrite an existing packet.

```powershell
python .\scripts\run.py --label upstream-a51-port-host-audit -- wsl.exe -d A51-KernelBuilder -- python3 /mnt/c/Users/Ankit/Desktop/A51/hakios-a51/scripts/audit-upstream-a51-port.py --checkout /opt/a51-hakios/upstream-a51/hakios --output evidence/phase-1/upstream-a51-port/<new-UTC-stamp>

python .\scripts\run.py --label upstream-a51-port-audit-verification -- wsl.exe -d A51-KernelBuilder -- python3 /mnt/c/Users/Ankit/Desktop/A51/hakios-a51/scripts/verify-upstream-a51-port.py --packet evidence/phase-1/upstream-a51-port/<new-UTC-stamp> --checkout /opt/a51-hakios/upstream-a51/hakios
```

## Limitations, failure handling and rollback

A passing replay is intentionally sensitive to later repository, artifact, configuration, toolchain, package or SDK drift. Such drift requires a new packet; do not rewrite the selected one. Preserve every failed or partial packet because it records the state that caused the failure.

Rollback is documentation-only: remove the supplemental selection from `docs/STATE.md`, `docs/INDEX.md` and `state.json` after checking for later edits, but retain this append-only implementation-log entry, the packet and all run logs. Removing the two audit scripts is sufficient to undo their implementation. No phone, partition, Android, recovery/DTBO, upstream checkout or WSL build rollback is required because the audit performed reads only.
