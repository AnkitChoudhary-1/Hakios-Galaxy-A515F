/* A51 Exynos9611 Audio Driver: TI TAS2562 Smart Amp + ABOX UAIF2
 * Experimental speaker output. Host checks do not establish audible playback.
 * Wired headphones, capture and route switching are not implemented here.
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

/* Configure open-drain pin state: released (high-Z with pullup) or low (driving 0) */
static void amp_line(unsigned bank, bool released)
{
    vm_offset_t p = amp_gpio + bank;
    if (released) {
        /* Input mode: line pulled HIGH by internal pull-up */
        audio_wr(p + 0, audio_rd(p + 0) & ~15u);
    } else {
        /* Output mode driving LOW (0) */
        audio_wr(p + 4, audio_rd(p + 4) & ~1u);
        audio_wr(p + 0, (audio_rd(p + 0) & ~15u) | 1u);
    }
    __asm__ volatile("dsb sy" ::: "memory");
    delay(5);
}

/* Wait for SCL to go high (clock stretching support) */
static int amp_high(void)
{
    amp_line(0x040, true); /* SCL released */
    for (unsigned i = 0; i < 2000; i++) {
        if (amp_read_scl() != 0) return 0;
        delay(1);
    }
    return -1; /* Clock stretch timeout or stuck low */
}

/* I2C START condition */
static int amp_start(void)
{
    amp_line(0x060, true); /* SDA high */
    if (amp_high() != 0) return -1; /* SCL high */
    if (!amp_read_sda()) return -2; /* SDA stuck low */
    delay(5);
    amp_line(0x060, false); /* SDA low while SCL high */
    delay(5);
    amp_line(0x040, false); /* SCL low */
    delay(5);
    return 0;
}

/* I2C STOP condition */
static void amp_stop(void)
{
    amp_line(0x040, false); /* SCL low */
    amp_line(0x060, false); /* SDA low */
    delay(5);
    (void)amp_high();       /* SCL high */
    delay(5);
    amp_line(0x060, true);  /* SDA high while SCL high */
    delay(5);
}

/* Write single byte over I2C and check ACK */
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
    /* Read ACK from slave */
    amp_line(0x060, true); /* Release SDA */
    delay(2);
    if (amp_high() != 0) return -1;
    delay(3);
    int ack = (amp_read_sda() == 0); /* 0 = ACK, 1 = NACK */
    delay(2);
    amp_line(0x040, false);
    delay(2);
    return ack ? 0 : -2; /* -2 = NACK */
}

