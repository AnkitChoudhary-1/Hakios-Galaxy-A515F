/* SPDX-License-Identifier: MIT */
/* Execute the actual portable core against an independently checked HCI/DMA model. */
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "a51_ufs_readonly.h"

static unsigned checks, cases;
#define CHECK(x) do { checks++; if (!(x)) { fprintf(stderr, "line %u: %s\n", __LINE__, #x); exit(1); } } while (0)
static _Alignas(4096) struct a51_ufs_utrd list[32];
static _Alignas(4096) struct a51_ufs_command command_buffer;
static _Alignas(65536) unsigned char data[65536];
enum fault { NONE, NEVER_COMPLETE, CLEAR_FAIL, STOP_FAIL, RESTORE_STOP_FAIL,
    RESTORE_POINTER_FAIL, START_FAIL, ADOPT_POINTER_FAIL, FOREIGN_TASK,
    OCS_BAD, TRANSACTION_BAD, LUN_BAD, TAG_BAD, STATUS_BAD, RESPONSE_BAD,
    RESIDUAL_BAD, FLAGS_BAD, EHS_BAD, SEGMENT_BAD, SENSE_BAD, HCI_BAD,
    RESTORE_START_FAIL, OCS_ANDROID, UPIU_ANDROID,
    BUS_FATAL_CLEAR, BUS_FATAL_ACTIVE, BUS_FATAL_CLEAR_FAIL, BUS_FATAL_RESTORE_FAIL };
struct model {
    unsigned standard[128], vendor[128], reads, writes, translations, cleans, invalidates;
    unsigned barriers, polls, submitted, clear_mask, phases, fault, phys_fault;
    unsigned restoring, stopped, last_write_reg, active, adopted, transaction_cleans;
    unsigned long long us;
};

static unsigned model_be32(const unsigned char *p)
{
    return (unsigned)p[0] * 16777216u + (unsigned)p[1] * 65536u +
        (unsigned)p[2] * 256u + p[3];
}

