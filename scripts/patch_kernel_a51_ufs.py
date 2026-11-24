#!/usr/bin/env python3
"""Patch XNU kernel source for A51 Exynos UFS Darwin partition support."""
from pathlib import Path

REPO = Path("/opt/a51-hakios/experimental/phase4-port/20261114T150320411427Z")

# 1. Update drivers/core/a51_ufs_readonly.h
hdr_path = REPO / "drivers/core/a51_ufs_readonly.h"
content = hdr_path.read_text(encoding="utf-8")

if "A51_UFS_DARWIN_LBA" not in content:
    content = content.replace(
        "#define A51_UFS_BOOT_BLOCKS 15104u\n",
        "#define A51_UFS_BOOT_BLOCKS 15104u\n#define A51_UFS_DARWIN_LBA 28614144u\n#define A51_UFS_DARWIN_BLOCKS 2621947u\n"
    )

old_check = (
    "        (reading && (!blocks || blocks > A51_UFS_MAX_BLOCKS || lba < A51_UFS_BOOT_LBA ||\n"
    "        lba - A51_UFS_BOOT_LBA > A51_UFS_BOOT_BLOCKS - blocks)) ||\n"
    "        (nodata && (lba || blocks))) { return A51_UFS_INVAL; }"
)

new_check = (
    "        (reading && (!blocks || blocks > A51_UFS_MAX_BLOCKS ||\n"
    "        !((lba >= A51_UFS_BOOT_LBA && lba - A51_UFS_BOOT_LBA <= A51_UFS_BOOT_BLOCKS - blocks) ||\n"
    "          (lba >= A51_UFS_DARWIN_LBA && lba - A51_UFS_DARWIN_LBA <= A51_UFS_DARWIN_BLOCKS - blocks)))) ||\n"
    "        (nodata && (lba || blocks))) { return A51_UFS_INVAL; }"
)

if old_check in content:
    content = content.replace(old_check, new_check, 1)
    print("Patched a51_ufs_readonly.h LBA check")
elif new_check in content:
    print("a51_ufs_readonly.h already has Darwin LBA check")
else:
    print("Warning: old_check not found in a51_ufs_readonly.h")

hdr_path.write_text(content, encoding="utf-8")
print("Wrote drivers/core/a51_ufs_readonly.h")

# 2. Update drivers/core/hakios.a51.h
h_path = REPO / "drivers/core/hakios.a51.h"
h_content = h_path.read_text(encoding="utf-8")
if "hakios_a51_ufs_read" not in h_content:
    h_content = h_content.replace(
        "#endif\n",
        "int hakios_a51_ufs_read(unsigned int lba, unsigned int blocks, void *dst);\n\n#endif\n"
    )
    h_path.write_text(h_content, encoding="utf-8")
    print("Added hakios_a51_ufs_read to hakios.a51.h")
else:
    print("hakios_a51_ufs_read already in hakios.a51.h")

# Also update userland/src/hakios.a51.h and userland/hakios.a51.h
for u_path in [REPO / "userland/src/hakios.a51.h", REPO / "userland/hakios.a51.h"]:
    if u_path.exists():
        u_content = u_path.read_text(encoding="utf-8")
        if "hakios_a51_ufs_read" not in u_content:
            u_content = u_content.replace(
                "#endif\n",
                "int hakios_a51_ufs_read(unsigned int lba, unsigned int blocks, void *dst);\n\n#endif\n"
            )
            u_path.write_text(u_content, encoding="utf-8")

