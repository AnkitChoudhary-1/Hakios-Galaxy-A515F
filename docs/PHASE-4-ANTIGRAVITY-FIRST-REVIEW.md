# First Antigravity Phase 4 handoff review

Recorded 17 November 2026 (Asia/Calcutta). **Disposition: changes required before integration.** Main implementation sources and the worker folder are preserved. Phase 4 remains in progress with its physical gate false.

The attached handoff's integration commands and silicon runbook are proposals; they do not independently authorize operations. This review follows the user's request.

## Versions and verified progress

Frozen source: parallel/snapshots/20261117T013929281709Z-antigravity-first-handoff. It retains 49 handoff files and 20 main baseline files. MANIFEST SHA-256: 024b3c2add18375efca9067684054d789844439b7b005090df359aa5e8a1322a. HANDOFF SHA-256: ad61a3b639bfca3e86a82714036bc27669041df880adfe1392f4c5de201b6d17.

| Suite | Cases | Checks |
|---|---:|---:|
| Display | 4 | 66 |
| Input | 44 | 20,682 |
| Reporting | 108 | 108 |
| UFS | 74 | 316,791 |
| Total | 230 | 337,647 |

Strict C11 ASan/UBSan models passed. All four C++ drivers compiled with stated flags and with -ffreestanding -fno-exceptions -fno-rtti. Earlier three C++ compilation failures were the coordinator's omission of the candidate drivers include path, not handoff compilation defects. Unchanged passing C models were reused for the supplement.

Original review: evidence/phase-4/antigravity-first-review/20261117T015701009941Z; run 20261117T015654481914Z-p4-first-handoff-isolated-review. Supplement: evidence/phase-4/antigravity-first-review-supplement/20261117T022721584880Z; run 20261117T022716702253Z-p4-first-handoff-review-supplement. Both indexed packets and frozen source pins were checked again when recording this disposition. Complete matching Android/XNU references are retained under the supplement's references directory.

Retain corrected DPU20 register definitions, deterministic pattern foundations, shared format-10 decoder, queue/manager foundations and host coverage. The first shared format-10 coordinate extraction matches reference source. A51 DTS confirms max_x_y 4095/4095, display 1080/2400 and event information 10/16/1. ALIVE base 0x11850000 plus GPA1 DAT offset 0x24 and active-low pins 5/6/7 agrees with matching references.

## Required corrections

- **D1 (P1):** Framebuffer PA 0xCA000000 is supported by gta4xl tablet DTS, not matching A51 DTS. Ownership, active scanout, DPP/SYSMMU translation, format/stride and cache semantics remain unproved; DRAM inclusion cannot certify ownership.
- **D2 (P1):** DECON validation ignores run/enable state; the kernel continues framebuffer/brightness writes after failed validation. Disabled DECON returned success and one shadow write in the supplemental model.
- **D3 (P1):** DSIM FIFO acceptance lacks bounded completion/error checks. C++ permanent FIFO-full timeout falls through to a header write and success; absent MMIO returns success. Power helpers must propagate errors and honor timing.
- **D4 (P1):** Five brightness steps total 500 microseconds in the model. Add observable dwell, timestamps and repeated trials. Both matching S6E3FA9 and EA8076 sources use DCS 0x51 with two parameter bytes/10-bit table entries; linear 8-to-10-bit mapping is not established panel policy.
- **M1 (P1):** Mapping constants are inherited defects in main and handoff: pinned XNU WCOMB=0x6, not 0x2; DEFAULT=0x2, not 0. The three-argument ml_io_map_unmappable declaration is correct. Resolve repeated mapping lifetime/unmap behavior without claiming an observed panic.
- **D5 (P2):** Pattern API needs capacity/overflow checks. Pattern SHA-256 proves memory contents, not visibility.
- **I1 (P1):** Kernel input handler reads page 0x02 register 0x04 as packet data. Matching Melfas registers: 0x04 EVENT_FORMAT, 0x10 PACKET_INFO, 0x11 PACKET_DATA. Read and validate packet metadata and data at the correct registers.
- **I2 (P1):** Propagate decoder/queue failures, define overflow and primary-contact policy beyond slot zero, and provide sustained event delivery. A single hello sample cannot establish repeatable physical input.

Frozen source citations:

- [DECON validation](PUBLICATION.md)
- [DSIM send](PUBLICATION.md)
- [brightness sequence](PUBLICATION.md)
- [display handler](PUBLICATION.md)
- [touch packet read](PUBLICATION.md)
- [inherited mapping constants](PUBLICATION.md)
- [queue handling](PUBLICATION.md)
- [C++ command handling](PUBLICATION.md)

All adversarial observations used simulated MMIO. They identify defects and missing proof; no measured A51 display failure, corruption or panic is claimed.

## Patches, limits and recovery

The unified patch SHA-256 2c3b32b820c81efac15a2e95fbaf82032ee48be939fa0f8c8fb7f9a6a91ad88c checked/applied only in private staging and reproduced candidate hashes. The alternative patch SHA-256 9c8273a39bb8d6f494f4f7eff4eeeb0a6975d7706bc609cb0c45a7a6525e0f52 failed due to embedded workstation paths. Default git apply already strips one prefix; explicit -p1 is not uniquely required.

No patch is promoted. The retained main checkpoint remains 216 native cases / 337,511 checks, 244 modeled storage cases and 25 QEMU checks when pins match. Main owns UFS/storage, recovery evidence, integration, central documentation and all phone operations. Full UFS initialization, current known-image silicon reads, binary recovery persistence and actual display/brightness/touch/key gates remain unfinished.

Disposition packet: evidence/phase-4/antigravity-first-review-disposition/20261117T024516001914Z. Verify index.json and document-changes.json before restoring only indexed before copies whose current bytes still match after pins. New documents have before_exists=false; preserve the append-only log and later work. Do not reverse an unapplied patch or restore a whole source tree. Both legacy device-gate entry guards are unchanged.
