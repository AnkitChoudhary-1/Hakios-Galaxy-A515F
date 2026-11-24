#!/usr/bin/env python3
"""Record r1 host repair evidence while preserving every phase gate."""
import json
from pathlib import Path

P = Path(__file__).resolve().parents[1]
E = P / 'evidence/build-repair/touch-audio-20261124-r1'


def main():
    manifest = json.loads((E / 'manifest.json').read_text())
    assert manifest['host_package_verified']
    export = json.loads((E / 'export.json').read_text())
    assert export['image'] == manifest['image']
    qemu = sorted(E.glob('qemu-*/result.json'))[-1]
    assert json.loads(qemu.read_text())['passed']
    state_path = P / 'state.json'
    state = json.loads(state_path.read_text())
    gates = {k: v for k, v in state.items() if 'phase' in k}
    state['touch_audio_repair_20261124_r1'] = {
        'status': 'host_verified_candidate_not_installed',
        'guide': 'docs/TOUCH-AUDIO-REPAIR-20261124.md',
        'packet': E.relative_to(P).as_posix(),
        'artifact': 'artifacts/A51-HakiOS-full-quality-touch-audio-r1-boot.img',
        'image': manifest['image'], 'audio': manifest['audio'], 'touch': manifest['touch'],
        'gpu': manifest['gpu'], 'host_package_verified': True, 'generic_qemu_verified': True,
        'user_report': 'Latest build: audio silent and taps land in the wrong place; Iris observation unanswered',
        'reported_installed_image_pin': None,
        'source_before_audio_sha256': 'ad5665883eba58b87c5cb99e2adacee3073aaac7fe71b95d91464b926b3b090d',
        'touch_coordinates_checked': 4096, 'clock_patterns_checked': 64,
        'audio_native_cases': 11, 'iris_native_cases': 4,
        'iris_helper_reused_from_verified_v3_image': True,
        'phone_writes_this_repair': False, 'device_boot_verified': False,
        'touch_accuracy_verified': False, 'audible_audio_verified': False,
        'iris_icon_verified': False, 'iris_launch_verified': False,
        'diagnostics_persistence_verified': False, 'phase_gates_changed': False,
        'qemu_scope': 'same kernel/loader, virt/raw PID1 hello, a51audio=0',
        'blocker': 'ADB sees no device; reconnect SM-A515F in TWRP for authorized checked installation'}
    state['active_task'] = 'Touch/audio r1 host repair verified; authorized TWRP installation and hardware acceptance pending; source publication refresh in progress'
    state['next_action'] = 'Reconnect in TWRP, capture current image/logs, back up full boot, flash checked r1; verify accurate touch, audible speaker media and Iris icon/launch; publish refreshed source'
    assert gates == {k: v for k, v in state.items() if 'phase' in k}
    state_path.write_text(json.dumps(state, indent=2) + '\n')
    guide = '''# Touch and speaker repair r1 — 24 November 2026

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
'''
    (P / 'docs/TOUCH-AUDIO-REPAIR-20261124.md').write_text(guide, encoding='utf-8')
    note = ('## Latest touch/audio r1 host candidate — 24 November 2026\n\n'
        'Latest user report: silent speaker and taps landing in the wrong place. '
        'The new r1 candidate corrects DT-based coordinate scaling, checked audio clocks/amp setup '
        'and restores full userland/Iris registration plus diagnostics. Fresh build, native/APFS/package '
        'and minimal QEMU checks passed. It is not installed yet: ADB sees no device. '
        'Physical touch/audio/Iris and diagnostic persistence remain unverified; phase gates unchanged. '
        'Read [r1 repair guide](TOUCH-AUDIO-REPAIR-20261124.md). '
        'Dated checkpoints below retain their historical scope.\n\n')
    for name in ['docs/STATE.md', 'docs/INDEX.md']:
        path = P / name
        old = path.read_text(encoding='utf-8')
        first, rest = old.split('\n', 1)
        path.write_text(first + '\n\n' + note + rest.lstrip('\n'), encoding='utf-8')
    with (P / 'docs/IMPLEMENTATION-LOG.md').open('a', encoding='utf-8') as out:
        out.write('\n\n## REPAIR-005 — Touch/audio r1 source and host implementation (2026-11-24)\n\n'
            + guide.split('## Changes and source basis\n\n')[1])
    print(json.dumps(state['touch_audio_repair_20261124_r1'], indent=2))


if __name__ == '__main__':
    main()
