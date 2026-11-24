#!/usr/bin/env python3
"""Export pinned v3 and its host evidence without overwriting v2."""
import hashlib
import json
from pathlib import Path
import shutil

PROJECT = Path(__file__).resolve().parents[1]
WSL = Path('//wsl.localhost/A51-KernelBuilder/opt/a51-hakios')
WORK = WSL / 'build-repair/audio-iris-20261124'
UP = WSL / 'upstream-a51/hakios'
IMAGE = 'A51-HakiOS-full-quality-audio-iris-v3-boot.img'
SHA = 'b0fa71744861524d40e97eb51214462ca81d9bd601d1a7fa320ca4b1677ad6c0'


def pin(path):
    raw = path.read_bytes()
    return {'size': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def main():
    manifest = json.loads((WORK / 'manifest.json').read_text())
    assert manifest['host_package_verified'] and manifest['image']['sha256'] == SHA
    qemu = sorted(WORK.glob('qemu-*/result.json'))[-1]
    assert json.loads(qemu.read_text())['passed']
    assert json.loads((WORK / 'audio-iris-tests.json').read_text())['passed']
    packet = PROJECT / 'evidence/build-repair/audio-iris-20261124-v3'
    packet.mkdir(exist_ok=False)
    shutil.copytree(WORK / 'before', packet / 'before')
    for file in WORK.iterdir():
        if file.is_file() and file.suffix in {'.json', '.txt', '.patch', '.head', '.status', '.log', '.c'}:
            shutil.copy2(file, packet / file.name)
    for folder in WORK.glob('qemu-*'):
        dest = packet / folder.name
        dest.mkdir()
        for file in folder.iterdir():
            if file.is_file() and file.suffix in {'.json', '.log', '.c', '.sh'}:
                shutil.copy2(file, dest / file.name)
    names = ['devices/a51/drivers/audio/hakios.a51audio.c', 'devices/a51/drivers/gpu/hakios.a51gpu.c',
             'userland/src/iris_register.c', 'userland/build.sh', 'userland/rc.jobs.audio-iris',
             'userland/root/etc/rc.jobs']
    for name in names:
        dest = packet / 'after' / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(UP / name, dest)
    dest = PROJECT / 'artifacts' / IMAGE
    assert not dest.exists(), 'Preserve an existing image'
    shutil.copy2(WORK / IMAGE, dest)
    assert pin(dest) == manifest['image']
    dest.with_suffix('.img.sha256').write_text(SHA + '  ' + IMAGE + '\n')
    shutil.copy2(WORK / 'manifest.json', dest.with_suffix('.img.manifest.json'))
    receipt = {'image': pin(dest), 'image_path': str(dest), 'packet': str(packet),
               'qemu_result': str(packet / qemu.parent.name / 'result.json'),
               'device_operations': False, 'audible_audio_verified': False, 'iris_icon_verified': False}
    (packet / 'export.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt, indent=2))


if __name__ == '__main__':
    main()
