#!/usr/bin/env python3
"""Publish verified r1 source with a normal follow-up commit to the requested repo."""
import importlib.util
import json
import hashlib
from pathlib import Path

P = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('checked_publish', P / 'scripts/publish-requested-source.py')
b = importlib.util.module_from_spec(spec)
spec.loader.exec_module(b)
b.PACKET = P / 'evidence/publication/touch-audio-20261124-r1'
original_git = b.git


def git(*args, **kwargs):
    if args[:2] == ('commit', '-m'):
        args = ('commit', '-m', 'Correct A51 touch scaling and rebuild checked audio with Iris diagnostics')
    return original_git(*args, **kwargs)


def record():
    receipt = json.loads((b.PACKET / 'documentation-push.json').read_text())
    assert receipt['remote_head_verified']
    path = P / 'state.json'
    state = json.loads(path.read_text())
    gates = {k: v for k, v in state.items() if 'phase' in k}
    publication = state['source_publication_20261124']
    publication.update(latest_commit=receipt['commit'], latest_tree=receipt['tree'],
        latest_manifest_sha256=receipt['source_manifest_sha256'],
        latest_packet=b.PACKET.relative_to(P).as_posix(),
        files=receipt['files'], remote_head_verified=True,
        github_connector_commit_verified=False)
    state['touch_audio_repair_20261124_r1']['source_publication_commit'] = receipt['commit']
    installed = state['touch_audio_repair_20261124_r1'].get('device_installation', {}).get('boot_write_verified', False)
    if installed:
        state['active_task'] = 'Touch/audio r1 flashed with verified readback and current source published; physical boot/touch/speaker/Iris acceptance pending'
        state['next_action'] = 'Confirm physical home screen, accurate taps, speaker playback and Iris icon/launch; recover diagnostics from TWRP if failures persist'
    else:
        state['active_task'] = 'Touch/audio r1 host image verified and current source published; authorized installation and hardware acceptance pending'
        state['next_action'] = 'Connect SM-A515F in TWRP and flash checked r1 with full backup/readback; verify physical touch, speaker audio and Iris'
    assert gates == {k: v for k, v in state.items() if 'phase' in k}
    path.write_text(json.dumps(state, indent=2) + '\n', encoding='utf-8')
    note = ('\n\n### r1 source publication result\n\nCurrent source and repair documentation '
        'were pushed normally to the requested main branch at `' + receipt['commit'] +
        '`, tree `' + receipt['tree'] + '`, ' + str(receipt['files']) +
        ' reviewed files. Remote main independently matched. Staged bytes, identifier/'
        'credential/JSON scan and all269 pristine XNU patch result hashes passed. '
        'Receipt: evidence/publication/touch-audio-20261124-r1/documentation-push.json. '
        'This publication performed no device operation. ' +
        ('The separate authorized r1 installation and full readback passed; ' if installed else
         'R1 installation is pending; ') + 'physical touch/audio/Iris acceptance '
        'and diagnostic persistence remain unverified, with all phase gates unchanged.\n')
    with (P / 'docs/IMPLEMENTATION-LOG.md').open('a', encoding='utf-8') as out:
        out.write(note)
    (b.PACKET / 'documentation-result.json').write_text(json.dumps({
        'receipt': receipt, 'phase_gates_unchanged': True,
        'state_sha256': hashlib.sha256(path.read_bytes()).hexdigest()}, indent=2) + '\n')


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['validate', 'publish'])
    args = parser.parse_args()
    b.git = git
    if args.action == 'validate':
        b.validate()
    else:
        b.publish(True)
        record()
