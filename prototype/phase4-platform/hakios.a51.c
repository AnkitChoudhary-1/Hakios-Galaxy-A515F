/* SPDX-License-Identifier: MIT */
/*
 * SM-A515F/Exynos 9611 early controller diagnostics. Register facts are traced
 * to the retained matching Android DTS and cal_9610/ufshci/i2c-s3c2410 files.
 * Storage transactions adopt an already initialized, idle UFS link. Complete
 * controller/PHY initialization and physical peripheral acceptance are pending.
 * Boot firmware must keep the selected controller clock/power domains alive.
 */
#include <kern/locks.h>
#include <libkern/libkern.h>
#include <sys/errno.h>
#include <sys/sysctl.h>
#include <sys/systm.h>
#include <pexpert/pexpert.h>
#include <pexpert/arm64/board_config.h>
#include <arm/machine_routines.h>
#include <mach/mach_types.h>
#include "hakios.a51.h"
#include "a51_ufs_readonly.h"

/* BSD lacks MACH_KERNEL_PRIVATE/PEXPERT_KERNEL_PRIVATE. Match the
 * osfmk/arm/machine_routines.h declaration, as existing BSD drivers do. */
extern vm_offset_t ml_io_map(vm_offset_t phys_addr, vm_size_t size);
extern vm_offset_t ml_io_map_unmappable(vm_offset_t phys_addr, vm_size_t size, unsigned int flags);
extern unsigned long long kvtophys(vm_offset_t va);
#define VM_WIMG_DEFAULT 0x0
#define VM_WIMG_WCOMB   0x2

static inline void
a51_dcache_inval_range(vm_offset_t va, vm_size_t size)
{
    vm_offset_t addr = va & ~63ULL;
    vm_offset_t end = va + size;
    __asm__ volatile("dsb sy" ::: "memory");
    for (; addr < end; addr += 64) {
        __asm__ volatile("dc ivac, %0" :: "r"(addr) : "memory");
    }
    __asm__ volatile("dsb sy" ::: "memory");
    __asm__ volatile("isb" ::: "memory");
}

static inline void
a51_dcache_flush_range(vm_offset_t va, vm_size_t size)
{
    vm_offset_t addr = va & ~63ULL;
    vm_offset_t end = va + size;
    __asm__ volatile("dsb sy" ::: "memory");
    for (; addr < end; addr += 64) {
        __asm__ volatile("dc civac, %0" :: "r"(addr) : "memory");
    }
    __asm__ volatile("dsb sy" ::: "memory");
    __asm__ volatile("isb" ::: "memory");
}

/* Freestanding SHA-256 Algorithm */
struct a51_sha256_ctx {
    unsigned int state[8];
    unsigned long long count;
    unsigned char buffer[64];
};

static void
a51_sha256_transform(unsigned int state[8], const unsigned char data[64])
{
    static const unsigned int K[64] = {
        0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
        0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
        0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
        0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
        0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
        0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
        0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
        0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2
    };
    unsigned int a = state[0], b = state[1], c = state[2], d = state[3];
    unsigned int e = state[4], f = state[5], g = state[6], h = state[7];
    unsigned int W[64];

    for (int i = 0; i < 16; i++) {
        W[i] = ((unsigned int)data[i * 4] << 24) |
               ((unsigned int)data[i * 4 + 1] << 16) |
               ((unsigned int)data[i * 4 + 2] << 8) |
               ((unsigned int)data[i * 4 + 3]);
    }
    for (int i = 16; i < 64; i++) {
        unsigned int s0 = (((W[i - 15] >> 7) | (W[i - 15] << 25)) ^
                           ((W[i - 15] >> 18) | (W[i - 15] << 14)) ^
                           (W[i - 15] >> 3));
        unsigned int s1 = (((W[i - 2] >> 17) | (W[i - 2] << 15)) ^
                           ((W[i - 2] >> 19) | (W[i - 2] << 13)) ^
                           (W[i - 2] >> 10));
        W[i] = W[i - 16] + s0 + W[i - 7] + s1;
    }
    for (int i = 0; i < 64; i++) {
        unsigned int S1 = (((e >> 6) | (e << 26)) ^ ((e >> 11) | (e << 21)) ^ ((e >> 25) | (e << 7)));
        unsigned int ch = (e & f) ^ ((~e) & g);
        unsigned int temp1 = h + S1 + ch + K[i] + W[i];
        unsigned int S0 = (((a >> 2) | (a << 30)) ^ ((a >> 13) | (a << 19)) ^ ((a >> 22) | (a << 10)));
        unsigned int maj = (a & b) ^ (a & c) ^ (b & c);
        unsigned int temp2 = S0 + maj;

        h = g;
        g = f;
        f = e;
        e = d + temp1;
        d = c;
        c = b;
        b = a;
        a = temp1 + temp2;
    }
    state[0] += a;
    state[1] += b;
    state[2] += c;
    state[3] += d;
    state[4] += e;
    state[5] += f;
    state[6] += g;
    state[7] += h;
}

