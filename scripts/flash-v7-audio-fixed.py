#!/usr/bin/env python3
"""Authorized v7 installation with non-halting init idle loop, launchd fallback, and physical sound_test commands.

Preserves all safety guarantees:
- Asserts device model, serial (A51_SERIAL_HERE), TWRP mode, and battery
- Verifies recovery and dtbo partition pins
- Takes full-partition backup of /dev/block/sda12 before writing
- Stages verified Android rollback image
- Writes only /dev/block/sda12 (boot partition)
- Compares full-partition readback hash before issuing reboot
"""
import argparse
import importlib.util
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('v2_install', HERE / 'flash-gpu-audio-repair.py')
b = importlib.util.module_from_spec(spec)
spec.loader.exec_module(b)
b.ADB = 'C:/Android/platform-tools/adb.exe'
b.IMAGE = b.PROJECT / 'artifacts/A51-HakiOS-full-quality-audio-iris-v7-boot.img'
b.IMAGE_SHA = '1b60eee07be94e13c86907039d196470b1ed50de95fd9bc8c93870d7af589c2b'
b.LATEST = b.PROJECT / 'evidence/build-repair/latest-audio-v7-flash.txt'

source = (HERE / 'flash-gpu-audio-repair.py').read_text(encoding='utf-8')
body = source[source.index('def install():'):source.index('\ndef observe(')]
assert body.count('len(image) == 29700096') == 1
body = body.replace('len(image) == 29700096', 'len(image) == 29712384')
exec(compile(body, 'v7-retained-install-procedure', 'exec'), b.__dict__)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['install', 'observe'])
    parser.add_argument('--seconds', type=int, default=45)
    args = parser.parse_args()
    {'install': b.install, 'observe': lambda: b.observe(args.seconds)}[args.action]()
