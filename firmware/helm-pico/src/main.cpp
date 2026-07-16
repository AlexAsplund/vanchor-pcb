/*
 * main.cpp — vanchor helm-board Pico 2 firmware.
 *
 * One Pico replaces both vanchor-ng Arduinos: it is the ENGINE board (thrust
 * via the external BTN8982 driver on J13) and the STEERING board (on-board
 * BTN8982 bridge + AS5600 azimuth encoder + hall zero index) on a single
 * USB-CDC serial port speaking the exact vanchor line protocol:
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
#include <stdio.h>
#include <string.h>

#include "hardware/adc.h"
#include "hardware/gpio.h"
#include "hardware/i2c.h"
#include "hardware/pwm.h"
#include "hardware/watchdog.h"
#include "pico/stdlib.h"

#include "board.h"
#include "control_logic.h"
#include "protocol_ext.h"

// ------------------------------------------------------------------ PWM -- //
// 150 MHz clk_sys / clkdiv 2 = 75 MHz PWM tick: wrap = 75e6/freq (2 kHz ->
// 37500, 16 kHz -> 4687 — always >= 12-bit resolution, always < 65536).
static const float PWM_TICK_HZ = 75.0e6f;

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
static void thrustRetune(float amps, float mag, int8_t dir) {
  float ideal = thrustFreqHzForAmps(amps);
  float atNow = thrustFreqHzForAmps(amps + THR_FREQ_HYST_A);
  float atLow = thrustFreqHzForAmps(amps - THR_FREQ_HYST_A);
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
  bool magnet = (buf[0] & 0x20) != 0;  // MD: magnet detected
  r.raw = (uint16_t)(((buf[1] & 0x0F) << 8) | buf[2]);
  r.ok = magnet;
  return r;
}

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
static char g_line[VANCHOR_LINE_MAX];
static uint8_t g_lineLen = 0;

static void sendLine(char *buf, size_t cap) {
  vanchorAppendCrc(buf, (unsigned int)cap);
  fputs(buf, stdout);
  fputs("\r\n", stdout);
  fflush(stdout);
}

// -------------------------------------------------------------- state ---- //
static float g_wantThrust = 0.0f;   // 0..1 requested magnitude
static int8_t g_wantDir = +1;
static uint32_t g_lastCmdMs = 0;    // last *valid* command line
static bool g_everCommanded = false;
static int g_lastSeq = -1;

static ThrustGate g_thrust;
static SteeringLoop g_steer;
static EncoderUnwrap g_enc;
static int32_t g_zeroAccum = 0;     // encoder counts at azimuth zero
static bool g_feedbackOk = false;
static float g_angleDeg = 0.0f;
static float g_thrAmpsFilt = 0.0f;
static float g_srvAmpsFilt = 0.0f;

static void handleLine(char *line, uint32_t nowMs) {
  if (!vanchorAcceptLine(line)) return;  // CRC gate (VANCHOR_REQUIRE_CRC)
  int pwm, steer, seq;
  char dir;
  float deg;
  if (vanchorParseCmd(line, &pwm, &dir, &steer, &seq)) {
    g_wantThrust = (float)pwm / 255.0f;
    g_wantDir = (dir == 'R') ? -1 : +1;
    g_steer.setTarget(((float)steer / 100.0f) * STEER_FULL_SCALE_DEG);
  } else if (vanchorParseSteerDeg(line, &deg, &seq)) {
    g_steer.setTarget(deg);
  } else if (vanchorParseThrust(line, &pwm, &dir, &seq)) {
    g_wantThrust = (float)pwm / 255.0f;
    g_wantDir = (dir == 'R') ? -1 : +1;
  } else {
    return;  // unknown token: ignore, do not feed the watchdog
  }
  g_lastSeq = seq;
  g_lastCmdMs = nowMs;
  g_everCommanded = true;
}

static void pollSerial(uint32_t nowMs) {
  for (;;) {
    int c = getchar_timeout_us(0);
    if (c == PICO_ERROR_TIMEOUT) break;
    if (c == '\n' || c == '\r') {
      if (g_lineLen > 0) {
        g_line[g_lineLen] = '\0';
        handleLine(g_line, nowMs);
      }
      g_lineLen = 0;
    } else if (g_lineLen < VANCHOR_LINE_MAX - 1) {
      g_line[g_lineLen++] = (char)c;
    } else {
      g_lineLen = 0;  // overflow -> drop the line
    }
  }
}

// ------------------------------------------------------------------ main -- //
int main() {
  stdio_init_all();

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

  // Hall zero input (board has the pull-up + RC).
  gpio_init(PIN_HALL_ZERO);
  gpio_set_dir(PIN_HALL_ZERO, GPIO_IN);
  gpio_set_irq_enabled_with_callback(PIN_HALL_ZERO, GPIO_IRQ_EDGE_FALL, true,
                                     &hallIsr);

  adc_init();
  adc_gpio_init(PIN_ADC_SERVO_IS);
  adc_gpio_init(PIN_ADC_THR_IS);
  adc_gpio_init(PIN_ADC_VBAT);

  // Prime the encoder and hold the current heading (steering.ino boot rule).
  EncoderRead er = as5600Read();
  if (er.ok) {
    g_enc.feed(er.raw);
    g_feedbackOk = true;
  }
  g_steer.setTarget(0.0f);
  g_steer.targetDeg = g_enc.degrees(g_zeroAccum);
  g_steer.stallRefDeg = g_steer.targetDeg;

  uint32_t bootMs = to_ms_since_boot(get_absolute_time());
  g_lastCmdMs = bootMs;
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
    if (er.ok) g_enc.feed(er.raw);
    g_feedbackOk = er.ok;
    if (g_hallEvent) {  // magnet edge: this position IS the hall reference
      g_hallEvent = false;
      g_zeroAccum =
          g_enc.accum -
          (int32_t)(HALL_ANGLE_DEG / 360.0f * ENC_GEAR_RATIO *
                    (float)ENC_COUNTS_PER_REV);
    }
    g_angleDeg = g_enc.degrees(g_zeroAccum);

    float thrAmps = adcVolts(1) / THR_IS_V_PER_A;
    float srvAmps = adcVolts(0) / SERVO_IS_V_PER_A;
    g_thrAmpsFilt += 0.1f * (thrAmps - g_thrAmpsFilt);
    g_srvAmpsFilt += 0.1f * (srvAmps - g_srvAmpsFilt);

    // --- control --------------------------------------------------------- //
    bool failsafe = (nowMs - g_lastCmdMs) > VANCHOR_WATCHDOG_MS;

    // Bridges stay disabled until the Pi has spoken once (defence in depth
    // on top of the board pulldowns); after that they are held enabled so
    // failsafe can still brake/hold.
    bool enable = g_everCommanded;
    gpio_put(PIN_SRV_R_EN, enable);
    gpio_put(PIN_SRV_L_EN, enable);
    gpio_put(PIN_THR_R_EN, enable);
    gpio_put(PIN_THR_L_EN, enable);

    float mag = g_thrust.update(g_wantThrust, g_wantDir, failsafe, nowMs, dtS);
    thrustDrive(mag, g_thrust.appliedDir);
    thrustRetune(g_thrAmpsFilt, mag, g_thrust.appliedDir);

    int srvPwm = g_steer.update(g_angleDeg, g_feedbackOk, failsafe,
                                g_srvAmpsFilt, nowMs, dtS);
    servoDrive(srvPwm);

    // --- status LED: solid on trouble, 1 Hz heartbeat otherwise ---------- //
    bool trouble = failsafe || !g_feedbackOk || g_steer.stalled;
    gpio_put(PIN_LED_STAT, trouble ? 1 : ((nowMs / 500) & 1));

    // --- feedback lines --------------------------------------------------- //
    if (nowMs - lastAMs >= REPORT_A_MS) {
      lastAMs = nowMs;
      int wrap = (int)(g_angleDeg / STEER_RANGE_DEG * 100.0f);
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