static void
a51_sha256_init(struct a51_sha256_ctx *ctx)
{
    ctx->state[0] = 0x6a09e667;
    ctx->state[1] = 0xbb67ae85;
    ctx->state[2] = 0x3c6ef372;
    ctx->state[3] = 0xa54ff53a;
    ctx->state[4] = 0x510e527f;
    ctx->state[5] = 0x9b05688c;
    ctx->state[6] = 0x1f83d9ab;
    ctx->state[7] = 0x5be0cd19;
    ctx->count = 0;
}

static void
a51_sha256_update(struct a51_sha256_ctx *ctx, const unsigned char *data, size_t len)
{
    size_t i = 0;
    size_t idx = (size_t)(ctx->count & 63);
    ctx->count += len;

    if (idx) {
        size_t left = 64 - idx;
        if (len < left) {
            for (size_t k = 0; k < len; k++) { ctx->buffer[idx + k] = data[k]; }
            return;
        }
        for (size_t k = 0; k < left; k++) { ctx->buffer[idx + k] = data[k]; }
        a51_sha256_transform(ctx->state, ctx->buffer);
        i = left;
    }
    for (; i + 64 <= len; i += 64) {
        a51_sha256_transform(ctx->state, &data[i]);
    }
    for (size_t k = 0; i + k < len; k++) {
        ctx->buffer[k] = data[i + k];
    }
}

static void
a51_sha256_final(struct a51_sha256_ctx *ctx, unsigned char digest[32])
{
    unsigned long long total_bits = ctx->count * 8;
    size_t idx = (size_t)(ctx->count & 63);
    ctx->buffer[idx++] = 0x80;
    if (idx > 56) {
        while (idx < 64) { ctx->buffer[idx++] = 0; }
        a51_sha256_transform(ctx->state, ctx->buffer);
        idx = 0;
    }
    while (idx < 56) { ctx->buffer[idx++] = 0; }
    for (int i = 7; i >= 0; i--) {
        ctx->buffer[56 + (7 - i)] = (unsigned char)((total_bits >> (i * 8)) & 0xFF);
    }
    a51_sha256_transform(ctx->state, ctx->buffer);
    for (int i = 0; i < 8; i++) {
        digest[i * 4]     = (unsigned char)((ctx->state[i] >> 24) & 0xFF);
        digest[i * 4 + 1] = (unsigned char)((ctx->state[i] >> 16) & 0xFF);
        digest[i * 4 + 2] = (unsigned char)((ctx->state[i] >> 8) & 0xFF);
        digest[i * 4 + 3] = (unsigned char)(ctx->state[i] & 0xFF);
    }
}

/* Portable Bounded Exynos UFS Hardware Adapter */
#define UFS_ERR_WRITE_PROHIBITED    (-30)

static unsigned int
a51_ufs_io_read(void *ctx, unsigned int vendor, unsigned int offset)
{
    vm_offset_t base = (vm_offset_t)ctx;
    vm_offset_t va = vendor ? (base + 0x1100) : base;
    return *(volatile unsigned int *)(va + offset);
}

