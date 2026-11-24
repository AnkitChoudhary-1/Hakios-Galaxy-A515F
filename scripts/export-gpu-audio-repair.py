#!/usr/bin/env python3
"""Export the host-verified WSL repair, receipts and before/after sources."""
import difflib
import hashlib
import json
from pathlib import Path
import shutil

PROJECT = Path(__file__).resolve().parents[1]
WSL = Path('//wsl.localhost/A51-KernelBuilder/opt/a51-hakios')
WORK = WSL / 'build-repair/gpu-audio-20261124'
UP = WSL / 'upstream-a51/hakios'
IMAGE = 'A51-HakiOS-full-quality-gpu-audio-fixed-v2-boot.img'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest = json.loads((WORK / 'manifest.json').read_text())
    assert manifest['host_package_verified'] and not manifest['device_boot_verified']
    qemu = sorted(WORK.glob('qemu-*/result.json'))
    assert qemu and json.loads(qemu[-1].read_text())['passed']
    packet = PROJECT / 'evidence/build-repair/gpu-audio-20261124-fixed-v2'
    packet.mkdir(exist_ok=False)
    shutil.copytree(WORK / 'before', packet / 'before')
    for file in WORK.iterdir():
        if file.is_file() and file.suffix in ['.json', '.txt', '.patch', '.head', '.status', '.log', '.c']:
            shutil.copy2(file, packet / file.name)
    for folder in [WORK / 'qemu', *WORK.glob('qemu-*')]:
        if folder.is_dir():
            dest = packet / folder.name
            dest.mkdir()
            for file in folder.iterdir():
                if file.is_file() and file.suffix in ['.json', '.log', '.c', '.sh']:
                    shutil.copy2(file, dest / file.name)
    for name in ['gpu', 'audio']:
        file = UP / f'devices/a51/drivers/{name}/hakios.a51{name}.c'
        dest = packet / 'after/devices/a51/drivers' / name / file.name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(file, dest)
    old = (PROJECT / 'restored_speaker_hakios.a51audio.c').read_text()
    latest = (UP / 'devices/a51/drivers/audio/hakios.a51audio.c').read_text()
    (packet / 'audio-included-vs-restored.patch').write_text(''.join(difflib.unified_diff(
        old.splitlines(True), latest.splitlines(True), fromfile='restored_speaker_hakios.a51audio.c',
        tofile='included/devices/a51/drivers/audio/hakios.a51audio.c')))
    blob = (WSL / 'experimental/a51-xnu-loader/payload_blob.bin').read_bytes()
    flashboot = (WORK / 'before/userland/flashboot.apfs').read_bytes()
    root = (WORK / 'root.apfs').read_bytes()
    assert blob[0x3870:0x403870] == flashboot, 'Failed payload boot disk mismatch'
    assert root not in blob, 'Reassess missing second disk diagnosis'
    diagnosis = {'failed_blob_contains_exact_existing_flashboot': True,
                 'existing_flashboot_contains_executable_sbin_launchd': True,
                 'failed_blob_contains_latest_root_apfs': False,
                 'stage0_requires_md1': True, 'missing_startup_program_claim': 'corrected; md1 was missing',
                 'stale_ufs_shared_page_in_failed_cmdline': '0xa1553000',
                 'failed_blob_sha256': hashlib.sha256(blob).hexdigest()}
    (packet / 'diagnosis.json').write_text(json.dumps(diagnosis, indent=2) + '\n')
    dest = PROJECT / 'artifacts' / IMAGE
    assert not dest.exists(), 'Preserve an existing image; use a new filename'
    shutil.copy2(WORK / IMAGE, dest)
    assert digest(dest) == manifest['image']['sha256'] and dest.stat().st_size == manifest['image']['size']
    checksum = dest.with_suffix('.img.sha256')
    checksum.write_text(manifest['image']['sha256'] + '  ' + IMAGE + '\n')
    shutil.copy2(WORK / 'manifest.json', dest.with_suffix('.img.manifest.json'))
    pins = {
        'artifacts/A51-HakiOS-audio-boot.img': 'd061a034c7e683a486b8fb6e5997d35e628f0237ccea58bc99da0ed990f4673b',
        'artifacts/a51_xnu_loader_audio.bin': 'b96009c9dd7180292fff543a309a38be6a2a0c60c8264bae6c3ee7ebf7ae9f40',
    }
    for name, sha in pins.items():
        assert digest(PROJECT / name) == sha, 'Original changed: ' + name
    baseline = PROJECT.parent / 'everline-ksu/artifacts/A51-PixelOS-Everline-KernelSU-Next-boot.img'
    assert digest(baseline) == 'eb30609a62999e3282ac81e0a5e56411ef12ec1a39c107171bf3e01209c7cb67'
    receipt = {'image_path': str(dest), 'image': manifest['image'], 'packet': str(packet),
               'qemu_result': str(packet / qemu[-1].parent.name / 'result.json'),
               'original_artifact_pins_verified': pins, 'android_baseline_unchanged': True,
               'phone_writes': False}
    (packet / 'export.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt, indent=2))


if __name__ == '__main__':
    main()
