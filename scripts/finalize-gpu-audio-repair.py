#!/usr/bin/env python3
"""Record supplemental repair state or verify its export/documentation offline.

Use through scripts/run.py with action record, then verify. Never contacts ADB.
"""
import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
import re

PROJECT = Path(__file__).resolve().parents[1]
PACKET = PROJECT / 'evidence/build-repair/gpu-audio-20261124-fixed-v2'
CHECK = PROJECT / 'evidence/build-repair/gpu-audio-20261124-documentation'
BEFORE = PROJECT / 'evidence/build-repair/20261124T022342Z/before/workspace/state.json'
IMAGE = 'A51-HakiOS-full-quality-gpu-audio-fixed-v2-boot.img'
SHA = '9f7fd881143c1ba81a28359ead8000b0d9a953690e67ebac3e0a603dd806ec30'
WSL = Path('//wsl.localhost/A51-KernelBuilder/opt/a51-hakios')
ALLOWED = {'updated_date_local', 'active_task', 'next_action', 'build_repair_20261124'}


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def pin(path):
    data = path.read_bytes()
    return {'size': len(data), 'sha256': hashlib.sha256(data).hexdigest()}


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')


def record():
    path = PROJECT / 'state.json'
    state = read(path)
    assert 'build_repair_20261124' not in state, 'Already recorded; preserve existing selection'
    CHECK.mkdir(exist_ok=False)
    (CHECK / 'state-before.json').write_bytes(path.read_bytes())
    manifest = read(PACKET / 'manifest.json')
    assert manifest['image'] == {'size': 29700096, 'sha256': SHA}
    prior_task = state['active_task']
    state['updated_date_local'] = '2026-11-24'
    state['active_task'] = ('User-requested full-quality GPU/audio boot build repair: '
                            'v2 exported and host/QEMU verified; phone boot/GPU/audio unverified')
    state['next_action'] = ('Deliver the pinned v2 repair and documentation; physical validation '
                            'requires separately authorized device/logging/rollback work. '
                            'Retain the historical Phase 4 recovery/export persistence blocker.')
    state['build_repair_20261124'] = {
        'status': 'host_package_and_generic_qemu_verified_device_pending',
        'guide': 'docs/GPU-AUDIO-BUILD-REPAIR.md',
        'artifact': 'artifacts/' + IMAGE,
        'image': manifest['image'],
        'manifest': 'evidence/build-repair/gpu-audio-20261124-fixed-v2/manifest.json',
        'packet': 'evidence/build-repair/gpu-audio-20261124-fixed-v2',
        'documentation_check': 'evidence/build-repair/gpu-audio-20261124-documentation/result.json',
        'gpu': manifest['gpu'], 'audio': manifest['audio'],
        'kernel': manifest['entries']['kernel'],
        'gpu_fix': 'physically_contiguous_allocation_and_guard_failure_cleanup',
        'boot_fix': 'UEFI_live_shared_page_and_both_md0_flashboot_md1_root_disks',
        'latest_audio_source_preserved': True,
        'iris_original_files_preserved': True,
        'host_package_verified': True, 'allocator_model_cases': 4,
        'qemu_kernel_loader_pid1_uid0_verified': True,
        'qemu_final_md0_md1_route_verified': False,
        'device_boot_verified': False, 'home_screen_verified': False,
        'gpu_hardware_execution_verified': False, 'audible_audio_verified': False,
        'phone_queries_this_repair': True, 'phone_writes_this_repair': False,
        'phone_reboots_this_repair': False, 'phase_gates_changed': False,
        'prior_full_quality_image_located': False,
        'superseded_image': 'artifacts/A51-HakiOS-full-quality-gpu-audio-fixed-boot.img',
        'prior_active_task': prior_task,
        'historical_storage_trial_preserved': True,
    }
    write(path, state)
    print(json.dumps(state['build_repair_20261124'], indent=2))