static void dma_complete(struct model *m)
{
    struct a51_ufs_utrd *u = list;
    const unsigned char *q = command_buffer.request;
    unsigned reading = q[16] == 0x28;
    /* Independently decode UTRD/UPIU and the single contiguous FMP span. */
    CHECK(u->dw0 == (reading ? 0x15000000u : 0x11000000u) && !u->dw1 && !u->dw3);
    CHECK(u->cmd_lo == 0x84002000 && !u->cmd_hi);
    CHECK(u->rsp_off == 1024 && u->rsp_len == 1024);
    CHECK(q[0] == 1 && q[1] == (reading ? 0x40 : 0) && !q[3]);
    unsigned blocks = ((unsigned)q[23] << 8) | q[24];
    unsigned lba = model_be32(q + 18), bytes = model_be32(q + 12);
    if (reading) {
        CHECK(!q[2] && blocks > 0 && blocks <= 16 && bytes == blocks * 4096);
        CHECK(lba >= 27792 && lba + blocks <= 42896);
        CHECK(u->prdt_off == 2048 && u->prdt_len == 128);
    } else {
        CHECK(!blocks && !bytes && !u->prdt_off && !u->prdt_len);
        CHECK((q[2] == 0 && q[16] == 0 && q[20] == 0) ||
            (q[16] == 0x1b && ((q[2] == 0xd0 && q[20] == 0x10) || (q[2] == 0 && q[20] == 1))));
    }
    unsigned total = 0;
    for (unsigned i = 0; i < 16; i++) {
        const unsigned *entry = command_buffer.prdt[i].words;
        if (reading && i == 0) {
            CHECK(entry[0] == 0x84010000 && !entry[1] && !entry[2]);
            CHECK(entry[3] == bytes - 1);
            total += entry[3] + 1;
            for (unsigned j = 4; j < 32; j++) CHECK(!entry[j]);
        } else {
            for (unsigned j = 0; j < 32; j++) CHECK(!entry[j]);
        }
    }
    CHECK(total == bytes);
    for (unsigned i = 1; i < 32; i++) {
        const unsigned char *p = (const unsigned char *)&list[i];
        for (unsigned j = 0; j < 32; j++) CHECK(!p[j]);
    }
    CHECK(m->transaction_cleans == (reading ? 3u : 2u) && m->barriers >= 4);
    for (unsigned i = 0; i < bytes; i++) data[i] = (unsigned char)((i * 37u + lba) & 255u);
    if (m->fault == OCS_ANDROID || m->fault == UPIU_ANDROID) memcpy(data, "ANDROID!", 8);
    list[0].ocs = m->fault == OCS_BAD || m->fault == OCS_ANDROID ? 7 : 0;
    unsigned char *p = command_buffer.response;
    p[0] = m->fault == TRANSACTION_BAD || m->fault == UPIU_ANDROID ? 0x3f : 0x21;
    p[2] = q[2];
    if (m->fault == LUN_BAD) p[2] ^= 1;
    if (m->fault == TAG_BAD) p[3] = 1;
    if (m->fault == STATUS_BAD) p[7] = 2;
    if (m->fault == RESPONSE_BAD) p[6] = 1;
    if (m->fault == RESIDUAL_BAD) a51_ufs_put_be32(p + 12, 4096);
    if (m->fault == FLAGS_BAD) p[1] = 0x20;
    if (m->fault == EHS_BAD) p[8] = 1;
    if (m->fault == SEGMENT_BAD) p[11] = 18;
    if (m->fault == SENSE_BAD) p[33] = 18;
    m->standard[A51_UFS_IS / 4] |= 1;
    m->standard[A51_UFS_DOORBELL / 4] = 0;
    m->active = 0;
    if (m->fault == FOREIGN_TASK) m->standard[A51_UFS_TASK_DOORBELL / 4] = 2;
}
static unsigned rd(void *context, unsigned vendor, unsigned offset)
{
    struct model *m = context; m->reads++;
    CHECK(vendor <= 1 && !(offset & 3) && offset < 512);
    if (!vendor && offset == A51_UFS_DOORBELL && m->active &&
        m->standard[offset / 4] && ++m->polls == 3 &&
        m->fault != NEVER_COMPLETE && m->fault != CLEAR_FAIL) {
        /* Inject during the doorbell read, after the first status check.
         * No response or data writes: fatal status is not completed DMA.
         */
        if (m->fault == HCI_BAD || m->fault >= BUS_FATAL_CLEAR) {
            m->standard[A51_UFS_IS / 4] |= m->fault == HCI_BAD ? 0x10000 : 0x20001;
            m->vendor[A51_UFS_INVALID_UPIU_LO / 4] = 0x1234;
            m->vendor[A51_UFS_INVALID_UPIU_HI / 4] = 0x5678;
            m->vendor[A51_UFS_INVALID_UTR_OFFSET / 4] = 0x20;
            m->vendor[A51_UFS_INVALID_DIN_OFFSET / 4] = 0x24;
            m->vendor[A51_UFS_SMU_ABORT_MATCH / 4] = 0x10c;
            if (m->fault != BUS_FATAL_ACTIVE && m->fault != BUS_FATAL_CLEAR_FAIL) {
                m->standard[A51_UFS_DOORBELL / 4] = 0;
                m->active = 0;
            }
        } else dma_complete(m);
    }
    return (vendor ? m->vendor : m->standard)[offset / 4];
}
static void wr(void *context, unsigned vendor, unsigned offset, unsigned value)
{
    struct model *m = context; m->writes++; m->last_write_reg = offset;
    CHECK(vendor <= 1 && !(offset & 3) && offset < 512);
    /* The core may change only the owned slot/list/run state and its nexus bit. */
    CHECK(vendor ? offset == A51_UFS_NEXUS :
        (offset == A51_UFS_RUN || offset == A51_UFS_LIST_LO || offset == A51_UFS_LIST_HI ||
         offset == A51_UFS_DOORBELL || offset == A51_UFS_CLEAR || offset == A51_UFS_IS));
    if (!vendor && offset == A51_UFS_IS) {
        CHECK(value == 1 && !m->active); /* W1C only our transfer completion */
        m->standard[offset / 4] &= ~value;
        return;
    }
    if (!vendor && offset == A51_UFS_RUN && value == 0) {
        if (m->adopted) m->restoring = 1;
        if (m->fault == STOP_FAIL || (m->restoring && m->fault == RESTORE_STOP_FAIL)) return;
        m->stopped++;
    }
    if (!vendor && offset == A51_UFS_RUN && value == 1 && m->fault == START_FAIL && !m->restoring) return;
    if (!vendor && offset == A51_UFS_RUN && value == 1 &&
        (m->fault == RESTORE_START_FAIL || m->fault == BUS_FATAL_RESTORE_FAIL) && m->restoring) return;
    if (!vendor && offset == A51_UFS_LIST_LO &&
        ((m->fault == ADOPT_POINTER_FAIL && value == 0x84000000) ||
         (m->fault == RESTORE_POINTER_FAIL && value == 0x8f000000))) return;
    if (!vendor && offset == A51_UFS_DOORBELL) {
        CHECK(value == 1 && m->standard[A51_UFS_RUN / 4] == 1);
        CHECK(m->standard[A51_UFS_LIST_LO / 4] == 0x84000000 && !m->standard[A51_UFS_LIST_HI / 4]);
        CHECK(m->vendor[A51_UFS_NEXUS / 4] == 0xaaaaaaaa + 1);
        m->submitted++; m->active = 1; m->polls = 0;
    }
    if (!vendor && offset == A51_UFS_CLEAR) {
        CHECK(value == 1 && (m->standard[A51_UFS_DOORBELL / 4] & 1)); m->clear_mask = value;
        if (m->fault != CLEAR_FAIL && m->fault != BUS_FATAL_CLEAR_FAIL) {
            m->standard[A51_UFS_DOORBELL / 4] &= ~value; m->active = 0;
        }
        return;
    }
    if (!vendor && offset == A51_UFS_LIST_LO && value == 0x84000000) m->adopted = 1;
    (vendor ? m->vendor : m->standard)[offset / 4] = value;
}
static unsigned long long physical(void *context, const void *pointer)
{
    struct model *m = context; m->translations++;
    uintptr_t v = (uintptr_t)pointer;
    const void *bases[3] = {list, &command_buffer, data};
    const unsigned sizes[3] = {1024, 4096, 65536};
    const unsigned long long pas[3] = {0x84000000, 0x84002000, 0x84010000};
    for (unsigned i = 0; i < 3; i++) {
        uintptr_t base = (uintptr_t)bases[i];
        if (v < base || v - base >= sizes[i]) continue;
        unsigned long long pa = pas[i] + (v - base);
        if (i == 2) {
            if (m->phys_fault == 1) pa += 0x100000000ULL;
            if (m->phys_fault == 2 && v - base == 4096) pa += 4096;
            if (m->phys_fault == 3 && v - base == 65535) pa++;
            if (m->phys_fault == 4) pa = 0x84002000 + (v - base);
            if (m->phys_fault == 5) pa++;
            if (m->phys_fault == 6) pa = 0xfffff000ULL + (v - base);
            if (m->phys_fault == 7) pa = 0;
            if (m->phys_fault == 8) pa += 4096; /* contiguous but crosses a 64 KiB boundary */
        }
        return pa;
    }
    return 0;
}
static void clean(void *context, const void *p, unsigned bytes)
{
    struct model *m = context; CHECK(!m->active && !m->restoring);
    CHECK((p == list && bytes == 1024) || (p == &command_buffer && bytes == 4096) || (p == data && bytes == 65536));
    m->cleans++; m->transaction_cleans++;
}
static void invalidate(void *context, const void *p, unsigned bytes)
{
    struct model *m = context; (void)p; (void)bytes;
    CHECK(m->restoring && !m->active && !m->standard[A51_UFS_DOORBELL / 4]);
    CHECK(m->standard[A51_UFS_LIST_LO / 4] == 0x8f000000 && m->vendor[A51_UFS_NEXUS / 4] == 0xaaaaaaaa);
    m->invalidates++;
}
static void barrier(void *p) { ((struct model *)p)->barriers++; }
static unsigned long long now_us(void *p) { return ((struct model *)p)->us; }
static void relax(void *p) { ((struct model *)p)->us += 1000; }
static void trace(void *p, unsigned stage)
{
    struct model *m = p;
    if (stage == A51_UFS_PREFLIGHT) {
        CHECK(!m->active);
        m->phases = m->restoring = m->stopped = m->adopted = m->transaction_cleans = 0;
    }
    m->phases |= 1u << stage;
}
static void init(struct model *m, struct a51_ufs_io *io, struct a51_ufs_memory *memory)
{
    memset(m, 0, sizeof(*m)); memset(list, 0xa5, sizeof(list));
    memset(&command_buffer, 0xa5, sizeof(command_buffer)); memset(data, 0xa5, sizeof(data));
    m->standard[A51_UFS_CAP / 4] = 31; m->standard[A51_UFS_VER / 4] = 0x210;
    m->standard[A51_UFS_HCS / 4] = 3; m->standard[A51_UFS_HCE / 4] = 1;
    m->standard[A51_UFS_LIST_LO / 4] = 0x8f000000; m->standard[A51_UFS_RUN / 4] = 1;
    m->vendor[A51_UFS_TX_PRDT / 4] = 0x8000000c; m->vendor[A51_UFS_RX_PRDT / 4] = 12;
    m->vendor[A51_UFS_REORDER / 4] = 10; m->vendor[A51_UFS_NEXUS / 4] = 0xaaaaaaaa;
    m->vendor[A51_UFS_DMA_BURST / 4] = 0x98000003;
    m->vendor[A51_UFS_WRITE_DMA_CTRL / 4] = 0x12345678;
    m->vendor[A51_UFS_AXI_DMA_IF / 4] = 0x87654321;
    *io = (struct a51_ufs_io){m, rd, wr, physical, clean, invalidate, barrier, now_us, relax, trace};
    *memory = (struct a51_ufs_memory){list, &command_buffer, data, 1, 0};
    cases++;
}
int main(void)
{
    struct model m; struct a51_ufs_io io; struct a51_ufs_memory memory; struct a51_ufs_report report;
    for (unsigned op = 1; op < 256; op++) {
        CHECK(a51_ufs_submit((void *)(uintptr_t)1, (void *)(uintptr_t)1, op, 0, 0, (void *)(uintptr_t)1) == -30);
    }
    CHECK(a51_ufs_submit(NULL, NULL, A51_UFS_READ, 27792, 1, NULL) == -22);
    for (unsigned i = 0; i < 5; i++) {
        init(&m, &io, &memory);
        unsigned lba = i == 0 ? 27791 : i == 1 ? 42896 : 27792;
        unsigned blocks = i == 2 ? 0 : i == 3 ? 17 : i == 4 ? 0xffffffffu : 1;
        CHECK(a51_ufs_submit(&io, &memory, 0, lba, blocks, &report) == -22);
        CHECK(!m.reads && !m.writes && !m.cleans && !m.translations);
    }
    for (unsigned i = 1; i <= 8; i++) {
        init(&m, &io, &memory); m.phys_fault = i;
        CHECK(a51_ufs_submit(&io, &memory, 0, 27792, 1, &report) == -22);
        CHECK(!m.reads && !m.writes && !m.cleans && data[0] == 0xa5);
    }
    init(&m, &io, &memory); memory.kernel_owned = 0;
    CHECK(a51_ufs_submit(&io, &memory, 0, 27792, 1, &report) == -22 && !m.translations);
    init(&m, &io, &memory); memory.data++;
    CHECK(a51_ufs_submit(&io, &memory, 0, 27792, 1, &report) == -22 && !m.writes);
    init(&m, &io, &memory); memory.data += 4096;
    CHECK(a51_ufs_submit(&io, &memory, 0, 27792, 16, &report) == -22);
    CHECK(!m.reads && !m.writes && !m.cleans && !m.invalidates && data[0] == 0xa5);
    const unsigned regs[] = {A51_UFS_DOORBELL, A51_UFS_TASK_DOORBELL, A51_UFS_HCE, A51_UFS_HCS, A51_UFS_IS};
    for (unsigned i = 0; i < 5; i++) {
        init(&m, &io, &memory);
        /* Matching ufshci.h: bit 11 is fatal; bit 10 is benign UIC completion. */
        m.standard[regs[i] / 4] = i < 2 ? 0x80000000 : i == 4 ? 0x800 : 0;
        CHECK(a51_ufs_submit(&io, &memory, 0, 27792, 1, &report) == (i < 2 ? -16 : -5));
        CHECK(!m.writes && !m.cleans && data[0] == 0xa5);
    }
    const unsigned vendor_regs[] = {A51_UFS_TX_PRDT, A51_UFS_RX_PRDT, A51_UFS_REORDER};
    for (unsigned i = 0; i < 3; i++) {
        init(&m, &io, &memory); m.vendor[vendor_regs[i] / 4] = 0;
        CHECK(a51_ufs_submit(&io, &memory, 0, 27792, 1, &report) == -95);
        CHECK(!m.writes && !m.cleans);
    }
    for (unsigned blocks = 1; blocks <= 16; blocks *= 2) {
        init(&m, &io, &memory);
        m.standard[A51_UFS_IS / 4] = 0x400;
        CHECK(a51_ufs_submit(&io, &memory, 0, 27792, blocks, &report) == 0);
        CHECK(report.submitted == 1 && report.completed == 1 && report.restored == 1 && !report.quarantined);
        CHECK(report.bytes == blocks * 4096 && report.ocs == 0 && m.invalidates == 3);
        CHECK(report.prdt_count == 1 && report.prdt_bytes == 128);
        CHECK(report.dma_burst == 0x98000003 && report.write_dma_ctrl == 0x12345678 && report.axi_dma_if == 0x87654321);
        CHECK(m.vendor[A51_UFS_DMA_BURST / 4] == 0x98000003 &&
            m.vendor[A51_UFS_WRITE_DMA_CTRL / 4] == 0x12345678 && m.vendor[A51_UFS_AXI_DMA_IF / 4] == 0x87654321);
        CHECK(report.final_is == 0x401 && m.standard[A51_UFS_IS / 4] == 0x400);
        for (unsigned i = 0; i < report.bytes; i++) CHECK(data[i] == (unsigned char)((i * 37u + 27792) & 255));
        CHECK(m.standard[A51_UFS_RUN / 4] == 1 && m.standard[A51_UFS_LIST_LO / 4] == 0x8f000000);
        CHECK(m.vendor[A51_UFS_NEXUS / 4] == 0xaaaaaaaa && report.stages == m.phases);
    }
    /* Same controller, list, command and buffer across readiness and reads. */
    init(&m, &io, &memory); m.vendor[A51_UFS_TX_PRDT / 4] = 12;
    const unsigned sequence[][4] = {{0xd0, 0x1b, 0x10, 0}, {0, 0x1b, 1, 0}, {0, 0, 0, 0},
        {0, 0x28, 0, 1}, {0, 0x28, 0, 16}, {0, 0x28, 0, 1}};
    for (unsigned i = 0; i < 6; i++) {
        int rc = sequence[i][1] == 0x28 ?
            a51_ufs_submit(&io, &memory, 0, 27792, sequence[i][3], &report) :
            a51_ufs_nodata(&io, &memory, sequence[i][0], sequence[i][1], sequence[i][2], &report);
        CHECK(rc == 0 && report.completed && report.restored && !report.quarantined);
        CHECK(m.submitted == i + 1 && m.vendor[A51_UFS_TX_PRDT / 4] == 12);
        CHECK(m.standard[A51_UFS_RUN / 4] == 1 && report.stages == m.phases);
        CHECK(m.standard[A51_UFS_LIST_LO / 4] == 0x8f000000);
        if (i < 3) CHECK(data[0] == 0xa5 && report.bytes == 0 && !report.prdt_count);
        else for (unsigned j = 0; j < report.bytes; j++) CHECK(data[j] == (unsigned char)((j * 37u + 27792) & 255));
    }
    CHECK(m.invalidates == 15);
    CHECK(a51_ufs_nodata((void *)(uintptr_t)1, (void *)(uintptr_t)1, 0, 0x2a, 0,
        (void *)(uintptr_t)1) == -30);
    CHECK(a51_ufs_nodata((void *)(uintptr_t)1, (void *)(uintptr_t)1, 0, 0x28, 0,
        (void *)(uintptr_t)1) == -30);
    for (unsigned f = OCS_BAD; f <= HCI_BAD; f++) {
        init(&m, &io, &memory); m.fault = f;
        CHECK(a51_ufs_submit(&io, &memory, 0, 27792, 1, &report) == (f == OCS_BAD || f == HCI_BAD ? -5 : -71));
        CHECK(report.completed == (f != HCI_BAD) && report.restored && !report.quarantined);
        CHECK(m.invalidates == (f == HCI_BAD ? 0u : 3u));
        CHECK(!(report.stages & (1u << A51_UFS_VALIDATED)));
    }
    const unsigned prefix_faults[] = {OCS_ANDROID, UPIU_ANDROID};
    for (unsigned i = 0; i < 2; i++) {
        init(&m, &io, &memory); m.fault = prefix_faults[i];
        CHECK(a51_ufs_submit(&io, &memory, 0, 27792, 1, &report) == (i ? -71 : -5));
        CHECK(!memcmp(data, "ANDROID!", 8) && !(report.stages & (1u << A51_UFS_VALIDATED)));
    }
    /* Readiness commands have the same protocol failure rules as reads. */
    for (unsigned f = OCS_BAD; f <= HCI_BAD; f++) {
        init(&m, &io, &memory); m.fault = f;
        CHECK(a51_ufs_nodata(&io, &memory, 0xd0, 0x1b, 0x10, &report) == (f == OCS_BAD || f == HCI_BAD ? -5 : -71));
        CHECK(report.completed == (f != HCI_BAD) && report.restored && !memory.quarantined && data[0] == 0xa5);
        CHECK(m.invalidates == (f == HCI_BAD ? 0u : 2u) && !(report.stages & (1u << A51_UFS_VALIDATED)));
    }
    /* Bus-fatal status must survive cancellation/restoration errors. Never
     * expose DMA contents or reuse quarantined memory, even with a clear DBR.
     */
    for (unsigned blocks = 1; blocks <= 16; blocks *= 16) {
        for (unsigned f = BUS_FATAL_CLEAR; f <= BUS_FATAL_RESTORE_FAIL; f++) {
            init(&m, &io, &memory); m.fault = f;
            CHECK(a51_ufs_submit(&io, &memory, 0, 27792, blocks, &report) == -5);
            CHECK(report.rc == -5 && report.submitted && !report.completed && !m.invalidates);
            CHECK(report.final_is == 0x20001 && report.ocs == 15 && report.elapsed_us == 2000);
            CHECK(!(report.stages & ((1u << A51_UFS_COMPLETED) | (1u << A51_UFS_VALIDATED))));
            CHECK(report.invalid_upiu[0] == 0x1234 && report.invalid_upiu[1] == 0x5678);
            CHECK(report.invalid_utr_offset == 0x20 && report.invalid_din_offset == 0x24 && report.smu_abort_match == 0x10c);
            CHECK(m.clear_mask == (f == BUS_FATAL_ACTIVE || f == BUS_FATAL_CLEAR_FAIL ? 1u : 0u));
            unsigned unsafe_cleanup = f == BUS_FATAL_CLEAR_FAIL || f == BUS_FATAL_RESTORE_FAIL;
            CHECK(report.cleanup_rc == (unsafe_cleanup ? -110 : 0));
            CHECK(report.quarantined == unsafe_cleanup && memory.quarantined == unsafe_cleanup);
            CHECK(report.restored == !unsafe_cleanup);
            if (unsafe_cleanup) {
                unsigned reads = m.reads, writes = m.writes, translations = m.translations;
                CHECK(a51_ufs_submit(&io, &memory, 0, 27792, 16, &report) == -16);
                CHECK(m.reads == reads && m.writes == writes && m.translations == translations);
            } else {
                CHECK(m.standard[A51_UFS_IS / 4] == 0x20000);
                CHECK(a51_ufs_submit(&io, &memory, 0, 27792, 16, &report) == -5);
                CHECK(m.submitted == 1 && !m.invalidates);
            }
        }
    }
    init(&m, &io, &memory); m.fault = NEVER_COMPLETE;
    CHECK(a51_ufs_submit(&io, &memory, 0, 27792, 1, &report) == -110);
    CHECK(m.clear_mask == 1 && report.restored && !report.completed && !m.invalidates);
    CHECK(report.terminal_doorbell == 1 && report.final_doorbell == 0 && report.elapsed_us == 5000000);
    m.fault = NONE;
    CHECK(a51_ufs_submit(&io, &memory, 0, 27792, 16, &report) == 0);
    CHECK(report.completed && report.restored && m.submitted == 2 && m.invalidates == 3);
    init(&m, &io, &memory); m.fault = CLEAR_FAIL;
    CHECK(a51_ufs_nodata(&io, &memory, 0, 0, 0, &report) == -110);
    CHECK(memory.quarantined && report.quarantined && !m.invalidates && data[0] == 0xa5);
    unsigned quarantined_reads = m.reads, quarantined_writes = m.writes;
    CHECK(a51_ufs_nodata(&io, &memory, 0, 0, 0, &report) == -16);
    CHECK(m.reads == quarantined_reads && m.writes == quarantined_writes);
    const unsigned unsafe[] = {CLEAR_FAIL, STOP_FAIL, RESTORE_STOP_FAIL, RESTORE_POINTER_FAIL,
        FOREIGN_TASK, RESTORE_START_FAIL};
    for (unsigned i = 0; i < sizeof(unsafe) / sizeof(unsafe[0]); i++) {
        init(&m, &io, &memory); m.fault = unsafe[i];
        CHECK(a51_ufs_submit(&io, &memory, 0, 27792, 1, &report) < 0);
        CHECK(memory.quarantined && report.quarantined && !report.restored && !m.invalidates);
        unsigned reads = m.reads, writes = m.writes, translations = m.translations;
        CHECK(a51_ufs_submit(&io, &memory, 0, 27792, 16, &report) == -16);
        CHECK(m.reads == reads && m.writes == writes && m.translations == translations);
    }
    const unsigned clean_failure[] = {START_FAIL, ADOPT_POINTER_FAIL};
    for (unsigned i = 0; i < 2; i++) {
        init(&m, &io, &memory); m.fault = clean_failure[i];
        CHECK(a51_ufs_submit(&io, &memory, 0, 27792, 1, &report) < 0);
        CHECK(!m.submitted && report.restored && !memory.quarantined && !m.invalidates);
    }
    printf("{\"suite\":\"ufs\",\"cases\":%u,\"checks\":%u,\"passed\":true}\n", cases, checks);
    return 0;
}
