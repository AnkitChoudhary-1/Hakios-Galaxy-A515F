/* SPDX-License-Identifier: MIT */
/* Versioned fixed-size kernel/user ABI; no pointers or arbitrary MMIO requests. */
#ifndef HAKIOS_A51_H
#define HAKIOS_A51_H
#define HAKIOS_A51_ABI_VERSION 1u
#define HAKIOS_A51_REG_MAX 192u
#define HAKIOS_A51_GPIO    (1u << 0)
#define HAKIOS_A51_I2C     (1u << 1)
#define HAKIOS_A51_DSIM    (1u << 2)
#define HAKIOS_A51_DECON   (1u << 3)
#define HAKIOS_A51_UFS     (1u << 4)
#define HAKIOS_A51_DPP     (1u << 5)
#define HAKIOS_A51_SYSMMU  (1u << 6)
#define HAKIOS_A51_ALL     0x7fu

struct hakios_a51_register {
    unsigned long long pa;
    unsigned int value;
    unsigned int group;
};
struct hakios_a51_snapshot {
    unsigned int version;
    unsigned int count;
    unsigned int groups;
    unsigned int sequence;
    unsigned long long counter;
    struct hakios_a51_register regs[HAKIOS_A51_REG_MAX];
};
_Static_assert(sizeof(struct hakios_a51_register) == 16, "A51 register ABI");
_Static_assert(sizeof(struct hakios_a51_snapshot) == 3096, "A51 snapshot ABI");

/* Version 2: lifecycle and protocol evidence accompany each digest. */
#define HAKIOS_A51_UFS_ABI_VERSION 2u
#define HAKIOS_A51_UFS_SUBMITTED   1u
#define HAKIOS_A51_UFS_COMPLETED   2u
#define HAKIOS_A51_UFS_RESTORED    4u
#define HAKIOS_A51_UFS_QUARANTINED 8u
#define HAKIOS_A51_UFS_VALIDATED   16u
#define HAKIOS_A51_UFS_SUCCESS     23u
#define HAKIOS_A51_UFS_SUCCESS_STAGES 0xfeu

struct hakios_a51_ufs_transfer_result {
    unsigned int lba, blocks;
    int rc;
    unsigned int ocs, stages, lifecycle, transaction, response, status, residual;
    unsigned int sense_length, prdt_count, prdt_bytes;
    unsigned long long elapsed_us;
    unsigned char sha256[32]; /* populated only for a validated transfer */
};
struct hakios_a51_ufs_result {
    unsigned int version, hcs, hce, ufs_version;
    int init_rc, write_rc;
    unsigned int write_rejected, doorbell_after_write;
    unsigned int diag_rs, diag_dbr, diag_dest_pa_lo, diag_dest_pa_hi;
    struct hakios_a51_ufs_transfer_result single, multi, reread;
};
_Static_assert(sizeof(struct hakios_a51_ufs_transfer_result) == 96, "A51 UFS transfer ABI");
_Static_assert(sizeof(struct hakios_a51_ufs_result) == 336, "A51 UFS result ABI");

/* Validate the fixed diagnostic report, not the known contents of its digest.
 * Callers supply the intended command size; accepting r->blocks as its own
 * expectation could disguise a one-block command as the 64 KiB experiment.
 * The kernel separately checks the actual DMA byte extent before hashing.
 */
static inline int
hakios_a51_ufs_transfer_valid(const struct hakios_a51_ufs_transfer_result *r,
    unsigned int expected_blocks)
{
    return r && (expected_blocks == 1u || expected_blocks == 16u) &&
        !r->rc && !r->ocs && r->lba == 27792u && r->blocks == expected_blocks &&
        r->lifecycle == HAKIOS_A51_UFS_SUCCESS &&
        r->stages == HAKIOS_A51_UFS_SUCCESS_STAGES && r->transaction == 0x21u &&
        !r->response && !r->status && !r->residual && !r->sense_length &&
        r->prdt_count == 1u && r->prdt_bytes == 128u &&
        r->elapsed_us > 0 && r->elapsed_us <= 5000000ULL;
}