static void
a51_ufs_io_write(void *ctx, unsigned int vendor, unsigned int offset, unsigned int val)
{
    vm_offset_t base = (vm_offset_t)ctx;
    vm_offset_t va = vendor ? (base + 0x1100) : base;
    *(volatile unsigned int *)(va + offset) = val;
}

static unsigned long long
a51_ufs_io_phys(void *ctx, const void *ptr)
{
    (void)ctx;
    return (unsigned long long)kvtophys((vm_offset_t)ptr);
}

static void
a51_ufs_io_clean(void *ctx, const void *ptr, unsigned int bytes)
{
    (void)ctx;
    a51_dcache_flush_range((vm_offset_t)ptr, bytes);
}

static void
a51_ufs_io_inval(void *ctx, const void *ptr, unsigned int bytes)
{
    (void)ctx;
    a51_dcache_inval_range((vm_offset_t)ptr, bytes);
}

static void
a51_ufs_io_barrier(void *ctx)
{
    (void)ctx;
    __asm__ volatile("dsb sy; isb" ::: "memory");
}

static unsigned long long
a51_ufs_io_now(void *ctx)
{
    (void)ctx;
    unsigned long long cnt = __builtin_arm_rsr64("CNTVCT_EL0");
    return cnt / 26;
}

static void
a51_ufs_io_relax(void *ctx)
{
    (void)ctx;
    for (volatile int d = 0; d < 50; d++) { }
}

static _Alignas(4096) struct a51_ufs_utrd ufs_mem_list[32];
static _Alignas(4096) struct a51_ufs_command ufs_mem_cmd;
static unsigned char ufs_mem_data_pool[A51_UFS_DMA_BYTES + A51_UFS_DMA_ALIGNMENT];
/* Quarantine belongs to these static buffers, not to an individual sysctl. */
static struct a51_ufs_memory ufs_memory = {ufs_mem_list, &ufs_mem_cmd, NULL, 1, 0};
static unsigned int ufs_writes_rejected = 0;



SYSCTL_DECL(_kern_hakios);
static LCK_GRP_DECLARE(a51_lck_grp, "a51-mmio");
static LCK_MTX_DECLARE(a51_lock, &a51_lck_grp);
static unsigned int a51_sequence;

/* Only passive status/configuration registers. FIFO/data ports are excluded. */
static const unsigned short gpio_regs[] = {0x20, 0x24, 0x28, 0x2c, 0x40, 0x44, 0x48, 0x4c};
static const unsigned short i2c_regs[] = {0, 4, 8, 0x10};
static const unsigned short dsim_regs[] = {
    0, 8, 0xc, 0x14, 0x18, 0x1c, 0x20, 0x28, 0x2c, 0x30,
    0x38, 0x3c, 0x40, 0x44, 0x48, 0x4c, 0x50, 0x54, 0x58, 0x64, 0x68, 0x74, 0xa0
};
static const unsigned short decon_regs[] = {
    0, 0x10, 0x14, 0x18, 0x30, 0x40, 0x44, 0x4c, 0x50,
    0x64, 0x70, 0x78, 0xa0, 0x100, 0x104,
    0x120, 0x124, 0x128, 0x200, 0x214, 0x218, 0x250, 0x2a0,
    0x1000, 0x1004, 0x1008, 0x100c,
    0x1030, 0x1034, 0x1038, 0x103c,
    0x1060, 0x1064, 0x1068, 0x106c,
    0x1090, 0x1094, 0x1098, 0x109c,
    0x10c0, 0x10c4, 0x10c8, 0x10cc,
    0x8000, 0x8004, 0x8008, 0x800c,
    0x8030, 0x8034, 0x8038, 0x803c,
    0x8060, 0x8064, 0x8068, 0x806c,
    0x8090, 0x8094, 0x8098, 0x809c,
    0x80c0, 0x80c4, 0x80c8, 0x80cc
};
static const unsigned short ufs_regs[] = {
    0, 8, 0x10, 0x14, 0x18, 0x20, 0x24, 0x30, 0x34, 0x4c,
    0x50, 0x54, 0x58, 0x60, 0x64, 0x70, 0x74, 0x78, 0x80,
    0x90, 0x94, 0x98, 0x9c
};
static const unsigned short dpp_regs[] = {0, 4, 8, 0xc, 0x10, 0x14, 0x18, 0x20, 0x40, 0x44};
static const unsigned short sysmmu_regs[] = {0, 4, 8, 0xc, 0x30, 0x34, 0x38, 0x60, 0x70, 0x78, 0x80, 0x88};