# 3. Update drivers/core/hakios.a51.c
c_path = REPO / "drivers/core/hakios.a51.c"
c_content = c_path.read_text(encoding="utf-8")
if "hakios_a51_ufs_read" not in c_content:
    read_func = """static bool a51_ufs_activated = false;

int
hakios_a51_ufs_read(unsigned int lba, unsigned int blocks, void *dst)
{
    if (!dst || blocks == 0 || blocks > A51_UFS_MAX_BLOCKS) {
        return A51_UFS_INVAL;
    }

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
    if (!ufs_va) {
        lck_mtx_unlock(&a51_lock);
        return ENXIO;
    }

    struct a51_ufs_io io = {
        (void *)ufs_va, a51_ufs_io_read, a51_ufs_io_write, a51_ufs_io_phys,
        a51_ufs_io_clean, a51_ufs_io_inval, a51_ufs_io_barrier,
        a51_ufs_io_now, a51_ufs_io_relax, NULL
    };

    if (!a51_ufs_activated) {
        int act_rc = a51_ufs_activate(&io);
        if (act_rc != 0) {
            printf("hakios_a51_ufs: activation failed: %d\\n", act_rc);
            lck_mtx_unlock(&a51_lock);
            return EIO;
        }
        a51_ufs_activated = true;
    }

    struct a51_ufs_report report;
    int rc = a51_ufs_submit(&io, &ufs_memory, A51_UFS_READ, lba, blocks, &report);
    if (rc == 0) {
        memcpy(dst, ufs_memory.data, blocks * A51_UFS_BLOCK_SIZE);
    } else {
        printf("hakios_a51_ufs: read failed at LBA %u blocks %u rc=%d ocs=%u\\n",
               lba, blocks, rc, report.ocs);
    }

    lck_mtx_unlock(&a51_lock);
    return rc ? EIO : 0;
}

"""
    target = "static int\nsysctl_a51_ufs_test("
    assert target in c_content, "sysctl_a51_ufs_test target not found"
    c_content = c_content.replace(target, read_func + target, 1)
    c_path.write_text(c_content, encoding="utf-8")
    print("Added hakios_a51_ufs_read to drivers/core/hakios.a51.c")
else:
    print("hakios_a51_ufs_read already in drivers/core/hakios.a51.c")

# 4. Update drivers/storage/hakios.ufs.c
ufs_path = REPO / "drivers/storage/hakios.ufs.c"
ufs_content = ufs_path.read_text(encoding="utf-8")

