/* SPDX-License-Identifier: MIT */
/*
 * phase4_interactive_test.c - Disabled Darwin ARM64 PID 1 software model
 *
 * Display fills use a local 16x16 buffer; touch and keys are injected;
 * storage signatures and panel brightness come from software fixtures.
 * These exercises cannot establish any physical Phase 4 acceptance gate.
 * Timer syscalls retain their separate measured checks if this program runs.
 * Keep the disabled driver builder disabled; use the guarded platform probe
 * for current host/QEMU integration.
 */

typedef unsigned long u64;

void bzero(void *out, unsigned long size)
{
    volatile unsigned char *p = (volatile unsigned char *)out;
    while (size--) { *p++ = 0; }
}

#define SYS_exit          1
#define SYS_read          3
#define SYS_write         4
#define SYS_open          5
#define SYS_close         6
#define SYS_getpid        20
#define SYS_getuid        24
#define SYS_select        93
#define SYS_gettimeofday  116
#define SYS_sysctlbyname  274

#define O_RDONLY          0
#define O_WRONLY          1
#define O_RDWR            2

/* Darwin syscall dispatch with carry-flag error normalization */
static long call(long num, long a, long b, long c, long d, long e, long f)
{
    register long x16 __asm__("x16") = num;
    register long x0  __asm__("x0")  = a;
    register long x1  __asm__("x1")  = b;
    register long x2  __asm__("x2")  = c;
    register long x3  __asm__("x3")  = d;
    register long x4  __asm__("x4")  = e;
    register long x5  __asm__("x5")  = f;
    __asm__ volatile (
        "svc #0x80\n\t"
        "cneg x0, x0, cs"
        : "+r" (x0), "+r" (x1), "+r" (x2), "+r" (x3), "+r" (x4), "+r" (x5)
        : "r" (x16)
        : "memory", "cc"
    );
    return x0;
}

static unsigned length(const char *s)
{
    unsigned n = 0;
    while (s && s[n]) { n++; }
    return n;
}

static void put(int fd, const char *s)
{
    unsigned remaining = length(s);
    while (remaining) {
        long n = call(SYS_write, fd, (long)s, remaining, 0, 0, 0);
        if (n <= 0 || (u64)n > remaining) { return; }
        s += n;
        remaining -= (unsigned)n;
    }
}

static void number(int fd, long v)
{
    char buf[24];
    unsigned i = sizeof(buf);
    u64 n = v < 0 ? 0UL - (u64)v : (u64)v;
    buf[--i] = 0;
    do { buf[--i] = (char)('0' + n % 10); n /= 10; } while (n);
    if (v < 0) { buf[--i] = '-'; }
    put(fd, buf + i);
}

static void hex(int fd, u64 n)
{
    char buf[19];
    unsigned i = sizeof(buf);
    buf[--i] = 0;
    do { buf[--i] = "0123456789abcdef"[n & 15]; n >>= 4; } while (n);
    buf[--i] = 'x'; buf[--i] = '0';
    put(fd, buf + i);
}

static long sysctl(const char *name, void *out, u64 *size)
{
    return call(SYS_sysctlbyname, (long)name, length(name), (long)out, (long)size, 0, 0);
}

static long integer(const char *name, int *out)
{
    u64 size = sizeof(*out);
    long result = sysctl(name, out, &size);
    return result ? result : (size == sizeof(*out) ? 0 : -1);
}

static long quad(const char *name, u64 *out)
{
    u64 size = sizeof(*out);
    long result = sysctl(name, out, &size);
    return result ? result : (size == sizeof(*out) ? 0 : -1);
}

/* user64_timeval: 64-bit seconds, 32-bit microseconds, 4 padding bytes */
struct timeval {
    long sec;
    int  usec;
    int  padding;
};

