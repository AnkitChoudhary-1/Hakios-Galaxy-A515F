#!/usr/bin/env python3
"""Explicitly authorized TWRP installation of the pinned GPU/audio v2 image.

Run install/observe through scripts/run.py. Installation writes boot only,
verifies full-partition readback, and reboots only after successful checks.
"""
import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import time
import uuid

PROJECT = Path(__file__).resolve().parents[1]
ADB = shutil.which('adb')
SERIAL = 'A51_SERIAL_HERE'
BOOT = '/dev/block/sda12'
SIZE = 61865984
IMAGE = PROJECT / 'artifacts/A51-HakiOS-full-quality-gpu-audio-fixed-v2-boot.img'
IMAGE_SHA = '9f7fd881143c1ba81a28359ead8000b0d9a953690e67ebac3e0a603dd806ec30'
BASELINE = PROJECT.parent / 'everline-ksu/artifacts/A51-PixelOS-Everline-KernelSU-Next-boot.img'
BASELINE_SHA = 'eb30609a62999e3282ac81e0a5e56411ef12ec1a39c107171bf3e01209c7cb67'
RECOVERY_SHA = '12412e2008d950260cda627ac7a6b8eac954b49ef9db5573a297f67e4fc85999'
DTBO_SHA = '41662c61ff3158448935025477a4e29d445823dab2cddafb18ea649c8ea925d6'
LATEST = PROJECT / 'evidence/build-repair/latest-device-flash.txt'


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def digest(data):
    return hashlib.sha256(data).hexdigest()


def write(path, data):
    path.write_text(json.dumps(data, indent=2) + '\n', encoding='utf-8')


class Device:
    def __init__(self, packet):
        self.packet = packet
        self.index = len(list(packet.glob('command-*.json')))

    def run(self, name, args, timeout=35, required=True):
        self.index += 1
        stem = self.packet / f'command-{self.index:03d}-{name}'
        cmd = [ADB, '-s', SERIAL, *args]
        record = {'command': cmd, 'started_utc': now()}
        write(stem.with_suffix('.json'), record)
        print('COMMAND ' + json.dumps(cmd), flush=True)
        try:
            proc = subprocess.run(cmd, capture_output=True, timeout=timeout)
            stem.with_suffix('.stdout.bin').write_bytes(proc.stdout)
            stem.with_suffix('.stderr.bin').write_bytes(proc.stderr)
            record.update(exit_code=proc.returncode, stdout_bytes=len(proc.stdout),
                          stdout_sha256=digest(proc.stdout), stderr_bytes=len(proc.stderr))
            print(f'RETURN {proc.returncode}; stdout bytes={len(proc.stdout)}', flush=True)
            if args[0] != 'exec-out':
                print((proc.stdout + proc.stderr).decode(errors='replace')[:1400], flush=True)
            if required and proc.returncode:
                raise RuntimeError(name + ': ADB exit ' + str(proc.returncode))
            return proc
        except subprocess.TimeoutExpired as exc:
            stem.with_suffix('.stdout.bin').write_bytes(exc.stdout or b'')
            stem.with_suffix('.stderr.bin').write_bytes(exc.stderr or b'')
            record['error'] = 'timeout'
            raise
        finally:
            record['finished_utc'] = now()
            write(stem.with_suffix('.json'), record)

    def shell(self, name, command, required=True):
        framed = command + "; hakios_rc=$?; printf '\\nHAKIOS_REMOTE_RC=%s\\n' \"$hakios_rc\"; exit \"$hakios_rc\""
        proc = self.run(name, ['shell', 'sh', '-c', shlex.quote(framed)], required=False)
        match = re.search(rb'\r?\nHAKIOS_REMOTE_RC=([0-9]+)\r?\n?$', proc.stdout)
        if not match:
            if required:
                raise RuntimeError(name + ': missing remote exit frame')
            return proc.stdout.decode(errors='replace').strip()
        if required and (proc.returncode or int(match[1])):
            raise RuntimeError(name + ': remote exit ' + match[1].decode())
        return proc.stdout[:match.start()].decode(errors='replace').strip()


def require(value, message):
    if not value:
        raise RuntimeError(message)