/* Version 2: display and brightness diagnostic evidence. */
#define HAKIOS_A51_DISPLAY_ABI_VERSION 2u

struct hakios_a51_display_diag {
    unsigned int version;
    unsigned int width;
    unsigned int height;
    unsigned int stride;
    unsigned int bpp;
    unsigned int decon_online;
    unsigned int dsim_online;
    unsigned int current_brightness;
    unsigned int initial_brightness;
    unsigned int brightness_steps_done;
    unsigned int pattern_drawn;
    int rc;
    unsigned long long fb_pa;
    unsigned int brightness_history[8];
    unsigned long long step_timestamps[8];
    unsigned short step_10bit_values[8];
    unsigned char pattern_sha256[32];
};
_Static_assert(sizeof(struct hakios_a51_display_diag) == 200, "A51 display ABI");

static inline int
hakios_a51_display_diag_valid(const struct hakios_a51_display_diag *d)
{
    if (!d || d->version != HAKIOS_A51_DISPLAY_ABI_VERSION) return 0;
    if ((d->fb_pa & 0xfffu) != 0) return 0;
    if (d->fb_pa < 0x80000000ULL || d->fb_pa >= 0x100000000ULL) return 0;
    if ((0x100000000ULL - d->fb_pa) < 10368000ULL) return 0;
    if (d->width != 1080u || d->height != 2400u ||
        d->stride != 4320u || d->bpp != 32u) return 0;
    if (d->decon_online != 1u || d->dsim_online != 1u ||
        d->pattern_drawn != 1u || d->brightness_steps_done != 5u || d->rc != 0) return 0;
    if (d->initial_brightness > 255u || d->current_brightness > 255u ||
        d->current_brightness != d->initial_brightness) return 0;

    const unsigned int expected_steps[5] = {50u, 120u, 200u, 255u, 180u};
    for (unsigned int i = 0; i < 5u; i++) {
        if (d->brightness_history[i] != expected_steps[i] ||
            d->step_10bit_values[i] == 0 || d->step_10bit_values[i] > 1023u) return 0;
    }
    if (d->step_timestamps[0] == 0) return 0;
    for (unsigned int i = 1; i < 5u; i++) {
        if (d->step_timestamps[i] <= d->step_timestamps[i - 1] ||
            d->step_timestamps[i] - d->step_timestamps[i - 1] < 600000ULL) return 0;
    }
    return 1;
}

/* Version 3: touch and key diagnostic evidence. */
#define HAKIOS_A51_INPUT_ABI_VERSION 3u
#define HAKIOS_A51_INPUT_MAX_EVENTS 16u

struct hakios_a51_input_event_diag {
    unsigned long long timestamp_us;
    unsigned int type;
    unsigned int code;
    int value;
    int x;
    int y;
    unsigned int reserved;
};
_Static_assert(sizeof(struct hakios_a51_input_event_diag) == 32, "A51 input event ABI");

struct hakios_a51_input_diag {
    unsigned int version;
    unsigned int touch_slots_active;
    unsigned int touch_total_events;
    int primary_x;
    int primary_y;
    unsigned int primary_down;
    unsigned int key_gpa1_raw;
    unsigned int key_debounced_state;
    unsigned int key_volup_count;
    unsigned int key_voldown_count;
    unsigned int key_power_count;
    unsigned int queue_events_count;
    int i2c_rc;
    unsigned int attn_raw;
    unsigned int attn_active;
    unsigned int irq_attached_mask;
    unsigned int touch_irq_count;
    unsigned int key_irq_count;
    unsigned int dropped_events;
    int deferred_touch_error;
    unsigned int quarantined;
    unsigned int terminal_fault;
    struct hakios_a51_input_event_diag events[HAKIOS_A51_INPUT_MAX_EVENTS];
};
_Static_assert(sizeof(struct hakios_a51_input_diag) == 600, "A51 input diag ABI v3");

static inline int
hakios_a51_input_diag_valid(const struct hakios_a51_input_diag *i)
{
    return i && i->version == HAKIOS_A51_INPUT_ABI_VERSION &&
        i->queue_events_count <= HAKIOS_A51_INPUT_MAX_EVENTS;
}

#endif