struct a51_register_bank {
    unsigned long long pa;
    unsigned int size, group, count;
    const unsigned short *offsets;
    vm_offset_t va;
};
#define BANK(pa_, size_, group_, regs_) \
    {pa_, size_, group_, sizeof(regs_) / sizeof((regs_)[0]), regs_, 0}
static struct a51_register_bank banks[] = {
    BANK(0x11850000, 0x1000, HAKIOS_A51_GPIO, gpio_regs),
    BANK(0x13870000, 0x1000, HAKIOS_A51_I2C, i2c_regs),
    BANK(0x148e0000, 0x1000, HAKIOS_A51_DSIM, dsim_regs),
    BANK(0x148b0000, 0x9000, HAKIOS_A51_DECON, decon_regs),
    BANK(0x13520000, 0x2000, HAKIOS_A51_UFS, ufs_regs),
    BANK(0x14884000, 0x1000, HAKIOS_A51_DPP, dpp_regs),
    BANK(0x14883000, 0x1000, HAKIOS_A51_DPP, dpp_regs),
    BANK(0x14881000, 0x1000, HAKIOS_A51_DPP, dpp_regs),
    BANK(0x14882000, 0x1000, HAKIOS_A51_DPP, dpp_regs),
    BANK(0x14820000, 0x1000, HAKIOS_A51_SYSMMU, sysmmu_regs),
};

/* QEMU's /arm-io ranges cannot pass this test, even with the bootarg present. */
static int
a51_probe_groups(unsigned int *groups)
{
#if defined(GENERIC_GIC_V2_IRQ) && defined(HAKIOS_A51)
    unsigned int enable = 0, mask = 0;
    if (pe_arm_get_soc_base_phys() != 0x10000000 ||
        !PE_parse_boot_argn("hakios_a51_mmio", &enable, sizeof(enable)) || enable != 1 ||
        !PE_parse_boot_argn("hakios_a51_probe", &mask, sizeof(mask)) ||
        !mask || (mask & ~HAKIOS_A51_ALL)) {
        return ENXIO;
    }
    *groups = mask;
    return 0;
#else
    (void)groups;
    return ENXIO;
#endif
}

static int
a51_snapshot_read(struct hakios_a51_snapshot *snapshot)
{
    unsigned int groups = 0;
    int error = a51_probe_groups(&groups);
    if (error) { return error; }
    bzero(snapshot, sizeof(*snapshot));
    snapshot->version = HAKIOS_A51_ABI_VERSION;
    snapshot->groups = groups;
    lck_mtx_lock(&a51_lock);
    snapshot->sequence = ++a51_sequence;
    snapshot->counter = __builtin_arm_rsr64("CNTVCT_EL0");
    for (unsigned int i = 0; i < sizeof(banks) / sizeof(banks[0]); i++) {
        struct a51_register_bank *bank = &banks[i];
        if (!(groups & bank->group)) { continue; }
        printf("HAKIOS_A51_PROBE_BEGIN pa=0x%llx group=0x%x\n", bank->pa, bank->group);
        if (!bank->va) { bank->va = ml_io_map(bank->pa, bank->size); }
        if (!bank->va) { error = ENOMEM; break; }
        for (unsigned int j = 0; j < bank->count; j++) {
            unsigned int offset = bank->offsets[j];
            if (offset + 4 > bank->size || (offset & 3) || snapshot->count == HAKIOS_A51_REG_MAX) {
                error = EOVERFLOW; break;
            }
            struct hakios_a51_register *reg = &snapshot->regs[snapshot->count++];
            reg->pa = bank->pa + offset;
            reg->group = bank->group;
            reg->value = *(volatile unsigned int *)(bank->va + offset);
        }
        if (error) { break; }
        if (bank->group == HAKIOS_A51_UFS) {
            unsigned int hcs = *(volatile unsigned int *)(bank->va + 0x30);
            unsigned int hce = *(volatile unsigned int *)(bank->va + 0x34);
            unsigned int ver = *(volatile unsigned int *)(bank->va + 0x08);
            printf("HAKIOS_UFS_HCI_STATUS hcs=0x%x hce=0x%x ver=0x%x ready=%d\n", hcs, hce, ver, (hcs & 2) != 0);
        }
        printf("HAKIOS_A51_PROBE_DONE pa=0x%llx count=%u\n", bank->pa, bank->count);
    }
    lck_mtx_unlock(&a51_lock);
    return error;
}

