#!/usr/bin/env python3
"""Reconcile v3 installation evidence and v2 user report, preserving phase gates."""
import datetime as dt
import hashlib
import json
from pathlib import Path
import shutil

P = Path(__file__).resolve().parents[1]
PACKET = P / 'evidence/build-repair/audio-iris-20261124-v3'


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    before = PACKET / 'documentation-before'
    before.mkdir(exist_ok=False)
    for name in ['state.json', 'docs/STATE.md', 'docs/INDEX.md', 'docs/IMPLEMENTATION-LOG.md', 'README.md']:
        target = before / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(P / name, target)
    manifest = json.loads((PACKET / 'manifest.json').read_text())
    image = P / 'artifacts/A51-HakiOS-full-quality-audio-iris-v3-boot.img'
    assert sha(image) == manifest['image']['sha256']
    flash = Path((P / 'evidence/build-repair/latest-audio-iris-flash.txt').read_text().strip())
    result = json.loads((flash / 'result.json').read_text())
    old = (flash / 'boot-before.img').read_bytes()
    assert len(old) == 61865984 and hashlib.sha256(old).hexdigest() == result['boot_backup']['sha256']
    expected = hashlib.sha256(image.read_bytes() + old[image.stat().st_size:]).hexdigest()
    assert result['flash_verified'] and result['reboot_command_succeeded']
    assert expected == result['expected_full_partition_sha256'] == result['full_partition_readback_sha256']
    assert result['preserved_partition_pins_before'] == result['preserved_partition_pins_after']
    state = json.loads((P / 'state.json').read_text())
    original = json.loads(json.dumps(state))
    report = {'text': 'yes the phone is on the ios home screen and the audio is not working and there is no ssh app is there',
              'iris_report': 'the Iris app is not there', 'classification': 'user_reported_v2_home_screen_audio_silent_iris_absent',
              'recorded_utc': dt.datetime.now(dt.timezone.utc).isoformat(), 'independent_runtime_capture': False}
    state['build_repair_20261124']['device_installation']['subsequent_user_report'] = report
    state['build_repair_20261124']['device_installation']['status'] = 'flashed_verified_user_reports_home_screen_audio_silent_iris_absent'
    state['build_repair_20261124']['device_installation']['home_screen_user_reported'] = True
    relative = flash.relative_to(P).as_posix()
    state['audio_iris_repair_20261124'] = {
        'status': 'v3_host_verified_flashed_readback_verified_screen_audio_iris_pending',
        'guide': 'docs/AUDIO-IRIS-REPAIR-20261124.md', 'artifact': image.relative_to(P).as_posix(),
        'image': manifest['image'], 'kernel': manifest['entries']['kernel'], 'gpu': manifest['gpu'], 'audio': manifest['audio'],
        'host_packet': PACKET.relative_to(P).as_posix(), 'installation_result': relative + '/result.json',
        'full_partition_sha256': expected, 'v2_backup': {'packet': relative, **result['boot_backup']},
        'phone_write_verified': True, 'reboot_command_succeeded': True, 'recovery_dtbo_unchanged': True,
        'observation_status': result['observation_status'], 'home_screen_user_reported': False,
        'audible_audio_verified': False, 'iris_icon_verified': False, 'iris_launch_verified': False,
        'gpu_hardware_execution_verified': False, 'phase_gates_changed': False,
        'native_audio_cases': 11, 'native_iris_cases': 4, 'qemu_scope': 'virt/raw hello/audio disabled',
        'hardware_limits': ['speaker unverified', 'headphones/capture/routes unavailable', 'idle ring clearing only on callbacks',
                            'clock/DMA/MMU/cache assumptions unverified', 'Iris LaunchServices result unverified']}
    state['active_task'] = 'V3 audio/Iris repair flashed and readback verified; v2 home-screen report confirmed silent audio/missing Iris; publish source and verify v3 screen/audio/Iris'
    state['next_action'] = 'Collect v3 home-screen, speaker media playback and Iris icon/launch observations; push audited source to AnkitChoudhary-1/Hakios-Galaxy-A515F. Preserve phase gates.'
    write(P / 'state.json', state)
    for key in original:
        if key not in {'active_task', 'next_action', 'build_repair_20261124'}:
            assert state[key] == original[key], 'Historical/phase state drift: ' + key
    brief = ('V2 reached the iOS home screen per user, but audio was silent, Iris absent and SSH unavailable. '
             'V3 includes targeted audio clock/DMA/amplifier changes and nondestructive Iris boot registration. '
             'Its native checks, APFS/package checks and minimal QEMU PID1 test passed; authorized TWRP installation '
             'and full boot-partition readback passed. Recovery/DTBO are unchanged. V3 home-screen/audio/Iris acceptance '
             'is pending. Phase 4 and all existing completion gates are unchanged. See ')
    for name in ['docs/STATE.md', 'docs/INDEX.md', 'README.md']:
        path = P / name
        text = path.read_text(encoding='utf-8')
        heading, rest = text.split('\n', 1)
        guide = 'AUDIO-IRIS-REPAIR-20261124.md' if name.startswith('docs/') else 'docs/AUDIO-IRIS-REPAIR-20261124.md'
        path.write_text(heading + '\n\n## Audio/Iris v3 installation — 24 November 2026\n\n' + brief +
                        '[repair details](' + guide + ').\n\nOlder checkpoints below retain their historical scope.\n' + rest, encoding='utf-8')
    with (P / 'docs/IMPLEMENTATION-LOG.md').open('a', encoding='utf-8') as out:
        out.write('\n\n## REPAIR-003 — Audio/Iris v3 build and authorized installation (2026-11-24)\n\n' + brief +
                  '[source, exact hashes, failures, rebuild and rollback](AUDIO-IRIS-REPAIR-20261124.md).\n\n'
                  'Files changed: active A51 audio driver and synchronized XNU copy; staged/project Iris plist; '
                  'userland/src/iris_register.c, userland/build.sh, packaged rc.jobs and selectable rc.jobs.audio-iris; '
                  'scripts/repair-audio-iris.py, iris-register.c, test-audio-iris.py, export-audio-iris.py, '
                  'flash-audio-iris.py and record-audio-iris.py; repair guide, STATE/INDEX/README and state.json. '
                  'Before snapshots and both audio patches retained. GPU source/UEFI/init and Iris executable preserved. '
                  'Purpose: correct documented TAS ratio/book selection and DMA geometry/clock setup, bound the ring '
                  'writer, remove the boot square wave, gate unavailable audio and register the included app after startup.\n\n'
                  'Checks: 11 audio + 4 Iris actual-source native sanitizer cases; linked kernel/helper/loader; '
                  'APFS fsck/tree readback (505 md1, 12 md0); Android v2 packaging and pins; QEMU virt PID1/uid0 '
                  'with audio disabled. Existing kext symbol-set exit2 remains a build-check limitation. Failed stale '
                  'audio hash, helper main signature, reference URL and duplicated Windows export path attempts are '
                  'documented in the guide and preserved runs. V3 image ' + manifest['image']['sha256'] + '; full partition ' + expected + '.\n\n'
                  'Device: exactly one v3 boot write and one reboot; full backup independently hashed, candidate and '
                  'Android fallback staged/verified; recovery/DTBO identical before/after. No rollback required. '
                  '45-second ADB observation found no connected device, which does not establish iOS boot outcome. '
                  'V2 user report is added separately to its retained receipt/state checkpoint. No phase gate changed. '
                  'Rollback: pinned v2 full boot backup or pinned Android image from the guide, exact-model recovery '
                  'and independent readback before reboot. Limitations: live audio/Iris pending; headphones/capture '
                  'unavailable; consumer clearing callback-dependent; clock/MMU/DMA/cache assumptions need measurement.\n')
    write(PACKET / 'documentation-verification.json', {'passed': True, 'phase_gates_unchanged': True,
          'candidate_and_backup_pins_verified': True, 'full_partition_receipt_verified': True,
          'device_operations': False, 'files': {name: sha(P / name) for name in
              ['state.json', 'docs/STATE.md', 'docs/INDEX.md', 'docs/IMPLEMENTATION-LOG.md', 'README.md',
               'docs/AUDIO-IRIS-REPAIR-20261124.md', 'scripts/export-audio-iris.py', 'scripts/flash-audio-iris.py']}})
    print('v3 documentation reconciled; phase gates unchanged; runtime acceptance pending')


if __name__ == '__main__':
    main()
