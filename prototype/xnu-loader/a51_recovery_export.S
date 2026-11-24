/* SPDX-License-Identifier: MIT */
/* Exact leaf exporter used by the storage trampoline and QEMU execution tests.
 * x0 = 256-byte record, x1 = physical log, x2 = complete raw log length,
 * x3 = pmsg zone, x4 = independent console zone (each 512 KiB, aligned 64).
 * Return x0 = 0 or -22. Caller supplies audited destinations, MMU/D-cache OFF.
 * No stack, MMIO, source writes, truncation, or unbounded copy. Preserves LR
 * and x19-x29. Publication is ordered; a fresh nonce rejects an old envelope.
 */
#define __ASSEMBLY__ 1
#include "xnu_trampoline.h"
    .section .text.recovery_export, "ax", %progbits
    .align 3
    .global a51_recovery_export
    .type a51_recovery_export, %function
a51_recovery_export:
    cbz     x3, .Lre_invalid
    cbz     x4, .Lre_invalid
    orr     x5, x3, x4
    tst     x5, #63
    b.ne    .Lre_invalid
    ldr     x5, =0xfff80000
    cmp     x3, x5
    b.hi    .Lre_invalid
    cmp     x4, x5
    b.hi    .Lre_invalid
    subs    x5, x3, x4
    cneg    x5, x5, lo
    cmp     x5, #A51_RECOVERY_ZONE_BYTES
    b.lo    .Lre_invalid
    cbz     x2, .Lre_invalid
    cmp     x2, #A51_RECOVERY_LOG_MAX
    b.hi    .Lre_invalid
    tst     x0, #7
    b.ne    .Lre_invalid
    ldr     x5, =0x80000000
    cmp     x0, x5
    b.lo    .Lre_invalid
    cmp     x1, x5
    b.lo    .Lre_invalid
    ldr     x5, =0xc0000000
    sub     x6, x5, #HKE_XNU_RECORD_BYTES
    cmp     x0, x6
    b.hi    .Lre_invalid
    sub     x6, x5, x2
    cmp     x1, x6
    b.hi    .Lre_invalid
    /* Refuse any source/destination overlap before writing either zone. */
    mov     x6, x3
    mov     w7, #2
.Lre_overlap:
    add     x8, x6, #A51_RECOVERY_ZONE_BYTES
    cmp     x0, x8
    b.hs    .Lre_log_overlap
    add     x9, x0, #HKE_XNU_RECORD_BYTES
    cmp     x9, x6
    b.hi    .Lre_invalid
.Lre_log_overlap:
    cmp     x1, x8
    b.hs    .Lre_next_zone
    add     x9, x1, x2
    cmp     x9, x6
    b.hi    .Lre_invalid
.Lre_next_zone:
    mov     x6, x4
    subs    w7, w7, #1
    b.ne    .Lre_overlap
    ldr     x5, [x0, #XBR_O_MAGIC]
    ldr     x6, =HKE_XNU_RECORD_MAGIC
    cmp     x5, x6
    b.ne    .Lre_invalid
    ldr     x5, [x0, #XBR_O_VERSION]
    cmp     x5, #HKE_XNU_RECORD_VERSION
    b.ne    .Lre_invalid
    ldr     x5, [x0, #XBR_O_BYTES]
    cmp     x5, #HKE_XNU_RECORD_BYTES
    b.ne    .Lre_invalid
    ldr     x5, [x0, #XBR_O_LOG_PA]
    cmp     x5, x1
    b.ne    .Lre_invalid
    ldr     x5, [x0, #XBR_O_LOG_LEN]
    cmp     x5, x2
    b.ne    .Lre_invalid

    /* Invalidate persistent headers and commit before replacing their data. */
    str     wzr, [x3]
    str     wzr, [x3, #4]
    str     wzr, [x3, #8]
    str     wzr, [x3, #40] /* persistent header 12 + commit offset 28 */
    str     wzr, [x4]
    str     wzr, [x4, #4]
    str     wzr, [x4, #8]
    dsb     sy
    add     x13, x3, #12
    ldr     x5, =A51_RECOVERY_MAGIC
    /* persistent_ram's 12-byte header leaves this destination 4 mod 8.
     * Naturally aligned word stores also work with SCTLR_EL1.A set and
     * preserve the envelope's exact little-endian bytes.
     */
    str     w5, [x13]
    lsr     x5, x5, #32
    str     w5, [x13, #4]
    mov     w5, #1
    str     w5, [x13, #8]
    mov     w5, #HKE_XNU_RECORD_BYTES
    str     w5, [x13, #12]
    str     w2, [x13, #16]
    add     x14, x2, #(A51_RECOVERY_HEADER_BYTES + HKE_XNU_RECORD_BYTES)
    str     w14, [x13, #20]
    str     wzr, [x13, #24]
    add     x5, x13, #A51_RECOVERY_HEADER_BYTES
    mov     x6, x0
    mov     w7, #(HKE_XNU_RECORD_BYTES / 4)
.Lre_record:
    ldr     w8, [x6], #4
    str     w8, [x5], #4
    subs    w7, w7, #1
    b.ne    .Lre_record
    mov     x6, x1
    mov     x7, x2
    add     x8, x4, #12
.Lre_log:
    ldrb    w9, [x6], #1
    strb    w9, [x5], #1
    strb    w9, [x8], #1
    subs    x7, x7, #1
    b.ne    .Lre_log

    /* IEEE CRC32 of first 24 header bytes followed by all record/log bytes. */
    mov     w5, #-1
    ldr     w8, =0xedb88320
    mov     x6, x13
    mov     x7, #24
    mov     w12, #0
.Lre_crc_byte:
    ldrb    w9, [x6], #1
    eor     w5, w5, w9
    mov     w10, #8
.Lre_crc_bit:
    and     w11, w5, #1
    neg     w11, w11
    lsr     w5, w5, #1
    and     w11, w11, w8
    eor     w5, w5, w11
    subs    w10, w10, #1
    b.ne    .Lre_crc_bit
    subs    x7, x7, #1
    b.ne    .Lre_crc_byte
    cbnz    w12, .Lre_crc_done
    mov     w12, #1
    add     x6, x6, #8
    add     x7, x2, #HKE_XNU_RECORD_BYTES
    b       .Lre_crc_byte
.Lre_crc_done:
    mvn     w5, w5
    str     w5, [x13, #24]
    dsb     sy
    ldr     w5, =A51_RECOVERY_COMMIT
    str     w5, [x13, #28]
    dsb     sy
    /* start=size yields the unwrapped data in persistent_ram_save_old(). */
    str     w2, [x4, #4]
    str     w2, [x4, #8]
    str     w14, [x3, #4]
    str     w14, [x3, #8]
    dsb     sy
    ldr     w5, =0x43474244
    str     w5, [x4]
    str     w5, [x3]
    dsb     sy
    mov     x0, #0
    ret
.Lre_invalid:
    mov     x0, #-22
    ret
    .size a51_recovery_export, . - a51_recovery_export