static int
sysctl_a51_snapshot(__unused struct sysctl_oid *oidp, __unused void *arg1,
    __unused int arg2, struct sysctl_req *req)
{
    struct hakios_a51_snapshot snapshot;
    unsigned int groups = 0;
    if (req->newptr) { return EPERM; }
    int error = a51_probe_groups(&groups);
    if (error) { return error; }
    /* Length queries and undersized buffers must never access hardware. */
    if (!req->oldptr) { return SYSCTL_OUT(req, NULL, sizeof(snapshot)); }
    if (req->oldlen < sizeof(snapshot)) { return ENOMEM; }
    error = a51_snapshot_read(&snapshot);
    return error ? error : SYSCTL_OUT(req, &snapshot, sizeof(snapshot));
}
SYSCTL_PROC(_kern_hakios, OID_AUTO, a51_snapshot,
    CTLTYPE_OPAQUE | CTLFLAG_RD | CTLFLAG_LOCKED, 0, 0, sysctl_a51_snapshot,
    "S,hakios_a51_snapshot", "Guarded bounded A51 controller snapshot; no MMIO writes");

static void
a51_ufs_log(const char *name, const struct a51_ufs_report *r)
{
    printf("HAKIOS_UFS_REPORT name=%s rc=%d cleanup_rc=%d lba=%u blocks=%u bytes=%u ocs=%u trans=0x%x resp=%u status=%u residual=%u sense_len=%u stages=0x%x submitted=%u completed=%u restored=%u quarantined=%u prdt_count=%u prdt_bytes=%u elapsed_us=%llu\n",
        name, r->rc, r->cleanup_rc, r->lba, r->blocks, r->bytes, r->ocs, r->transaction,
        r->response, r->status, r->residual, r->sense_length, r->stages,
        r->submitted, r->completed, r->restored, r->quarantined,
        r->prdt_count, r->prdt_bytes, r->elapsed_us);
    printf("HAKIOS_UFS_ADDR name=%s list=0x%llx command=0x%llx data=0x%llx tx=0x%x rx=0x%x reorder=0x%x\n",
        name, r->list_pa, r->command_pa, r->data_pa, r->tx_prdt, r->rx_prdt, r->reorder);
    printf("HAKIOS_UFS_DMA_CONFIG name=%s burst=0x%x write_ctrl=0x%x axi=0x%x\n",
        name, r->dma_burst, r->write_dma_ctrl, r->axi_dma_if);
    printf("HAKIOS_UFS_TERMINAL name=%s is=0x%x dbr=0x%x task=0x%x run=0x%x hcs=0x%x hce=0x%x uic=0x%x:0x%x:0x%x:0x%x:0x%x rx_error=0x%x dma=0x%x:0x%x:0x%x:0x%x final_dbr=0x%x final_run=0x%x\n",
        name, r->final_is, r->terminal_doorbell, r->terminal_task, r->terminal_run,
        r->terminal_hcs, r->terminal_hce, r->uic_errors[0], r->uic_errors[1],
        r->uic_errors[2], r->uic_errors[3], r->uic_errors[4], r->rx_upiu_error,
        r->dma_monitor[0], r->dma_monitor[1], r->dma_monitor[2], r->dma_monitor[3],
        r->final_doorbell, r->final_run);
    printf("HAKIOS_UFS_VENDOR name=%s invalid_upiu=0x%x:0x%x invalid_utr=0x%x invalid_din=0x%x smu_abort=0x%x\n",
        name, r->invalid_upiu[0], r->invalid_upiu[1], r->invalid_utr_offset,
        r->invalid_din_offset, r->smu_abort_match);
    /* The report contains a copy made after DMA stopped, never an active buffer. */
    if (r->completed && r->restored && !r->quarantined && r->sense_length) {
        printf("HAKIOS_UFS_SENSE name=%s len=%u bytes=%02x:%02x:%02x:%02x:%02x:%02x:%02x:%02x:%02x:%02x:%02x:%02x:%02x:%02x:%02x:%02x:%02x:%02x\n",
            name, r->sense_length, r->sense[0], r->sense[1], r->sense[2], r->sense[3],
            r->sense[4], r->sense[5], r->sense[6], r->sense[7], r->sense[8],
            r->sense[9], r->sense[10], r->sense[11], r->sense[12], r->sense[13],
            r->sense[14], r->sense[15], r->sense[16], r->sense[17]);
    }
}

