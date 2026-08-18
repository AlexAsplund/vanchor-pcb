/*
 * main.cpp — vanchor helm-board Pico 2 firmware.
 *
 * One Pico replaces both vanchor-ng Arduinos: it is the ENGINE board (thrust
 * via the external BTN8982 driver on J13) and the STEERING board (on-board
 * BTN8982 bridge + AS5600 azimuth encoder + hall zero index) speaking the
 * exact vanchor line protocol on TWO equivalent transports — USB-CDC and an
 * I2C slave tunnel at 0x42 on the SBC ribbon (docs/I2C-TUNNEL.md):
 *
 *   in :  CMD <pwm> <dir> <steer> [<seq>]*HH     (combined, the default)
 *         STEERD <deg> [<seq>]*HH                (v2.1 degrees-native)
 *         THRUST <pwm> <dir> [<seq>]*HH          (split thrust channel)
 *   out:  A <angle_deg> <ok> <wrap_pct> <seq>*HH   ~10 Hz
 *         E <pwm> <dir> <state> <seq>*HH           ~5 Hz
 *
 * Pi side: set motor_port to this board's CDC device (e.g. /dev/ttyACM0).
 * Baud is ignored on CDC. NMEA2000 (GP18/19) is intentionally absent for now.
 *
 * Safety chain: 800 ms protocol watchdog -> thrust slews to zero + steering
 * holds (worm self-locks); RP2350 hardware watchdog (2 s) reboots a wedged
 * firmware, and the board's 100 k pulldowns on every EN/INH pin keep both
 * bridges disabled through reset and reflash.
 */
#include <stdarg.h>
#include <stdio.h>
#include <string.h>

#include <stdlib.h>

#include "hardware/adc.h"
#include "hardware/clocks.h"
#include "hardware/flash.h"
#include "hardware/gpio.h"
#include "hardware/i2c.h"
#include "hardware/pwm.h"
#include "hardware/watchdog.h"
#include "pico/flash.h"
#include "pico/stdlib.h"

#include "board.h"
#include "config.h"

// Stamped by CMake from `git describe`; "dev" for out-of-tree builds.
#ifndef FW_VERSION
#define FW_VERSION "dev"
#endif
#if PICO_RP2040
#define MCU_NAME "pico"
#else
#define MCU_NAME "pico2"
#endif
#include "control_logic.h"
#include "i2c_tunnel.h"
#include "protocol_ext.h"

// ------------------------------------------------------------------ PWM -- //
// clk_sys / clkdiv 2 = PWM tick. Read at init instead of hardcoding 75 MHz:
// RP2350 runs 150 MHz but the RP2040 (plain Pico, a supported DIY target)
// runs 125 MHz -- a hardcoded tick made every PWM frequency come out x0.833
// there. wrap = tick/freq (at 62.5-75 MHz: 2 kHz -> 31249-37500, 16 kHz ->
// 3905-4687 — always >= 12-bit resolution, always < 65536).
static float PWM_TICK_HZ = 75.0e6f;   // overwritten in main() from clk_sys

static uint g_srvSlice, g_thrSlice;
static uint16_t g_srvWrap, g_thrWrap;

static uint16_t wrapForHz(float hz) {
  float w = PWM_TICK_HZ / hz - 1.0f;
  if (w > 65535.0f) w = 65535.0f;
  if (w < 1000.0f) w = 1000.0f;
  return (uint16_t)w;
}

static void pwmPairInit(uint pinA, uint pinB, uint *slice, uint16_t *wrap,
                        float hz) {
  gpio_set_function(pinA, GPIO_FUNC_PWM);
  gpio_set_function(pinB, GPIO_FUNC_PWM);
  *slice = pwm_gpio_to_slice_num(pinA);
  *wrap = wrapForHz(hz);
  pwm_set_clkdiv(*slice, 2.0f);
  pwm_set_wrap(*slice, *wrap);
  pwm_set_chan_level(*slice, PWM_CHAN_A, 0);
  pwm_set_chan_level(*slice, PWM_CHAN_B, 0);
  pwm_set_enabled(*slice, true);
}

