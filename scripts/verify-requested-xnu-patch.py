#!/usr/bin/env python3
"""Apply-check the publication patch on isolated pristine source (WSL)."""
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile

P = Path(__file__).resolve().parents[1]
D = P / 'publication/Hakios-Galaxy-A515F-source'
NATIVE = Path('/opt/a51-hakios/upstream-a51/hakios/xnu-src/xnu-8796.121.2')


def pin(raw):
    return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def main():
    manifest = json.loads((D / 'manifests/current-sources.json').read_text())
    commit = next(x['commit'] for x in manifest['dependencies']
                  if x['path'] == 'xnu-src/xnu-8796.121.2')
    patch = D / 'patches/current-xnu.patch'
    with tempfile.TemporaryDirectory(prefix='publication-xnu-check-', dir='/opt/a51-hakios') as work:
        root = Path(work)
        for record in manifest['native_patch_files']:
            name = record['path']
            assert not Path(name).is_absolute() and '..' not in Path(name).parts
            proc = subprocess.run(['git', '-C', str(NATIVE), 'show', commit + ':' + name],
                                  capture_output=True)
            raw = proc.stdout if proc.returncode == 0 else b''
            assert pin(raw) == record['before'], 'Pristine drift: ' + name
            if proc.returncode == 0:
                target = root / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(raw)
        for action in ['--check', None]:
            args = ['git', 'apply'] + ([action] if action else []) + [str(patch)]
            proc = subprocess.run(args, cwd=root, capture_output=True)
            print(json.dumps({'command': args, 'exit': proc.returncode,
                              'output': (proc.stdout + proc.stderr).decode(errors='replace')[:5000]}), flush=True)
            assert proc.returncode == 0, 'Patch did not apply'
        for record in manifest['native_patch_files']:
            target = root / record['path']
            raw = target.read_bytes() if target.is_file() else b''
            assert pin(raw) == record['after'], 'Applied source differs: ' + record['path']
    result = {'passed': True, 'pristine_commit': commit, 'patch': pin(patch.read_bytes()),
              'files_verified': len(manifest['native_patch_files']),
              'check_and_apply_passed': True, 'exact_after_hashes_verified': True,
              'active_source_changed': False, 'phone_operations': False}
    (P / 'evidence/publication/requested-20261124/xnu-patch-verification.json').write_text(
        json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