if "#if defined(HAKIOS_A51)" not in ufs_content:
    # Add includes & helpers
    top_include = '#include "hakios.ufshc.h"\n'
    a51_include = '#include "hakios.ufshc.h"\n#if defined(HAKIOS_A51)\n#include "a51_ufs_readonly.h"\n#include "hakios.a51.h"\nextern vm_offset_t pe_arm_get_soc_base_phys(void);\n#endif\n'
    assert top_include in ufs_content, "hakios.ufshc.h include not found"
    ufs_content = ufs_content.replace(top_include, a51_include, 1)

    # Add ufs_a51_read right after ufs_write_mtx
    mtx_target = 'static LCK_MTX_DECLARE(ufs_write_mtx, &ufs_lck_grp);\n'
    a51_read_impl = """static LCK_MTX_DECLARE(ufs_write_mtx, &ufs_lck_grp);

#if defined(HAKIOS_A51)
static _Alignas(4096) uint8_t a51_bounce[A51_UFS_DMA_BYTES];

static int
ufs_a51_read(uint64_t offset, uint8_t *dst, uint64_t len)
{
	uint64_t part_size = (uint64_t)A51_UFS_DARWIN_BLOCKS * A51_UFS_BLOCK_SIZE;

	if (offset > part_size || len > part_size - offset) {
		return EINVAL;
	}
	if (len == 0) {
		return 0;
	}

	uint8_t *out = dst;
	uint64_t remaining = len;
	uint64_t cur_offset = offset;

	lck_mtx_lock(&ufs_lock);
	while (remaining > 0) {
		uint64_t block_idx = cur_offset / A51_UFS_BLOCK_SIZE;
		uint32_t block_offset = (uint32_t)(cur_offset % A51_UFS_BLOCK_SIZE);
		uint32_t chunk_bytes;
		uint32_t blocks_to_read;
		int rc;

		if (block_offset != 0 || remaining < A51_UFS_BLOCK_SIZE) {
			blocks_to_read = 1;
			uint32_t avail = A51_UFS_BLOCK_SIZE - block_offset;
			chunk_bytes = (uint32_t)MIN(remaining, (uint64_t)avail);
			rc = hakios_a51_ufs_read((uint32_t)(A51_UFS_DARWIN_LBA + block_idx), 1, a51_bounce);
			if (rc != 0) {
				lck_mtx_unlock(&ufs_lock);
				return EIO;
			}
			memcpy(out, a51_bounce + block_offset, chunk_bytes);
		} else {
			uint32_t max_blocks = (uint32_t)MIN(remaining / A51_UFS_BLOCK_SIZE, (uint64_t)A51_UFS_MAX_BLOCKS);
			blocks_to_read = max_blocks;
			chunk_bytes = blocks_to_read * A51_UFS_BLOCK_SIZE;
			rc = hakios_a51_ufs_read((uint32_t)(A51_UFS_DARWIN_LBA + block_idx), blocks_to_read, a51_bounce);
			if (rc != 0) {
				lck_mtx_unlock(&ufs_lock);
				return EIO;
			}
			memcpy(out, a51_bounce, chunk_bytes);
		}
		out += chunk_bytes;
		cur_offset += chunk_bytes;
		remaining -= chunk_bytes;
	}
	lck_mtx_unlock(&ufs_lock);
	return 0;
}
#endif
"""
    assert mtx_target in ufs_content, "ufs_write_mtx not found"
    ufs_content = ufs_content.replace(mtx_target, a51_read_impl, 1)

    # Update ufs_part_bytes
    part_target = "static uint64_t\nufs_part_bytes(uint32_t part)\n{\n"
    part_replacement = """static uint64_t
ufs_part_bytes(uint32_t part)
{
#if defined(HAKIOS_A51)
	if (pe_arm_get_soc_base_phys() == 0x10000000) {
		return (uint64_t)A51_UFS_DARWIN_BLOCKS * A51_UFS_BLOCK_SIZE;
	}
#endif
"""
    assert part_target in ufs_content, "ufs_part_bytes not found"
    ufs_content = ufs_content.replace(part_target, part_replacement, 1)

    # Update ufs_read
    read_target = "static int\nufs_read(uint32_t part, uint64_t offset, uint8_t *dst, uint64_t len)\n{\n"
    read_replacement = """static int
ufs_read(uint32_t part, uint64_t offset, uint8_t *dst, uint64_t len)
{
#if defined(HAKIOS_A51)
	if (pe_arm_get_soc_base_phys() == 0x10000000) {
		return ufs_a51_read(offset, dst, len);
	}
#endif
"""
    assert read_target in ufs_content, "ufs_read not found"
    ufs_content = ufs_content.replace(read_target, read_replacement, 1)

    # Update ufs_open
    open_target = "\tif (!ufs_ready || (uint32_t)minor(dev) >= ufs_parts || (ufs_page->part[minor(dev)].flags & BLOCK_PART_UNIT)) {\n\t\treturn ENXIO;\n\t}\n"
    open_replacement = """#if defined(HAKIOS_A51)
	if (pe_arm_get_soc_base_phys() == 0x10000000) {
		if (!ufs_ready || (uint32_t)minor(dev) >= ufs_parts) {
			return ENXIO;
		}
	} else
#endif
	if (!ufs_ready || (uint32_t)minor(dev) >= ufs_parts || (ufs_page->part[minor(dev)].flags & BLOCK_PART_UNIT)) {
		return ENXIO;
	}
"""
    assert open_target in ufs_content, "ufs_open target not found"
    ufs_content = ufs_content.replace(open_target, open_replacement, 1)

    # Update ufs_ioctl
    ioctl_target = "\tif (!ufs_ready || part >= ufs_parts) {\n\t\treturn ENXIO;\n\t}\n\tnative = ufs_page->part[part].block_size;\n"
    ioctl_replacement = """\tif (!ufs_ready || part >= ufs_parts) {
		return ENXIO;
	}
#if defined(HAKIOS_A51)
	if (pe_arm_get_soc_base_phys() == 0x10000000) {
		native = 4096;
	} else
#endif
	native = ufs_page->part[part].block_size;
"""
    assert ioctl_target in ufs_content, "ufs_ioctl target not found"
    ufs_content = ufs_content.replace(ioctl_target, ioctl_replacement, 1)

    # Update hakios_ufs_init
    init_target = "void\nhakios_ufs_init(void)\n{\n\tuint64_t pa = 0, buffer_pa;\n"
    init_replacement = """void
hakios_ufs_init(void)
{
#if defined(HAKIOS_A51)
	if (pe_arm_get_soc_base_phys() == 0x10000000) {
		ufs_bmajor = bdevsw_add(-1, &ufs_bdevsw);
		ufs_cmajor = ufs_bmajor < 0 ? -1 : cdevsw_add_with_bdev(-1, &ufs_cdevsw, ufs_bmajor);
		if (ufs_cmajor < 0) {
			printf("ufs: A51: no device numbers to be had\\n");
			return;
		}
		ufs_parts = 1;
		ufs_bsize[0] = 4096;
		ufs_buffer_size = 65536;
		if (devfs_make_node(makedev(ufs_bmajor, 0), DEVFS_BLOCK, UID_ROOT, GID_OPERATOR, 0640, "ufs_darwin") == NULL) {
			printf("ufs: A51: failed to create /dev/ufs_darwin\\n");
			return;
		}
		(void)devfs_make_node(makedev(ufs_cmajor, 0), DEVFS_CHAR, UID_ROOT, GID_OPERATOR, 0640, "rufs_darwin");
		ufs_ready = true;
		printf("ufs: A51 Exynos 9611 UFS initialized: /dev/ufs_darwin and /dev/rufs_darwin (LBA %u..%u, %llu MB)\\n",
		    A51_UFS_DARWIN_LBA, A51_UFS_DARWIN_LBA + A51_UFS_DARWIN_BLOCKS - 1,
		    ((uint64_t)A51_UFS_DARWIN_BLOCKS * 4096) >> 20);
		return;
	}
#endif

	uint64_t pa = 0, buffer_pa;
"""
    assert init_target in ufs_content, "hakios_ufs_init target not found"
    ufs_content = ufs_content.replace(init_target, init_replacement, 1)

    ufs_path.write_text(ufs_content, encoding="utf-8")
    print("Patched drivers/storage/hakios.ufs.c")
