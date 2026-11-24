#!/usr/bin/env python3
"""Review the frozen first Antigravity handoff in private WSL staging only.

Run through scripts/run.py. Never edits Antigravity, main platform sources or
upstream checkouts; never performs a device operation or marks a physical gate.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
from phase4_support import PROJECT, command, index_packet, new_packet, pin, require, write_json

SNAPSHOT = 'parallel/snapshots/20261117T013929281709Z-antigravity-first-handoff'
MANIFEST_SHA256 = '024b3c2add18375efca9067684054d789844439b7b005090df359aa5e8a1322a'
PORT = Path('/opt/a51-hakios/experimental/phase4-port/20261114T150320411427Z')
XNU = PORT / 'xnu-src/xnu-8796.121.2'
ANDROID = Path('/opt/a51-everline/src')
REFERENCES = {
    'xnu': (XNU, [
        'osfmk/arm/machine_routines.h', 'osfmk/arm64/machine_routines.c',
        'osfmk/arm/memory_types.h', 'osfmk/arm/io_map.c', 'osfmk/arm/pmap/pmap.c',
        'osfmk/console/video_console.c']),
    'android': (ANDROID, [
        'arch/arm64/boot/dts/exynos/exynos9610.dts',
        'arch/arm64/boot/dts/samsung/display-lcd_a51_common.dtsi',
        'arch/arm64/boot/dts/samsung/display-lcd_gta4xl_common.dtsi',
        'arch/arm64/boot/dts/samsung/exynos9610-a51xx_common.dtsi',
        'drivers/video/fbdev/exynos/dpu20/cal_9610/regs-decon.h',
        'drivers/video/fbdev/exynos/dpu20/cal_9610/regs-dsim.h',
        'drivers/video/fbdev/exynos/dpu20/cal_9610/regs-dpp.h',
        'drivers/video/fbdev/exynos/dpu20/panels/s6e3fa9_a51_lcd_ctrl.c',
        'drivers/video/fbdev/exynos/dpu20/panels/s6e3fa9_a51_param.h',
        'drivers/video/fbdev/exynos/dpu20/panels/ea8076_a51_lcd_ctrl.c',
        'drivers/video/fbdev/exynos/dpu20/panels/ea8076_a51_param.h',
        'drivers/input/touchscreen/melfas_mss100/melfas_mss100.c',
        'drivers/input/touchscreen/melfas_mss100/melfas_mss100_reg.h',
        'drivers/input/touchscreen/melfas_mss100/melfas_mss100_input.c'])}

def copy_pinned(source, destination, expected=None):
    actual = pin(source)
    if expected is not None:
        require(actual == expected, 'Source pin mismatch: ' + str(source))
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    require(pin(destination) == actual and pin(source) == actual,
            'Source changed during capture: ' + str(source))
    return actual

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--snapshot', default=SNAPSHOT)
    args = parser.parse_args()
    if os.name == 'nt':
        script = '/mnt/c' + str(Path(__file__).resolve()).replace('\\', '/')[2:]
        return subprocess.call(['wsl.exe', '-d', 'A51-KernelBuilder', '--exec',
                                'python3', '-B', script, '--snapshot', args.snapshot])
    require(args.snapshot == SNAPSHOT, 'Review is bound to the first frozen handoff')
    snapshot = PROJECT / args.snapshot
    require(pin(snapshot / 'MANIFEST.json')['sha256'] == MANIFEST_SHA256,
            'Frozen snapshot manifest changed')
    manifest = json.loads((snapshot / 'MANIFEST.json').read_text())
    packet = new_packet('antigravity-first-review', __file__)
    build = Path('/opt/a51-hakios/parallel/main/first-handoff-review') / packet.name
    build.mkdir(parents=True, exist_ok=False)
    result = {'schema_version': 1, 'packet': packet.relative_to(PROJECT).as_posix(),
              'build': str(build), 'snapshot': args.snapshot,
              'snapshot_manifest': pin(snapshot / 'MANIFEST.json'),
              'review_execution_complete': False, 'accepted_for_main': False,
              'device_operations': False, 'phase_4_gate_passed': False,
              'sources': {}, 'references': {}, 'suites': {}, 'cpp': {}, 'patches': {}}
    records = []
    try:
        copy_pinned(snapshot / 'MANIFEST.json', packet / 'snapshot-manifest.json')
        for rel, expected in manifest['antigravity_files'].items():
            copy_pinned(snapshot / 'antigravity' / rel, packet / 'handoff' / rel, expected)
            if rel.startswith('work/') and '__pycache__' not in rel:
                copy_pinned(snapshot / 'antigravity' / rel, build / 'candidate' / rel[5:], expected)
                result['sources'][rel[5:]] = expected
        for rel, expected in manifest['base_files'].items():
            require(pin(PROJECT / rel) == expected, 'Main base drift: ' + rel)
            copy_pinned(snapshot / 'main-base' / rel, build / 'base' / rel, expected)
            copy_pinned(snapshot / 'main-base' / rel, packet / 'base' / rel, expected)
        for group, (root, paths) in REFERENCES.items():
            result['references'][group] = {'root': str(root), 'files': {}, 'missing': []}
            for rel in paths:
                source = root / rel
                if not source.is_file():
                    result['references'][group]['missing'].append(rel)
                    continue
                result['references'][group]['files'][rel] = copy_pinned(
                    source, packet / 'references' / group / rel)
        command(packet, records, 'clang-version', ['clang-18', '--version'])
        command(packet, records, 'clang-cpp-version', ['clang++-18', '--version'])
        candidate = build / 'candidate'
        includes = candidate / 'prototype/phase4-platform'
        (build / 'outputs').mkdir()
        for suite in ('display', 'input', 'reporting', 'ufs'):
            binary = build / 'outputs' / (suite + '_model')
            compile_proc = command(packet, records, suite + '-compile', [
                'clang-18', '-std=c11', '-O1', '-g', '-Wall', '-Wextra', '-Werror',
                '-fsanitize=address,undefined', '-fno-sanitize-recover=all',
                '-fno-omit-frame-pointer', '-I', str(includes),
                str(includes / 'tests' / (suite + '_model.c')), '-o', str(binary)],
                timeout=60, check=False)
            entry = {'compiled': compile_proc.returncode == 0, 'passed': False}
            if entry['compiled']:
                proc = command(packet, records, suite + '-execute', [str(binary)], timeout=30,
                    env=dict(os.environ, ASAN_OPTIONS='detect_leaks=1:abort_on_error=1',
                             UBSAN_OPTIONS='halt_on_error=1'), check=False)
                entry['exit_code'] = proc.returncode
                entry['binary'] = copy_pinned(binary, packet / 'binaries' / binary.name)
                if proc.returncode == 0:
                    observed = json.loads(proc.stdout)
                    require(observed['suite'] == suite and observed['passed'] is True,
                            'Invalid model result: ' + suite)
                    entry.update(observed)
            result['suites'][suite] = entry
        for rel in ('drivers/display/ExynosDECON.cpp', 'drivers/display/ExynosDSIM.cpp',
                    'drivers/input/ExynosKeyDriver.cpp', 'drivers/input/MelfasTouchDriver.cpp'):
            output = build / 'outputs' / (Path(rel).stem + '.o')
            proc = command(packet, records, Path(rel).stem + '-cpp-compile', [
                'clang++-18', '-std=c++17', '-Wall', '-Wextra', '-Werror',
                '-ffreestanding', '-fno-exceptions', '-fno-rtti',
                '-c', str(candidate / rel), '-o', str(output)], timeout=60, check=False)
            result['cpp'][rel] = {'compiled': proc.returncode == 0, 'exit_code': proc.returncode}
            if proc.returncode == 0:
                result['cpp'][rel]['object'] = copy_pinned(output, packet / 'objects' / output.name)
        for filename in ('unified_antigravity_phase4.patch', 'phase4_display_input.patch'):
            patch = packet / 'handoff/patches' / filename
            staging = build / ('patch-stage-' + Path(filename).stem)
            shutil.copytree(build / 'base', staging)
            stat = command(packet, records, Path(filename).stem + '-stat',
                           ['git', 'apply', '--stat', str(patch)], cwd=staging, check=False)
            check = command(packet, records, Path(filename).stem + '-check',
                            ['git', 'apply', '--check', str(patch)], cwd=staging, check=False)
            item = {'pin': pin(patch), 'stat_exit_code': stat.returncode,
                    'check_exit_code': check.returncode, 'matches_candidate': False}
            if check.returncode == 0:
                applied = command(packet, records, Path(filename).stem + '-apply-private',
                                  ['git', 'apply', str(patch)], cwd=staging, check=False)
                item['private_apply_exit_code'] = applied.returncode
                mismatches = [rel for rel, expected in result['sources'].items()
                              if not (staging / rel).is_file() or pin(staging / rel) != expected]
                item['mismatches'] = mismatches
                item['matches_candidate'] = applied.returncode == 0 and not mismatches
            result['patches'][filename] = item
        for rel, expected in manifest['antigravity_files'].items():
            require(pin(snapshot / 'antigravity' / rel) == expected,
                    'Frozen handoff changed after tests: ' + rel)
        for rel, expected in manifest['base_files'].items():
            require(pin(PROJECT / rel) == expected, 'Main base changed after tests: ' + rel)
        result['native_claims_reproduced'] = all(e['passed'] for e in result['suites'].values())
        result['total_cases'] = sum(e.get('cases', 0) for e in result['suites'].values())
        result['total_checks'] = sum(e.get('checks', 0) for e in result['suites'].values())
        result['review_execution_complete'] = True
    except Exception as exc:
        result['error'] = str(exc)
    write_json(packet / 'result.json', result)
    index_packet(packet)
    print(json.dumps(result, indent=2), flush=True)
    return 0 if result['review_execution_complete'] else 1

if __name__ == '__main__':
    raise SystemExit(main())