// Servo bridge: signed -255..255. RPWM = channel A (GP8), LPWM = B (GP9).
static void servoDrive(int signedPwm) {
  uint32_t lvl =
      (uint32_t)((signedPwm < 0 ? -signedPwm : signedPwm)) * g_srvWrap / 255;
  pwm_set_chan_level(g_srvSlice, PWM_CHAN_A, signedPwm > 0 ? lvl : 0);
  pwm_set_chan_level(g_srvSlice, PWM_CHAN_B, signedPwm < 0 ? lvl : 0);
}

// Thrust bridge: magnitude 0..1 in `dir` (+1 F on RPWM/GP12, -1 R on LPWM).
static void thrustDrive(float mag, int8_t dir) {
  uint32_t lvl = (uint32_t)(mag * (float)g_thrWrap + 0.5f);
  pwm_set_chan_level(g_thrSlice, PWM_CHAN_A, dir > 0 ? lvl : 0);
  pwm_set_chan_level(g_thrSlice, PWM_CHAN_B, dir < 0 ? lvl : 0);
}

// Current-adaptive thrust PWM frequency (see board.h / driver README).
// Retunes wrap + level together; only when the schedule moved past the
// hysteresis band, so it never hunts and any sub-cycle blip is rare.
static float g_thrFreqHz = 16000.0f;
static void thrustRetune(float hystA, float amps, float mag, int8_t dir) {
  float ideal = thrustFreqHzForAmps(amps);
  float atNow = thrustFreqHzForAmps(amps + hystA);
  float atLow = thrustFreqHzForAmps(amps - hystA);
  // move only if the band no longer contains the current frequency
  if (g_thrFreqHz <= atNow - 1.0f || g_thrFreqHz >= atLow + 1.0f) {
    g_thrFreqHz = ideal;
    g_thrWrap = wrapForHz(g_thrFreqHz);
    pwm_set_wrap(g_thrSlice, g_thrWrap);
    thrustDrive(mag, dir);  // rescale duty to the new wrap immediately
  }
}

// ---------------------------------------------------------------- AS5600 -- //
static const uint8_t AS5600_ADDR = 0x36;
static const uint8_t AS5600_REG_STATUS = 0x0B;  // then RAW_ANGLE hi, lo

struct EncoderRead {
  bool ok;        // transaction succeeded AND magnet detected
  uint16_t raw;   // 12-bit angle
};

static EncoderRead as5600Read() {
  EncoderRead r{false, 0};
  uint8_t reg = AS5600_REG_STATUS;
  uint8_t buf[3];
  if (i2c_write_timeout_us(ENC_I2C, AS5600_ADDR, &reg, 1, true, 1000) != 1)
    return r;
  if (i2c_read_timeout_us(ENC_I2C, AS5600_ADDR, buf, 3, false, 1000) != 3)
    return r;
  // MD (0x20) magnet detected; ML (0x10) magnet too weak -> the angle is
  // unreliable even though MD may still be set. MH (too strong) still reads
  // a valid angle, so it is tolerated.
  bool magnet = (buf[0] & 0x20) != 0 && (buf[0] & 0x10) == 0;
  r.raw = (uint16_t)(((buf[1] & 0x0F) << 8) | buf[2]);
  r.ok = magnet;
  return r;
}

// If the slave wedges holding SDA low (mid-transfer power blip), every read
// times out forever and steering stays in feedback-hold until power cycle.
// The standard remedy: reclaim the pins as GPIO, clock 9 SCL pulses so the
// slave finishes whatever bit it thinks it is sending, then re-init.
static void as5600BusRecover() {
  i2c_deinit(ENC_I2C);
  gpio_set_function(PIN_ENC_SCL, GPIO_FUNC_SIO);
  gpio_set_function(PIN_ENC_SDA, GPIO_FUNC_SIO);
  gpio_set_dir(PIN_ENC_SCL, GPIO_OUT);
  gpio_set_dir(PIN_ENC_SDA, GPIO_IN);   // observe only; never drive SDA
  for (int i = 0; i < 9; i++) {
    gpio_put(PIN_ENC_SCL, 0);
    busy_wait_us(5);
    gpio_put(PIN_ENC_SCL, 1);
    busy_wait_us(5);
  }
  i2c_init(ENC_I2C, ENC_I2C_HZ);
  gpio_set_function(PIN_ENC_SDA, GPIO_FUNC_I2C);
  gpio_set_function(PIN_ENC_SCL, GPIO_FUNC_I2C);
}

