# Independent Agent 2 display and brightness review

Decision: **changes_required** for `phase4-round-d1-candidate-20261117`, round `phase4-three-agents-20261117`, task P4-D1. The supplied native suites pass, but targeted checks reproduce merge blockers. Phase 4 remains **IN PROGRESS** and every current physical peripheral gate remains **UNPASSED**.

This review captures and inspects Agent 2's supplied delivery, independently executes its native checks, characterizes missing failure cases, and repairs its patch reconstruction in private proposal staging. It performs zero phone operations, zero full XNU builds, zero QEMU executions, and no main or worker implementation changes. Storage and input deliveries declare `ready_for_review` on disk; this review does not accept or test them.

Use the [copy-ready correction prompt](PUBLICATION.md) and the [round workflow](PHASE-4-THREE-AGENT-WORKFLOW.md). The [coordinator registry](PUBLICATION.md) separates each delivery's claim from the independent disposition.

## Exact inputs and retained evidence

Project: `C:/Users/Ankit/Desktop/A51/hakios-a51`. WSL distribution: `A51-KernelBuilder`. Private coordinator root: `parallel/phase4-three-agents-20261117/codex-integration`; Linux outputs remain below `/opt/a51-hakios/parallel/phase4-three-agents-20261117/codex-integration/reviews`.

The immutable [delivery packet](PUBLICATION.md) retains the complete 241-file submission, 273 input files, the user's original delivery text, fixed references, round instructions, and 49 protected main files. All source citations below refer to **that packet's `submission/work/`**, not a mutable worker folder. The root capture is indexed by `CAPTURE.json`; it has no root `MANIFEST.json`. The native result, targeted packet and packaging packet have separate file manifests and final source/dependency/artifact rechecks.

| Submitted artifact | SHA-256 |
| --- | --- |
| WORK-MANIFEST.json | `e073eb986a2eafc239daf63290f984fccb72fac4b0003dc596eddac2531e3dd7` |
| patches/owned.patch | `45cc0927e4af339a7b96c06f2d72ef5fe99eba3638e390c1c2c90982d2fd60b5` |
| patches/shared-proposals.patch | `8bdb6ee7961a6f60d7a8772a43ff963c03f0833e08f98606e7dbf17b6bca6be3` |
| patches/seed-followup.patch | `25e2c4651a188e11f848dee6cce9c74eee147b021abfcbe83736db508133c36a` |

The [native reproduction](PUBLICATION.md) independently attributes rebuilt artifacts and exact commands to the frozen source. Worker artifacts captured later are explicitly unbound to the original worker run; they are not substituted for the new attributed execution.

| Native suite | Cases | Checks | Result |
| --- | ---: | ---: | --- |
| Display | 13 | 3,379 | Passed, ASan/UBSan |
| Input baseline regression | 42 | 20,620 | Passed, ASan/UBSan |
| Reporting | 106 | 106 | Passed, ASan/UBSan |
| UFS baseline regression | 74 | 316,791 | Passed, ASan/UBSan |
| C++ drivers | 2 | 194 | Passed, ASan/UBSan |
| Total | 237 | 341,090 | Passed |

Four freestanding objects compiled: ExynosDECON, ExynosDSIM, ExynosKeyDriver and MelfasTouchDriver. These suites/objects target **native x86-64 WSL**. They do not establish AArch64 execution, production callback linkage, a combined XNU build, QEMU behavior, or A51 peripheral operation. The overlapping worker totals must not be added together.

The separate [targeted result](PUBLICATION.md) records **38 characterization observations: 27 reproduced defect observations and 11 controls**. C records 19/14/5; C++ records 19/13/6. Both executed under ASan/UBSan with source, compiler, header/runtime, binary and output hashes. Exit zero means the predicted bad behavior was reproduced; these are not 38 passing acceptance tests. All modeled MMIO uses host arrays and mapping tokens are inert bookkeeping.

Three read-only reviewers contributed source findings: `display_ownership_review`, `dsim_brightness_review`, and `display_integration_review`. They made no edits and executed no tests or phone commands. Codex retained their findings here and centrally executed all reproduction/characterization commands. This attribution prevents a future agent from mistaking parallel source inspection for parallel hardware validation.

## Required corrections

### D1-R1 / P1 — Framebuffer authority remains caller-declared

At `prototype/phase4-platform/hakios.a51.c:772`, boot argument scalars are converted into INHERITED, reserved, coherent and cache flags. `a51_display.h:254` validates and copies those values; it does not acquire an allocator exclusion or validate a live authority. `drivers/display/ExynosDECON.cpp:150` similarly marks a caller-provided interval owned. Removing the guessed address fallback improves refusal behavior, but does not create ownership or DMA/coherency evidence. The stale C comment at line 749 still describes a fallback that the implementation removed.