def verify():
    result = {'started_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
              'passed': False, 'device_operations': False}
    try:
        state = read(PROJECT / 'state.json')
        original = read(BEFORE)
        assert set(state) - set(original) == {'build_repair_20261124'}
        assert not set(original) - set(state)
        for key, value in original.items():
            if key not in ALLOWED:
                assert state[key] == value, 'Historical state changed: ' + key
        assert state['phase_4_status'] == 'in_progress'
        assert state['phase_4_device_gate_passed'] is False
        selected = state['build_repair_20261124']
        for key in ['device_boot_verified', 'home_screen_verified',
                    'gpu_hardware_execution_verified', 'audible_audio_verified',
                    'phone_writes_this_repair', 'phone_reboots_this_repair', 'phase_gates_changed']:
            assert selected[key] is False, key
        image = PROJECT / 'artifacts' / IMAGE
        manifest = read(PACKET / 'manifest.json')
        assert pin(image) == manifest['image'] == selected['image'] == {'size': 29700096, 'sha256': SHA}
        assert read(image.with_suffix('.img.manifest.json')) == manifest
        assert image.with_suffix('.img.sha256').read_text().strip() == SHA + '  ' + IMAGE
        assert read(PACKET / 'export.json')['image'] == manifest['image']
        for name, expected in read(PACKET / 'inputs.json').items():
            assert pin(PACKET / 'before' / name) == expected, 'Before pin: ' + name
        up = WSL / 'upstream-a51/hakios'
        for name in ['gpu', 'audio']:
            relative = f'devices/a51/drivers/{name}/hakios.a51{name}.c'
            expected = manifest[name]
            assert pin(PACKET / 'after' / relative) == expected
            assert pin(up / relative) == expected
            assert pin(up / f'xnu-src/xnu-8796.121.2/bsd/dev/hakios.a51{name}.c') == expected
        assert pin(PACKET / 'before/devices/a51/drivers/audio/hakios.a51audio.c') == manifest['audio']
        assert pin(WSL / 'build-repair/gpu-audio-20261124/hakios-kernel') == manifest['entries']['kernel']
        assert pin(up / 'Mu-Silicium/Build/a51Pkg/RELEASE_CLANGPDB/FV/SILICIUM_UEFI.fd') == manifest['firmware']
        export = read(PACKET / 'export.json')
        for name, sha in export['original_artifact_pins_verified'].items():
            assert pin(PROJECT / name)['sha256'] == sha
        baseline = PROJECT.parent / 'everline-ksu/artifacts/A51-PixelOS-Everline-KernelSU-Next-boot.img'
        assert pin(baseline)['sha256'] == 'eb30609a62999e3282ac81e0a5e56411ef12ec1a39c107171bf3e01209c7cb67'
        qdir = PACKET / 'qemu-20261124T023853Z'
        qemu = read(qdir / 'result.json')
        assert qemu['passed'] and qemu['process_1_uid_0_verified']
        assert qemu['kernel'] == manifest['entries']['kernel']
        assert qemu['loader'] == manifest['entries']['loader.efi']
        assert pin(qdir / 'serial.log') == qemu['serial']
        assert pin(qdir / 'hello.c') == qemu['hello_source']
        allocator = read(PACKET / 'allocator-test.json')
        assert allocator['passed'] and allocator['cases'] == 4
        assert allocator['source'] == manifest['gpu']
        assert pin(PACKET / 'gpu-allocator-test.c') == allocator['harness']
        links = 0
        for name in ['GPU-AUDIO-BUILD-REPAIR.md', 'STATE.md', 'INDEX.md']:
            file = PROJECT / 'docs' / name
            content = file.read_text(encoding='utf-8')
            if name == 'STATE.md':
                content = content.split('## Retained 19 November checkpoint')[0]
            if name == 'INDEX.md':
                content = content.split('## Phase 4 delivery review')[0]
            for target in re.findall(r'\]\(([^)]+)\)', content):
                assert (file.parent / target).exists() or (file.parent / target).resolve() == (CHECK / 'result.json').resolve(), target
                links += 1
        ledger = {str(p.relative_to(PROJECT)).replace('\\', '/'): pin(p)
                  for p in PACKET.rglob('*') if p.is_file()}
        for name in ['state.json', 'docs/GPU-AUDIO-BUILD-REPAIR.md', 'docs/STATE.md',
                     'docs/INDEX.md', 'docs/IMPLEMENTATION-LOG.md',
                     'scripts/audit-gpu-audio-build.py', 'scripts/repair-gpu-audio-build.py',
                     'scripts/export-gpu-audio-repair.py', 'scripts/finalize-gpu-audio-repair.py']:
            ledger[name] = pin(PROJECT / name)
        ledger['artifacts/' + IMAGE] = pin(image)
        write(CHECK / 'selected-files.json', ledger)
        result.update(passed=True, image=manifest['image'], phase_gates_unchanged=True,
                      historical_state_preserved=True, evidence_files_pinned=len(ledger),
                      local_links_checked=links, audio_source_bytes_preserved=True,
                      source_and_xnu_copies_match=True, original_images_unchanged=True,
                      qemu_result_and_serial_replayed=True,
                      selected_files_manifest=pin(CHECK / 'selected-files.json'))
    except Exception as exc:
        result['error'] = str(exc)
        raise
    finally:
        result['finished_utc'] = dt.datetime.now(dt.timezone.utc).isoformat()
        write(CHECK / ('result.json' if result['passed'] else 'failed-' + dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') + '.json'), result)
        print(json.dumps(result, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['record', 'verify'])
    {'record': record, 'verify': verify}[parser.parse_args().action]()