/* Read single byte over I2C */
static int amp_read_byte(uint8_t *val, bool send_ack)
{
    uint8_t byte = 0;
    amp_line(0x060, true); /* Release SDA to sample */
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
    /* Send ACK or NACK to slave */
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

/* Bus recovery: release hung slave holding SDA low */
static void amp_bus_recovery(void)
{
    amp_line(0x060, true); /* SDA released */
    for (int i = 0; i < 9; i++) {
        amp_line(0x040, false);
        delay(5);
        if (amp_high() != 0) break;
        delay(5);
        if (amp_read_sda() != 0) break;
    }
    amp_stop();
}

/* Write 8-bit register on TAS2562 (I2C 0x4C) */
static int amp_write_reg(uint8_t reg, uint8_t val)
{
    int ret = amp_start();
    if (ret != 0) goto out;
    ret = amp_write_byte(0x98); /* 0x4C << 1 | 0 */
    if (ret != 0) goto out;
    ret = amp_write_byte(reg);
    if (ret != 0) goto out;
    ret = amp_write_byte(val);
out:
    amp_stop();
    return ret;
}

/* Read 8-bit register on TAS2562 (I2C 0x4C) */
static int amp_read_reg(uint8_t reg, uint8_t *val)
{
    int ret = amp_start();
    if (ret != 0) goto out;
    ret = amp_write_byte(0x98);
    if (ret != 0) goto out;
    ret = amp_write_byte(reg);
    if (ret != 0) goto out;
    /* Repeated START */
    ret = amp_start();
    if (ret != 0) goto out;
    ret = amp_write_byte(0x99); /* 0x4C << 1 | 1 */
    if (ret != 0) goto out;
    ret = amp_read_byte(val, false); /* Send NACK for single-byte read */
out:
    amp_stop();
    return ret;
}

/* Cached Book / Page tracking */
static int current_book = -1;
static int current_page = -1;

static int amp_select_book_page(uint8_t book, uint8_t page)
{
    int ret = 0;
    if (current_book != (int)book) {
        /* Book select is only accessible on page zero. */
        ret = amp_write_reg(0, 0);
        if (ret != 0) { current_page = -1; return ret; }
        current_page = 0;
        ret = amp_write_reg(127, book); /* Book register is 127 */
        if (ret != 0) return ret;
        current_book = book;
    }
    if (current_page != (int)page) {
        ret = amp_write_reg(0, page);   /* Page register is 0 */
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

static int16_t *dma_virt_buffer = NULL;
static vm_offset_t abox_base = 0;
static volatile uint32_t dma_write_frame_offset = 0;
static bool audio_sink_active = false;

/* BUF_OFFSET is the DMA period size, not a software producer pointer.
 * Read STATUS to keep writes ahead of the hardware consumer. Generic audio
 * serializes this sink. RDMA0 alone feeds SPUS OUT0 -> SIFS1 -> UAIF2.
 */
#define A51_DMA_PERIOD 4096u
static bool dma_writer_started;
static uint32_t dma_last_read;
static uint32_t a51_audio_sink(const int16_t *frames, uint32_t count)
{
    if (!audio_sink_active || !dma_virt_buffer || !abox_base) return 0;
    if (!count) return 0;
    uint32_t status = audio_rd(abox_base + 0x1030);
    if (!(status & (1u << 31))) return 0;
    uint32_t read_frame = (((status >> 16) & 0x1fffu) << 4) / HAKIOS_AUDIO_FRAME;
    if (read_frame >= A51_DMA_FRAMES) return 0;
    volatile uint32_t *words = (volatile uint32_t *)dma_virt_buffer;
    /* Clear consumed samples so idle playback does not loop old sound. */
    if (dma_writer_started) {
        for (uint32_t f = dma_last_read; f != read_frame; f = (f + 1) % A51_DMA_FRAMES)
            words[f] = 0;
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
    uint32_t free_frames = ahead >= A51_DMA_FRAMES - period_frames ? 0 : A51_DMA_FRAMES - ahead - period_frames;
    if (count > free_frames) count = free_frames;
    for (uint32_t i = 0; i < count; i++) {
        uint32_t sample = ((uint32_t)(uint16_t)frames[2*i + 1] << 16) | (uint16_t)frames[2*i];
        words[(cur + i) % A51_DMA_FRAMES] = sample;
    }
    __asm__ volatile("dsb sy" ::: "memory");
    dma_write_frame_offset = (cur + count) % A51_DMA_FRAMES;
    return count;
}

/* Retained PLL_AUD: 26 MHz reference, signed fractional K, AUDIF parent.
 * Do not assume a 73.728 MHz parent or silently claim a measured BCLK.
 */
static uint32_t a51_bclk_div(uint32_t con0, uint32_t con3, uint32_t audif,
    uint32_t *actual)
{
    uint32_t p = (con0 >> 8) & 63, m = (con0 >> 16) & 1023, shift = con0 & 7;
    if (!p || !m || (con0 & 0xa0000000u) != 0xa0000000u) return 0;
    int64_t fixed = (int64_t)m * 65536 + (int16_t)(con3 & 65535);
    if (fixed <= 0) return 0;
    uint64_t parent = (26000000ULL * (uint64_t)fixed) /
        ((uint64_t)p * 65536 * (1u << shift) * ((audif & 511) + 1));
    uint32_t div = (uint32_t)((parent + 768000) / 1536000);
    if (!div || div > 512) return 0;
    *actual = (uint32_t)(parent / div);
    uint32_t error = *actual > 1536000 ? *actual - 1536000 : 1536000 - *actual;
    return error <= 15360 ? div : 0; /* within one percent of 48k/32fs */
}

/* =========================================================================
 * Exynos 9611 DISPAUD Pinmux, Clocks, SysMMU, ABOX Routing & DMA Configuration
 * ========================================================================= */
static int a51_audio_hardware_init(vm_offset_t cmu)
{
    /* 1. Ungate GPIO_DISPAUD clock and main DISPAUD audio clock */
    audio_wr(cmu + 0x206c, audio_rd(cmu + 0x206c) | 1u); /* GPIO_DISPAUD PCLK */
    audio_wr(cmu + 0x2040, audio_rd(cmu + 0x2040) | 1u); /* CLK_DISPAUD_AUD */

    /* 2. Pinmux: Configure GPB2 pins 0..3 for AUD_I2S2 bus (function 2) with 4x drive strength */
    vm_offset_t pinctrl = ml_io_map(0x14a60000UL, 0x1000);
    if (pinctrl) {
        audio_wr(pinctrl + 0x40, 0x2222); /* gpb2-0..3 func 2 (AUD_I2S2_BCLK/WS/SDI/SDO) */
        audio_wr(pinctrl + 0x48, 0x0000); /* no pull */
        audio_wr(pinctrl + 0x4C, 0x00FF); /* 4x drive strength on all GPB2 pins */
        loader_log_line("a51audio: GPB2 configured for AUD_I2S2 bus (func 2, 4x drive)\n");
    }

    if (!pinctrl) return -1;

    /* 3. Clocks: CMU_DISPAUD ungate & dividers */
    audio_wr(cmu + 0x2008, audio_rd(cmu + 0x2008) | 1u); /* UAIF2 BCLK gate */
    audio_wr(cmu + 0x2018, audio_rd(cmu + 0x2018) | 1u); /* UAIF2 reset gate */
    audio_wr(cmu + 0x2020, audio_rd(cmu + 0x2020) | (1u << 21) | 1u); /* ABOX ACLK */
    audio_wr(cmu + 0x2030, audio_rd(cmu + 0x2030) | 1u); /* ABOX CCLK */
    audio_wr(cmu + 0x2078, audio_rd(cmu + 0x2078) | 1u); /* LHS_AXI_D_ABOX AXI DRAM bus gate */
    audio_wr(cmu + 0x20a4, audio_rd(cmu + 0x20a4) | 1u); /* RSTNSYNC_CLK_DISPAUD_AUD */
    uint32_t bclk = 0;
    uint32_t div = a51_bclk_div(audio_rd(cmu + 0x160), audio_rd(cmu + 0x16c),
        audio_rd(cmu + 0x1800), &bclk);
    char clock_log[160];
    snprintf(clock_log, sizeof(clock_log), "a51audio: retained PLL=%08x K=%08x AUDIF=%08x BCLK estimate=%u divider=%u\n",
        audio_rd(cmu + 0x160), audio_rd(cmu + 0x16c), audio_rd(cmu + 0x1800), bclk, div);
    loader_log_line(clock_log);
    if (!div) return -1;
    audio_wr(cmu + 0x182c, (audio_rd(cmu + 0x182c) & ~511u) | (div - 1));
    audio_wr(cmu + 0x1018, audio_rd(cmu + 0x1018) & ~1u); /* internal UAIF2 parent */
    /* This driver uses reserved physical DRAM, not DSP IOVA mappings. */
    vm_offset_t sysmmu = ml_io_map(0x14920000UL, 0x1000);
    if (!sysmmu) return -1;
    uint32_t mmu_before = audio_rd(sysmmu);
    audio_wr(sysmmu, 0u); /* Samsung CTRL_DISABLE: translation bypass */
    if (audio_rd(sysmmu) != 0) return -1;
    snprintf(clock_log, sizeof(clock_log), "a51audio: ABOX SysMMU CTRL %08x -> %08x\n", mmu_before, audio_rd(sysmmu));
    loader_log_line(clock_log);

    /* 5. ABOX system registers & UAIF2 interface */
    abox_base = ml_io_map(0x14a50000UL, 0x10000);
    if (abox_base) {
        /* Power on ABOX system */
        audio_wr(abox_base + 0x0010, 1u);

        /* Route SIFS1 to UAIF2 SPK (bits [11:8] = 2) */
        uint32_t route = audio_rd(abox_base + 0x0040);
        route &= ~(0xfu << 8);
        route |= (2u << 8);
        audio_wr(abox_base + 0x0040, route);

        /* SPUS_CTRL0 (0x0200): Chain 0 (RDMA0->SIFS1, ASRC Off) & Chain 7 (RDMA7->SIFS1, ASRC Off) */
        audio_wr(abox_base + 0x0200, 0u);

        /* SPUS_CTRL1 (0x0204): SIFS_OUT1_SEL selects SPUS OUT0 (bits 18:16 = 0), MIXP format 16-bit 2ch (bits 4:0 = 9) */
        audio_wr(abox_base + 0x0204, (0u << 16) | 9u);

        /* UAIF2 CTRL1: 16-bit 2ch I2S, BCLK polarity 1, slot_max=1, sbit_max=15 -> 0x0984F000 */
        audio_wr(abox_base + 0x0524, 0x0984F000);

        /* UAIF2 CTRL0: Set FIFO diff = 4 samples, ABOX Master Mode (bit 2), leave SPK_ENABLE (bit 0) OFF until DMA is primed */
        audio_wr(abox_base + 0x0520, (4u << 24) | (1u << 2));

        /* Stop before changing DMA geometry; no continuous boot tone. */
        audio_wr(abox_base + 0x1000, 0u);
        audio_wr(abox_base + 0x1700, 0u);
        dma_virt_buffer = (int16_t *)ml_io_map(A51_DMA_BASE_PA, A51_DMA_BUFFER_SIZE);
        if (!dma_virt_buffer) return -1;
        volatile uint32_t *words = (volatile uint32_t *)dma_virt_buffer;
        for (uint32_t f = 0; f < A51_DMA_FRAMES; f++) words[f] = 0;
        dma_write_frame_offset = 0;
        dma_writer_started = false;
        audio_wr(abox_base + 0x1008, (uint32_t)A51_DMA_BASE_PA);
        audio_wr(abox_base + 0x100c, (uint32_t)(A51_DMA_BASE_PA + A51_DMA_BUFFER_SIZE));
        audio_wr(abox_base + 0x1010, A51_DMA_PERIOD);
        audio_wr(abox_base + 0x1014, (uint32_t)A51_DMA_BASE_PA);
        audio_wr(abox_base + 0x1018, 0x007fffffu); /* half of the 24-bit maximum */
        audio_wr(abox_base + 0x101c, 1u);
        audio_wr(abox_base + 0x1000, 1u);
        loader_log_line("a51audio: RDMA0 physical ring enabled, 4096-byte period; RDMA7 stopped\n");

        /* Now that RDMA is streaming samples into SIFS1 FIFO, enable UAIF2 SPK transmitter */
        audio_wr(abox_base + 0x0520, (1u << 0) | (4u << 24) | (1u << 2));
        delay(20000); /* 20ms settling time for BCLK and WS */

        char log[160];
        snprintf(log, sizeof(log), "a51audio: ABOX UAIF2 active: CTRL0=0x%08x, CTRL1=0x%08x, STATUS=0x%08x, RDMA0_STATUS=0x%08x\n",
                 audio_rd(abox_base + 0x0520), audio_rd(abox_base + 0x0524),
                 audio_rd(abox_base + 0x052c), audio_rd(abox_base + 0x1030));
        loader_log_line(log);
        return 0;
    }
    return -1;
}

/* =========================================================================
 * TAS2562 Smart Amp Bring-up (invoked AFTER clocks and pinmux are active!)
 * ========================================================================= */
static int tas2562_bringup(void)
{
    char log[256];
    amp_gpio = ml_io_map(0x11c20000UL, 0x1000);
    if (!amp_gpio) {
        loader_log_line("a51audio: failed to map CMGP GPIO (0x11C20000)\n");
        return -1;
    }

    /* 1. Configure internal pull-ups on I2C lines: gpm2-0 (SCL) and gpm3-0 (SDA) */
    audio_wr(amp_gpio + 0x040 + 8, 3u);  /* gpm2-0 PUD = EXYNOS_PIN_PULL_UP */
    audio_wr(amp_gpio + 0x060 + 8, 3u);  /* gpm3-0 PUD = EXYNOS_PIN_PULL_UP */
    audio_wr(amp_gpio + 0x040 + 12, 3u); /* gpm2-0 DRV = 4x */
    audio_wr(amp_gpio + 0x060 + 12, 3u); /* gpm3-0 DRV = 4x */

    /* Release lines to high-Z input */
    amp_line(0x040, true);
    amp_line(0x060, true);
    delay(100);

    /* Diagnostic bus idle check */
    int scl_idle = amp_read_scl();
    int sda_idle = amp_read_sda();
    snprintf(log, sizeof(log), "a51audio: CMGP I2C bus state: SCL=%d, SDA=%d\n", scl_idle, sda_idle);
    loader_log_line(log);

    /* Run bus recovery in case slave was previously stuck in data phase */
    amp_bus_recovery();

    /* 2. Hardware Reset Sequence: gpm0-0 (spk_en / ti,reset-gpio)
     * Active LOW pulse: 20ms LOW, then 20ms HIGH
     */
    vm_offset_t p_rst = amp_gpio + 0x000;
    audio_wr(p_rst + 8, 3u);  /* pull-up */
    audio_wr(p_rst + 12, 3u); /* max drive */
    /* Drive LOW (Reset active) */
    audio_wr(p_rst + 4, audio_rd(p_rst + 4) & ~1u);
    audio_wr(p_rst + 0, (audio_rd(p_rst + 0) & ~15u) | 1u);
    __asm__ volatile("dsb sy" ::: "memory");
    delay(20000); /* 20 ms reset pulse */

    /* Drive HIGH (Reset released / enabled) */
    audio_wr(p_rst + 4, audio_rd(p_rst + 4) | 1u);
    __asm__ volatile("dsb sy" ::: "memory");
    delay(20000); /* 20 ms reset recovery */
    loader_log_line("a51audio: TAS2562 hardware reset completed (gpm0-0 driven HIGH)\n");

    /* Invalidate cached book/page after hardware reset */
    current_book = -1;
    current_page = -1;

    /* 3. Probe: Read Silicon ID from Book 0, Page 0, Reg 0x7D (TAS2562_REVISIONANDPGID) */
    uint8_t id = 0;
    int err = amp_read(0, 0, 0x7D, &id);
    snprintf(log, sizeof(log), "a51audio: TAS2562 probe: silicon_id=0x%02x (err=%d, SCL=%d, SDA=%d)\n",
             id, err, amp_read_scl(), amp_read_sda());
    loader_log_line(log);

    if (err != 0) {
        loader_log_line("a51audio: TAS2562 I2C probe failed; aborting amplifier configuration\n");
        return err;
    }

    /* 4. Software Reset: Book 0, Page 0, Reg 0x01 = 0x01 */
    if (amp_write(0, 0, 0x01, 0x01) != 0) return -1;
    delay(20000); /* 20 ms post-SW-reset settling */
    current_book = -1;
    current_page = -1;

    /* 5. Configure Hardware Settings matching Exynos 9611 Android Kernel */
    /* Book 0, Page 0 */
    if (amp_write(0, 0, 0x04, 0xCF) != 0) return -1; /* MISCCONFIG0: auto retry all faults */
    if (amp_write(0, 0, 0x0A, 0x03) != 0) return -1; /* TDMConfigurationReg4: Exynos slot mode */
    if (amp_write(0, 0, 0x38, 0x08) != 0) return -1; /* CLOCKCONFIGURATION: 32fs, 16-bit stereo */
    if (amp_write(0, 0, 0x35, 0x78) != 0) return -1; /* BOOSTSLOPE */
    if (amp_write(0, 0, 0x3B, 0x38) != 0) return -1; /* VBATFILTER */
    if (amp_write(0, 0, 0x3C, 0x3C) != 0) return -1; /* CLASSHRELEASETIMER */

    /* Book 0, Page 0xFD: Class-D & Internal Boost Oscillator (ti,bst-clk-src = 1) */
    if (amp_write(0, 0xFD, 0x0D, 0x0D) != 0) return -1; /* TESTPAGECONFIGURATION */
    if (amp_write(0, 0xFD, 0x19, 0x80) != 0) return -1; /* CLASSDCONFIGURATION1 */
    if (amp_write(0, 0xFD, 0x32, 0x49) != 0) return -1; /* CLASSDCONFIGURATION2 */
    if (amp_write(0, 0xFD, 0x33, 0x8E) != 0) return -1; /* CLASSDCONFIGURATION3 */
    if (amp_write(0, 0xFD, 0x3F, 0x21) != 0) return -1; /* CLASSDCONFIGURATION4 */
    if (amp_write(0, 0xFD, 0x5F, 0xC5) != 0) return -1; /* EFFICIENCYCONFIGURATION: OSC_BOOST_CLK enabled */
    if (amp_write(0, 0xFD, 0x0D, 0x0D) != 0) return -1; /* Confirm test page config */

    /* Book 0, Page 0: Audio format, Volume, Power */
    if (amp_write(0, 0, 0x06, 0x08) != 0) return -1; /* 48 kHz sample rate auto-detect */
    if (amp_write(0, 0, 0x07, 0x03) != 0) return -1; /* I2S falling edge, 1-bit offset */
    if (amp_write(0, 0, 0x08, 0x10) != 0) return -1; /* TAS2562_TDMCONFIGURATIONREG2_RXSCFG54_MONO_LEFT (Slot 0 Mono) */
    if (amp_write(0, 0, 0x09, 0x00) != 0) return -1; /* Slot 0 = Left */
    if (amp_write(0, 0, 0x0B, 0x42) != 0) return -1; /* IV slot config */
    if (amp_write(0, 0, 0x0C, 0x40) != 0) return -1;
    if (amp_write(0, 0, 0x31, 0x00) != 0) return -1; /* TAS2562_DIGITALINPUTPINPULLDOWN: disable weak pull-downs */
    if (amp_write(0, 0, 0x3E, 0x00) != 0) return -1; /* TAS2562_ICN_SW_REG: disable ICN squelch muting */
    if (amp_write(0, 0, 0x03, 0x1E) != 0) return -1; /* Playback Volume/Level (+17.5 dB full output level) */

    /* 6. Clear latched interrupts while clocks are running and transition to ACTIVE */
    uint8_t pwr = 0xFF, irq = 0xFF;
    for (int retry = 0; retry < 15; retry++) {
        if (amp_write(0, 0, 0x30, 0x04) != 0) return -1; /* TAS2562_INTERRUPTCONFIGURATION: LTCHINTCLEAR */
        if (amp_read(0, 0, 0x24, &irq) != 0) return -1;   /* TAS2562_LATCHEDINTERRUPTREG0: read and clear */
        if (amp_write(0, 0, 0x02, 0x00) != 0) return -1; /* TAS2562_POWERCONTROL: ACTIVE */
        delay(6000);                 /* 6ms settling */
        if (amp_read(0, 0, 0x02, &pwr) != 0) return -1;
        if (amp_read(0, 0, 0x24, &irq) != 0) return -1;
        if (pwr == 0x00 && (irq & 0x04) == 0) {
            break;
        }
    }
    snprintf(log, sizeof(log), "a51audio: TAS2562 power_mode=0x%02x, latched_irq=0x%02x\n", pwr, irq);
    loader_log_line(log);

    /* 7. Diagnostic Status Readbacks: INTSTATUS, Live Clock Faults, and Battery ADC */
    uint8_t intstatus = 0, liveirq = 0, vbat_msb = 0, vbat_lsb = 0;
    if (amp_read(0, 0, 0x78, &intstatus) != 0) return -1;
    if (amp_read(0, 0, 0x1F, &liveirq) != 0) return -1;
    if (amp_read(0, 0, 0x2A, &vbat_msb) != 0) return -1;
    if (amp_read(0, 0, 0x2B, &vbat_lsb) != 0) return -1;
    uint32_t vbat_mv = (((uint32_t)vbat_msb << 4) | (vbat_lsb >> 4)) * 61 / 10;
    snprintf(log, sizeof(log), "a51audio: TAS2562 state: INTSTATUS=0x%02x (ClassD=%d, DAC=%d), LIVE_IRQ=0x%02x, VBAT=%u mV\n",
             intstatus, !!(intstatus & 0x04), !!(intstatus & 0x08), liveirq, vbat_mv);
    loader_log_line(log);

    return (pwr == 0x00 && (irq & 0x04) == 0 && (liveirq & 0x04) == 0) ? 0 : -1;
}

/* =========================================================================
 * Driver Initialization Entry Point
 * ========================================================================= */
static void a51audio_init(void)
{
    uint32_t step = 0;
    if (!PE_parse_boot_argn("a51audio", &step, sizeof(step))) {
        step = 4; /* Default to fully enabled audio on A51 */
    }
    if (step == 0) return;

    loader_log_line("a51audio: initializing Galaxy A51 audio subsystem...\n");

    /* 1. Verify PMU DISPAUD power domain */
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

    /* 2. Map CMU_DISPAUD */
    vm_offset_t cmu = ml_io_map(0x14980000UL, 0x4000);
    if (!cmu) {
        loader_log_line("a51audio: CMU mapping failed; aborting\n");
        return;
    }

    /* 3. Configure Exynos hardware pinmux, clocks, ABOX routing & DMA FIRST */
    if (a51_audio_hardware_init(cmu) != 0) {
        loader_log_line("a51audio: hardware setup failed; sink unavailable\n");
        return;
    }

    /* 4. Bring up TAS2562 Smart Amp (now that BCLK is actively running!) */
    int amp_status = tas2562_bringup();

    if (amp_status != 0) {
        (void)amp_write(0, 0, 0x02, 0x02); /* shutdown */
        audio_wr(abox_base + 0x1000, 0u);
        audio_wr(abox_base + 0x0520, audio_rd(abox_base + 0x0520) & ~1u);
        loader_log_line("a51audio: amp configuration failed; sink unavailable\n");
        return;
    }

    /* 5. Register with Darwin / CoreAudio as primary output sink */
    hakios_audio_set_sink("Galaxy A51 Speaker (TAS2562 / ABOX)", a51_audio_sink);
    audio_sink_active = true;

    char msg[128];
    snprintf(msg, sizeof(msg), "a51audio: registered speaker sink with CoreAudio (amp_status=%d)\n", amp_status);
    loader_log_line(msg);
}

STARTUP(EARLY_BOOT, STARTUP_RANK_LAST, a51audio_init);
