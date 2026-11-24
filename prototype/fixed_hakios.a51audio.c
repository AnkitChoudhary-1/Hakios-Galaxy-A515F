/* A51 Exynos9611 Audio Driver: TI TAS2562 Smart Amp + ABOX UAIF2
 * Complete implementation: un-reset, I2C register config, clock ungating,
 * I2S2 pinmux, ABOX routing, DMA ring buffer, boot chime, and CoreAudio sink.
 */
#include <kern/startup.h>
#include <kern/clock.h>
#include <kern/locks.h>
#include <kern/thread.h>
#include <libkern/libkern.h>
#include <mach/mach_types.h>
#include <pexpert/pexpert.h>
#include <sys/systm.h>
#include <sys/hakios.audio.h>

extern vm_offset_t ml_io_map(vm_offset_t phys_addr, vm_size_t size);
extern void loader_log_line(const char *line);
extern void hakios_audio_set_sink(const char *name, hakios_audio_sink_t sink);

static inline uint32_t audio_rd(vm_offset_t address)
{
    return *(volatile uint32_t *)address;
}

static inline void audio_wr(vm_offset_t address, uint32_t val)
{
    *(volatile uint32_t *)address = val;
    __asm__ volatile("dsb sy" ::: "memory");
}

/* =========================================================================
 * CMGP GPIO for HSI2C3 (Bit-banged I2C) & TAS2562 Hardware Reset
 * Exynos 9611 CMGP Base: 0x11C20000
 * Banks:
 *   gpm0: offset 0x000 (gpm0-0 = spk_en / ti,reset-gpio)
 *   gpm2: offset 0x040 (gpm2-0 = SCL, hsi2c3_bus)
 *   gpm3: offset 0x060 (gpm3-0 = SDA, hsi2c3_bus)
 * Registers per bank:
 *   +0x00: CON (function: 0 = input, 1 = output)
 *   +0x04: DAT (bit 0 = pin data)
 *   +0x08: PUD (pull-up/down: 0 = none, 1 = pulldown, 3 = pullup)
 *   +0x0C: DRV (drive strength: 3 = 4x)
 * ========================================================================= */
static vm_offset_t amp_gpio;

static inline int amp_read_scl(void)
{
    return (int)(audio_rd(amp_gpio + 0x040 + 4) & 1u);
}

static inline int amp_read_sda(void)
{
    return (int)(audio_rd(amp_gpio + 0x060 + 4) & 1u);
}

static void amp_line(unsigned bank, bool released)
{
    vm_offset_t p = amp_gpio + bank;
    if (released) {
        audio_wr(p + 0, audio_rd(p + 0) & ~15u);
    } else {
        audio_wr(p + 4, audio_rd(p + 4) & ~1u);
        audio_wr(p + 0, (audio_rd(p + 0) & ~15u) | 1u);
    }
    __asm__ volatile("dsb sy" ::: "memory");
    delay(5);
}

static int amp_high(void)
{
    amp_line(0x040, true);
    for (unsigned i = 0; i < 2000; i++) {
        if (amp_read_scl() != 0) return 0;
        delay(1);
    }
    return -1;
}

static int amp_start(void)
{
    amp_line(0x060, true);
    if (amp_high() != 0) return -1;
    if (!amp_read_sda()) return -2;
    delay(5);
    amp_line(0x060, false);
    delay(5);
    amp_line(0x040, false);
    delay(5);
    return 0;
}

static void amp_stop(void)
{
    amp_line(0x040, false);
    amp_line(0x060, false);
    delay(5);
    (void)amp_high();
    delay(5);
    amp_line(0x060, true);
    delay(5);
}

static int amp_write_byte(uint8_t byte)
{
    for (int i = 7; i >= 0; i--) {
        amp_line(0x060, !!(byte & (1 << i)));
        delay(2);
        if (amp_high() != 0) return -1;
        delay(5);
        amp_line(0x040, false);
        delay(2);
    }
    amp_line(0x060, true);
    delay(2);
    if (amp_high() != 0) return -1;
    delay(3);
    int ack = (amp_read_sda() == 0);
    delay(2);
    amp_line(0x040, false);
    delay(2);
    return ack ? 0 : -2;
}

