# Public A51 source publication

On 15 November 2026 the user explicitly authorized pushing the current work to
`https://github.com/AnkitChoudhary-1/hakios-SM-A515F.git`.

The export is prepared in `publication/hakios-SM-A515F`, separate from active
sources and evidence. `scripts/prepare-publication.py` captures text-only
authored sources, comprehensive documentation, selected source/build pins,
cumulative Phase 3/4 common/XNU patches, retained license texts and a derived
Phase 3 device summary. Templates live in `publication/templates/`.

Full raw evidence/runs, device backups, firmware, Apple runtime/SDK files,
generated binaries/images, unrelated Android work and personal device
identifiers are excluded. Original evidence and sources are preserved locally.
The export's manifest identifies original and sanitized hashes; publication
summaries do not replace original evidence or promote Phase 4's device gate.

Validation uses `scripts/public-smoke.py` from the exported tree and
`scripts/validate-publication.py` for patch application and exact result hashes
against temporary copies of the pinned prepared baseline, JSON/text scans,
staged-file review and post-push remote verification. Consequential commands
run through `scripts/run.py`. Git publishing does not query/write/reboot the
phone or create an upstream HakiOS PR.

Rollback: the publication clone is isolated; discard only its unpublished
files to redo export. Preserve local original work and captured run/export
records. Published corrections should use normal follow-up commits, preserving
history; never force-push to conceal a prior result.


## Published snapshot — 15 November 2026

Successfully published 370 reviewed files to [hakios-SM-A515F](https://github.com/AnkitChoudhary-1/hakios-SM-A515F) on `main`.
Commit: [`e793af437f39cd56ec55bad5a3992ae0f8ebcb35`](https://github.com/AnkitChoudhary-1/hakios-SM-A515F/commit/e793af437f39cd56ec55bad5a3992ae0f8ebcb35).

The staged audit `20261115T154832492438Z-publication-staged-audit` passed for every actual Git blob against the finalized manifest. The commit and normal push passed in `20261115T155200598075Z-publication-commit` and `20261115T155210843797Z-publication-push`. Post-push verification `20261115T155301226602Z-publication-remote-verify` confirmed matching local HEAD, origin/main and GitHub refs/heads/main, a clean publication clone, all 370 committed files and the required public status, build, license, patch and validation files.

Portable host and patch validation are recorded in PUB-003 and the public validation directory. The published commit is the reviewed capture; concurrent Phase 4 changes in the active workspace are separate from this snapshot. Phase 4 remains incomplete and its hardware gate remains unpassed. This publication performed no device operations or upstream PR.


## Requested source published — 24 November 2026

Current HakiOS source, audio/Iris v3 changes, UEFI source overlays, build tools and documentation were published to [Hakios-Galaxy-A515F](https://github.com/AnkitChoudhary-1/Hakios-Galaxy-A515F) on main at initial commit `24c2b1b5e1b6d6bea0144fd5380f3b8ffe6053c2`. Native remote main and the GitHub connector independently confirmed the commit. All 1515 staged files matched the reviewed bytes. XNU patch application and all 269 result hashes passed. Publication receipts are under evidence/publication/requested-20261124. This is a source export; binaries and private/proprietary inputs remain local. V3 screen/audio/Iris acceptance remains pending, and no phase gate changed. A follow-up documentation commit records this first-publication receipt.


## Current r1 repair

The current candidate is described in [TOUCH-AUDIO-REPAIR-20261124.md](TOUCH-AUDIO-REPAIR-20261124.md). It uses a separately restored retained v3 root image and new diagnostics helper, rather than the stripped active root. Some current platform/userland sources and job recipes contain later experiments; they were not compiled into the restored v3 root. Use the r1 separate-root recipe for this candidate, rather than the older RC_JOBS recommendation above. The scripts intentionally require local retained inputs and preserve their hashes. Current physical touch/audio/Iris acceptance and diagnostic persistence are unverified. The current cumulative XNU patch supersedes the older v3 patch snapshot; an isolated pristine apply and all resulting hashes are checked before this publication.