Required result: an explicit provider contract for an allocated or inherited live reservation, with allocation exclusion, lifetime, addressed span, CPU mapping/cache attributes, and verified DMA translation/coherency. Boot arguments may locate a candidate; they cannot certify it. Codex owns the production provider and shared boot/allocator interface. The driver must remain NOT_READY before any display write when that provider is unavailable. Document this dependency rather than manufacturing a receipt, owner tag or true flag. The current initializer also accepts a framebuffer-sized reservation; do not claim it enforces a 16 MiB minimum.

Evidence class: independent source review. Host flags can test a model contract but cannot prove the real provider or framebuffer lifetime. Hardware ownership remains unresolved.

### D1-R2 / P1 — Validate the entire DMA span with checked arithmetic

`a51_display.h:263` tests unchecked `base + size` against an 8 GiB ceiling; `:448` checks containment but not the framebuffer's complete 32-bit addressed span. The C++ initialization/setter checks at `ExynosDECON.cpp:290` and `:353` have corresponding omissions.

The targeted probes accept base `0xfffff000`, a 16 MiB reservation and a 10,368,000-byte framebuffer, although the framebuffer crosses 4 GiB. They also accept a reservation whose unsigned end wraps to zero. C++ registration, initialization and the setter accept the crossing framebuffer. **The production C boot-argument call site separately guards its reservation end at 4 GiB; the helper observations do not demonstrate bypassing that particular guard.**

Required result: subtraction-based or checked arithmetic for every reservation/end/mapping calculation and complete addressed-span containment in `[0, 2^32)` for the current IDMA path, including the last byte. Apply it consistently to registration, adoption, rebinding, setters, drawing and reporting. Treat an IOVA as physical RAM only under an explicitly verified translation/bypass contract. Add boundary, overflow and end-equals-4-GiB cases.

Evidence: `run-c.stdout` and `run-cpp.stdout` in the targeted packet; preserved sources remain unchanged.

### D1-R3 / P1 — Display mutations bypass or precede readiness

`ExynosDECON.cpp:337` permits an address setter after initialization refused missing SYSMMU. The targeted probe then observes an IDMA address write and DECON shadow update while `is_enabled` is false and SYSMMU is absent. `TriggerUpdate` at line 444 also writes after the modeled controller is stopped.

Separately, production C calls `a51_decon_verify_and_update` at `hakios.a51.c:695`; its helper commits the shadow update at `a51_display.h:690` before the callback checks routing, reservation authority and SYSMMU at C lines 707–801. A later NOT_READY return therefore does not imply the absence of a prior MMIO write. This production ordering finding is source-reviewed, not an executed kernel-callback observation.

Required result: split read-only observation from commit. Recheck running state, active window/channel, map-color exclusion, format, SYSMMU, owned span and mapping/cache prerequisites before each public mutation. Write/draw and flush only after validation, then commit in the documented order. A refused operation must preserve live resources and produce no display mutation. Test actual helper/driver entry points and a host-executable production sequencing path with write counters and failure injection.

### D1-R4 / P1 — C mapping lifecycle can lose live associations

`a51_display.h:275` permits active reinitialization that clears its mapping/hooks without cleanup or refusal. `:314` permits a same-VA bind to remove an existing unmap hook. `:340` releases physical authority and discards mapping state even when a live mapping has no unmap callback. The targeted C probes reproduce all three with counted callbacks.

Production C at `hakios.a51.c:824` directly unmaps its cached VA outside the reservation bookkeeping, binds the replacement with a null unmap hook at line 845, and ignores binding failure. The improved C++ refusal when an owned mapping lacks an unmap hook is supported, but does not repair this C path.

Required result: one explicit mapping owner; distinguish borrowed/owned mappings; retain state on missing cleanup; make reinitialization/rebind/release transactional; preserve a same-VA hook; invoke unmap exactly once before releasing physical ownership; check every production bind result. Keep the old association until replacement succeeds. Include idempotent cleanup, failed replacement and actual production callback cleanup coverage.

### D1-R5 / P1 — DSIM accepts replies carrying CRC/ECC errors

The C error mask at `a51_display.h:119` and C++ mask at `ExynosDSIM.h:56` include bits 27/23/22, omitting receive integrity errors. The frozen Android reference `inputs/snapshot/references/android/drivers/video/fbdev/exynos/dpu20/cal_9610/regs-dsim.h:180` and `:183` defines RX completion at bit 18, ECC at bit 15 and CRC at bit 14.