static int amp_read_byte(uint8_t *val, bool send_ack)
{
    uint8_t byte = 0;
    amp_line(0x060, true);
    for (int i = 7; i >= 0; i--) {
        if (amp_high() != 0) return -1;
        delay(3);
        if (amp_read_sda()) {
            byte |= (1 << i);
        }
        delay(2);
        amp_line(0x040, false);
        delay(2);
    }
    amp_line(0x060, !send_ack);
    delay(2);
    if (amp_high() != 0) return -1;
    delay(5);
    amp_line(0x040, false);
    amp_line(0x060, true);
    delay(2);
    *val = byte;
    return 0;
}

static void amp_bus_recovery(void)
{
    amp_line(0x060, true);
    for (int i = 0; i < 9; i++) {
        amp_line(0x040, false);
        delay(5);
        if (amp_high() != 0) break;
        delay(5);
        if (amp_read_sda() != 0) break;
    }
    amp_stop();
}

static int amp_write_reg(uint8_t reg, uint8_t val)
{
    int ret = amp_start();
    if (ret != 0) goto out;
    ret = amp_write_byte(0x98);
    if (ret != 0) goto out;
    ret = amp_write_byte(reg);
    if (ret != 0) goto out;
    ret = amp_write_byte(val);
out:
    amp_stop();
    return ret;
}

static int amp_read_reg(uint8_t reg, uint8_t *val)
{
    int ret = amp_start();
    if (ret != 0) goto out;
    ret = amp_write_byte(0x98);
    if (ret != 0) goto out;
    ret = amp_write_byte(reg);
    if (ret != 0) goto out;
    ret = amp_start();
    if (ret != 0) goto out;
    ret = amp_write_byte(0x99);
    if (ret != 0) goto out;
    ret = amp_read_byte(val, false);
out:
    amp_stop();
    return ret;
}

static int current_book = -1;
static int current_page = -1;

static int amp_select_book_page(uint8_t book, uint8_t page)
{
    int ret = 0;
    if (current_book != (int)book) {
        ret = amp_write_reg(0, 0);
        if (ret != 0) { current_page = -1; return ret; }
        current_page = 0;
        ret = amp_write_reg(127, book);
        if (ret != 0) return ret;
        current_book = book;
    }
    if (current_page != (int)page) {
        ret = amp_write_reg(0, page);
        if (ret != 0) return ret;
        current_page = page;
    }
    return 0;
}

static int amp_write(uint8_t book, uint8_t page, uint8_t reg, uint8_t val)
{
    int ret = amp_select_book_page(book, page);
    if (ret != 0) return ret;
    return amp_write_reg(reg, val);
}

static int amp_read(uint8_t book, uint8_t page, uint8_t reg, uint8_t *val)
{
    int ret = amp_select_book_page(book, page);
    if (ret != 0) return ret;
    return amp_read_reg(reg, val);
}

/* =========================================================================
 * Audio DMA Ring Buffer in Reserved Audio DRAM (0xE9400000, 64KB)
 * ========================================================================= */
#define A51_DMA_BASE_PA      0xE9400000UL
#define A51_DMA_BUFFER_SIZE  (64 * 1024)
#define A51_DMA_FRAMES       (A51_DMA_BUFFER_SIZE / HAKIOS_AUDIO_FRAME)
#define A51_DMA_PERIOD       4096u

static int16_t *dma_virt_buffer = NULL;
static vm_offset_t abox_base = 0;
static volatile uint32_t dma_write_frame_offset = 0;
static bool audio_sink_active = false;
static bool dma_writer_started = false;
static uint32_t dma_last_read = 0;

static uint32_t a51_audio_sink(const int16_t *frames, uint32_t count)
{
    if (!audio_sink_active || !dma_virt_buffer || !abox_base || !count) return 0;

    uint32_t status = audio_rd(abox_base + 0x1030);
    uint32_t read_frame = (((status >> 16) & 0x1fffu) << 4) / HAKIOS_AUDIO_FRAME;
    if (read_frame >= A51_DMA_FRAMES) read_frame = 0;

    volatile uint32_t *words = (volatile uint32_t *)dma_virt_buffer;
    if (dma_writer_started) {
        for (uint32_t f = dma_last_read; f != read_frame; f = (f + 1) % A51_DMA_FRAMES) {
            words[f] = 0;
        }
    }
    dma_last_read = read_frame;

    uint32_t cur = dma_write_frame_offset;
    uint32_t ahead = (cur + A51_DMA_FRAMES - read_frame) % A51_DMA_FRAMES;
    uint32_t period_frames = A51_DMA_PERIOD / HAKIOS_AUDIO_FRAME;
    if (!dma_writer_started || ahead < period_frames) {
        cur = (read_frame + 2 * period_frames) % A51_DMA_FRAMES;
        ahead = 2 * period_frames;
        dma_writer_started = true;
    }

    uint32_t free_frames = (ahead >= A51_DMA_FRAMES - period_frames) ? 0 : (A51_DMA_FRAMES - ahead - period_frames);
    if (count > free_frames) count = free_frames;

    for (uint32_t i = 0; i < count; i++) {
        uint32_t sample = ((uint32_t)(uint16_t)frames[2 * i + 1] << 16) | (uint16_t)frames[2 * i];
        words[(cur + i) % A51_DMA_FRAMES] = sample;
    }
    __asm__ volatile("dsb sy" ::: "memory");
    dma_write_frame_offset = (cur + count) % A51_DMA_FRAMES;

    audio_wr(abox_base + 0x1010, A51_DMA_PERIOD);
    if (!(audio_rd(abox_base + 0x1000) & 1u)) {
        audio_wr(abox_base + 0x1000, 1u);
    }
    return count;
}