static void
a51_ufs_result_transfer(struct hakios_a51_ufs_transfer_result *out,
    const struct a51_ufs_report *r, unsigned int expected_blocks)
{
    bzero(out, sizeof(*out));
    out->lba = r->lba; out->blocks = r->blocks; out->rc = r->rc; out->ocs = r->ocs;
    out->stages = r->stages;
    out->lifecycle = (r->submitted ? HAKIOS_A51_UFS_SUBMITTED : 0) |
        (r->completed ? HAKIOS_A51_UFS_COMPLETED : 0) |
        (r->restored ? HAKIOS_A51_UFS_RESTORED : 0) |
        (r->quarantined ? HAKIOS_A51_UFS_QUARANTINED : 0) |
        ((r->stages & (1u << A51_UFS_VALIDATED)) ? HAKIOS_A51_UFS_VALIDATED : 0);
    out->transaction = r->transaction; out->response = r->response;
    out->status = r->status; out->residual = r->residual; out->sense_length = r->sense_length;
    out->prdt_count = r->prdt_count; out->prdt_bytes = r->prdt_bytes; out->elapsed_us = r->elapsed_us;
    if (hakios_a51_ufs_transfer_valid(out, expected_blocks) && !r->cleanup_rc &&
        r->submitted == 1 && r->completed == 1 && r->restored == 1 &&
        ufs_memory.data && r->bytes == expected_blocks * A51_UFS_BLOCK_SIZE &&
        r->bytes <= A51_UFS_DMA_BYTES) {
        struct a51_sha256_ctx ctx;
        a51_sha256_init(&ctx);
        a51_sha256_update(&ctx, ufs_memory.data, r->bytes);
        a51_sha256_final(&ctx, out->sha256);
    } else if (!out->rc) {
        out->rc = A51_UFS_PROTOCOL;
    }
}

static int
a51_ufs_activate(const struct a51_ufs_io *io)
{
    /* These exact non-writing commands previously succeeded on this device.
     * They now share all preflight, timeout, restoration and UPIU checks.
     * A failed command stops the sequence; OCS 7 is a controller fatal error.
     */
    const unsigned int commands[3][3] = {{0xd0, 0x1b, 0x10}, {0, 0x1b, 1}, {0, 0, 0}};
    const char *names[3] = {"device-start", "lun0-start", "unit-ready"};
    for (unsigned int i = 0; i < 3; i++) {
        struct a51_ufs_report report;
        int rc = a51_ufs_nodata(io, &ufs_memory, commands[i][0], commands[i][1], commands[i][2], &report);
        a51_ufs_log(names[i], &report);
        if (rc) { return rc; }
    }
    return 0;
}