def pins(dev, suffix):
    rec = dev.shell('recovery-' + suffix, 'sha256sum /dev/block/by-name/recovery').split()[0]
    dtbo = dev.shell('dtbo-' + suffix, 'sha256sum /dev/block/by-name/dtbo').split()[0]
    require(rec == RECOVERY_SHA and dtbo == DTBO_SHA, 'Recovery/DTBO pins differ')
    return {'recovery': rec, 'dtbo': dtbo}


def install():
    packet = PROJECT / 'evidence/build-repair' / ('device-flash-' + dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
    packet.mkdir()
    LATEST.write_text(str(packet) + '\n', encoding='utf-8')
    for name in ['state.json', 'docs/STATE.md', 'docs/IMPLEMENTATION-LOG.md', 'docs/INDEX.md', 'docs/GPU-AUDIO-BUILD-REPAIR.md']:
        target = packet / 'before' / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(PROJECT / name, target)
    result = {'started_utc': now(), 'serial': SERIAL, 'image': str(IMAGE),
              'image_sha256': IMAGE_SHA, 'authorization': 'User explicitly requested flashing this image from connected TWRP',
              'boot_partition': BOOT, 'boot_write_attempted': False,
              'flash_verified': False, 'reboot_attempted': False,
              'device_boot_verified': False, 'audible_audio_verified': False,
              'gpu_hardware_execution_verified': False}
    write(packet / 'result.json', result)
    dev = Device(packet)
    token = uuid.uuid4().hex
    candidate = '/tmp/hakios-gpu-audio-' + token + '.img'
    rollback = '/tmp/hakios-android-rollback-' + token + '.img'
    try:
        image = IMAGE.read_bytes()
        baseline = BASELINE.read_bytes()
        require(digest(image) == IMAGE_SHA and len(image) == 29700096, 'Candidate pin mismatch')
        require(digest(baseline) == BASELINE_SHA and len(baseline) == SIZE, 'Rollback pin mismatch')
        require(dev.run('state', ['get-state']).stdout.strip() == b'recovery', 'Device is not in recovery')
        require('uid=0(root)' in dev.shell('root', 'id'), 'Recovery is not root')
        require(dev.shell('model', 'getprop ro.product.model') == 'SM-A515F', 'Wrong phone model')
        require(bool(dev.shell('twrp', 'getprop ro.twrp.version')), 'TWRP version missing')
        require(dev.shell('target', 'readlink -f /dev/block/by-name/boot') == BOOT, 'Boot target differs')
        require(int(dev.shell('partition-size', 'blockdev --getsize64 ' + BOOT)) == SIZE, 'Boot size differs')
        require(int(dev.shell('battery', 'cat /sys/class/power_supply/battery/capacity')) >= 30, 'Battery too low')
        result['preserved_partition_pins_before'] = pins(dev, 'before')
        dev.shell('tmp-space', 'df -k /tmp')
        old = dev.run('backup-current-boot', ['exec-out', 'cat', BOOT], timeout=60).stdout
        require(len(old) == SIZE, 'Boot backup incomplete')
        original_sha = digest(old)
        require(dev.shell('backup-independent-hash', 'sha256sum ' + BOOT).split()[0] == original_sha, 'Boot backup hash mismatch')
        (packet / 'boot-before.img').write_bytes(old)
        result['boot_backup'] = {'file': 'boot-before.img', 'size': SIZE, 'sha256': original_sha}
        dev.run('pstore-before', ['pull', '/sys/fs/pstore', str(packet / 'pstore-before')], required=False)
        expected_partition_sha = digest(image + old[len(image):])
        result.update(expected_full_partition_sha256=expected_partition_sha,
                      staging_paths=[candidate, rollback], staging_attempted=True)
        write(packet / 'result.json', result)
        for local, remote, expected_size, sha in [(IMAGE, candidate, len(image), IMAGE_SHA), (BASELINE, rollback, SIZE, BASELINE_SHA)]:
            dev.shell('staging-absent', 'test ! -e ' + remote + ' && test ! -L ' + remote)
            dev.run('stage-image', ['push', str(local), remote], timeout=60)
            require(int(dev.shell('stage-size', 'stat -c %s ' + remote)) == expected_size, 'Staged size mismatch')
            require(dev.shell('stage-hash', 'sha256sum ' + remote).split()[0] == sha, 'Staged hash mismatch')
        require(dev.run('state-before-write', ['get-state']).stdout.strip() == b'recovery', 'Recovery connection changed')
        require(dev.shell('target-before-write', 'readlink -f /dev/block/by-name/boot') == BOOT, 'Boot target changed')
        require(dev.shell('current-before-write', 'sha256sum ' + BOOT).split()[0] == original_sha, 'Boot changed during staging')
        result['boot_write_attempted'] = True
        write(packet / 'result.json', result)
        try:
            dev.shell('flash-boot', 'dd if=' + candidate + ' of=' + BOOT + ' bs=4096 conv=fsync')
            dev.shell('sync-after-flash', 'sync')
            actual = dev.shell('full-partition-readback', 'sha256sum ' + BOOT).split()[0]
            require(actual == expected_partition_sha, 'Full-partition readback mismatch')
            result['full_partition_readback_sha256'] = actual
            result['preserved_partition_pins_after'] = pins(dev, 'after')
            result['flash_verified'] = True
            write(packet / 'result.json', result)
        except Exception:
            result['rollback_attempted'] = True
            write(packet / 'result.json', result)
            dev.shell('rollback-boot', 'dd if=' + rollback + ' of=' + BOOT + ' bs=4096 conv=fsync')
            restored = dev.shell('rollback-readback', 'sha256sum ' + BOOT).split()[0]
            result['rollback_verified'] = restored == BASELINE_SHA
            write(packet / 'result.json', result)
            require(result['rollback_verified'], 'Rollback could not be verified; retain recovery')
            raise
        dev.shell('cleanup-staging', 'rm -f ' + candidate + ' ' + rollback)
        result['reboot_attempted'] = True
        result['reboot_requested_utc'] = now()
        write(packet / 'result.json', result)
        dev.run('reboot-system', ['reboot'], timeout=20)
        result['reboot_command_succeeded'] = True
    except Exception as exc:
        result['error'] = str(exc)
        raise
    finally:
        result['finished_utc'] = now()
        write(packet / 'result.json', result)
        print('PACKET ' + str(packet), flush=True)
        print(json.dumps(result, indent=2), flush=True)


def observe(seconds):
    packet = Path(LATEST.read_text(encoding='utf-8').strip())
    result = json.loads((packet / 'result.json').read_text(encoding='utf-8'))
    require(result['flash_verified'] and result['reboot_command_succeeded'], 'No verified installation/reboot')
    dev = Device(packet)
    deadline = time.monotonic() + seconds
    observations = []
    while time.monotonic() < deadline:
        proc = dev.run('observe-state', ['get-state'], timeout=10, required=False)
        state = proc.stdout.decode(errors='replace').strip()
        observations.append({'utc': now(), 'adb_state': state, 'exit_code': proc.returncode})
        if proc.returncode == 0 and state == 'recovery':
            result['returned_to_recovery'] = True
            result['recovery_boot_id'] = dev.shell('recovery-boot-id', 'cat /proc/sys/kernel/random/boot_id')
            result['postboot_partition_sha256'] = dev.shell('postboot-hash', 'sha256sum ' + BOOT).split()[0]
            result['preserved_partition_pins_postboot'] = pins(dev, 'postboot')
            dev.run('pstore-after', ['pull', '/sys/fs/pstore', str(packet / 'pstore-after')], required=False)
            dev.run('recovery-log-after', ['pull', '/tmp/recovery.log', str(packet / 'recovery-after.log')], required=False)
            break
        if proc.returncode == 0 and state == 'device':
            completed = dev.shell('android-completed', 'getprop sys.boot_completed', required=False)
            result['android_boot_completed_observed'] = completed == '1'
            if completed == '1':
                break
        time.sleep(min(5, max(0, deadline - time.monotonic())))
    result.update(observation_finished_utc=now(), observation_seconds_limit=seconds,
                  observation_status=('returned_to_recovery' if result.get('returned_to_recovery') else
                                      'android_observed' if result.get('android_boot_completed_observed') else
                                      'no_adb_boot_confirmation'), observations=observations)
    write(packet / 'result.json', result)
    print(json.dumps(result, indent=2), flush=True)


def record_installation(user_report):
    packet = Path(LATEST.read_text(encoding='utf-8').strip())
    result = json.loads((packet / 'result.json').read_text(encoding='utf-8'))
    require(result['flash_verified'] and result['reboot_command_succeeded'], 'Installation incomplete')
    require('observation_status' in result, 'Finish bounded observation first')
    require(digest(IMAGE.read_bytes()) == IMAGE_SHA, 'Image changed')
    old = (packet / 'boot-before.img').read_bytes()
    require(digest(old) == result['boot_backup']['sha256'] and len(old) == SIZE, 'Backup changed')
    full_sha = digest(IMAGE.read_bytes() + old[IMAGE.stat().st_size:])
    require(full_sha == result['expected_full_partition_sha256'] == result['full_partition_readback_sha256'], 'Readback receipt differs')
    require(result['preserved_partition_pins_before'] == result['preserved_partition_pins_after'], 'Preserved partitions differ')
    result['user_screen_report'] = {'text': user_report, 'recorded_utc': now(), 'classification': 'user_reported_boot_progress_only'}
    write(packet / 'result.json', result)
    state_path = PROJECT / 'state.json'
    state = json.loads(state_path.read_text(encoding='utf-8'))
    before = json.loads((packet / 'before/state.json').read_text(encoding='utf-8'))
    require(state == before, 'State changed since preflash snapshot; reconcile instead of overwriting')
    relative = str(packet.relative_to(PROJECT)).replace('\\', '/')
    state['active_task'] = 'Repaired full-quality v2 flashed and readback verified; user reports booting in iOS; home-screen/GPU/audio acceptance pending'
    state['next_action'] = 'Wait for home-screen completion and verify physical audio/GPU behavior; retain logs and existing phase gates. No additional flash is scheduled.'
    state['build_repair_20261124']['device_installation'] = {
        'packet': relative, 'result': relative + '/result.json',
        'status': 'flashed_verified_user_reports_boot_progress',
        'serial': SERIAL, 'boot_partition': BOOT,
        'image_sha256': IMAGE_SHA, 'full_partition_sha256': full_sha,
        'backup': result['boot_backup'], 'boot_write_verified': True,
        'reboot_command_succeeded': True,
        'recovery_dtbo_unchanged': True, 'user_screen_report': result['user_screen_report'],
        'observation_status': result['observation_status'],
        'device_boot_completed_verified': False, 'home_screen_verified': False,
        'audible_audio_verified': False, 'gpu_hardware_execution_verified': False,
        'phone_writes_this_installation': True, 'phase_gates_changed': False,
        'authorization': result['authorization'],
    }
    write(state_path, state)
    for key, value in before.items():
        if key not in {'active_task', 'next_action', 'build_repair_20261124'}:
            require(state[key] == value, 'Phase/historical state drift: ' + key)
    brief = ("The user explicitly authorized installation from connected TWRP. Repaired full-quality v2 was written to "
             "boot and independently verified by full-partition SHA-256 before reboot. The user reports “" + user_report +
             ".” This is boot progress, not home-screen/GPU/audio acceptance. Recovery/DTBO remain unchanged; "
             "the old boot partition is backed up. Bounded ADB observation: " + result['observation_status'] +
             ". Phase gates are unchanged. Evidence: [installation receipt](../" + relative + "/result.json).")
    for name, title in [('STATE.md', '# HakiOS A51 - current state'),
                        ('INDEX.md', '# Documentation index and reading order')]:
        path = PROJECT / 'docs' / name
        text = path.read_text(encoding='utf-8')
        require(text.startswith(title + '\n'), 'Unexpected document heading')
        text = text.replace(title + '\n', title + '\n\n## Authorized device installation — 24 November 2026\n\n' + brief + '\n\nThe host-repair checkpoint below describes the state before this installation.\n', 1)
        path.write_text(text, encoding='utf-8')
    guide = PROJECT / 'docs/GPU-AUDIO-BUILD-REPAIR.md'
    with guide.open('a', encoding='utf-8') as out:
        out.write('\n\n## Subsequent authorized installation — 24 November 2026\n\n' + brief +
                  '\n\nThe earlier no-device-write statements describe the completed host repair, before the new flash request. '
                  'The installed image remains the same pinned v2 artifact. The full-partition hash is `' + full_sha +
                  '`: image bytes followed by the preserved original partition tail. A backup of the former 61,865,984-byte '
                  'boot partition is retained as `boot-before.img` in the installation packet. The pinned Android rollback '
                  'was staged and verified before writing; rollback was not needed. One candidate write and one reboot '
                  'completed. Both temporary staged images were removed before reboot. No recovery/DTBO, repartitioning, '
                  'module or security change occurred.\n\n'
                  'The initial install run failed its backup-length check before staging or a partition write: '
                  'exec-out quoting produced a shell error. Binary `exec-out cat /dev/block/sda12` corrected the capture. '
                  'The failed packet and run are preserved. The installation script records exact arguments, raw outputs, '
                  'remote exit frames and durable write/reboot intent. On partial/failed write or readback it restores the '
                  'preverified Android rollback and verifies it while retaining recovery.\n\n'
                  'Commands: `python scripts/run.py --label gpu-audio-v2-authorized-twrp-install-binary-backup -- '
                  'python scripts/flash-gpu-audio-repair.py install`, then `observe --seconds 60` through the wrapper. '
                  'These are historical installation commands, not an instruction for another device cycle.\n')
    with (PROJECT / 'docs/IMPLEMENTATION-LOG.md').open('a', encoding='utf-8') as out:
        out.write('\n\n## REPAIR-002 — User-authorized TWRP installation of repaired v2 (2026-11-24)\n\n' + brief +
                  '\n\nFiles/purpose: add scripts/flash-gpu-audio-repair.py with install, bounded observe and record actions. '
                  'Capture the original full boot partition and pstore; assert exact serial/model/root/TWRP/partition/battery '
                  'and recovery/DTBO pins; verify host/staged candidate and Android rollback; retain durable intents, commands '
                  'and remote exits. Write only /dev/block/sda12, sync and compare full readback against candidate plus original '
                  'tail; preserve the tail. Remove two nonce-named temporary files and reboot after verification. '
                  'Initial run 20261124T025226923406Z failed binary backup length with a shell quoting error before staging/write. '
                  'Corrected exec-out cat backup; run 20261124T025257397382Z completed. Original boot hash ' +
                  result['boot_backup']['sha256'] + '; candidate ' + IMAGE_SHA + '; full readback ' + full_sha +
                  '. One candidate boot write, one reboot, zero rollback writes; recovery/DTBO unchanged. '
                  'Preverified pinned Android rollback was available throughout flashing. No source/kernel/image change occurred.\n\n'
                  'State/documentation: record supplemental device_installation in state.json; update task/next action and prepend '
                  'installation checkpoint in STATE/INDEX; append this entry and guide supplement. Retain host-repair false '
                  'device-operation flags as historical capture facts. Preserve every existing phase criterion/status/gate/blocker '
                  'and historical evidence value. User screen report is boot progress only. ADB absence cannot establish success '
                  'or failure of the iOS boot. Home-screen completion, GPU acceleration and audible playback remain unverified.\n\n'
                  'Verification/rollback: record action independently rehashes host image and original backup, reconstructs full '
                  'partition digest, checks retained readback/preserved-partition receipts and unchanged historical state, then '
                  'pins installation evidence and updated docs/scripts. Retain failed/successful packets and run logs. '
                  'No rollback was needed. A later restoration must use connected recovery, verified exact model/partition and '
                  'the pinned Android backup with readback before reboot; do not restore the known failed original boot image '
                  'as a working baseline. Additional flashing is not scheduled by this record.\n')
    ledger = {}
    for path in packet.rglob('*'):
        if path.is_file():
            ledger[str(path.relative_to(PROJECT)).replace('\\', '/')] = digest(path.read_bytes())
    for name in ['state.json', 'docs/STATE.md', 'docs/INDEX.md', 'docs/IMPLEMENTATION-LOG.md',
                 'docs/GPU-AUDIO-BUILD-REPAIR.md', 'scripts/flash-gpu-audio-repair.py']:
        ledger[name] = digest((PROJECT / name).read_bytes())
    write(packet / 'installation-files.json', ledger)
    verification = {'passed': True, 'verified_utc': now(), 'device_operations': False,
                    'host_image_and_backup_pins_verified': True, 'readback_receipt_verified': True,
                    'phase_gates_unchanged': True, 'files_pinned': len(ledger),
                    'installation_result_sha256': digest((packet / 'result.json').read_bytes())}
    write(packet / 'documentation-verification.json', verification)
    print(json.dumps(verification, indent=2), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['install', 'observe', 'record'])
    parser.add_argument('--seconds', type=int, default=60)
    parser.add_argument('--user-report', default='unknown')
    args = parser.parse_args()
    require(ADB is not None, 'ADB unavailable')
    {'install': install, 'observe': lambda: observe(args.seconds),
     'record': lambda: record_installation(args.user_report)}[args.action]()
