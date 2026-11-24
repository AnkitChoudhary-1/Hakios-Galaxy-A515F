#!/usr/bin/env python3
"""Record requested publication preparation/result without changing phase gates."""
import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path

P = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['prepare', 'result'])
    action = parser.parse_args().action
    log = P / 'docs/IMPLEMENTATION-LOG.md'
    if action == 'prepare':
        with log.open('a', encoding='utf-8') as out:
            out.write('\n\n## REPAIR-004 — Requested source publication preparation (2026-11-24)\n\n'
                'User destination: https://github.com/AnkitChoudhary-1/Hakios-Galaxy-A515F.git. Connector metadata '
                'verified empty public repository and push access. Bulk publication uses native Git; the connector '
                'offers individual file/object operations. A new clone preserves the older hakios-SM-A515F checkout '
                'and all active/Android/backups. Files: scripts/prepare-requested-publication.py, '
                'publish-requested-source.py, record-requested-publication.py, pin-audio-references.py and '
                'publication/requested-templates/{README,AGENTS,.gitignore,docs/PUBLIC-STATUS,PUBLIC-BUILD,PUBLICATION}. '
                'Purpose: publish current common/A51 source, Iris native/web source, authored research/build tools, '
                'native cumulative XNU patch, earlier ports/patches, comprehensive docs, licenses and pinned manifests; '
                'exclude generated/proprietary/private inputs. Export records original/transformed hashes and '
                'executable modes; staged Git bytes are checked before a normal main push.\n\n'
                'Failures/corrections: first export in publication/Hakios-Galaxy-A515F failed a credential-URL pattern '
                'on upstream ci/github-check.yml. Strict inspection confirmed an x-access-token URL containing only '
                'a shell-variable placeholder, no literal credential. The scanner now permits only that variable '
                'form while retaining literal-token/password detection. The failed checkout/run is preserved; '
                'publication/Hakios-Galaxy-A515F-source is a fresh clone for the corrected export. A diagnostic '
                'PowerShell command failed parsing its literal variable expression; corrected single shell quoting '
                'avoids interpolation. Source files in active upstream were not changed by publication.\n\n'
                'Reference/document correction: scripts/pin-audio-references.py replayed exact-commit LineageOS '
                'downloads and verified prior bytes; provenance records SHA256 for abox.h and abox_rdma.c. '
                'An initial direct download was followed by the ledgered run.py replay. The old active '
                'docs/a51_audio_bringup.md was backed up, its hardware-verified status qualified as a historical '
                'source audit, and a v2/v3 evidence-limit note prepended. Audio source/build bytes were unchanged.\n\n'
                'Verification/limits: export parses Python, scans text/JSON/device identifiers and credential '
                'patterns, pins dependency commits and every published file. Native XNU patch is cumulative '
                'against its pristine pinned commit; runtime/SDK/firmware/build images/private evidence remain '
                'local, so the public source alone cannot reproduce device execution. V3 audio/Iris validation '
                'is pending and no phase gate changes. Rollback: these are separate publication checkouts and '
                'new source commits; active work and backups remain intact. No force push or device operation '
                'is part of publication. Git core.autocrlf=false/core.filemode=false apply only to the new clone, '
                'with executable modes explicitly retained in its index.\n')
        print('Publication preparation and provenance corrections recorded')
        return
    packet = P / 'evidence/publication/requested-20261124'
    receipt = json.loads((packet / 'push.json').read_text())
    assert receipt['remote_head_verified']
    state_path = P / 'state.json'
    state = json.loads(state_path.read_text())
    before = dict(state)
    state['source_publication_20261124'] = {'repository': receipt['repository'], 'branch': receipt['branch'],
        'commit': receipt['commit'], 'tree': receipt['tree'], 'files': receipt['files'], 'remote_head_verified': True,
        'packet': packet.relative_to(P).as_posix(), 'phone_operations': False, 'phase_gates_changed': False}
    state['active_task'] = 'V3 audio/Iris repair flashed and source published; user v3 screen/audio/Iris acceptance pending'
    state['next_action'] = 'Collect v3 home-screen, speaker media playback and Iris icon/launch observations; preserve evidence and phase gates.'
    for key in before:
        if key not in {'active_task', 'next_action'}:
            assert state[key] == before[key]
    state_path.write_text(json.dumps(state, indent=2) + '\n')
    with log.open('a', encoding='utf-8') as out:
        out.write('\n\n### Requested publication result\n\n'
            'Published main commit `' + receipt['commit'] + '` to the requested repository; remote main matched '
            'independently. Git tree `' + receipt['tree'] + '`, ' + str(receipt['files']) + ' files. '
            'Staged bytes matched the export manifest and identifier/credential/JSON scan passed before push. '
            'Exact export, staging and push receipts remain under evidence/publication/requested-20261124. '
            'No firmware/device operation or phase change occurred. V3 screen/audio/Iris acceptance remains '
            'pending. This result records the first publication; a follow-up documentation commit may record '
            'the receipt without changing source/build bytes.\n')
    record = {'recorded_utc': dt.datetime.now(dt.timezone.utc).isoformat(), 'receipt': receipt,
              'state_sha256': hashlib.sha256(state_path.read_bytes()).hexdigest(), 'phase_gates_unchanged': True}
    (packet / 'documentation-result.json').write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps(receipt, indent=2))


if __name__ == '__main__':
    main()