// Debounced encoder health + glitch gate around the raw unwrap:
//  - a single bad transaction must not drop feedback-ok for a tick (integral
//    dump + drive chatter on a marginal bus);
//  - a single corrupted-but-"successful" read must not feed the accumulator
//    (one glitch sample can alias the multi-turn count);
//  - sustained failure (~50 ticks) attempts a bus recovery.
// The worm gear self-locks, so the head cannot move while the loop holds in
// feedback-loss -- the position is frozen across an outage and the shortest-
// path unwrap on recovery is trustworthy. (The hall index still re-trues the
// zero on every centre pass as the absolute backstop.)
static const int ENC_BAD_TO_UNHEALTHY = 3;
static const int ENC_GOOD_TO_HEALTHY = 3;
static const int ENC_BAD_TO_BUSCLEAR = 50;
static const int16_t ENC_MAX_DELTA_PER_TICK = 512;  // 45 deg shaft / 2 ms

// ------------------------------------------------------------- hall zero -- //
// Open-collector hall pulls GP0 LOW at the centre magnet. On each (debounced)
// falling edge the ISR snapshots a request; the control loop applies it so
// the zero capture is race-free with the encoder accumulator.
static volatile bool g_hallEvent = false;
static volatile uint32_t g_hallLastMs = 0;

static void hallIsr(uint gpio, uint32_t events) {
  (void)gpio;
  (void)events;
  uint32_t now = to_ms_since_boot(get_absolute_time());
  if (now - g_hallLastMs >= HALL_DEBOUNCE_MS) {
    g_hallLastMs = now;
    g_hallEvent = true;
  }
}

// ------------------------------------------------------------------- ADC -- //
static float adcVolts(uint input) {
  adc_select_input(input);
  (void)adc_read();  // settle after mux switch
  uint32_t acc = 0;
  for (int i = 0; i < 4; i++) acc += adc_read();
  return (float)acc / 4.0f * ADC_VREF_V / 4096.0f;
}

// ------------------------------------------------------------ serial I/O -- //
// One accumulator per transport so interleaved half-lines cannot mix.
struct LineAccum {
  char buf[VANCHOR_LINE_MAX];
  uint8_t len = 0;
  bool poisoned = false;  // overflowed or NUL-corrupted: discard to newline
};
static LineAccum g_usbAcc, g_i2cAcc;

// Every outbound line goes to BOTH transports: USB always, the I2C tunnel
// whenever a master has polled recently (so the FIFO never fills with stale
// telemetry when nobody is on the bus).
static void sendLine(char *buf, size_t cap) {
  vanchorAppendCrc(buf, (unsigned int)cap);
  fputs(buf, stdout);
  fputs("\r\n", stdout);
  fflush(stdout);
  i2cTunnelSendLine(buf, to_ms_since_boot(get_absolute_time()));
}

// -------------------------------------------------------------- config --- //
static HelmConfig g_cfg;

// Persisted image lives in the LAST 4 kB flash sector, far above the code.
#define CONF_FLASH_OFFSET (PICO_FLASH_SIZE_BYTES - FLASH_SECTOR_SIZE)
#define CONF_WRITE_MIN_MS 2000  // wear/abuse guard between erase cycles

static const uint8_t *confFlashPtr() {
  return (const uint8_t *)(XIP_BASE + CONF_FLASH_OFFSET);
}

static void confFlashJob(void *param) {
  // Runs with IRQs off / other core locked out (flash_safe_execute).
  flash_range_erase(CONF_FLASH_OFFSET, FLASH_SECTOR_SIZE);
  flash_range_program(CONF_FLASH_OFFSET, (const uint8_t *)param,
                      FLASH_PAGE_SIZE);
}

// Persist `c`. Returns 1 written+verified, 0 flash already identical (no
// erase happened), -1 rate-limited, -2 flash error/verify mismatch.
static int confPersist(const HelmConfig &c, uint32_t nowMs) {
  static uint32_t lastWriteMs = 0;
  static uint8_t img[FLASH_PAGE_SIZE];
  memset(img, 0xFF, sizeof img);
  confSerialize(c, img);
  if (memcmp(confFlashPtr(), img, sizeof img) == 0) return 0;  // diff guard
  if (lastWriteMs != 0 && (nowMs - lastWriteMs) < CONF_WRITE_MIN_MS) return -1;
  watchdog_update();  // the erase stalls everything for tens of ms
  if (flash_safe_execute(confFlashJob, img, 500) != PICO_OK) return -2;
  lastWriteMs = nowMs;
  return memcmp(confFlashPtr(), img, sizeof img) == 0 ? 1 : -2;
}

