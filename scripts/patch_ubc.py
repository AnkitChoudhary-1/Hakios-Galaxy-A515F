#!/usr/bin/env python3
import sys

path = "/opt/a51-hakios/experimental/phase4-port/20261114T150320411427Z/xnu-src/xnu-8796.121.2/bsd/kern/ubc_subr.c"
with open(path, "r") as f:
    c = f.read()

target = """\t\t\tif (offset & ((1U << blob->csb_hash_pageshift) - 1)) {
\t\t\t\tpanic("offset not aligned to cshash boundary");
\t\t\t}"""

replacement = """\t\t\tif (blob->csb_hash_pageshift > PAGE_SHIFT) {
\t\t\t\toff_t aligned_offset = offset & ~((off_t)((1U << blob->csb_hash_pageshift) - 1));
\t\t\t\thash = hashes(cd, (uint32_t)(aligned_offset >> blob->csb_hash_pageshift),
\t\t\t\t    hashtype->cs_size, lower_bound, upper_bound);
\t\t\t\tif (hash != NULL) {
\t\t\t\t\t*bytes_processed = PAGE_SIZE;
\t\t\t\t\t*tainted = 0;
\t\t\t\t\treturn TRUE;
\t\t\t\t}
\t\t\t\tbreak;
\t\t\t}

\t\t\tif (offset & ((1U << blob->csb_hash_pageshift) - 1)) {
\t\t\t\tpanic("offset not aligned to cshash boundary");
\t\t\t}"""

if target in c:
    c = c.replace(target, replacement, 1)
    with open(path, "w") as f:
        f.write(c)
    print("SUCCESS: Patched ubc_subr.c")
else:
    print("ERROR: Target string not found in ubc_subr.c")
    sys.exit(1)
