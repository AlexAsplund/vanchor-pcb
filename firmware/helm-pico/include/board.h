/*
 * board.h — helm board v4.2 pin map + tuning for the on-board Pico 2.
 *
 * Pin numbers are RP2350 GPIOs; the net names match the schematic
 * (boards/helm/sheets/mcu.py) and docs/HANDOFF.md. Anything marked
 * CALIBRATE has a bench procedure in the firmware README.
 *
 * DIY / bare-Pico builds: every #define below is #ifndef-guarded, so any pin
 * or default can be overridden from the build instead of editing this file:
 *   cmake -B build -DPICO_BOARD=pico \
 *     -DCMAKE_CXX_FLAGS="-DPIN_LED_STAT=25 -DTUN_I2C_ADDR=0x42"
 * See README "Bare Pico / DIY build" for the wiring that goes with it —
 * especially the EXTERNAL pulldowns on the four EN pins: the firmware cannot
 * protect the reset/BOOTSEL window, only resistors can.
 */
#ifndef HELM_BOARD_H
#define HELM_BOARD_H

// ---------------------------------------------------------------- inputs --
#ifndef PIN_HALL_ZERO
#define PIN_HALL_ZERO      0   // HALL_ZERO: open-collector hall (J9.3), 10k
#endif
                               // pull-up + RC on board; LOW at the magnet.

// I2C0 to the SBC (PI_SDA/PI_SCL on the ribbon): line-protocol tunnel,
// slave address 0x42 — equivalent to the USB CDC port (docs/I2C-TUNNEL.md).
#ifndef PIN_PI_SDA
#define PIN_PI_SDA         4
#endif
#ifndef PIN_PI_SCL
#define PIN_PI_SCL         5
#endif

// I2C1 master -> AS5600 steering encoder (J11; 4.7k pull-ups R9/R10 on board)
#ifndef PIN_ENC_SDA
#define PIN_ENC_SDA        6
#endif
#ifndef PIN_ENC_SCL
#define PIN_ENC_SCL        7
#endif
#ifndef ENC_I2C
#define ENC_I2C            i2c1
#endif
#ifndef ENC_I2C_HZ
#define ENC_I2C_HZ         400000
#endif

// -------------------------------------------------------- servo H-bridge --
// 2x BTN8982TA on protected VIN. IN = PWM, INH = enable (100k pulldowns on
// board keep the bridge disabled whenever the Pico is dead or rebooting).
#ifndef PIN_SRV_RPWM
#define PIN_SRV_RPWM       8   // U7 IN  (drive toward +deg / starboard)
#endif
#ifndef PIN_SRV_LPWM
#define PIN_SRV_LPWM       9   // U8 IN  (drive toward -deg / port)
#endif
#ifndef PIN_SRV_R_EN
#define PIN_SRV_R_EN      10   // U7 INH
#endif
#ifndef PIN_SRV_L_EN
#define PIN_SRV_L_EN      11   // U8 INH
#endif

// ------------------------------------------------- thrust bridge on J13 --
// 8-wire cable to the companion thrust-driver board (IBT-2 pin order).
#ifndef PIN_THR_RPWM
#define PIN_THR_RPWM      12
#endif
#ifndef PIN_THR_LPWM
#define PIN_THR_LPWM      13
#endif
#ifndef PIN_THR_R_EN
#define PIN_THR_R_EN      14
#endif
#ifndef PIN_THR_L_EN
#define PIN_THR_L_EN      15
#endif

#ifndef PIN_LED_STAT
#define PIN_LED_STAT      17   // yellow LED via R13 (bare Pico: use 25 = onboard LED)
#endif

// ------------------------------------------------------------------ ADCs --
#ifndef PIN_ADC_SERVO_IS
#define PIN_ADC_SERVO_IS  26   // ADC0: servo bridge current sense
#endif
#ifndef PIN_ADC_THR_IS
#define PIN_ADC_THR_IS    27   // ADC1: thrust driver current sense (mixed R/L)
#endif
#ifndef PIN_ADC_VBAT
#define PIN_ADC_VBAT      28   // ADC2: VBAT through 47k/10k divider
#endif

#ifndef ADC_VREF_V
#define ADC_VREF_V        3.3f
#endif
// VBAT divider R11 47k / R12 10k  ->  Vbat = Vadc * 5.7
#ifndef VBAT_SCALE
#define VBAT_SCALE        ((47.0f + 10.0f) / 10.0f)
#endif
// Thrust IS: BTN8982 kILIS ~= 22700; 1k loads at the driver, 1k series +
// 20k to GND on the helm. Simulated end-to-end: ~21 mV per motor amp
// (sim/README.md). CALIBRATE against a clamp meter before trusting it.
#ifndef THR_IS_V_PER_A
#define THR_IS_V_PER_A    0.021f
#endif
// Servo IS: RAW node 1k load (R19), so ~44 mV/A before the R18/C12 filter.
#ifndef SERVO_IS_V_PER_A
#define SERVO_IS_V_PER_A  0.044f
#endif