// The config currently stored in flash (defaults where absent/invalid).
static HelmConfig confStored() {
  HelmConfig c;
  confDeserialize(c, confFlashPtr(), FLASH_PAGE_SIZE);
  return c;
}

// -------------------------------------------------------------- state ---- //
static float g_wantThrust = 0.0f;   // 0..1 requested magnitude
static int8_t g_wantDir = +1;
// PER-CHANNEL watchdogs. With the split channels (STEERD + THRUST are
// separate Pi-side writers) a single shared timestamp would let a live
// steering stream mask a dead thrust writer -- prop stuck at the last pwm
// indefinitely. On the two-Arduino system each board's own watchdog covered
// its channel; one board must keep that per-channel guarantee.
static uint32_t g_lastThrustMs = 0;  // last valid CMD or THRUST
static uint32_t g_lastSteerMs = 0;   // last valid CMD or STEERD
static bool g_everCommanded = false;
static int g_lastSeq = -1;

static int g_confLoaded = -1;  // keys applied from flash at boot (-1 = none)
static ThrustGate g_thrust;
static SteeringLoop g_steer;
static EncoderUnwrap g_enc;
static int32_t g_zeroAccum = 0;     // encoder counts at azimuth zero
static bool g_feedbackOk = false;
static float g_angleDeg = 0.0f;
static float g_thrAmpsFilt = 0.0f;
static float g_srvAmpsFilt = 0.0f;

static void confReply(const char *fmt, ...) {
  char buf[VANCHOR_LINE_MAX];
  va_list ap;
  va_start(ap, fmt);
  vsnprintf(buf, sizeof buf, fmt, ap);
  va_end(ap);
  sendLine(buf, sizeof buf);
}

// "CONF <key> <value>"  -> RAM only.
// "CONFW <key> <value>" -> RAM + persist THAT KEY into the stored image.
// "CONFSAVE"            -> persist the whole active config.
// "CONFDUMP"            -> one "C <key> <ram> <stored>" line per key.
// Config traffic never feeds the motor watchdog or the heartbeat seq.
static void handleConf(const char *line, uint32_t nowMs) {
  const char *p = line + 4;
  bool writeThrough = false;
  if (strncmp(p, "SAVE", 4) == 0) {
    int r = confPersist(g_cfg, nowMs);
    confReply(r == 1   ? "C saved"
              : r == 0 ? "C clean"
              : r == -1 ? "C err ratelimit"
                        : "C err flash");
    return;
  }
  if (strncmp(p, "DUMP", 4) == 0) {
    HelmConfig stored = confStored();
    for (int i = 0; i < CONF_NKEYS; i++)
      confReply("C %s %g %g", CONF_KEYS[i].name, (double)confGet(g_cfg, i),
                (double)confGet(stored, i));
    confReply("C end %d", CONF_NKEYS);
    return;
  }
  if (*p == 'W') {
    writeThrough = true;
    p++;
  }
  if (*p != ' ') return;  // unknown CONFx token: ignore
  while (*p == ' ') p++;
  char key[24];
  size_t k = 0;
  while (*p && *p != ' ' && k + 1 < sizeof key) key[k++] = *p++;
  key[k] = '\0';
  int idx = confFind(key);
  if (idx < 0) {
    confReply("C err key %s", key);
    return;
  }
  while (*p == ' ') p++;
  char *endp = nullptr;
  float v = strtof(p, &endp);
  if (endp == p || !confSet(g_cfg, idx, v)) {
    confReply("C err range %s", key);
    return;
  }
  if (!writeThrough) {
    confReply("C ok %s %g", key, (double)v);
    return;
  }
  // Write-through: update ONLY this key in the stored image, so other
  // in-RAM experiments stay temporary.
  HelmConfig stored = confStored();
  confSet(stored, idx, v);
  int r = confPersist(stored, nowMs);
  confReply(r == 1   ? "C wrote %s %g"
            : r == 0 ? "C clean %s %g"
            : r == -1 ? "C err ratelimit %s"
                      : "C err flash %s",
            key, (double)v);
}

