/* SPDX-License-Identifier: MIT */
#ifndef RECOVERY_TEST_ALIGNMENT
#define RECOVERY_TEST_ALIGNMENT 1
#endif
    .section .text.entry, "ax", %progbits
    .global _start
_start:
    msr daifset, #0xf
    adrp x9, recovery_test_vectors
    add x9, x9, :lo12:recovery_test_vectors
    msr vbar_el1, x9
    isb
    adrp x9, recovery_test_stack_top
    add x9, x9, :lo12:recovery_test_stack_top
    mov sp, x9
    /* Match the production physical return path, including I-cache enabled.
     * Exercise alignment checking explicitly rather than inheriting QEMU's
     * reset value. Vectors are physical and installed before this transition.
     */
    mrs x9, sctlr_el1
    bic x9, x9, #1
    bic x9, x9, #4
    bic x9, x9, #2
#if RECOVERY_TEST_ALIGNMENT
    orr x9, x9, #2
#endif
    orr x9, x9, #0x1000
    msr sctlr_el1, x9
    isb
    bl recovery_test_main
    mov x2, x0
    adr x1, .Lexit_args
    str x2, [x1, #8]
    mov w0, #0x20
    hlt #0xf000
1:  wfi
    b 1b

/* Call the production leaf with SP=0 and check the AAPCS callee registers.
 * Restore SP from memory even when a broken exporter corrupts x19.
 */
    .global recovery_export_zero_stack
recovery_export_zero_stack:
    stp x19, x20, [sp, #-96]!
    stp x21, x22, [sp, #16]
    stp x23, x24, [sp, #32]
    stp x25, x26, [sp, #48]
    stp x27, x28, [sp, #64]
    stp x29, x30, [sp, #80]
    mov x19, sp
    adrp x9, recovery_saved_sp
    str x19, [x9, :lo12:recovery_saved_sp]
    mov x20, #0x120
    mov x21, #0x121
    mov x22, #0x122
    mov x23, #0x123
    mov x24, #0x124
    mov x25, #0x125
    mov x26, #0x126
    mov x27, #0x127
    mov x28, #0x128
    mov x29, #0x129
    mov x9, #0
    mov sp, x9
    bl a51_recovery_export
    mov x9, sp
    mov w12, #1
    cbnz x9, .Labi_done
    adrp x9, recovery_saved_sp
    ldr x9, [x9, :lo12:recovery_saved_sp]
    cmp x19, x9
    b.ne .Labi_done
    cmp x20, #0x120
    b.ne .Labi_done
    cmp x21, #0x121
    b.ne .Labi_done
    cmp x22, #0x122
    b.ne .Labi_done
    cmp x23, #0x123
    b.ne .Labi_done
    cmp x24, #0x124
    b.ne .Labi_done
    cmp x25, #0x125
    b.ne .Labi_done
    cmp x26, #0x126
    b.ne .Labi_done
    cmp x27, #0x127
    b.ne .Labi_done
    cmp x28, #0x128
    b.ne .Labi_done
    cmp x29, #0x129
    b.ne .Labi_done
    mov w12, #0
.Labi_done:
    adrp x9, recovery_abi_error
    str w12, [x9, :lo12:recovery_abi_error]
    adrp x9, recovery_saved_sp
    ldr x9, [x9, :lo12:recovery_saved_sp]
    mov sp, x9
    ldp x21, x22, [sp, #16]
    ldp x23, x24, [sp, #32]
    ldp x25, x26, [sp, #48]
    ldp x27, x28, [sp, #64]
    ldp x29, x30, [sp, #80]
    ldp x19, x20, [sp], #96
    ret

    .balign 2048
recovery_test_vectors:
    .rept 16
    b .Lexception
    .balign 128
    .endr
.Lexception:
    adr x1, .Lexception_text
    mov w0, #4
    hlt #0xf000
    adr x1, .Lexception_exit
    mov w0, #0x20
    hlt #0xf000
2:  wfi
    b 2b
    .section .data
    .balign 8
.Lexit_args: .quad 0x20026, 0
.Lexception_exit: .quad 0x20026, 1
.Lexception_text: .asciz "RECOVERY_EXPORT_EXCEPTION\n"
    .section .bss
    .balign 8
recovery_saved_sp: .skip 8
    .balign 16
recovery_test_stack: .skip 16384
recovery_test_stack_top:
