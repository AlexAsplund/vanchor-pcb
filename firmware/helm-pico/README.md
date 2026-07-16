# vanchor helm-board Pico 2 firmware

One RP2350 replaces both vanchor-ng Arduinos: **engine** (thrust, via the
companion BTN8982 driver board on J13) and **steering** (on-board BTN8982
bridge, AS5600 azimuth encoder, hall zero index) behind a single USB-CDC
serial port that speaks the vanchor-ng line protocol **unchanged** — the Pi
needs zero code changes. NMEA2000 (GP18/19) is deliberately not included yet.

## Protocol (the contract)

Vendored verbatim from vanchor-ng in `vendor/` (see `vendor/README.md`):

| Direction | Line | Notes |
|---|---|---|
| Pi → Pico | `CMD <pwm> <dir> <steer> [<seq>]*HH` | combined thrust + steering (the default) |
| Pi → Pico | `STEERD <deg> [<seq>]*HH` | v2.1 degrees-native steering |
| Pi → Pico | `THRUST <pwm> <dir> [<seq>]*HH` | split thrust channel |
| Pico → Pi | `A <angle_deg> <ok> <wrap_pct> <seq>*HH` | ~10 Hz steering feedback |
| Pico → Pi | `E <pwm> <dir> <state> <seq>*HH` | ~5 Hz engine status (`RUN/SOFTSTART/REVDELAY/FAILSAFE`) |

CRC-8 (`*HH`) on every line, both directions; CRC-less commands are rejected
(build with `-DVANCHOR_REQUIRE_CRC=0` to tolerate an old Pi). `<steer>`
±100 maps to ±180° (`STEER_FULL_SCALE_DEG`), soft endstops at ±360°
(`STEER_RANGE_DEG`) — identical numbers to `steering.ino`.

**Pi configuration**: point `motor_port` at this board's CDC device, e.g.

```yaml
hardware:
  motor_port: /dev/serial/by-id/usb-Raspberry_Pi_Pico_2*-if00
```

(baud is ignored on CDC; leave `steering_port`/`thrust_port` blank so the
combined `SerialMotorController` drives both axes through this one port.)

## Behaviour

- **Thrust** mirrors `engine.ino`: 1.0/s throttle slew, 1000 ms reverse
  dead-time interlock (must rest at zero before a direction flip), watchdog
  failsafe slews to zero without flipping. Output is the J13 bridge
  (GP12/13 PWM, GP14/15 enables) with the **current-adaptive PWM schedule**
  from `boards/thrust-driver/README.md`: 16 kHz when quiet, stepping down to
  2 kHz at full current (2 A hysteresis), retuned glitch-minimal.
- **Steering** mirrors `steering.ino`: same PID (6.0/0.8/0.6), deadband
  1.2°, stiction floor, stall detection (position + optional current), hold
  on watchdog loss (the worm self-locks). Feedback is the AS5600 on I2C1,
  unwrapped to a continuous multi-turn angle; the **hall index on GP0**
  re-zeros the angle absolutely every time the head passes centre — set
  `HALL_ANGLE_DEG` if your magnet isn't at dead-centre.
- **Safety chain**: 800 ms protocol watchdog → safe state; 2 s hardware
  watchdog → reboot; both bridges held disabled until the first valid
  command, and the board's 100 k pulldowns keep them disabled whenever the
  Pico is dead, rebooting or being reflashed.
- **Telemetry**: THR_IS / SERVO_IS / VBAT are sampled and filtered every
  tick (used for the PWM schedule and stall trip). Scale constants in
  `include/board.h` carry CALIBRATE notes — verify against a clamp meter.

## Building

Requires the [pico-sdk](https://github.com/raspberrypi/pico-sdk) (2.0+ for
RP2350) and `gcc-arm-none-eabi`:

```sh
export PICO_SDK_PATH=~/pico-sdk        # or -DPICO_SDK_FETCH_FROM_GIT=on
cmake -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build -j
# -> build/vanchor_helm_pico.uf2 / .elf
```

## Flashing

- **First time / no debugger**: hold BOOTSEL, plug USB, copy the `.uf2`.
- **In-circuit (assembled boat)**: SWD over the ribbon from the SBC —
  SWCLK/SWDIO land on Zero 3 pins 16/18 (PC15/PC14), RUN on pin 12:
  `openocd -f interface/linuxgpiod.cfg -f target/rp2350.cfg` (pin mapping in
  `docs/HANDOFF.md`). Never needed for normal operation.

## Bring-up checklist

1. Bench-power the helm board, no props, `screen /dev/ttyACM0`.
2. You should see `A ...` at 10 Hz and `E 0 F RUN -1*..` at 5 Hz. `ok` will
   be `1` only with the AS5600 magnet in range.
3. Type `CMD 0 F 0*DC` — the enables assert (bridge LEDs / 5 V on J13.7).
4. `CMD 60 F 0*..` (compute a CRC with `tests/`, or build with
   `VANCHOR_REQUIRE_CRC=0` for the bench) — thrust ramps softly; stop
   commanding — after 800 ms the `E` state shows `FAILSAFE` and it ramps out.
5. Swing the head by hand past centre — the hall edge re-zeros `A`'s angle.
6. `STEERD 10.0*..` — the servo drives; verify +deg = starboard, else set
   `ENC_INVERT 1` (encoder) and/or swap the servo motor leads (drive).

## Tests

`make -C tests` — host-compiles the **exact** shipped headers and replays
the golden `protocol_vectors.txt` through the real accept/parse path (both
CRC modes), round-trips outbound `A`/`E` CRCs, and unit-tests the reverse
gate, slew, failsafe states, PID direction/deadband/stall and the multi-turn
unwrap. CI-friendly: exits non-zero on any failure.

## Layout

```
CMakeLists.txt, pico_sdk_import.cmake   build glue (PICO_BOARD=pico2)
include/board.h                          pin map + tuning (single source)
src/main.cpp                             transport, sensors, output stages
src/control_logic.h                      hardware-free control cores
src/protocol_ext.h                       THRUST token parser (+ vendored hdr)
vendor/                                  the contract, verbatim from vanchor-ng
tests/                                   host test suite (no SDK needed)
```