Realistic W1C/FIFO mocks publish a fresh **long, two-byte** reply after DCS dispatch. Both APIs return success/length 2 when fresh completion accompanies CRC or ECC and leave that error latched. Both initial-brightness queries accept raw `0x308` from those replies without any brightness write. No-error controls succeed and bit-22 controls reject with actual length zero. This characterizes receive-error handling; it does not claim physical corruption was observed or emulate silicon's CRC algorithm.

Required result: source-backed receive-specific error masks, error priority over completion, bounded FIFO recovery and correct W1C retirement on every error/empty-header/timeout path. Error returns must carry actual length zero and must not establish panel identity or initial/restored brightness. The C bit-22 control also retains completion bit 18, whereas C++ clears it; the C empty-header branch at line 915 omits acknowledgement. Include CRC/ECC plus completion, delayed fresh response after stale completion, incomplete/oversized payload and subsequent successful recovery tests for both APIs.

### D1-R6 / P1 — The validator and captured report cannot prove the diagnostic

The actual inline validator at `hakios.a51.h:103` accepts above-4-GiB or wrapped framebuffer addresses, unaligned addresses, zero timestamps/history, 50 ms intervals, raw values above 1023, and equal `UINT_MAX` initial/current brightness. Eight targeted mutations reproduce these acceptances. The supplied `reporting_model.c:103` labels a fixture with zero history and 50 ms intervals valid; its passing total does not cover the claimed evidence contract.

`hello.c:356` exports step index/logical brightness but omits timestamps, raw step values and initial/restored brightness. Five start timestamps alone also cannot establish the final step's full dwell. A successful transmit and assigned cached logical value do not independently establish final hardware readback.

Required result: define the accepted shared report schema with exact geometry/span, panel identity, initial raw/logical state, expected sequence, per-step raw/logical value and monotonic timestamps, final-dwell completion time, restore status, and fresh restored readback or an explicit unavailable status. Reject unknown/malformed/truncated/overflowing evidence; validate raw ranges and panel mapping. Export all required fields into the original nonce-bound capture, including diagnostic failures. Keep software evidence separate from the human visible-display/brightness acceptance. Codex owns shared ABI version/layout, validator, user output and recovery-capture reconciliation with the other streams.

### D1-R7 / P2 — Submitted patches do not reconstruct tested shared source

With explicit `git -c core.autocrlf=false -c core.eol=lf`, submitted owned/shared patches apply and reverse, but omit:

- `prototype/phase4-platform/hakios.a51.h`
- `prototype/phase4-platform/hello.c`
- `prototype/phase4-platform/tests/reporting_model.c`

See [original LF reconstruction](PUBLICATION.md). Apply/reverse checks alone do not establish complete source correspondence. The seed-followup route reconstructs production/test bytes but omits the private evidence-generation helper.

Codex generated a separate [omitted-shared proposal](PUBLICATION.md), **6,679 bytes**, SHA-256 `2d635b298f47775b20e8a62df104ddfac48c46770c18774a5ae9316dbbd87c54`. In fresh private staging, original + owned + shared + this supplement matches every frozen production/test file. All three patches reverse in separate staging to the exact original tree. Submitted patches remain unchanged.

The supplement still omits private runner/helper changes: `generate_evidence_and_manifest.py`, `generate_patches.py`, `generate_round_patches.py`, and `run_tests.sh`. These must be retained/versioned for complete reproduction. This is a **packaging proposal, not a source fix or accepted integration**. Regenerate complete owned/shared/private-helper delivery artifacts for the corrected revision; do not layer it blindly over another stream's shared ABI changes.

### D1-R8 / P2 — Correct the evidence and recovery claims

`HANDOFF.md:33` claims QEMU verification without a retained QEMU command. Worker evidence labels an AArch64 target even though retained command flags and rebuilt ELF headers establish native x86-64. Correct the handoff, evidence JSON, subsystem documentation and central-log proposal consistently. Keep independently supported BTA, reply bounds and model results; label freestanding compilation separately from execution.

The user's supplied delivery also describes volatile RAM and Power + Volume Down as a universal hardware recovery guarantee. Replace that assertion with the named, evidenced baseline return procedure and explicit test abort/restoration conditions. This delivery has no physical fault/return proof. No-flash operation, a current phone state, or safe recovery from every hardware fault is not established by host models.

## Supported improvements and remaining coverage

Source and independent native checks support the added BTA request, short-reply capacity checks, oversized/incomplete payload rejection, stale completion clearing, channel/map-color/format checks, and two brightness parameter bytes for **both** S6E3FA9 and EA8076. Production source uses five 600 ms dwells, freshly queries initial raw brightness, and attempts exact raw restoration after stepping errors. Preserve these improvements while closing the findings.