/* =========================================================================
 * Exynos 9611 DISPAUD Pinmux, Clocks, ABOX Routing & DMA Configuration
 * ========================================================================= */
static int a51_audio_hardware_init(vm_offset_t cmu)
{
    audio_wr(cmu + 0x206c, audio_rd(cmu + 0x206c) | 1u); /* GPIO_DISPAUD PCLK */
    audio_wr(cmu + 0x2040, audio_rd(cmu + 0x2040) | 1u); /* CLK_DISPAUD_AUD */

    vm_offset_t pinctrl = ml_io_map(0x14a60000UL, 0x1000);
    if (pinctrl) {
        audio_wr(pinctrl + 0x40, 0x2222); /* gpb2-0..3 func 2 */
        audio_wr(pinctrl + 0x48, 0x0000); /* no pull */
        audio_wr(pinctrl + 0x4c, 0x00ff); /* 4x drive strength */
        loader_log_line("a51audio: GPB2 configured for AUD_I2S2 bus (func 2, 4x drive)\n");
    }

    audio_wr(cmu + 0x2008, audio_rd(cmu + 0x2008) | 1u); /* UAIF2 BCLK gate */
    audio_wr(cmu + 0x2018, audio_rd(cmu + 0x2018) | 1u); /* UAIF2 reset gate */
    audio_wr(cmu + 0x2020, audio_rd(cmu + 0x2020) | (1u << 21) | 1u); /* ABOX ACLK */
    audio_wr(cmu + 0x2030, audio_rd(cmu + 0x2030) | 1u); /* ABOX CCLK */
    audio_wr(cmu + 0x2078, audio_rd(cmu + 0x2078) | 1u); /* LHS_AXI_D_ABOX */
    audio_wr(cmu + 0x20a4, audio_rd(cmu + 0x20a4) | 1u); /* RSTNSYNC_CLK_DISPAUD_AUD */

    audio_wr(cmu + 0x182c, (audio_rd(cmu + 0x182c) & ~511u) | 47u);
    audio_wr(cmu + 0x1018, audio_rd(cmu + 0x1018) & ~1u);
    loader_log_line("a51audio: CMU_DISPAUD clocks ungated, UAIF2 BCLK=1.536MHz\n");

    vm_offset_t sysmmu = ml_io_map(0x14920000UL, 0x1000);
    if (sysmmu) {
        audio_wr(sysmmu, 0u);
    }

    abox_base = ml_io_map(0x14a50000UL, 0x10000);
    if (!abox_base) return -1;

    audio_wr(abox_base + 0x0010, 1u);

    uint32_t route = audio_rd(abox_base + 0x0040);
    route &= ~(0xfu << 8);
    route |= (2u << 8);
    audio_wr(abox_base + 0x0040, route);

    audio_wr(abox_base + 0x0200, 0u);
    audio_wr(abox_base + 0x0204, (0u << 16) | 9u);
    audio_wr(abox_base + 0x0524, 0x0984F000);
    audio_wr(abox_base + 0x0520, (4u << 24) | (1u << 2));

    dma_virt_buffer = (int16_t *)ml_io_map(A51_DMA_BASE_PA, A51_DMA_BUFFER_SIZE);
    if (!dma_virt_buffer) return -1;

    audio_wr(abox_base + 0x1000, 0u);
    audio_wr(abox_base + 0x1700, 0u);
    audio_wr(abox_base + 0x1008, (uint32_t)A51_DMA_BASE_PA);
    audio_wr(abox_base + 0x100c, (uint32_t)(A51_DMA_BASE_PA + A51_DMA_BUFFER_SIZE));
    audio_wr(abox_base + 0x1010, A51_DMA_PERIOD);
    audio_wr(abox_base + 0x1014, (uint32_t)A51_DMA_BASE_PA);
    audio_wr(abox_base + 0x1018, 0x00FFFFFFu);
    audio_wr(abox_base + 0x101c, 1u);

    volatile uint32_t *dma_words = (volatile uint32_t *)dma_virt_buffer;
    for (uint32_t f = 0; f < A51_DMA_FRAMES; f++) {
        int16_t l = (int16_t)(18000 * ((f % 109) < 55 ? 1 : -1));
        int16_t r = (int16_t)(18000 * ((f % 55) < 28 ? 1 : -1));
        dma_words[f] = ((uint32_t)(uint16_t)r << 16) | (uint16_t)l;
    }
    dma_write_frame_offset = 0;
    dma_writer_started = false;

    audio_wr(abox_base + 0x1000, 1u);
    audio_wr(abox_base + 0x0520, (1u << 0) | (4u << 24) | (1u << 2));
    delay(20000);

    char log[160];
    snprintf(log, sizeof(log), "a51audio: ABOX UAIF2 active: CTRL0=0x%08x, CTRL1=0x%08x, STATUS=0x%08x, RDMA0=0x%08x\n",
             audio_rd(abox_base + 0x0520), audio_rd(abox_base + 0x0524),
             audio_rd(abox_base + 0x052c), audio_rd(abox_base + 0x1030));
    loader_log_line(log);
    loader_log_line("a51audio: RDMA0 physical ring enabled (64KB buffer, unity volume, chime primed)\n");
    return 0;
}