// ------------------------------------------------------- steering tuning --
// DEFAULTS ONLY from here down: every value below is runtime-tunable over
// the serial port (CONF/CONFW/CONFSAVE — see README + src/config.h). A
// value stored in the config flash sector overrides these at boot.
// Mirrors firmware/steering/steering.ino in vanchor-ng: same command scale,
// endstops and loop constants, so the Pi-side behaviour is unchanged.
#ifndef STEER_RANGE_DEG
#define STEER_RANGE_DEG        360.0f  // soft endstops (cable wrap limit)
#endif
#ifndef STEER_FULL_SCALE_DEG
#define STEER_FULL_SCALE_DEG   180.0f  // CMD steer +-100 maps to +-180 deg
#endif
#ifndef STEER_KP
#define STEER_KP               6.0f
#endif
#ifndef STEER_KI
#define STEER_KI               0.8f
#endif
#ifndef STEER_KD
#define STEER_KD               0.6f
#endif
#ifndef STEER_INTEGRAL_LIMIT
#define STEER_INTEGRAL_LIMIT   120.0f  // clamp on Ki*integral, PWM units
#endif
#ifndef STEER_DEADBAND_DEG
#define STEER_DEADBAND_DEG     1.2f
#endif
#ifndef STEER_MIN_DRIVE_PWM
#define STEER_MIN_DRIVE_PWM    35      // stiction floor (0..255 scale)
#endif
#ifndef STEER_MAX_DRIVE_PWM
#define STEER_MAX_DRIVE_PWM    220     // cap (0..255 scale)
#endif
#ifndef STEER_STALL_ERR_DEG
#define STEER_STALL_ERR_DEG    4.0f
#endif
#ifndef STEER_STALL_MOVE_DEG
#define STEER_STALL_MOVE_DEG   1.0f
#endif
#ifndef STEER_STALL_TIME_MS
#define STEER_STALL_TIME_MS    600
#endif
#ifndef STEER_STALL_CURRENT_A
#define STEER_STALL_CURRENT_A  0.0f    // >0 enables current-based stall trip
#endif
#ifndef STEER_FAILSAFE_RECENTER
#define STEER_FAILSAFE_RECENTER 0      // hold (worm self-locks); 1 = recentre
#endif
#ifndef SRV_PWM_HZ
#define SRV_PWM_HZ             2000    // BTN8982 on-board bridge PWM
#endif

// AS5600 geometry: counts -> azimuth degrees. Magnet on the azimuth shaft,
// 1:1. Set ENC_INVERT if +PWM (starboard) decreases the reading.
#ifndef ENC_COUNTS_PER_REV
#define ENC_COUNTS_PER_REV     4096
#endif
#ifndef ENC_GEAR_RATIO
#define ENC_GEAR_RATIO         1.0f    // shaft revs per azimuth rev
#endif
#ifndef ENC_INVERT
#define ENC_INVERT             0
#endif
// Angle at the hall magnet (deg): 0.0 when the magnet marks dead-centre.
#ifndef HALL_ANGLE_DEG
#define HALL_ANGLE_DEG         0.0f
#endif
#ifndef HALL_DEBOUNCE_MS
#define HALL_DEBOUNCE_MS       50
#endif

// --------------------------------------------------------- thrust tuning --
// Mirrors firmware/engine/engine.ino semantics (slew, reverse dead-time,
// E-line states); the output stage is the BTN8982 bridge instead of a
// hijacked ESC.
#ifndef THR_SLEW_PER_S
#define THR_SLEW_PER_S         1.0f    // full scale per second
#endif
#ifndef THR_REVERSE_DEADTIME_MS
#define THR_REVERSE_DEADTIME_MS 1000
#endif
#ifndef THR_ZERO_EPS
#define THR_ZERO_EPS           0.02f
#endif

// Current-adaptive PWM schedule (boards/thrust-driver/README.md): high
// frequency where it is silent and cheap, lower as current rises.
//   amps:  0   5   10  15  20  25  30  40  50
//   kHz : 16  16  12   8   6   5   4   3   2
#ifndef THR_FREQ_HYST_A
#define THR_FREQ_HYST_A        2.0f    // hysteresis so the retune never hunts
#endif

// ------------------------------------------------------------- reporting --
#ifndef REPORT_A_MS
#define REPORT_A_MS            100     // steering feedback line, ~10 Hz
#endif
#ifndef REPORT_E_MS
#define REPORT_E_MS            200     // engine status line, ~5 Hz
#endif
#ifndef CONTROL_TICK_US
#define CONTROL_TICK_US        2000    // 500 Hz control loop
#endif

#endif // HELM_BOARD_H