else:
    print("HAKIOS_A51 already in drivers/storage/hakios.ufs.c")

# 5. Update drivers/map
map_path = REPO / "drivers/map"
map_content = map_path.read_text(encoding="utf-8")
if "a51_ufs_readonly.h" not in map_content:
    map_content += "\ncore     bsd/dev/a51_ufs_readonly.h\ncore     bsd/dev/a51_input.h\n"
    map_path.write_text(map_content, encoding="utf-8")
    print("Added a51_ufs_readonly.h and a51_input.h to drivers/map")

# 6. Update userland/build.sh for /tmp symlink
bld_path = REPO / "userland/build.sh"
bld_content = bld_path.read_text(encoding="utf-8")
if "root/tmp" not in bld_content:
    old_bld = "mkdir -p root/dev root/private/var\n\tmkdir -p root/lib\n"
    new_bld = "mkdir -p root/dev root/private/var root/private/var/tmp\n\tln -sf private/var/tmp root/tmp\n\tmkdir -p root/lib\n"
    assert old_bld in bld_content, "root/dev in userland/build.sh not found"
    bld_content = bld_content.replace(old_bld, new_bld, 1)
    bld_path.write_text(bld_content, encoding="utf-8")
    print("Added /tmp symlink in userland/build.sh")
else:
    print("/tmp symlink already in userland/build.sh")

print("All patches applied successfully!")