/* =========================================================================
 * TAS2562 Smart Amp Bring-up
 * ========================================================================= */
static int tas2562_bringup(void)
{
    char log[256];
    amp_gpio = ml_io_map(0x11c20000UL, 0x1000);
    if (!amp_gpio) {
        loader_log_line("a51audio: failed to map CMGP GPIO (0x11C20000)\n");
        return -1;
    }

    audio_wr(amp_gpio + 0x040 + 8, 3u);  /* gpm2-0 PUD = pullup */
    audio_wr(amp_gpio + 0x060 + 8, 3u);  /* gpm3-0 PUD = pullup */
    audio_wr(amp_gpio + 0x040 + 12, 3u); /* gpm2-0 DRV = 4x */
    audio_wr(amp_gpio + 0x060 + 12, 3u); /* gpm3-0 DRV = 4x */

    amp_line(0x040, true);
    amp_line(0x060, true);
    delay(100);

    amp_bus_recovery();

    vm_offset_t p_rst = amp_gpio + 0x000;
    audio_wr(p_rst + 8, 3u);
    audio_wr(p_rst + 12, 3u);
    audio_wr(p_rst + 4, audio_rd(p_rst + 4) & ~1u);
    audio_wr(p_rst + 0, (audio_rd(p_rst + 0) & ~15u) | 1u);
    __asm__ volatile("dsb sy" ::: "memory");
    delay(20000);

    audio_wr(p_rst + 4, audio_rd(p_rst + 4) | 1u);
    __asm__ volatile("dsb sy" ::: "memory");
    delay(20000);
    loader_log_line("a51audio: TAS2562 hardware reset completed (gpm0-0 driven HIGH)\n");

    current_book = -1;
    current_page = -1;

    uint8_t id = 0;
    int err = amp_read(0, 0, 0x7D, &id);
    snprintf(log, sizeof(log), "a51audio: TAS2562 probe: silicon_id=0x%02x (err=%d, SCL=%d, SDA=%d)\n",
             id, err, amp_read_scl(), amp_read_sda());
    loader_log_line(log);

    if (err != 0) {
        loader_log_line("a51audio: TAS2562 I2C probe failed; aborting amplifier configuration\n");
        return err;
    }

    (void)amp_write(0, 0, 0x01, 0x01);
    delay(20000);
    current_book = -1;
    current_page = -1;

    (void)amp_write(0, 0, 0x04, 0xCF); /* MISCCONFIG0: auto retry all faults */
    (void)amp_write(0, 0, 0x0A, 0x03); /* TDMConfigurationReg4 */
    (void)amp_write(0, 0, 0x38, 0x0C); /* CLOCKCONFIGURATION: auto-detect rate, 64-fs ratio */
    (void)amp_write(0, 0, 0x35, 0x78); /* BOOSTSLOPE */
    (void)amp_write(0, 0, 0x3B, 0x38); /* VBATFILTER */
    (void)amp_write(0, 0, 0x3C, 0x3C); /* CLASSHRELEASETIMER */

    (void)amp_write(0, 0xFD, 0x0D, 0x0D);
    (void)amp_write(0, 0xFD, 0x19, 0x80);
    (void)amp_write(0, 0xFD, 0x32, 0x49);
    (void)amp_write(0, 0xFD, 0x33, 0x8E);
    (void)amp_write(0, 0xFD, 0x3F, 0x21);
    (void)amp_write(0, 0xFD, 0x5F, 0xC5); /* OSC_BOOST_CLK enabled */
    (void)amp_write(0, 0xFD, 0x0D, 0x0D);

    (void)amp_write(0, 0, 0x06, 0x08); /* 48 kHz auto-detect */
    (void)amp_write(0, 0, 0x07, 0x02); /* I2S standard, 1-bit offset, rising edge */
    (void)amp_write(0, 0, 0x08, 0x30); /* 16-bit I2S, Stereo Downmix ((L+R)/2) */
    (void)amp_write(0, 0, 0x09, 0x10); /* Slot 0 = Left, Slot 1 = Right */
    (void)amp_write(0, 0, 0x0B, 0x42);
    (void)amp_write(0, 0, 0x0C, 0x40);
    (void)amp_write(0, 0, 0x31, 0x00); /* disable weak pull-downs */
    (void)amp_write(0, 0, 0x3E, 0x00); /* disable ICN squelch muting */
    (void)amp_write(0, 0, 0x03, 0x1E); /* Volume: +17.5 dB full output */

    uint8_t pwr = 0xFF, irq = 0xFF;
    for (int retry = 0; retry < 15; retry++) {
        (void)amp_write(0, 0, 0x30, 0x04); /* LTCHINTCLEAR */
        (void)amp_read(0, 0, 0x24, &irq);   /* read latched IRQ */
        (void)amp_write(0, 0, 0x02, 0x00); /* ACTIVE */
        delay(6000);
        (void)amp_read(0, 0, 0x02, &pwr);
        (void)amp_read(0, 0, 0x24, &irq);
        if (pwr == 0x00) break;
    }
    snprintf(log, sizeof(log), "a51audio: TAS2562 power_mode=0x%02x, latched_irq=0x%02x\n", pwr, irq);
    loader_log_line(log);

    uint8_t intstatus = 0, liveirq = 0;
    (void)amp_read(0, 0, 0x78, &intstatus);
    (void)amp_read(0, 0, 0x1F, &liveirq);
    snprintf(log, sizeof(log), "a51audio: TAS2562 status: INTSTATUS=0x%02x, LIVE_IRQ=0x%02x\n", intstatus, liveirq);
    loader_log_line(log);

    return (pwr == 0x00) ? 0 : -1;
}

