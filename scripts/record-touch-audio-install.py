#!/usr/bin/env python3
"""Reconcile verified r1 installation with current state; never grants phase gates."""
import datetime as dt
import hashlib
import json
from pathlib import Path

P = Path(__file__).resolve().parents[1]


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def main():
    packet = Path((P / 'evidence/build-repair/latest-touch-audio-flash.txt').read_text().strip())
    result = json.loads((packet / 'result.json').read_text())
    assert result['flash_verified'] and result['reboot_command_succeeded']
    assert 'observation_status' in result
    image = (P / 'artifacts/A51-HakiOS-full-quality-touch-audio-r1-boot.img').read_bytes()
    old = (packet / 'boot-before.img').read_bytes()
    assert len(image) == 29720576 and sha(image) == result['image_sha256']
    assert len(old) == 61865984 and sha(old) == result['boot_backup']['sha256']
    assert sha(image + old[len(image):]) == result['expected_full_partition_sha256'] == result['full_partition_readback_sha256']
    assert result['preserved_partition_pins_before'] == result['preserved_partition_pins_after']
    state_path = P / 'state.json'
    before = state_path.read_bytes()
    state = json.loads(before)
    gates = {k: v for k, v in state.items() if 'phase' in k}
    relative = packet.relative_to(P).as_posix()
    repair = state['touch_audio_repair_20261124_r1']
    repair.update(status='flashed_readback_verified_hardware_acceptance_pending',
        phone_writes_this_repair=True, blocker='Physical boot/touch/speaker/Iris confirmation pending',
        reported_installed_image_pin=result['image_sha256'],
        previous_installed_full_partition_sha256=result['boot_backup']['sha256'],
        device_installation={
            'packet': relative, 'result': relative + '/result.json',
            'boot_partition': result['boot_partition'],
            'image_sha256': result['image_sha256'],
            'full_partition_sha256': result['full_partition_readback_sha256'],
            'boot_backup': result['boot_backup'], 'boot_write_verified': True,
            'reboot_command_succeeded': True, 'recovery_dtbo_unchanged': True,
            'low_battery_override': result.get('low_battery_override'),
            'observation_status': result['observation_status'],
            'device_boot_verified': False, 'phase_gates_changed': False})
    state['active_task'] = 'Touch/audio r1 flashed and full readback verified; physical acceptance pending; current source publication in progress'
    state['next_action'] = 'Confirm home screen, accurate taps, audible speaker media and Iris icon/launch; publish current source and installation documentation'
    assert gates == {k: v for k, v in state.items() if 'phase' in k}
    (packet / 'state-before-record.json').write_bytes(before)
    state_path.write_text(json.dumps(state, indent=2) + '\n', encoding='utf-8')
    note = ('R1 was flashed from rooted TWRP on 25 November 2026 after the user explicitly '
        'requested proceeding at 1% battery. USB power and Charging were verified before staging '
        'and immediately before writing. The full boot backup is retained and independently hashed. '
        'One boot write and one reboot succeeded; full-partition SHA-256 readback matched, and '
        'recovery/DTBO hashes stayed unchanged. Physical boot completion, touch accuracy, speaker '
        'playback, Iris icon/launch and diagnostic persistence remain unverified. '
        'Bounded ADB observation: ' + result['observation_status'] + '. Phase gates unchanged. '
        'Receipt: [installation result](../' + relative + '/result.json).')
    for name in ['docs/STATE.md', 'docs/INDEX.md']:
        path = P / name
        first, rest = path.read_text(encoding='utf-8').split('\n', 1)
        path.write_text(first + '\n\n## Touch/audio r1 installation — 25 November 2026\n\n' + note +
            '\n\nEarlier checkpoints below retain their historical scope.\n\n' + rest.lstrip('\n'), encoding='utf-8')
    path = P / 'README.md'
    first, rest = path.read_text(encoding='utf-8').split('\n', 1)
    path.write_text(first + '\n\n## Touch/audio r1 installation — 25 November 2026\n\n' +
        note.replace('../evidence/', 'evidence/') + '\n\n' + rest.lstrip('\n'), encoding='utf-8')
    detail = ('\n\n## Authorized r1 installation — 25 November 2026\n\n' + note +
        '\n\nFull partition: `' + result['full_partition_readback_sha256'] +
        '`. Before-image full partition: `' + result['boot_backup']['sha256'] +
        '`. These hashes identify image bytes plus the retained partition tail. '
        'The earlier host-only/no-installation paragraphs describe the preceding checkpoint.\n\n'
        'Initial attempt `20261124T233514923243Z-touch-audio-r1-install` stopped at '
        'the 30% battery check before staging or any write. The user then requested '
        '“just flash it anyway.” The r1 wrapper adds an explicit --allow-low-battery '
        'option; the default 30% check remains. The override verifies battery range, '
        'Charging/Full status and USB online at preflight and immediately before writing. '
        'All serial/model/root/partition/image/fallback/backup/readback checks remain. '
        'Successful run: `20261124T233948796103Z-touch-audio-r1-install-user-battery-override`. '
        'Observation: `20261124T234041342882Z-touch-audio-r1-observe`.\n\n'
        'Changed files: scripts/flash-touch-audio.py (opt-in override), '
        'scripts/record-touch-audio-install.py (independent receipt verification and reconciliation), '
        'STATE/INDEX/README, this guide, implementation log and state.json. '
        'No build or image byte changed. No rollback was needed. '
        'Keep the full boot backup; its previous image had reported touch/audio failures. '
        'For a known Android fallback use the pinned image already described above, '
        'through exact-model recovery with full readback before reboot.\n')
    with (P / 'docs/TOUCH-AUDIO-REPAIR-20261124.md').open('a', encoding='utf-8') as out:
        out.write(detail)
    with (P / 'docs/IMPLEMENTATION-LOG.md').open('a', encoding='utf-8') as out:
        out.write('\n\n## REPAIR-006 — User-authorized r1 installation and battery override (2026-11-25)\n' + detail)
    receipt = {'recorded_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
        'installation_packet': relative, 'independent_host_hash_verification': True,
        'phase_gates_unchanged': True, 'state_sha256': sha(state_path.read_bytes())}
    (packet / 'record-result.json').write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(receipt, indent=2))


if __name__ == '__main__':
    main()
