# Vanchor Helm Board

Carrier PCB for the [vanchor-ng](../vanchor-ng) trolling-motor autopilot:
a **Raspberry Pi 4/5** (autopilot computer) + **Raspberry Pi Pico 2** (real-time
motor controller, I²C slave) on one 160×120 mm 2-layer board (**order in 2 oz
copper**) with BOTH motor drivers on board.

```
BATT+ lug ──ACS758──► VBRIDGE ──► on-board H-bridge (HIP4082 + 8x IRF100P219)
   │                              >=800W @ 12V (67A cont), fwd/rev ──► MOTOR A/B lugs
   └─[F1 10A]─[reverse-FET]──┬─ 5V/5A buck ── Pi + touchscreen + fan
                             └─ 12V/4.5A buck ── servo bridge + gate driver
Pi (mounts UNDER the board, HAT-style)          (12V boats: omit U6, bridge J17)
 ├─ I²C ── Pico 2 @0x42 ──┬─ AHI/BHI/ALI/BLI ──► thrust H-bridge (above)
 │                        ├─ RPWM/LPWM ──► 2x BTN8982TA ──► 12V worm-gear servo motor
 │                        └─ I²C ──► AS5600 encoder (cable, in servo housing)
 ├─ UART0/2/3/4/5 ──► JST headers (GPS, compass, NMEA)
 └─ DSI ribbon ──► 7" touchscreen (5V from J10)
```

## Repository layout

| Path | Content |
|---|---|
| `hardware/` | KiCad 10 project (schematic, board, custom symbols/footprints) |
| `hardware/sheets/*.py` | Net-spec sources — the schematic is **generated** from these |
| `hardware/scripts/` | Generators + gates (`build_sch.sh`, `build_board.py`, ERC/DRC helpers) |
| `hardware/fab/` | Gerbers, drill, BOM — upload these to PCBWay/JLCPCB |
| `docs/superpowers/` | Design spec + implementation plan |
| `.claude/skills/` | kicad-happy review skills (vendored) |

## Regenerating the design

```sh
docker compose up -d                 # KiCad 10 container (GUI at http://localhost:3000)
./hardware/scripts/build_sch.sh      # specs -> .kicad_sch + ERC
docker exec vanchor-kicad kicad-cli sch export netlist --format kicadsexpr \
    -o /config/vanchor-pcb/hardware/vanchor-helm.net /config/vanchor-pcb/hardware/vanchor-helm.kicad_sch
git checkout hardware/vanchor-helm.kicad_pcb   # reset to skeleton first
docker exec vanchor-kicad python3 /config/vanchor-pcb/hardware/scripts/build_board.py
```

## Connector map

| Ref | Label | Wire to |
|---|---|---|
| J18 | LUG BATT+ | battery + via external ANL/MIDI fuse (80-100 A) + kill switch, ≥16 mm² (5-6 AWG) |
| J19/J20 | LUG MOTOR A/B | trolling motor leads, ≥16 mm² |
| J21 | LUG GND | battery − , ≥16 mm² |
| J22 | SERVO MOTOR | 12 V worm gearmotor of the steering servo |
| J17 | 12V LINK | **12 V boats only**: wire link VIN→12V rail (omit U6) |
| J11 | AS5600 | 4-wire cable into servo housing: 3V3 GND SDA SCL (≤1 m, twisted) |
| J3–J7 | UART0/2/3/4/5 | GPS, compass, NMEA gear (3V3 TTL; ttyAMA0/2/3/4/5) |
| J8 | I2C1 spare | I²C sensors (bus shared with Pico link — keep short) |
| J10 | DISP PWR | official 7" touchscreen 5V/GND (DSI ribbon goes to the Pi itself) |
| J9 | FAN | 5 V fan |
| J2 | GPIO breakout | all 40 Pi pins 1:1 |
| J12 | PICO UTIL | 3V3, GP0-3, GP18-19, GND (spare Pico I/O) |

## Mechanical

- The Pi mounts **under** the board on 4× M2.5 standoffs (~19-20 mm) with an
  **extra-tall 2×20 stacking header** (e.g. Adafruit 1979). Its USB/ETH tower
  (16 mm) clears the board; SD card and all Pi ports remain reachable from the
  sides. The Pico, DIP logic and all connectors live on the board top.
- 6× M3 mounting holes; the FET row sits along the left edge for a clip-on heatsink bar.

## Power & safety notes

- Board fuse F1 (10 A mini blade) protects **board logic loads only** (it taps
  the BATT+ lug upstream of the ACS758 so board draw doesn't skew telemetry).
  The 67 A motor path is fused externally: ANL/MIDI 80-100 A at the battery.
- **Thrust bridge**: ≥800 W @ 12 V ≈ 67 A continuous. 8× IRF100P219 (2 per
  switch) driven by HIP4082 (dead-time set by R30; DIS pulled up = bridge off
  whenever the Pico is absent/reset). **Fit a heatsink bar across the FET row**
  (~3 W per FET at 67 A) and provide airflow above ~40 A continuous.
  Order the PCB in **2 oz copper** — the power zones are sized for it.
- **Servo bridge**: 2× BTN8982TA (BTS7960-compatible interface, built-in
  protection). VM = 12 V rail: on 24-48 V boats stall current is limited by
  BUCK2 (4.5 A); on 12 V boats J17 feeds it battery-direct.
- Thrust telemetry: ACS758 hall sensor (±100 A) in the battery leg → Pico ADC1;
  servo current on ADC0; battery voltage on ADC2.
- Reverse polarity: IRF9540N high-side FET (100 V); TVS SMCJ58A; 2×470 µF bulk.
- Buck modules are rated 50 V absolute max: fine for 12/24/36 V systems.
  **48 V systems: measure your charging voltage** — if it can exceed 50 V, fit
  a pre-regulator or use the 60 V module variant.
- JP1 solder jumper selects the thrust output: **1-2** = X9C103 digipot wiper
  (knob-type controllers, default), **2-3** = buffered 0–5 V PWM-DAC
  (controllers with a voltage throttle input).
- Firmware contract (ported from the serial protocol): I²C slave 0x42,
  reg 0x00 CMD {pwm u8, dir u8, steer i8}, reg 0x10 STATUS {angle f32, ok u8,
  wrap i8, state u8, vbat_mV u16, isense u16}; 800 ms watchdog → thrust 0,
  steering holds (worm self-locks).
- The Pi can reflash the Pico in place: SWD is wired to Pi GPIO24 (SWDIO) /
  GPIO25 (SWCLK) — use openocd's `raspberrypi-native`/bcm2835gpio driver.

## Bring-up checklist

1. Visual + continuity: VIN↔GND, 5V↔GND, 12V↔GND not shorted.
2. No Pi/Pico fitted. Feed 12 V into J16: LED VIN + 5V (+12V) light;
   verify 5.0-5.2 V on J1 pins 2/4 and 12 V rail.
3. Fit the Pico only (no Pi): power up, flash test firmware over USB or SWD,
   check I²C pull-ups (3V3 on SDA/SCL), exercise LED_STAT.
4. Fit the Pi. `i2cdetect -y 1` → device at 0x42.
5. Connect AS5600 cable: Pico reads angle; rotate servo shaft by hand.
6. Connect IBT-2 + gearmotor on a bench supply: closed-loop steering test.
7. Thrust bridge dry test: scope MOTOR A-B with a small 12 V test motor,
   verify PWM, dead-time, direction reversal and the DIS failsafe (reset the
   Pico mid-run → bridge must drop out).
8. Only then bolt on the trolling motor with the external ANL fuse in place.