/* =========================================================================
 * Driver Initialization Entry Point
 * ========================================================================= */
static void a51audio_init(void)
{
    uint32_t step = 0;
    if (!PE_parse_boot_argn("a51audio", &step, sizeof(step))) {
        step = 4;
    }
    if (step == 0) return;

    loader_log_line("a51audio: initializing Galaxy A51 audio subsystem...\n");

    vm_offset_t pmu = ml_io_map(0x11860000UL, 0x5000);
    if (!pmu) {
        loader_log_line("a51audio: PMU mapping failed; aborting\n");
        return;
    }
    uint32_t status = audio_rd(pmu + 0x4004);
    if ((status & 0xf) != 0xf) {
        loader_log_line("a51audio: DISPAUD power domain is off\n");
        return;
    }

    vm_offset_t cmu = ml_io_map(0x14980000UL, 0x4000);
    if (!cmu) {
        loader_log_line("a51audio: CMU mapping failed; aborting\n");
        return;
    }

    if (a51_audio_hardware_init(cmu) != 0) {
        loader_log_line("a51audio: hardware setup failed; sink unavailable\n");
        return;
    }

    int amp_status = tas2562_bringup();

    hakios_audio_set_sink("Galaxy A51 Speaker (TAS2562 / ABOX)", a51_audio_sink);
    audio_sink_active = true;

    char msg[128];
    snprintf(msg, sizeof(msg), "a51audio: registered speaker sink with CoreAudio (amp_status=%d)\n", amp_status);
    loader_log_line(msg);
}

STARTUP(EARLY_BOOT, STARTUP_RANK_LAST, a51audio_init);
