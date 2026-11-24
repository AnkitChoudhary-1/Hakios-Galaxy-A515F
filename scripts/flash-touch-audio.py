#!/usr/bin/env python3
"""User-authorized r1 checked TWRP installer; preserve existing installer/evidence."""
import argparse
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('checked_install', HERE / 'flash-gpu-audio-repair.py')
b = importlib.util.module_from_spec(spec)
spec.loader.exec_module(b)
b.ADB = 'C:/Android/platform-tools/adb.exe'
b.IMAGE = b.PROJECT / 'artifacts/A51-HakiOS-full-quality-touch-audio-r1-boot.img'
b.IMAGE_SHA = '2f22fbb6f0cacae5afb17488d4bcdc6b6bd3b64a6fd046721bfee43880544ea7'
b.LATEST = b.PROJECT / 'evidence/build-repair/latest-touch-audio-flash.txt'


def require_external_power(dev, phase):
    """Explicit low-battery override requires observed USB charging at both gates."""
    capacity = int(dev.shell('battery-override-' + phase,
        'cat /sys/class/power_supply/battery/capacity'))
    status = dev.shell('charging-' + phase,
        'cat /sys/class/power_supply/battery/status')
    online = dev.shell('usb-power-' + phase,
        'cat /sys/class/power_supply/usb/online')
    b.require(0 <= capacity <= 100 and status in ('Charging', 'Full') and online == '1',
        'Low-battery override requires connected USB power and charging')


def install(allow_low_battery=False):
    packet = b.PROJECT / 'evidence/build-repair/touch-audio-20261124-r1'
    manifest = json.loads((packet / 'manifest.json').read_text())
    assert manifest['host_package_verified'] and manifest['image']['sha256'] == b.IMAGE_SHA
    assert json.loads(sorted(packet.glob('qemu-*/result.json'))[-1].read_text())['passed']
    for name in ['audio-iris-tests.json', 'touch-clock-tests.json']:
        assert json.loads((packet / name).read_text())['passed']
    # Retain every preflight/backup/staging/readback/rollback operation; only pin changes.
    source = (HERE / 'flash-gpu-audio-repair.py').read_text()
    body = source[source.index('def install():'):source.index('\ndef observe(')]
    assert 'len(image) == 29700096' in body
    body = body.replace('len(image) == 29700096', 'len(image) == 29720576')
    if allow_low_battery:
        gate = "require(int(dev.shell('battery', 'cat /sys/class/power_supply/battery/capacity')) >= 30, 'Battery too low')"
        assert body.count(gate) == 1
        body = body.replace(gate,
            "require_external_power(dev, 'preflight')\n"
            "        result['low_battery_override'] = {'explicit_user_request': 'just flash it anyway', 'usb_charging_required': True}")
        marker = "        result['boot_write_attempted'] = True"
        assert body.count(marker) == 1
        body = body.replace(marker,
            "        require_external_power(dev, 'before-write')\n" + marker)
        b.require_external_power = require_external_power
    exec(compile(body, 'r1-checked-install', 'exec'), b.__dict__)
    b.install()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['install', 'observe'])
    parser.add_argument('--seconds', type=int, default=45)
    parser.add_argument('--allow-low-battery', action='store_true',
        help='Only for an explicit user override; connected USB charging is required')
    args = parser.parse_args()
    if args.action == 'install':
        install(args.allow_low_battery)
    else:
        b.observe(args.seconds)
