#!/usr/bin/env python3
"""Read-only recovery capture and source snapshot for silent-speaker diagnosis."""
import datetime
import hashlib
import json
from pathlib import Path
import subprocess

PROJECT = Path(__file__).resolve().parents[1]
ADB = 'C:/Android/platform-tools/adb.exe'
SERIAL = 'A51_SERIAL_HERE'
UP = Path('//wsl.localhost/A51-KernelBuilder/opt/a51-hakios/upstream-a51/hakios')

def main():
    out = PROJECT / 'evidence/build-repair' / ('audio-failure-' + datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
    out.mkdir(exist_ok=False)
    records = {}
    commands = {
        'identity': ['shell', 'getprop ro.product.model; getprop ro.twrp.version; id'],
        'boot-sha256': ['shell', 'sha256sum /dev/block/sda12'],
        'last-kmsg': ['exec-out', 'cat', '/proc/last_kmsg'],
        'recovery-dmesg': ['exec-out', 'dmesg'],
        'persistent-inventory': ['shell', 'ls -la /sys/fs/pstore /cache /external_sd; cat /proc/mounts'],
    }
    for name, args in commands.items():
        cmd = [ADB, '-s', SERIAL] + args
        r = subprocess.run(cmd, capture_output=True, timeout=60)
        (out / (name + '.bin')).write_bytes(r.stdout)
        (out / (name + '.stderr')).write_bytes(r.stderr)
        records[name] = dict(command=cmd, exit_code=r.returncode, bytes=len(r.stdout), sha256=hashlib.sha256(r.stdout).hexdigest())
    assert b'SM-A515F' in (out / 'identity.bin').read_bytes()
    assert b'3.7.1_12' in (out / 'identity.bin').read_bytes()
    names = ['devices/a51/drivers/audio/hakios.a51audio.c', 'devices/a51/drivers/gpu/hakios.a51gpu.c',
             'drivers/audio/hakios.audio.c', 'userland/src/audio_plugin.c', 'userland/build.sh',
             'userland/root/etc/rc.jobs', 'userland/rc.jobs.audio-iris', '.config']
    source = {}
    for name in names:
        p = UP / name
        if not p.is_file():
            source[name] = dict(available=False)
            continue
        data = p.read_bytes()
        target = out / 'source' / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        source[name] = dict(bytes=len(data), sha256=hashlib.sha256(data).hexdigest())
    result = dict(schema_version=1, recovery_read_only=True, device_writes=False, records=records, source=source)
    (out / 'result.json').write_text(json.dumps(result, indent=2)+'\n')
    (PROJECT / 'evidence/build-repair/latest-audio-failure.txt').write_text(out.relative_to(PROJECT).as_posix()+'\n')
    print(out)
    log = (out / 'last-kmsg.bin').read_text(errors='replace')
    for line in log.splitlines():
        if any(s in line.lower() for s in ['a51audio', 'hakios-audio', 'tas2562', 'audio', 'darwin', 'xnu', 'panic']):
            print(line)

if __name__ == '__main__':
    main()