static int
sysctl_a51_ufs_test(__unused struct sysctl_oid *oidp, __unused void *arg1,
    __unused int arg2, struct sysctl_req *req)
{
    unsigned int groups = 0;
    if (req->newptr) { return EPERM; }
    int error = a51_probe_groups(&groups);
    if (error) { return error; }
    if (!(groups & HAKIOS_A51_UFS)) { return ENXIO; }
    if (!req->oldptr) { return SYSCTL_OUT(req, NULL, sizeof(struct hakios_a51_ufs_result)); }
    if (req->oldlen < sizeof(struct hakios_a51_ufs_result)) { return ENOMEM; }

    struct hakios_a51_ufs_result res;
    bzero(&res, sizeof(res));
    res.version = HAKIOS_A51_UFS_ABI_VERSION;
    res.single.lba = res.multi.lba = res.reread.lba = A51_UFS_BOOT_LBA;
    res.single.blocks = res.reread.blocks = 1; res.multi.blocks = A51_UFS_MAX_BLOCKS;
    res.single.rc = res.multi.rc = res.reread.rc = A51_UFS_UNSUPPORTED;
    res.single.ocs = res.multi.ocs = res.reread.ocs = 15;
    lck_mtx_lock(&a51_lock);
    if (!ufs_memory.data ||
        ((uintptr_t)ufs_memory.data & (A51_UFS_DMA_ALIGNMENT - 1)) ||
        (kvtophys((vm_offset_t)ufs_memory.data) & (A51_UFS_DMA_ALIGNMENT - 1))) {
        uintptr_t pa = (uintptr_t)kvtophys((vm_offset_t)ufs_mem_data_pool);
        uintptr_t off = (A51_UFS_DMA_ALIGNMENT - (pa & (A51_UFS_DMA_ALIGNMENT - 1))) & (A51_UFS_DMA_ALIGNMENT - 1);
        ufs_memory.data = ufs_mem_data_pool + off;
    }
    vm_offset_t ufs_va = 0;
    for (unsigned int i = 0; i < sizeof(banks) / sizeof(banks[0]); i++) {
        if (banks[i].group == HAKIOS_A51_UFS) {
            if (!banks[i].va) { banks[i].va = ml_io_map(banks[i].pa, banks[i].size); }
            ufs_va = banks[i].va;
            break;
        }
    }
    if (!ufs_va) { lck_mtx_unlock(&a51_lock); return ENXIO; }

    struct a51_ufs_io io = {
        (void *)ufs_va, a51_ufs_io_read, a51_ufs_io_write, a51_ufs_io_phys,
        a51_ufs_io_clean, a51_ufs_io_inval, a51_ufs_io_barrier,
        a51_ufs_io_now, a51_ufs_io_relax, NULL
    };
    /* Inherited firmware pointers are telemetry only. They are not owned or
     * necessarily mapped by XNU. Never map or dereference their targets.
     */
    printf("HAKIOS_UFS_SBOOT_INIT lba=0x%x:0x%x rs=0x%x dbr=0x%x hcs=0x%x hce=0x%x is=0x%x\n",
        io.read(io.context, 0, A51_UFS_LIST_HI), io.read(io.context, 0, A51_UFS_LIST_LO),
        io.read(io.context, 0, A51_UFS_RUN), io.read(io.context, 0, A51_UFS_DOORBELL),
        io.read(io.context, 0, A51_UFS_HCS), io.read(io.context, 0, A51_UFS_HCE),
        io.read(io.context, 0, A51_UFS_IS));

    vm_offset_t prot_va = ml_io_map(0x13530000, 0x1000);
    if (prot_va) {
        volatile unsigned int *pr = (volatile unsigned int *)prot_va;
        printf("HAKIOS_UFS_PROTECTOR ctrl=0x%x stat=0x%x sec=0x%x beg0=0x%x end0=0x%x lun0=0x%x ctl0=0x%x beg1=0x%x end1=0x%x\n",
            pr[0x000 / 4], pr[0x008 / 4], pr[0x010 / 4],
            pr[0x200 / 4], pr[0x204 / 4], pr[0x208 / 4], pr[0x20c / 4],
            pr[0x210 / 4], pr[0x214 / 4]);
    }
    res.ufs_version = io.read(io.context, 0, A51_UFS_VER);
    res.hcs = io.read(io.context, 0, A51_UFS_HCS);
    res.hce = io.read(io.context, 0, A51_UFS_HCE);

    struct a51_ufs_report write_report;
    res.write_rc = a51_ufs_submit(&io, &ufs_memory, A51_UFS_WRITE, A51_UFS_BOOT_LBA, 1, &write_report);
    if (res.write_rc == A51_UFS_RO) { ufs_writes_rejected++; }
    res.write_rejected = ufs_writes_rejected;
    res.doorbell_after_write = io.read(io.context, 0, A51_UFS_DOORBELL);
    printf("HAKIOS_UFS_WRITE_TEST write_rc=%d rejected=%u dbr=0x%x\n",
        res.write_rc, res.write_rejected, res.doorbell_after_write);

    res.init_rc = a51_ufs_activate(&io);
    if (!res.init_rc) {
        struct a51_ufs_report report;
        a51_ufs_submit(&io, &ufs_memory, A51_UFS_READ, A51_UFS_BOOT_LBA, 1, &report);
        a51_ufs_log("single", &report);
        a51_ufs_result_transfer(&res.single, &report, 1);
        res.diag_dest_pa_lo = (unsigned int)report.data_pa;
        res.diag_dest_pa_hi = (unsigned int)(report.data_pa >> 32);
        if (!res.single.rc) {
            a51_ufs_submit(&io, &ufs_memory, A51_UFS_READ, A51_UFS_BOOT_LBA, A51_UFS_MAX_BLOCKS, &report);
            a51_ufs_log("multi", &report);
            a51_ufs_result_transfer(&res.multi, &report, A51_UFS_MAX_BLOCKS);
            if (!res.multi.rc) {
                /* Confirm the same buffers/controller still work after 64 KiB. */
                a51_ufs_submit(&io, &ufs_memory, A51_UFS_READ, A51_UFS_BOOT_LBA, 1, &report);
                a51_ufs_log("reread", &report);
                a51_ufs_result_transfer(&res.reread, &report, 1);
            }
        }
    }
    res.diag_rs = io.read(io.context, 0, A51_UFS_RUN);
    res.diag_dbr = io.read(io.context, 0, A51_UFS_DOORBELL);
    lck_mtx_unlock(&a51_lock);
    return SYSCTL_OUT(req, &res, sizeof(res));
}
SYSCTL_PROC(_kern_hakios, OID_AUTO, a51_ufs_test,
    CTLTYPE_OPAQUE | CTLFLAG_RD | CTLFLAG_LOCKED, 0, 0, sysctl_a51_ufs_test,
    "S,hakios_a51_ufs_result", "Bounded read-only UFS transfer and lifecycle evidence");

