/* SPDX-License-Identifier: MIT */
/* Mutate the report consumed by XNU and Darwin PID 1. No hardware is modeled. */
#include <limits.h>
#include <stdio.h>
#include <stdlib.h>
#include "hakios.a51.h"
#include <string.h>

static unsigned int cases, checks;

static void
check(int condition, const char *name)
{
    cases++;
    checks++;
    if (!condition) {
        fprintf(stderr, "reporting case failed: %s\n", name);
        exit(1);
    }
}

static struct hakios_a51_ufs_transfer_result
successful_report(unsigned int blocks)
{
    struct hakios_a51_ufs_transfer_result r = {0};
    r.lba = 27792;
    r.blocks = blocks;
    r.lifecycle = HAKIOS_A51_UFS_SUCCESS;
    r.stages = HAKIOS_A51_UFS_SUCCESS_STAGES;
    r.transaction = 0x21;
    r.prdt_count = 1;
    r.prdt_bytes = 128;
    r.elapsed_us = 300;
    return r;
}

#define REJECT_FIELD(field, value) do { \
    struct hakios_a51_ufs_transfer_result changed = original; \
    changed.field = (value); \
    check(!hakios_a51_ufs_transfer_valid(&changed, blocks), #field); \
} while (0)

int
main(void)
{
    check(!hakios_a51_ufs_transfer_valid(NULL, 1), "null single report");
    check(!hakios_a51_ufs_transfer_valid(NULL, 16), "null multi report");
    for (unsigned int blocks = 1; blocks <= 16; blocks += 15) {
        struct hakios_a51_ufs_transfer_result original = successful_report(blocks);
        check(hakios_a51_ufs_transfer_valid(&original, blocks), "complete report");
        check(!hakios_a51_ufs_transfer_valid(&original, blocks == 1 ? 16 : 1),
            "one-block report cannot satisfy multi command");
        const unsigned int unsupported[] = {0, 2, 15, 17, UINT_MAX};
        for (unsigned int i = 0; i < sizeof(unsupported) / sizeof(unsupported[0]); i++) {
            check(!hakios_a51_ufs_transfer_valid(&original, unsupported[i]),
                "unsupported intended command size");
        }
        REJECT_FIELD(lba, 27791);
        REJECT_FIELD(lba, 27793);
        REJECT_FIELD(blocks, 0);
        REJECT_FIELD(blocks, 2);
        REJECT_FIELD(blocks, UINT_MAX);
        REJECT_FIELD(rc, -110);
        REJECT_FIELD(rc, -71);
        REJECT_FIELD(rc, 1);
        REJECT_FIELD(ocs, 7);
        REJECT_FIELD(ocs, 15);
        for (unsigned int stage = 1; stage <= 7; stage++) {
            REJECT_FIELD(stages, original.stages & ~(1u << stage));
        }
        REJECT_FIELD(stages, original.stages | 1u);
        REJECT_FIELD(stages, original.stages | (1u << 8));
        const unsigned int lifecycle[] = {1, 2, 4, 16};
        for (unsigned int i = 0; i < sizeof(lifecycle) / sizeof(lifecycle[0]); i++) {
            REJECT_FIELD(lifecycle, original.lifecycle & ~lifecycle[i]);
        }
        REJECT_FIELD(lifecycle, original.lifecycle | HAKIOS_A51_UFS_QUARANTINED);
        REJECT_FIELD(lifecycle, original.lifecycle | 32u);
        REJECT_FIELD(transaction, 0x20);
        REJECT_FIELD(transaction, 0x22);
        REJECT_FIELD(response, 1);
        REJECT_FIELD(status, 2);
        REJECT_FIELD(residual, 1);
        REJECT_FIELD(sense_length, 18);
        REJECT_FIELD(prdt_count, 0);
        REJECT_FIELD(prdt_count, 2);
        REJECT_FIELD(prdt_count, 16);
        REJECT_FIELD(prdt_bytes, 64);
        REJECT_FIELD(prdt_bytes, 127);
        REJECT_FIELD(prdt_bytes, 256);
        if (blocks == 16) REJECT_FIELD(prdt_bytes, blocks * 128);
        REJECT_FIELD(elapsed_us, 0);
        REJECT_FIELD(elapsed_us, 5000001ULL);
        REJECT_FIELD(elapsed_us, ULLONG_MAX);
        original.elapsed_us = 1;
        check(hakios_a51_ufs_transfer_valid(&original, blocks), "lower time boundary");
        original.elapsed_us = 5000000;
        check(hakios_a51_ufs_transfer_valid(&original, blocks), "upper time boundary");
        original.sha256[0] = 0xff;
        check(hakios_a51_ufs_transfer_valid(&original, blocks),
            "digest requires independent known-content comparison");
    }
    /* Display ABI reporting validation (D1-R6) */
    check(!hakios_a51_display_diag_valid(NULL), "null display diag");
    struct hakios_a51_display_diag disp = {0};
    disp.version = HAKIOS_A51_DISPLAY_ABI_VERSION;
    disp.fb_pa = 0x80000000ULL;
    disp.width = 1080u;
    disp.height = 2400u;
    disp.stride = 4320u;
    disp.bpp = 32u;
    disp.decon_online = 1u;
    disp.dsim_online = 1u;
    disp.initial_brightness = 200u;
    disp.current_brightness = 200u;
    disp.pattern_drawn = 1u;
    disp.brightness_steps_done = 5u;
    disp.rc = 0;
    const unsigned int valid_steps[5] = {50u, 120u, 200u, 255u, 180u};
    const unsigned short valid_10bit[5] = {173u, 424u, 776u, 1023u, 686u};
    for (unsigned int i = 0; i < 5u; i++) {
        disp.brightness_history[i] = valid_steps[i];
        disp.step_10bit_values[i] = valid_10bit[i];
        disp.step_timestamps[i] = 1000ULL + (unsigned long long)i * 600000ULL;
    }
    check(hakios_a51_display_diag_valid(&disp), "valid display diag");

    /* Out of range / crossing 4 GiB fb_pa */
    disp.fb_pa = 0x10000000ULL;
    check(!hakios_a51_display_diag_valid(&disp), "out of range low fb_pa");
    disp.fb_pa = 0x100000000ULL;
    check(!hakios_a51_display_diag_valid(&disp), "above 32-bit fb_pa rejected (D1-R6)");
    disp.fb_pa = 0xFFFFF000ULL;
    check(!hakios_a51_display_diag_valid(&disp), "crossing 4 GiB fb_pa rejected (D1-R2, D1-R6)");
    disp.fb_pa = 0x80000001ULL;
    check(!hakios_a51_display_diag_valid(&disp), "unaligned fb_pa rejected (D1-R6)");
    disp.fb_pa = 0x80000000ULL;

    /* Version check */
    disp.version = 0;
    check(!hakios_a51_display_diag_valid(&disp), "invalid display version");
    disp.version = HAKIOS_A51_DISPLAY_ABI_VERSION;

    /* Step count check */
    disp.brightness_steps_done = 4;
    check(!hakios_a51_display_diag_valid(&disp), "incomplete brightness steps");
    disp.brightness_steps_done = 5;

    /* Unrestored brightness rejected */
    disp.current_brightness = 50;
    check(!hakios_a51_display_diag_valid(&disp), "unrestored brightness rejected");
    disp.current_brightness = 200;

    /* Equal UINT_MAX sentinels rejected (D1-R6) */
    disp.initial_brightness = disp.current_brightness = 0xFFFFFFFFu;
    check(!hakios_a51_display_diag_valid(&disp), "equal unknown UINT_MAX brightness rejected (D1-R6)");
    disp.initial_brightness = disp.current_brightness = 200;

    /* 50 ms intervals rejected (D1-R6) */
    for (unsigned int i = 0; i < 5u; i++) {
        disp.step_timestamps[i] = 1000ULL + (unsigned long long)i * 50000ULL;
    }
    check(!hakios_a51_display_diag_valid(&disp), "50ms intervals rejected (D1-R6)");

    /* Zero timestamps rejected (D1-R6) */
    memset(disp.step_timestamps, 0, sizeof(disp.step_timestamps));
    check(!hakios_a51_display_diag_valid(&disp), "zero timestamps rejected (D1-R6)");
    for (unsigned int i = 0; i < 5u; i++) {
        disp.step_timestamps[i] = 1000ULL + (unsigned long long)i * 600000ULL;
    }

    /* Zero history rejected (D1-R6) */
    memset(disp.brightness_history, 0, sizeof(disp.brightness_history));
    check(!hakios_a51_display_diag_valid(&disp), "zero history rejected (D1-R6)");
    for (unsigned int i = 0; i < 5u; i++) {
        disp.brightness_history[i] = valid_steps[i];
    }

    /* Invalid raw 10-bit values rejected (D1-R6) */
    disp.step_10bit_values[0] = 65535;
    check(!hakios_a51_display_diag_valid(&disp), "raw values > 1023 rejected (D1-R6)");
    disp.step_10bit_values[0] = valid_10bit[0];

    /* Input ABI reporting validation */
    check(!hakios_a51_input_diag_valid(NULL), "null input diag");
    struct hakios_a51_input_diag inp = {0};
    inp.version = HAKIOS_A51_INPUT_ABI_VERSION;
    inp.queue_events_count = 16;
    check(hakios_a51_input_diag_valid(&inp), "valid input diag");
    inp.version = 0;
    check(!hakios_a51_input_diag_valid(&inp), "invalid input version 0");
    inp.version = 1;
    check(!hakios_a51_input_diag_valid(&inp), "invalid input version 1");
    inp.version = 2;
    check(!hakios_a51_input_diag_valid(&inp), "invalid input version 2");
    inp.version = HAKIOS_A51_INPUT_ABI_VERSION;
    inp.queue_events_count = 17;
    check(!hakios_a51_input_diag_valid(&inp), "overflowed input queue count");
    check(sizeof(struct hakios_a51_input_diag) == 600, "input diag ABI v3 size 600 bytes");

    printf("{\"suite\":\"reporting\",\"passed\":true,\"cases\":%u,\"checks\":%u}\n", cases, checks);

    return 0;
}
