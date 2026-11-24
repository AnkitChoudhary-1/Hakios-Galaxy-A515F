#!/usr/bin/env python3
"""Validate staged source hashes, commit and push to the explicitly requested repo.

Use scripts/run.py. No force push, no token printing, no phone operation.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess

P = Path(__file__).resolve().parents[1]
D = P / 'publication/Hakios-Galaxy-A515F-source'
URL = 'https://github.com/AnkitChoudhary-1/Hakios-Galaxy-A515F.git'
PACKET = P / 'evidence/publication/requested-20261124'


def run(args, binary=False):
    shown = args if len(args) < 20 else args[:6] + ['[remaining arguments retained by source/manifest]']
    print('COMMAND ' + json.dumps(shown), flush=True)
    env = dict(os.environ, GIT_TERMINAL_PROMPT='0', GCM_INTERACTIVE='Never')
    proc = subprocess.run(args, capture_output=True, env=env)
    if not binary:
        print((proc.stdout + proc.stderr).decode('utf-8', errors='replace')[:2500], flush=True)
    if proc.returncode:
        raise RuntimeError('Command exit ' + str(proc.returncode))
    return proc.stdout


def git(*args, binary=False):
    return run(['git', '-C', str(D), *args], binary)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def validate():
    assert git('remote', 'get-url', 'origin').decode().strip() == URL
    manifest = json.loads((D / 'PUBLICATION-MANIFEST.json').read_text())
    for name, record in manifest['files'].items():
        raw = (D / name).read_bytes()
        assert sha(raw) == record['sha256'] and len(raw) == record['bytes'], 'Export drift: ' + name
    spec = importlib.util.spec_from_file_location('helpers', P / 'scripts/prepare-publication.py')
    b = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(b)
    b.SECRET_PATTERNS['credential_url'] = re.compile(r'https?://[^\s/@]+:(?!\$(?:\{[A-Z_]+\}|[A-Z_]+)@)[^\s/@]+@')
    scan = b.scan_tree(D)
    assert scan['passed'], scan['failures']
    git('config', 'core.autocrlf', 'false')
    git('config', 'core.filemode', 'false')
    # Upstream ignore rules intentionally hide device checkouts/configuration.
    # Stage only the reviewed manifest paths, including those ignored sources.
    names_to_stage = sorted(set(manifest['files']) | {'PUBLICATION-MANIFEST.json'})
    proc = subprocess.run(['git', '-C', str(D), 'add', '--force',
                           '--pathspec-from-file=-', '--pathspec-file-nul'],
                          input=('\0'.join(names_to_stage) + '\0').encode(),
                          capture_output=True)
    assert proc.returncode == 0, proc.stderr.decode(errors='replace')
    executables = [name for name, record in manifest['files'].items() if record['mode'] == '100755']
    if executables:
        git('update-index', '--chmod=+x', '--', *executables)
    names = set(git('ls-files', '-z', binary=True).decode().split('\0')) - {''}
    assert names == set(manifest['files']) | {'PUBLICATION-MANIFEST.json'}, 'Unmanifested/missing Git files'
    # Git blobs must equal the exported UTF-8 bytes despite Windows line-ending rules.
    batch = ''.join(':' + name + '\n' for name in sorted(names)).encode()
    proc = subprocess.run(['git', '-C', str(D), 'cat-file', '--batch'], input=batch, capture_output=True, check=True)
    data, pos = proc.stdout, 0
    for name in sorted(names):
        end = data.index(b'\n', pos)
        header = data[pos:end].split()
        assert len(header) == 3 and header[1] == b'blob', name
        size = int(header[2])
        raw = data[end + 1:end + 1 + size]
        assert raw == (D / name).read_bytes(), 'Staged blob differs: ' + name
        pos = end + size + 2
    assert pos == len(data)
    result = {'passed': True, 'files': len(names), 'staged_bytes_verified': True, 'scan': scan,
              'manifest_sha256': sha((D / 'PUBLICATION-MANIFEST.json').read_bytes()), 'device_operations': False}
    (PACKET / 'staging-verification.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))


def publish():
    validate()
    assert not git('ls-remote', '--heads', 'origin').strip(), 'Destination changed; reconcile existing branch before push'
    git('symbolic-ref', 'HEAD', 'refs/heads/main')
    git('commit', '-m', 'Publish A51 HakiOS source and audio/Iris v3 repair')
    commit = git('rev-parse', 'HEAD').decode().strip()
    git('push', '--set-upstream', 'origin', 'main')
    remote = git('ls-remote', 'origin', 'refs/heads/main').decode().split()[0]
    assert commit == remote
    receipt = {'repository': URL, 'branch': 'main', 'commit': commit, 'remote_head_verified': True,
               'tree': git('rev-parse', 'HEAD^{tree}').decode().strip(), 'files': len(git('ls-files', '-z', binary=True).split(b'\0')) - 1,
               'source_manifest_sha256': sha((D / 'PUBLICATION-MANIFEST.json').read_bytes()), 'phone_operations': False}
    (PACKET / 'push.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['validate', 'publish'])
    args = parser.parse_args()
    {'validate': validate, 'publish': publish}[args.action]()