// "INFO" -> identity/version/health snapshot as "I ..." lines (the Pi's
// feedback parsers ignore them; a bench console reads them directly).
static void handleInfo(uint32_t nowMs) {
  confReply("I fw %s board helm-4.2 mcu " MCU_NAME, FW_VERSION);
  confReply("I proto 2.1 crc %d wdog %d", VANCHOR_REQUIRE_CRC,
            VANCHOR_WATCHDOG_MS);
  confReply("I conf %d keys %d flash %s", CONF_VERSION, CONF_NKEYS,
            g_confLoaded < 0 ? "defaults" : "stored");
  confReply("I i2c 0x%02X v%d active %d", TUN_I2C_ADDR, 1,
            i2cTunnelActive(nowMs) ? 1 : 0);
  confReply("I up %lu vbat %.1f ang %.1f fb %d", nowMs / 1000,
            (double)(adcVolts(2) * g_cfg.calVbat), (double)g_angleDeg,
            g_feedbackOk ? 1 : 0);
  confReply("I end 5");
}

static void handleLine(char *line, uint32_t nowMs) {
  if (!vanchorAcceptLine(line)) return;  // CRC gate (VANCHOR_REQUIRE_CRC)
  if (strcmp(line, "INFO") == 0) {
    handleInfo(nowMs);
    return;
  }
  if (strncmp(line, "CONF", 4) == 0) {
    handleConf(line, nowMs);
    return;
  }
  int pwm, steer, seq;
  char dir;
  float deg;
  if (vanchorParseCmd(line, &pwm, &dir, &steer, &seq)) {
    g_wantThrust = (float)pwm / 255.0f;
    g_wantDir = (dir == 'R') ? -1 : +1;
    g_steer.setTarget(g_cfg, ((float)steer / 100.0f) * g_cfg.steerFull);
    g_lastThrustMs = nowMs;
    g_lastSteerMs = nowMs;
  } else if (vanchorParseSteerDeg(line, &deg, &seq)) {
    g_steer.setTarget(g_cfg, deg);
    g_lastSteerMs = nowMs;
  } else if (vanchorParseThrust(line, &pwm, &dir, &seq)) {
    g_wantThrust = (float)pwm / 255.0f;
    g_wantDir = (dir == 'R') ? -1 : +1;
    g_lastThrustMs = nowMs;
  } else {
    return;  // unknown token: ignore, do not feed the watchdog
  }
  g_lastSeq = seq;
  g_everCommanded = true;
}

static void accumFeed(LineAccum &a, int c, uint32_t nowMs) {
  if (c == '\n' || c == '\r') {
    if (a.len > 0 && !a.poisoned) {
      a.buf[a.len] = '\0';
      handleLine(a.buf, nowMs);
    }
    a.len = 0;
    a.poisoned = false;
    return;
  }
  // The protocol is pure printable ASCII. An embedded NUL would truncate the
  // strlen-based CRC scan, converting a corrupted line into a "valid"
  // CRC-less prefix -- exactly the class the CRC exists to catch.
  if (c == '\0') {
    a.poisoned = true;
    return;
  }
  if (a.poisoned) return;  // discarding the rest of an oversized/bad line
  if (a.len < VANCHOR_LINE_MAX - 1) {
    a.buf[a.len++] = (char)c;
  } else {
    // Overflow: poison until the next newline. Just resetting len would
    // parse the TAIL of the same wire line as a fresh line -- a CRC-valid
    // substring (or, CRC-less builds, any digit-shaped garbage) after the
    // reset boundary would be accepted as a command.
    a.len = 0;
    a.poisoned = true;
  }
}

static void pollSerial(uint32_t nowMs) {
  for (;;) {
    int c = getchar_timeout_us(0);
    if (c == PICO_ERROR_TIMEOUT) break;
    accumFeed(g_usbAcc, c, nowMs);
  }
  for (;;) {
    int c = i2cTunnelGetchar();
    if (c < 0) break;
    accumFeed(g_i2cAcc, c, nowMs);
  }
}