/* This destructive pending-bit diagnostic is restricted to QEMU twice: here
 * and inside the backend. It cannot be enabled on the phone with bootargs. */
#if defined(GENERIC_GIC_V2_IRQ)
extern kern_return_t hakios_gicv2_qemu_test(unsigned int *);
#endif
static int
sysctl_a51_qemu_spi(__unused struct sysctl_oid *oidp, __unused void *arg1,
    __unused int arg2, struct sysctl_req *req)
{
    unsigned int enable = 0, flags = 0;
    if (req->newptr) { return EPERM; }
#if defined(GENERIC_GIC_V2_IRQ)
    if (pe_arm_get_soc_base_phys() != 0x08000000 ||
        !PE_parse_boot_argn("hakios_qemu_spi", &enable, sizeof(enable)) || enable != 1) {
        return ENXIO;
    }
    if (!req->oldptr) { return SYSCTL_OUT(req, NULL, sizeof(flags)); }
    if (req->oldlen < sizeof(flags)) { return ENOMEM; }
    kern_return_t test = hakios_gicv2_qemu_test(&flags);
    /* Retain partial flags even when the test fails. */
    int output = SYSCTL_OUT(req, &flags, sizeof(flags));
    return output ? output : (test == KERN_SUCCESS ? 0 : EIO);
#else
    (void)enable; (void)flags;
    return ENXIO;
#endif
}
SYSCTL_PROC(_kern_hakios, OID_AUTO, a51_qemu_spi,
    CTLTYPE_INT | CTLFLAG_RD | CTLFLAG_LOCKED, 0, 0, sysctl_a51_qemu_spi,
    "I", "QEMU-only bounded peripheral interrupt integration test");
