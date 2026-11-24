// SPDX-License-Identifier: GPL-2.0
/* Read only the assembly loader's bounded copy in reserved GNSS memory.
 * expected_log_pa is pinned provenance metadata and is never dereferenced.
 * This reader never changes the retained memory or any peripheral register.
 */
#include <linux/init.h>
#include <linux/kernel.h>
#include <linux/module.h>
#include <linux/io.h>
#include <linux/string.h>

MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("Bounded A51 assembly-loader storage diagnostic reader");

#define RECORD_MAGIC 0x32454c5241494b48ULL
#define LOG_MAGIC 0x48414b494f534c47ULL
#define GNSS_PA 0xfb000000UL
#define LOG_HEADER_OFFSET 0x1e0
#define LOG_DATA_OFFSET 0x200
#define MAX_LOG_BYTES 131072
#define GNSS_BYTES (LOG_DATA_OFFSET + MAX_LOG_BYTES)

static unsigned long expected_log_pa;
static char *capture_token;
module_param(expected_log_pa, ulong, 0400);
module_param(capture_token, charp, 0400);

/* The XNU log can have a binary stackshot tail. Report its exact extent and
 * emit only complete lines preceding the first nontext byte.
 */
static size_t text_prefix(void __iomem *src, size_t len)
{
    size_t i, complete_lines = 0;
    for (i = 0; i < len; i++) {
        unsigned char c = ioread8((u8 __iomem *)src + i);
        if ((c < 32 && c != '\t' && c != '\r' && c != '\n') || c > 126)
            break;
        if (c == '\n')
            complete_lines = i + 1;
    }
    return complete_lines;
}

/* An overlong line in the reported prefix is an explicit capture failure. */
static bool dump_lines(void __iomem *src, size_t len, const char *tag)
{
    char line[512];
    size_t i, pos = 0;
    for (i = 0; i < len; i++) {
        unsigned char c = ioread8((u8 __iomem *)src + i);
        if (c == '\r')
            continue;
        if (c == '\n') {
            line[pos] = 0;
            pr_emerg("%s: %s\n", tag, line);
            pos = 0;
        } else {
            if ((c < 32 && c != '\t') || c > 126 || pos >= sizeof(line) - 1)
                return false;
            line[pos++] = c;
        }
    }
    return pos == 0;
}

static int __init reader_init(void)
{
    void __iomem *gnss;
    u64 record[32], hdr[4];
    size_t text_bytes, tail_bytes;
    bool complete;
    unsigned int i;
    if (!capture_token || strlen(capture_token) != 32)
        return -EINVAL;
    for (i = 0; i < 32; i++)
        if (!((capture_token[i] >= '0' && capture_token[i] <= '9') ||
              (capture_token[i] >= 'a' && capture_token[i] <= 'f')))
            return -EINVAL;
    if (expected_log_pa < 0x80000000UL || expected_log_pa > 0xc0000000UL - MAX_LOG_BYTES)
        return -EINVAL;
    gnss = ioremap_cache(GNSS_PA, GNSS_BYTES);
    if (!gnss)
        return -ENOMEM;
    memcpy_fromio(record, gnss, sizeof(record));
    memcpy_fromio(hdr, (u8 __iomem *)gnss + LOG_HEADER_OFFSET, sizeof(hdr));
    pr_emerg("HAKIOS_STORAGE_RECORD token=%s magic=%016llx version=%llu bytes=%llu status=%llu reason=%llu code=%llu log_pa=%016llx log_len=%llu el=%llu cntfrq=%llu midr=%016llx\n",
             capture_token, record[0], record[1], record[2], record[3], record[4],
             record[5], record[6], record[7], record[8], record[11], record[12]);
    if (record[0] != RECORD_MAGIC || record[1] != 1 || record[2] != 256 ||
        record[6] != expected_log_pa || !record[7] || record[7] > MAX_LOG_BYTES ||
        hdr[0] != LOG_MAGIC || hdr[1] != record[7] || hdr[2] != record[6] || hdr[3] != record[3]) {
        pr_emerg("HAKIOS_STORAGE_CAPTURE_REFUSED token=%s\n", capture_token);
        iounmap(gnss);
        return 0;
    }
    text_bytes = text_prefix((u8 __iomem *)gnss + LOG_DATA_OFFSET, (size_t)record[7]);
    tail_bytes = (size_t)record[7] - text_bytes;
    pr_emerg("HAKIOS_STORAGE_CAPTURE_BEGIN token=%s bank=gnss bytes=%llu text_bytes=%zu tail_bytes=%zu\n",
             capture_token, record[7], text_bytes, tail_bytes);
    complete = text_bytes > 0 && dump_lines((u8 __iomem *)gnss + LOG_DATA_OFFSET,
                                          text_bytes, "HAKIOS_STORAGE_OUT");
    pr_emerg("HAKIOS_STORAGE_CAPTURE_END token=%s bank=gnss prefix_complete=%u text_bytes=%zu tail_bytes=%zu\n",
             capture_token, complete, text_bytes, tail_bytes);
    iounmap(gnss);
    return 0;
}

static void __exit reader_exit(void) { }
module_init(reader_init);
module_exit(reader_exit);
