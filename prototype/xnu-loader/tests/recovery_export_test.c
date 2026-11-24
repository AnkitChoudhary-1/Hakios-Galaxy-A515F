/* SPDX-License-Identifier: MIT */
#include <stddef.h>
#include <stdint.h>
#include "xnu_trampoline.h"
#ifndef RECOVERY_TEST_ALIGNMENT
#define RECOVERY_TEST_ALIGNMENT 1
#endif

struct recovery_case {
    const char *name;
    uintptr_t record, log, pmsg, console, stage_record, stage_log;
    uint64_t length;
    unsigned int mutation;
    int expected_rc;
    const unsigned char *expected;
    unsigned int expected_bytes;
};
#include "generated_cases.h"

extern long recovery_export_zero_stack(uintptr_t, uintptr_t, uint64_t, uintptr_t, uintptr_t);
unsigned int recovery_abi_error;
static unsigned long long checks;

static void say(const char *message)
{
    register uint64_t op __asm__("x0") = 4;
    register const char *data __asm__("x1") = message;
    __asm__ volatile("hlt #0xf000" : "+r"(op), "+r"(data) : : "memory");
}

static void say_number(unsigned long long number)
{
    char buffer[24];
    unsigned int end = sizeof(buffer) - 1;
    buffer[end] = 0;
    do { buffer[--end] = (char)('0' + number % 10); number /= 10; } while (number);
    say(buffer + end);
}

static void fill(uintptr_t address, unsigned int count, unsigned char byte)
{
    volatile unsigned char *out = (volatile unsigned char *)address;
    for (unsigned int i = 0; i < count; i++) { out[i] = byte; }
}

static void copy(uintptr_t address, const unsigned char *data, unsigned int count)
{
    volatile unsigned char *out = (volatile unsigned char *)address;
    for (unsigned int i = 0; i < count; i++) { out[i] = data[i]; }
}

static int same(uintptr_t address, const unsigned char *expected, unsigned int count)
{
    const volatile unsigned char *data = (const volatile unsigned char *)address;
    checks += count;
    for (unsigned int i = 0; i < count; i++) { if (data[i] != expected[i]) { return 0; } }
    return 1;
}

static int canary(uintptr_t address, unsigned int count, unsigned char byte)
{
    const volatile unsigned char *data = (const volatile unsigned char *)address;
    checks += count;
    for (unsigned int i = 0; i < count; i++) { if (data[i] != byte) { return 0; } }
    return 1;
}

int recovery_test_main(void)
{
    uint64_t sctlr;
    __asm__ volatile("mrs %0, sctlr_el1" : "=r"(sctlr));
    say("RECOVERY_EXPORT_SCTLR "); say_number(sctlr); say("\n");
    checks++;
    if ((sctlr & (1ULL | 2ULL | 4ULL | 0x1000ULL)) !=
        (0x1000ULL | (RECOVERY_TEST_ALIGNMENT ? 2ULL : 0ULL))) {
        say("FAIL physical_return_state\n");
        return 1;
    }
    for (unsigned int i = 0; i < sizeof(recovery_cases) / sizeof(recovery_cases[0]); i++) {
        const struct recovery_case *test = recovery_cases + i;
        unsigned char before_record[256];
        uintptr_t pmsg = test->expected_rc == 0 ? test->pmsg : A51_RECOVERY_PMSG_PA;
        uintptr_t console = test->expected_rc == 0 ? test->console : A51_RECOVERY_CONSOLE_PA;
        fill(pmsg, A51_RECOVERY_ZONE_BYTES, 0xa5);
        fill(console, A51_RECOVERY_ZONE_BYTES, 0x3c);
        unsigned int log_bytes = test->expected_bytes - 32 - 256;
        copy(test->stage_record, test->expected + 32, 256);
        copy(test->stage_log, test->expected + 32 + 256, log_bytes);
        volatile uint64_t *record = (volatile uint64_t *)test->stage_record;
        switch (test->mutation) {
            case 1: record[0] ^= 1; break;
            case 2: record[1] = 2; break;
            case 3: record[2] = 255; break;
            case 4: record[6] += 8; break;
            case 5: record[7]++; break;
        }
        for (unsigned int j = 0; j < sizeof(before_record); j++) {
            before_record[j] = ((volatile unsigned char *)test->stage_record)[j];
        }
        long rc = recovery_export_zero_stack(test->record, test->log, test->length, test->pmsg, test->console);
        int ok = rc == test->expected_rc && recovery_abi_error == 0;
        checks += 2;
        ok &= same(test->stage_record, before_record, 256);
        ok &= same(test->stage_log, test->expected + 288, log_bytes);
        if (test->expected_rc == 0) {
            uint32_t pmsg_header[3] = {0x43474244, test->expected_bytes, test->expected_bytes};
            uint32_t console_header[3] = {0x43474244, log_bytes, log_bytes};
            ok &= same(pmsg, (unsigned char *)pmsg_header, 12);
            ok &= same(pmsg + 12, test->expected, test->expected_bytes);
            ok &= canary(pmsg + 12 + test->expected_bytes,
                         A51_RECOVERY_ZONE_BYTES - 12 - test->expected_bytes, 0xa5);
            ok &= same(console, (unsigned char *)console_header, 12);
            ok &= same(console + 12, test->expected + 288, log_bytes);
            ok &= canary(console + 12 + log_bytes, A51_RECOVERY_ZONE_BYTES - 12 - log_bytes, 0x3c);
        } else {
            ok &= canary(pmsg, A51_RECOVERY_ZONE_BYTES, 0xa5);
            ok &= canary(console, A51_RECOVERY_ZONE_BYTES, 0x3c);
        }
        say(ok ? "PASS " : "FAIL "); say(test->name); say("\n");
        if (!ok) { return 1; }
    }
    say("{\"suite\":\"recovery-export\",\"cases\":");
    say_number(sizeof(recovery_cases) / sizeof(recovery_cases[0]));
    say(",\"checks\":"); say_number(checks);
    say(",\"alignment_checks\":"); say_number(RECOVERY_TEST_ALIGNMENT);
    say(",\"sctlr\":"); say_number(sctlr);
    say(",\"passed\":true}\n");
    return 0;
}