The existing stale-response mock supplies fresh data immediately rather than after a delay. The C brightness suite manually restores after success; its restoration-failure injection is not enabled. The native runner does not execute the real kernel diagnostic callback, so early commit, cached-map replacement and all production failure cleanup need dedicated shared-path coverage. These gaps explain how large passing model totals coexist with the reproduced defects.

## Rebuild, replay and integration handoff

Coordinator commands use the private logger and `python -B`. Original commands/outputs/times/exit statuses are retained in these coordinator run folders:

| Operation | Run ID |
| --- | --- |
| Capture | `20261117T145648274172Z-p4-d1-capture-delivery` |
| First reconstruction | `20261117T145752106112Z-p4-d1-reconstruct-submitted-patches` |
| Explicit LF reconstruction | `20261117T150013829260Z-p4-d1-reconstruct-with-pinned-line-endings` |
| Native reproduction | `20261117T150154592952Z-p4-d1-independent-native-reproduction` |
| Targeted probes | `20261117T151756332143Z-p4-d1-targeted-defect-characterization` |
| Packaging proposal | `20261117T152100324471Z-p4-d1-omitted-shared-packaging-proposal` |

Each run snapshots its exact adjacent scripts. `reproduce_display_d1.py`, `probe_display_d1.py` and `package_display_d1.py` require fresh output locations. Never rerun a writer into one of these retained packets. For replay, hash every MANIFEST entry; inspect exact `.json` command records and stdout/stderr. The frozen characterization executables expect the recorded defects; use new regression assertions for a corrected candidate.

Example to rebuild only the frozen targeted probes in a **new** packet:

```powershell
python -B C:/Users/Ankit/Desktop/A51/hakios-a51/parallel/phase4-three-agents-20261117/codex-integration/scripts/run.py --label p4-d1-probe-rebuild --cwd C:/Users/Ankit/Desktop/A51/hakios-a51 -- wsl.exe -d A51-KernelBuilder -u root -- python3 -B /mnt/c/Users/Ankit/Desktop/A51/hakios-a51/parallel/phase4-three-agents-20261117/codex-integration/scripts/probe_display_d1.py --packet /mnt/c/Users/Ankit/Desktop/A51/hakios-a51/evidence/phase-4/display-agent2-review/20261117T145649075937Z --supplement /mnt/c/Users/Ankit/Desktop/A51/hakios-a51/evidence/phase-4/display-agent2-review-supplement/NEW-UNUSED-ID
```

The review, probe and packaging guards pin 49 main implementation/runner files and the frozen submission/input bytes. None of this publication's 12 paths intersects those protected main files; the copies of prior workflow documents under inputs/ remain immutable history. This publication does not invalidate the frozen review guards. The full phase4-three-agent-plan.py verify operation checks preparation-time central documents and remains a historical preparation audit; use the current disposition verifier for current central state. If protected implementation files later change, rebuild from a preserved isolated copy or a new logged runner adaptation that preserves frozen source/input pins and checks current files separately. Never reset current documents or source merely to satisfy an old audit. The earlier native evidence remains attributed only to its original matched pins.

Agent 2 should correct its private revision and complete the [handoff template](PUBLICATION.md), including every failed attempt, exact reconstruction, source/dependency/binary attribution and provider limitations. Codex then captures a new immutable revision, independently checks all findings, reviews storage/input, reconciles shared reporting/event/memory interfaces, and serializes the combined build/native/QEMU work.

Only a reviewed combined candidate with fresh binary attribution, bounded capture/abort/restoration plan, human visible/touch/key observations and verified return proceeds to the later physical session. Register dumps, a printed PASS or a host check cannot satisfy visible output, repeatable restored brightness, real input or known-image storage gates. Both disabled legacy device-gate entry guards stay intact; `phase4-resume-audit.py` is never invoked.

Adding more agents follows the existing ownership registry: assign a unique task, frozen input hashes, one deliverable, separate Windows/WSL source/output/temp/cache roots and a named reviewer. Give one writer per file; additional agents inspect/propose. Good independent splits here are DSIM receive review, ownership-provider source tracing and report/replay review. Shared ABI promotion, full builds, central state and all phone operations retain one coordinator owner.

## Rollback and authority

No implementation patch was promoted, so no main-source reversal or device restoration is required. All new packet/staging paths are additive. The [central disposition packet](PUBLICATION.md) retains indexed before/after document and manifest bytes, publication checks and rollback guidance. Withdraw this review selection only after checking later changes; restore a file only if its current bytes still equal its recorded after hash. Preserve this append-only history, worker submissions, failed runs, original patches, snapshots and Android projects. Never perform a tree-wide reset or re-enable a legacy device helper.
