# Phase 4 completion review — audited 16 November 2026
## Historical audit scope — 16 November

The selected source/build and host verification have advanced since the dated records below. See [PHASE-4-HOST-CHECKPOINT.md](PHASE-4-HOST-CHECKPOINT.md) for the current genuine-read implementation, explicit pending reporting, exact host evidence and integration limits. Phase 4 remains **IN PROGRESS**, with its device gate **UNPASSED**. No phone operation occurred in this continuation; current screen/connection are unknown. Device commands below are retained procedures outside this host-only assignment.

**IN PROGRESS — device gate UNPASSED.** The earlier COMPLETE decision exceeds its evidence and is superseded. The original completion documents, source and state bytes are retained in this audit's `before/` directory; all execution packets remain unchanged.

The roadmap requires visible display at correct dimensions, physical touch coordinates, repeatable brightness and key behavior, known-image reads, larger-image loading and a read-only driver. Three automatic PASS reports do not supply the missing physical tests.

Original packet: `evidence/phase-4/silicon-execution/20261116T091954739903Z/`. Offline audit: `evidence/phase-4/completion-audit/20261116T101146104534Z/result.json`.

| Cycle | Nonce | 4 KiB hash | 64 KiB aggregate hash | Three timer samples | Phase 4 |
|---|---|---|---|---|---|
| 1 | `f1e24fd979d240948f26c73417575cfd` | matching | matching, chunked | replayed | unpassed |
| 2 | `13898851d28d4a20a3384ef4cdb486a0` | matching | matching, chunked | replayed | unpassed |
| 3 | `e33fd6d2574f48859d4710c758b225de` | matching | matching, chunked | replayed | unpassed |

Each candidate's full SHA-256 and length were checked against its per-cycle result and summary. Its first 4 KiB and 64 KiB were hashed independently and compared with complete normalized transfer records. Recovered copies are deduplicated; 852 extracted lines per cycle are not 852 independent hardware observations. Exact nonce records and timer indices, durations and increasing IRQ counters were replayed.

At audit capture, `prototype/phase4-platform/hello.c` printed constant DISPLAY/DSIM/TOUCH/KEYS_VERIFIED labels inside the snapshot-success branch, despite its own comment saying that snapshots do not prove visible output or input events. `HAKIOS_PHASE4_PASS` hard-codes display/touch/keys to 1. The legacy parser accepts these through substring matching and omits brightness. None qualifies a physical peripheral gate.

The audited `hakios.a51.c` submitted READ(10) with one block sixteen times, copies each result to staging and then rewrites the first report's block count, byte count and elapsed time as an aggregate. It does not submit one 64 KiB READ(10). The matching aggregate hash is useful chunked-loading evidence, but the genuine transfer's earlier system bus fatal error and repaired candidate's failed attributable-log capture are unresolved. Chunking does not establish the DMA root cause or verify that repair. The original roadmap does not prescribe a single 64 KiB command; that command is the outstanding repair test, while physical brightness/input alone already prevent roadmap completion.

Each cycle reports recovery reconnection and matching baseline readback. The packet lacks original staging, write/readback, remote-exit, Android-completion and final partition-hash command outputs, so this review preserves those reports without upgrading them to an independent rollback replay. The older [independent restoration](BASELINE-RESTORATION-20261116.md) remains verified. Recovery console and Android early_probe logs were recovered; the committed binary pmsg envelope has not been verified by these text captures.

The kernel and hello hashes available at audit capture were compared with the selected build manifest where available; the audit result retains the comparison. No matching `run.py` metadata was found among the metadata present at audit capture. That discovery is retained separately, so a later disabled-gate guard test cannot change historical replay. Candidate-to-kernel-segment and historical source/build correspondence were not established by this review. Historical source findings describe the captured template and available WSL source, while hardware observations are limited to the retained nonce-bound logs.

The legacy `phase4-device-gate.py` entry points are disabled before device actions. Its original code remains in the audit snapshot. No driver, kernel binary, phone partition or runtime was changed during this review. At the audit date, the next action was to replace constant PASS production and misleading aggregate protocol telemetry, establish physical display/brightness/input acceptance, and test the genuine read with matched source/build and reliable logs.

Replay the historical audit with current document reconciliation through `scripts/run.py`. The checkpoint calls `verify(check_current=False)` against the immutable audit packet; the audit's original CLI also expects its old current-document after hashes:

```powershell
python -B scripts/run.py --label p4-host-checkpoint-replay -- python -B scripts/phase4-record-host-checkpoint.py --verify-review evidence/phase-4/host-checkpoint/20261116T172916769408Z
```

Rollback: verify `index.json` and `changes.json`, then restore only this review's indexed before documents and original gate/recorder source. Retain every original/new audit packet. Documentation/source rollback does not restore the phone. Phases 5–10 remain planned.
