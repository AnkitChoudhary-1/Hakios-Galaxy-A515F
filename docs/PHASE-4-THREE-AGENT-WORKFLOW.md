# Current Phase 4 three-agent delivery review

Prepared 17 November 2026; current independent dispositions published the same day. Phase 4 remains **IN PROGRESS** and its physical peripheral gate **UNPASSED**. The preparation's zero-agent/zero-device record is historical. This review started no implementation agents, full XNU builds, QEMU executions or phone operations.

| Delivery | Worker declaration | Independent disposition | Next action |
| --- | --- | --- | --- |
| Storage `rev-20261117-s1-final` | ready_for_review | Unreviewed | Codex capture/review |
| Display `phase4-round-d1-candidate-20261117` | ready_for_review | changes_required | [Agent 2 correction assignment](PUBLICATION.md) |
| Input `Revision 8 (P4-I1)` | ready_for_review | Unreviewed | Codex capture/review |

Read the [display review](PHASE-4-DISPLAY-AGENT2-REVIEW.md) and [current registry](PUBLICATION.md). The independently reproduced native suites pass 237 cases / 341,090 checks; 27 targeted defect observations and 11 controls prevent merge acceptance. No combined or physical verification follows from these counts. Baseline/ownership JSON and the original planning manifest retain preparation-time status; the registry selects current deliveries. Agent 2 uses the correction assignment together with its original prompt below.

Use the complete copy-ready prompt for each of three separate agent contexts:

| Agent | Task | Prompt |
| --- | --- | --- |
| 1 | UFS/read-only storage and recovery persistence | [Agent 1](PUBLICATION.md) |
| 2 | Framebuffer/display and brightness | [Agent 2](PUBLICATION.md) |
| 3 | Melfas touch, power/volume keys and input events | [Agent 3](PUBLICATION.md) |

Codex owns independent review, shared ABI/platform integration, central documentation/state, serialized full builds and later physical tests. Each implementation agent edits only its private assigned sources and submits owned patches separately from shared proposals.

The [remaining-work assessment](PUBLICATION.md) distinguishes retained host progress from software gaps and unpassed physical gates. A reliable remaining percentage is unavailable. The saved display **Sixth Delivery** and input **Revision 7** remain pinned preparation seeds. Current delivery dispositions are in the table above; use the frozen reviewed display revision for corrections and capture storage/input before accepting their claims. Previous rounds, reviewed fifth/rev6 evidence and failed freeze attempts remain preserved.

The selected [MANIFEST](PUBLICATION.md) has SHA-256 `b3b772e5acfd0dffd926a0c6913892e655795d8ef3f1f76473b28f9c6edcb260`. Per-file pins and private seed/logging/output paths are in [BASELINE.json](PUBLICATION.md). The snapshot is a set of source slices, not a full dependency checkout. Main/adapted source checks matched the retained checkpoint at preparation.

Read these durable guides in order:

1. [Workflow and adding agents](PUBLICATION.md): file ownership, independent work, shared interface dependencies, private command logging, review states and scaling rules.
2. [Handoff/documentation requirements](PUBLICATION.md): architecture/APIs, hardware provenance, resource/IRQ/lock lifetimes, failure history, source/binary correspondence, rebuild/replay, rollback and next-agent guidance.
3. [Codex merge and physical acceptance](PUBLICATION.md): immutable submissions, patch reconstruction, combined checks, nonce-attributed observations/logs and verified return.

Planning evidence is retained at [REPORT.json](PUBLICATION.md). Commands go through `scripts/run.py`; [phase4-three-agent-plan.py](../scripts/phase4-three-agent-plan.py) supports `verify-inputs` for fixed worker seeds and `verify` for the published plan's point-in-time audit. Private commands use each worker's exact logger copy, as shown in its prompt. Later source or documentation changes must receive new evidence rather than reusing a passing preparation audit.

This dispatch supersedes the prior four-worker brief for new assignments. The [previous brief](PUBLICATION.md) and `phase_4_parallel_workflow` state record retain their historical scope. Keep both disabled legacy device-gate entry guards; do not run the obsolete resume audit. Historical phone-query/write fields remain preserved, and this planning record has zero device operations.