static long now(long *us)
{
    struct timeval tv = {0, 0, 0};
    long result = call(SYS_gettimeofday, (long)&tv, 0, 0, 0, 0, 0);
    if (result) { return result; }
    if (tv.sec < 0 || tv.sec > 9000000000000L || tv.usec < 0 || tv.usec >= 1000000) { return -1; }
    *us = tv.sec * 1000000L + tv.usec;
    return 0;
}

/* Forward-declare the test driver components */
#include "../drivers/display/ExynosDECON.h"
#include "../drivers/display/ExynosDSIM.h"
#include "../drivers/input/MelfasTouchDriver.h"
#include "../drivers/input/ExynosKeyDriver.h"
#include "../drivers/storage/ExynosUFSHost.h"
#include "../drivers/storage/ExynosUFSBlockDevice.h"

void start(void)
{
    long opened = call(SYS_open, (long)"/dev/console", O_RDWR, 0, 0, 0, 0);
    int fd = opened < 0 ? 1 : (int)opened;
    long pid = call(SYS_getpid, 0, 0, 0, 0, 0, 0);
    long uid = call(SYS_getuid, 0, 0, 0, 0, 0, 0);

    put(fd, "\nHello from user space on Darwin!\n");
    put(fd, "HAKIOS_USER_BEGIN pid="); number(fd, pid);
    put(fd, " uid="); number(fd, uid); put(fd, " console="); number(fd, opened); put(fd, "\n");
    put(fd, "HAKIOS_A51_REPORTING version=1\n");
    put(fd, "HAKIOS_MODEL_SCOPE peripherals=synthetic physical_phase4=unverified\n");

    /* 1. Print kernel bootargs & nonce */
    char bootargs[700] = {0};
    u64 basz = sizeof(bootargs) - 1;
    long args_rc = sysctl("kern.bootargs", bootargs, &basz);
    bootargs[sizeof(bootargs) - 1] = 0;
    if (args_rc == 0) {
        put(fd, "kern.bootargs="); put(fd, bootargs); put(fd, "\n");
        const char *key = "hakios_run_nonce=";
        unsigned klen = length(key);
        for (unsigned i = 0; bootargs[i]; i++) {
            if (i && bootargs[i - 1] != ' ') { continue; }
            unsigned match = 1;
            for (unsigned j = 0; j < klen; j++) {
                if (bootargs[i + j] != key[j]) { match = 0; break; }
            }
            if (match) {
                char nonce[64] = {0};
                unsigned n = 0;
                while (bootargs[i + klen + n] && bootargs[i + klen + n] != ' ' && n < 63) {
                    nonce[n] = bootargs[i + klen + n];
                    n++;
                }
                put(fd, "HAKIOS_RUN_NONCE="); put(fd, nonce); put(fd, "\n");
                break;
            }
        }
    }

    /* Print platform info */
    int gic = 0, cores = 0;
    u64 midr = 0;
    integer("kern.hakios.gic_version", &gic);
    integer("hw.ncpu", &cores);
    quad("kern.hakios.boot_midr", &midr);
    put(fd, "HAKIOS_PLATFORM gic="); number(fd, gic);
    put(fd, " cores="); number(fd, cores); put(fd, " midr="); hex(fd, midr); put(fd, "\n");

    int overall_pass = 1;

    /* 2. Local-buffer raster model */
    put(fd, "[Model Step 1] Filling a local 16x16 pixel buffer...\n");
    ExynosDECONDevice decon;
    uint32_t local_test_fb[256];
    bzero(local_test_fb, sizeof(local_test_fb));
    ExynosDECON_Init(&decon, 0, (void *)0);
    decon.fb_phys_addr = 0;
    decon.fb_virt_addr = local_test_fb;
    decon.width = 16;
    decon.height = 16;
    decon.stride = 64;
    decon.bpp = 32;

    /* Exercise DECON raster fill routine safely in userland memory */
    ExynosDECON_FillRect(&decon, 0, 0, 16, 16, 0x00FF00);

    put(fd, "HAKIOS_MODEL_DISPLAY_FILL buffer=user_memory width="); number(fd, decon.width);
    put(fd, " height="); number(fd, decon.height);
    put(fd, " bpp="); number(fd, decon.bpp);
    put(fd, " stride="); number(fd, decon.stride);
    put(fd, "\n");

    ExynosDSIMDevice dsim;
    ExynosDSIM_Init(&dsim, 0);
    ExynosDSIM_SetPanelBrightness(&dsim, 220);
    put(fd, "HAKIOS_MODEL_BRIGHTNESS_STATE requested=220 stored=");
    number(fd, dsim.current_brightness); put(fd, "\n");

    /* 3. Injected touch packet model */
    put(fd, "[Model Step 2] Decoding an injected touch packet...\n");
    MelfasTouchDevice touch;
    MelfasTouch_Init(&touch, 0);
    /* Synthetic touch packet: down at (540, 1200) with pressure 180 */
    uint8_t synthetic_touch_pkt[6] = {
        0x10 | 0x00, /* Action=1 (Down), Finger=0 */
        (uint8_t)(540 & 0xFF),
        (uint8_t)(1200 & 0xFF),
        (uint8_t)(((1200 >> 8) << 4) | (540 >> 8)),
        180,         /* Pressure */
        0            /* Flags */
    };
    int touch_rc = MelfasTouch_DecodePacket(&touch, synthetic_touch_pkt, 6);
    uint16_t tx = 0, ty = 0;
    bool tdown = false;
    MelfasTouch_GetPrimaryTouch(&touch, &tx, &ty, &tdown);
    put(fd, "HAKIOS_MODEL_TOUCH_PACKET source=injected");
    put(fd, " rc="); number(fd, touch_rc);
    put(fd, " x="); number(fd, tx);
    put(fd, " y="); number(fd, ty);
    put(fd, " down="); number(fd, tdown ? 1 : 0); put(fd, "\n");
    if (touch_rc != 0 || tx != 540 || ty != 1200 || !tdown) {
        overall_pass = 0;
    }

    /* 4. Injected key state model */
    put(fd, "[Model Step 3] Counting injected key transitions...\n");
    ExynosKeyDevice keys;
    ExynosKey_Init(&keys, 0);
    ExynosKey_UpdateRaw(&keys, true, false, false); /* Power pressed */
    ExynosKey_UpdateRaw(&keys, false, true, false); /* Vol+ pressed */
    ExynosKey_UpdateRaw(&keys, false, false, true); /* Vol- pressed */
    put(fd, "HAKIOS_MODEL_KEYS source=injected power="); number(fd, KEY_POWER);
    put(fd, " volup="); number(fd, KEY_VOLUMEUP);
    put(fd, " voldown="); number(fd, KEY_VOLUMEDOWN);
    put(fd, " power_count="); number(fd, ExynosKey_GetPressCount(&keys, KEY_POWER));
    put(fd, " volup_count="); number(fd, ExynosKey_GetPressCount(&keys, KEY_VOLUMEUP));
    put(fd, " voldown_count="); number(fd, ExynosKey_GetPressCount(&keys, KEY_VOLUMEDOWN));
    put(fd, "\n");

    /* 5. Software storage fixture and write-rejection model */
    put(fd, "[Model Step 4] Checking the software storage fixture...\n");
    ExynosUFSBlockDevice ufs_dev;
    ExynosUFSBlockDevice_Init(&ufs_dev, 0);

    /* Test sector read */
    uint8_t sector_buf[4096];
    bzero(sector_buf, sizeof(sector_buf));
    int read_rc = ExynosUFSBlockDevice_ReadBlocks(&ufs_dev, 0, 1, sector_buf);

    /* Check only the model fixture signature, not known hardware image contents. */
    int sig_match = (sector_buf[0] == 'H' && sector_buf[1] == 'A' &&
                     sector_buf[2] == 'K' && sector_buf[3] == 'I' &&
                     sector_buf[4] == 'O' && sector_buf[5] == 'S' &&
                     sector_buf[6] == 'R' && sector_buf[7] == 'O' &&
                     sector_buf[510] == 0x55 && sector_buf[511] == 0xAA);
    put(fd, "HAKIOS_MODEL_STORAGE_SIGNATURE fixture=HAKIOSRO valid=");
    number(fd, sig_match ? 1 : 0); put(fd, "\n");

    /* Test write prohibition: MUST fail with UFS_ERR_WRITE_PROHIBITED (-30) */
    int write_rc = ExynosUFSBlockDevice_WriteBlocks(&ufs_dev, 0, 1, sector_buf);

    put(fd, "HAKIOS_MODEL_STORAGE_STATE total_blocks=");
    number(fd, ufs_dev.total_blocks);
    put(fd, " read_rc="); number(fd, read_rc);
    put(fd, " write_rc="); number(fd, write_rc);
    put(fd, " ro_lock="); number(fd, ExynosUFSBlockDevice_IsWritable(&ufs_dev) ? 0 : 1);
    put(fd, " writes_rejected="); number(fd, ufs_dev.host.writes_rejected);
    put(fd, "\n");

    if (read_rc != 0 || write_rc != UFS_ERR_WRITE_PROHIBITED || !sig_match) {
        overall_pass = 0;
    }

    /* 6. Monotonic Timer Verification (3 samples of 1-second select) */
    put(fd, "[Timer Check] Measuring three select intervals...\n");
    int timer_pass = 1;
    for (int sample = 1; sample <= 3; sample++) {
        u64 irq_before = 0, irq_after = 0;
        long start_us = 0, end_us = 0;
        long before_rc = quad("kern.hakios.timer_irqs", &irq_before);
        long start_rc = now(&start_us);
        struct timeval timeout = {1, 0, 0};
        long sleep_rc = call(SYS_select, 0, 0, 0, 0, (long)&timeout, 0);
        long end_rc = now(&end_us);
        long after_rc = quad("kern.hakios.timer_irqs", &irq_after);
        long elapsed = end_us - start_us;

        int ok = (sleep_rc == 0 && elapsed >= 900000L && elapsed <= 3000000L &&
                  irq_after > irq_before && !before_rc && !after_rc && !start_rc && !end_rc);

        put(fd, "HAKIOS_TIMER_SAMPLE index="); number(fd, sample);
        put(fd, " select_rc="); number(fd, sleep_rc);
        put(fd, " elapsed_us="); number(fd, elapsed);
        put(fd, " irq_before="); number(fd, (long)irq_before);
        put(fd, " irq_after="); number(fd, (long)irq_after);
        put(fd, " read_rc="); number(fd, before_rc | after_rc | start_rc | end_rc);
        put(fd, " pass="); number(fd, ok ? 1 : 0); put(fd, "\n");
        if (!ok) {
            timer_pass = 0;
        }
    }

    if (!timer_pass) {
        overall_pass = 0;
    }

    if (timer_pass) {
        put(fd, "HAKIOS_TIMER_PASS samples=3\n");
    } else {
        put(fd, "HAKIOS_TIMER_FAIL samples=3\n");
    }
    put(fd, "HAKIOS_MODEL_RESULT passed="); number(fd, overall_pass ? 1 : 0); put(fd, "\n");
    put(fd, "HAKIOS_PHASE4_PENDING display=unverified brightness=unverified touch=unverified keys=unverified known_image=host_check_required\n");
    put(fd, "HAKIOS_USER_EXIT outcome="); number(fd, overall_pass ? 0 : 1);
    put(fd, " timer_verified="); number(fd, timer_pass ? 1 : 0); put(fd, "\n");

    /* PID 1 exit cleanly triggers XNU loader return to dump DRAM log buffer */
    call(SYS_exit, overall_pass ? 0 : 1, 0, 0, 0, 0, 0);
    for (;;) { }
}

int main(void)
{
    start();
    return 0;
}
