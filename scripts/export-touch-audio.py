#!/usr/bin/env python3
"""Export the checked r1 image and evidence, preserving older artifacts."""
import hashlib
import json
from pathlib import Path
import shutil

P = Path(__file__).resolve().parents[1]
W = Path('//wsl.localhost/A51-KernelBuilder/opt/a51-hakios/build-repair/touch-audio-20261124-r1')
UP = W.parents[1] / 'upstream-a51/hakios'
IMAGE = 'A51-HakiOS-full-quality-touch-audio-r1-boot.img'


def pin(path):
    raw = path.read_bytes()
    return {'size': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def main():
    manifest = json.loads((W / 'manifest.json').read_text())
    assert manifest['host_package_verified'] and 'touch' in manifest
    assert pin(W / IMAGE) == manifest['image']
    qemu = sorted(W.glob('qemu-*/result.json'))[-1]
    assert json.loads(qemu.read_text())['passed']
    for name in ['audio-iris-tests.json', 'touch-clock-tests.json']:
        assert json.loads((W / name).read_text())['passed']
    packet = P / 'evidence/build-repair/touch-audio-20261124-r1'
    packet.mkdir(exist_ok=False)
    shutil.copytree(W / 'before', packet / 'before')
    shutil.copytree(W / 'reference', packet / 'reference')
    for file in W.iterdir():
        if file.is_file() and file.suffix in {'.json', '.txt', '.patch', '.head', '.status', '.log', '.c'}:
            shutil.copy2(file, packet / file.name)
    for folder in W.glob('qemu-*'):
        dest = packet / folder.name
        dest.mkdir()
        for file in folder.iterdir():
            if file.is_file() and file.suffix in {'.json', '.log', '.c', '.sh'}:
                shutil.copy2(file, dest / file.name)
    for name in ['devices/a51/drivers/audio/hakios.a51audio.c',
                 'devices/a51/drivers/input/hakios.a51input.c',
                 'devices/a51/drivers/gpu/hakios.a51gpu.c']:
        dest = packet / 'after' / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(UP / name, dest)
    shutil.copy2(P / 'scripts/device-diagnostics.c', packet / 'device-diagnostics.c')
    dest = P / 'artifacts' / IMAGE
    assert not dest.exists(), 'Preserve existing image'
    shutil.copy2(W / IMAGE, dest)
    assert pin(dest) == manifest['image']
    dest.with_suffix('.img.sha256').write_text(manifest['image']['sha256'] + '  ' + IMAGE + '\n')
    shutil.copy2(W / 'manifest.json', dest.with_suffix('.img.manifest.json'))
    receipt = {'image': pin(dest), 'image_path': str(dest), 'packet': str(packet),
        'qemu_result': str(packet / qemu.parent.name / 'result.json'),
        'device_operations': False, 'audible_audio_verified': False,
        'touch_accuracy_verified': False, 'iris_icon_verified': False,
        'diagnostics_persistence_verified': False}
    (packet / 'export.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt, indent=2))


if __name__ == '__main__':
    main()
