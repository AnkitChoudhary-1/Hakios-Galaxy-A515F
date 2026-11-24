#!/usr/bin/env python3
"""Authorized v3 installation using the retained v2 safety/receipt procedure.

Only the candidate filename, hash and exact byte-length assertion change.
Historical v2 script and installation evidence remain untouched.
"""
import argparse
import importlib.util
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('v2_install', HERE / 'flash-gpu-audio-repair.py')
b = importlib.util.module_from_spec(spec)
spec.loader.exec_module(b)
b.ADB = 'C:/Android/platform-tools/adb.exe'
b.IMAGE = b.PROJECT / 'artifacts/A51-HakiOS-full-quality-audio-iris-v3-boot.img'
b.IMAGE_SHA = 'b0fa71744861524d40e97eb51214462ca81d9bd601d1a7fa320ca4b1677ad6c0'
b.LATEST = b.PROJECT / 'evidence/build-repair/latest-audio-iris-flash.txt'
source = (HERE / 'flash-gpu-audio-repair.py').read_text(encoding='utf-8')
body = source[source.index('def install():'):source.index('\ndef observe(')]
assert body.count('len(image) == 29700096') == 1
body = body.replace('len(image) == 29700096', 'len(image) == 29712384')
exec(compile(body, 'v3-retained-install-procedure', 'exec'), b.__dict__)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['install', 'observe'])
    parser.add_argument('--seconds', type=int, default=45)
    args = parser.parse_args()
    {'install': b.install, 'observe': lambda: b.observe(args.seconds)}[args.action]()
