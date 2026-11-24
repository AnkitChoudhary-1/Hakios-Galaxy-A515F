#!/usr/bin/env python3
from pathlib import Path
import shutil
import subprocess

code = """// SPDX-License-Identifier: GPL-2.0
#include <linux/init.h>
#include <linux/kernel.h>
#include <linux/module.h>
#include <linux/io.h>
#include <linux/string.h>

MODULE_LICENSE("GPL");

static void dump_bank(const char *name, unsigned long pa, size_t hdr_off, size_t text_off, size_t max_text)
{
    void __iomem *base = ioremap_cache(pa, hdr_off + max_text + 64);
    u64 hdr[4] = {0};
    static char buf[4096];
    char *line, *next;
    size_t len;

    if (!base) {
        pr_emerg("HAKIOS_%s: failed to ioremap 0x%lx\\n", name, pa);
        return;
    }

    memcpy_fromio(hdr, base + hdr_off, sizeof(hdr));
    pr_emerg("=== HAKIOS_%s_HEADER ===\\n", name);
    pr_emerg("HAKIOS_%s: magic=%016llx size=%llu log_pa=%016llx status=%llu\\n",
             name, hdr[0], hdr[1], hdr[2], hdr[3]);

    len = hdr[1];
    if (len > sizeof(buf) - 1)
        len = sizeof(buf) - 1;

    if (len > 0) {
        memset(buf, 0, sizeof(buf));
        memcpy_fromio(buf, base + text_off, len);
        buf[len] = '\\0';
        pr_emerg("=== HAKIOS_%s_TEXT (%zu bytes) ===\\n", name, len);
        line = buf;
        while (line && *line) {
            next = strchr(line, '\\n');
            if (next) *next = '\\0';
            pr_emerg("HAKIOS_LOG: %s\\n", line);
            if (next) line = next + 1;
            else break;
        }
    }
    iounmap(base);
}

static int __init probe_init(void)
{
    void __iomem *f9 = ioremap_cache(0xF9000040UL, 256);
    u64 p[32] = {0};
    int i;

    if (f9) {
        memcpy_fromio(p, f9, 256);
        for (i = 0; i < 32; i++) {
            pr_emerg("HAKIOS_XBR[%02d] = 0x%016llx (%llu)\\n", i, p[i], p[i]);
        }
        pr_emerg("HAKIOS_F9 status=%llu reason=%llu code=%llu log_pa=%016llx log_len=%llu\\n",
                 p[3], p[4], p[5], p[6], p[7]);
        iounmap(f9);
    }

    // Dump GNSS bank (0xFB000000)
    dump_bank("GNSS", 0xFB000000UL, 0x1E0, 0x200, 4000);

    // Dump Safe DRAM bank (0x8F000000)
    dump_bank("8F_DRAM", 0x8F000000UL, 0x140, 0x160, 4000);

    // Dump DSS bank (0xF9000000)
    dump_bank("DSS", 0xF9000000UL, 0x140, 0x160, 400);

    // If log_pa was recorded and valid DRAM
    if (p[6] >= 0x80000000UL && p[6] < 0xC0000000UL && p[7] > 0) {
        size_t len = p[7];
        void __iomem *dram;
        static char kbuf[4096];
        char *line, *next;
        if (len > sizeof(kbuf) - 1) len = sizeof(kbuf) - 1;
        dram = ioremap_cache(p[6], len + 64);
        if (dram) {
            memset(kbuf, 0, sizeof(kbuf));
            memcpy_fromio(kbuf, dram, len);
            kbuf[len] = '\\0';
            pr_emerg("=== HAKIOS_DIRECT_DRAM_LOG (%zu bytes from 0x%llx) ===\\n", len, p[6]);
            line = kbuf;
            while (line && *line) {
                next = strchr(line, '\\n');
                if (next) *next = '\\0';
                pr_emerg("HAKIOS_DRAM: %s\\n", line);
                if (next) line = next + 1;
                else break;
            }
            iounmap(dram);
        }
    }

    return 0;
}

static void __exit probe_exit(void) {}
module_init(probe_init);
module_exit(probe_exit);
"""

src_path = Path("/opt/a51-hakios/diagnostics/early-probe/early_probe.c")
src_path.write_text(code, encoding="utf-8")

cmd = [
    "make", "-C", "/opt/a51-everline/src", "O=/opt/a51-everline/out",
    "M=/opt/a51-hakios/diagnostics/early-probe", "ARCH=arm64", "LLVM=1",
    "LLVM_IAS=1", "CC=clang", "LD=ld.lld", "AR=llvm-ar", "NM=llvm-nm",
    "OBJCOPY=llvm-objcopy", "OBJDUMP=llvm-objdump", "READELF=llvm-readelf",
    "CROSS_COMPILE=aarch64-linux-gnu-", "CROSS_COMPILE_ARM32=arm-linux-gnueabi-",
    "CLANG_TRIPLE=aarch64-linux-gnu-", "-j4", "modules"
]
subprocess.run(cmd, check=True)
shutil.copy("/opt/a51-hakios/diagnostics/early-probe/early_probe.ko", "/mnt/c/Users/Ankit/Desktop/A51/hakios-a51/artifacts/early_probe.ko")
print("SUCCESS: Built and copied early_probe.ko")