// ------------------------------------------------------------------ main -- //
int main() {
  stdio_init_all();
  PWM_TICK_HZ = (float)clock_get_hz(clk_sys) / 2.0f;  // clkdiv 2 in pwmPairInit

  // Bridge enables as plain outputs, LOW (disabled) until first command.
  const uint enPins[] = {PIN_SRV_R_EN, PIN_SRV_L_EN, PIN_THR_R_EN,
                         PIN_THR_L_EN};
  for (uint p : enPins) {
    gpio_init(p);
    gpio_put(p, 0);
    gpio_set_dir(p, GPIO_OUT);
  }
  gpio_init(PIN_LED_STAT);
  gpio_set_dir(PIN_LED_STAT, GPIO_OUT);

  pwmPairInit(PIN_SRV_RPWM, PIN_SRV_LPWM, &g_srvSlice, &g_srvWrap, SRV_PWM_HZ);
  pwmPairInit(PIN_THR_RPWM, PIN_THR_LPWM, &g_thrSlice, &g_thrWrap, g_thrFreqHz);

  // AS5600 on I2C1 (board has the pull-ups).
  i2c_init(ENC_I2C, ENC_I2C_HZ);
  gpio_set_function(PIN_ENC_SDA, GPIO_FUNC_I2C);
  gpio_set_function(PIN_ENC_SCL, GPIO_FUNC_I2C);

  // I2C tunnel to the SBC (slave 0x42 on the ribbon's I2C3).
  i2cTunnelInit();

  // Hall zero input. The PCB has a 10k pull-up + RC; enable the internal
  // pull-up too so a bare-Pico DIY build with an open-collector hall does
  // not float (spurious re-zero IRQs). Harmless in parallel with the 10k.
  gpio_init(PIN_HALL_ZERO);
  gpio_set_dir(PIN_HALL_ZERO, GPIO_IN);
  gpio_pull_up(PIN_HALL_ZERO);
  gpio_set_irq_enabled_with_callback(PIN_HALL_ZERO, GPIO_IRQ_EDGE_FALL, true,
                                     &hallIsr);

  adc_init();
  adc_gpio_init(PIN_ADC_SERVO_IS);
  adc_gpio_init(PIN_ADC_THR_IS);
  adc_gpio_init(PIN_ADC_VBAT);

  // Stored configuration (defaults when the sector is blank/invalid).
  g_confLoaded = confDeserialize(g_cfg, confFlashPtr(), FLASH_PAGE_SIZE);

  // Prime the encoder and hold the current heading (steering.ino boot rule).
  EncoderRead er = as5600Read();
  if (er.ok) {
    g_enc.feed(er.raw);
    g_feedbackOk = true;
  }
  g_steer.targetDeg = g_enc.degrees(g_cfg, g_zeroAccum);
  g_steer.stallRefDeg = g_steer.targetDeg;

  uint32_t bootMs = to_ms_since_boot(get_absolute_time());
  g_lastThrustMs = bootMs;
  g_lastSteerMs = bootMs;
  uint32_t lastTickMs = bootMs;
  uint32_t lastAMs = bootMs, lastEMs = bootMs;
  absolute_time_t nextTick = make_timeout_time_us(CONTROL_TICK_US);

  // Hardware watchdog: reboots a wedged loop; the EN pulldowns keep both
  // bridges safe through the reboot.
  watchdog_enable(2000, true);

  for (;;) {
    watchdog_update();
    uint32_t nowMs = to_ms_since_boot(get_absolute_time());
    pollSerial(nowMs);

    if (!time_reached(nextTick)) continue;
    nextTick = make_timeout_time_us(CONTROL_TICK_US);

    float dtS = (float)(nowMs - lastTickMs) / 1000.0f;
    if (dtS <= 0.0f) dtS = 0.001f;
    lastTickMs = nowMs;

    // --- sensors --------------------------------------------------------- //
    er = as5600Read();
    static int encBadStreak = 0, encGoodStreak = 0;
    bool sampleOk = er.ok;
    if (sampleOk && g_enc.primed) {
      // Glitch gate: a shaft step > 45 deg in one 2 ms tick is physically
      // impossible (worm drive) -- corrupted read; do not feed the unwrap.
      int16_t d = (int16_t)(((er.raw - g_enc.prevRaw + ENC_COUNTS_PER_REV / 2) &
                             (ENC_COUNTS_PER_REV - 1)) -
                            ENC_COUNTS_PER_REV / 2);
      if (d > ENC_MAX_DELTA_PER_TICK || d < -ENC_MAX_DELTA_PER_TICK)
        sampleOk = false;
    }
    if (sampleOk) {
      g_enc.feed(er.raw);
      encBadStreak = 0;
      if (encGoodStreak < ENC_GOOD_TO_HEALTHY) encGoodStreak++;
      if (encGoodStreak >= ENC_GOOD_TO_HEALTHY) g_feedbackOk = true;
    } else {
      encGoodStreak = 0;
      if (encBadStreak < 1000000) encBadStreak++;
      if (encBadStreak >= ENC_BAD_TO_UNHEALTHY) g_feedbackOk = false;
      if (encBadStreak == ENC_BAD_TO_BUSCLEAR) as5600BusRecover();
    }
    if (g_hallEvent) {  // magnet edge: this position IS the hall reference
      g_hallEvent = false;
      float hallDeg = g_cfg.hallDeg * (g_cfg.encInvert >= 0.5f ? -1.0f : 1.0f);
      g_zeroAccum = g_enc.accum -
                    (int32_t)(hallDeg / 360.0f * g_cfg.encGear *
                              (float)ENC_COUNTS_PER_REV);
    }
    g_angleDeg = g_enc.degrees(g_cfg, g_zeroAccum);

    float thrAmps = adcVolts(1) / g_cfg.calThrVpa;
    float srvAmps = adcVolts(0) / g_cfg.calSrvVpa;
    g_thrAmpsFilt += 0.1f * (thrAmps - g_thrAmpsFilt);
    g_srvAmpsFilt += 0.1f * (srvAmps - g_srvAmpsFilt);

    // --- control --------------------------------------------------------- //
    bool thrustFailsafe = (nowMs - g_lastThrustMs) > VANCHOR_WATCHDOG_MS;
    bool steerFailsafe = (nowMs - g_lastSteerMs) > VANCHOR_WATCHDOG_MS;

    // Bridges stay disabled until the Pi has spoken once (defence in depth
    // on top of the board pulldowns); after that they are held enabled so
    // failsafe can still brake/hold.
    bool enable = g_everCommanded;
    gpio_put(PIN_SRV_R_EN, enable);
    gpio_put(PIN_SRV_L_EN, enable);
    gpio_put(PIN_THR_R_EN, enable);
    gpio_put(PIN_THR_L_EN, enable);

    float mag = g_thrust.update(g_cfg, g_wantThrust, g_wantDir, thrustFailsafe,
                                nowMs, dtS);
    thrustDrive(mag, g_thrust.appliedDir);
    thrustRetune(g_cfg.thrHystA, g_thrAmpsFilt, mag, g_thrust.appliedDir);

    int srvPwm = g_steer.update(g_cfg, g_angleDeg, g_feedbackOk, steerFailsafe,
                                g_srvAmpsFilt, nowMs, dtS);
    servoDrive(srvPwm);

    // --- status LED: solid on trouble, 1 Hz heartbeat otherwise ---------- //
    bool trouble =
        thrustFailsafe || steerFailsafe || !g_feedbackOk || g_steer.stalled;
    gpio_put(PIN_LED_STAT, trouble ? 1 : ((nowMs / 500) & 1));

    // --- feedback lines --------------------------------------------------- //
    if (nowMs - lastAMs >= REPORT_A_MS) {
      lastAMs = nowMs;
      int wrap = (int)(g_angleDeg / g_cfg.steerRange * 100.0f);
      if (wrap > 100) wrap = 100;
      if (wrap < -100) wrap = -100;
      char fb[VANCHOR_LINE_MAX];
      snprintf(fb, sizeof fb, "A %.1f %d %d %d", (double)g_angleDeg,
               g_feedbackOk ? 1 : 0, wrap, g_lastSeq);
      sendLine(fb, sizeof fb);
    }
    if (nowMs - lastEMs >= REPORT_E_MS) {
      lastEMs = nowMs;
      char fb[VANCHOR_LINE_MAX];
      snprintf(fb, sizeof fb, "E %d %c %s %d",
               (int)(g_thrust.applied * 255.0f + 0.5f),
               g_thrust.appliedDir < 0 ? 'R' : 'F', g_thrust.state, g_lastSeq);
      sendLine(fb, sizeof fb);
    }
  }
}
