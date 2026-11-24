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

static int __init probe_init(void)
{
    void __iomem *f9 = ioremap_cache(0xF9000040UL, 256);
    u64 p[32] = {0};
    int i;
    if (f9) {
        memcpy_fromio(p, f9, 256);
        for (i = 0; i < 32; i++) {
            pr_emerg("XBR[%02d] = 0x%016llx (%llu)\\n", i, p[i], p[i]);
        }
        iounmap(f9);
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
print("SUCCESS: Built xbr dumper")
