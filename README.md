# Vanchor Helm Board (v3)

Carrier PCB for the [vanchor-ng](../vanchor-ng) trolling-motor autopilot:
a **Raspberry Pi 4/5** (autopilot computer) + **Raspberry Pi Pico 2** (real-time
motor controller, I²C slave) on one **150×120 mm 2-layer board (standard 1 oz)**.
Thrust power stays on an **external IBT-2/BTS7960-class driver** (J13); the
steering-servo bridge is on board.

```
BATTERY 12-48V ──► J16 ─[F1 10A]─[reverse-FET]──┬─ 5V/5A buck ── Pi + touchscreen + fan
                                                └─ 12V rail ── servo bridge
                                        (12V boats: bridge J17, omit U6;
                                         24-48V boats: populate U6 12V buck)
Pi (mounts UNDER the board, HAT-style)
 ├─ I²C ── Pico 2 @0x42 ──┬─ GP12-15: RPWM/LPWM/R_EN/L_EN ──► J13 ──► EXTERNAL
 │                        │   (+ R_IS/L_IS current sense back)   THRUST DRIVER
 │                        ├─ RPWM/LPWM ──► 2x BTN8982TA ──► 12V worm-gear servo
 │                        └─ I²C ──► AS5600 encoder (cable, in servo housing)
 ├─ UART0/2/3/4/5 ──► JST headers (GPS, compass, NMEA)
 └─ DSI ribbon ──► 7" touchscreen (5V from J10)
```

Cost history: v1/v2 carried an on-board 800 W H-bridge; ten documented
cost-optimization passes (see `docs/cost-optimization-log.md`) brought a
12 V build from ~$111 to **~$41 per assembled board** (~$35 parts + ~$6 PCB).
The v2 on-board-bridge design remains available at git tag/commit `bf91c4a`.

## Repository layout

| Path | Content |
|---|---|
| `hardware/` | KiCad 10 project (schematic, board, custom symbols/footprints) |
| `hardware/sheets/*.py` | Net-spec sources — the schematic is **generated** from these |
| `hardware/scripts/` | Generators + gates (`build_sch.sh`, `build_board.py`, ERC/DRC helpers) |
| `hardware/fab/` | Gerbers, drill, BOM — upload these to PCBWay/JLCPCB |
| `docs/cost-optimization-log.md` | The 10 cost passes and their effect |
| `docs/superpowers/` | Design spec + implementation plan |
| `.claude/skills/` | kicad-happy review skills (vendored) |

## Regenerating the design

```sh
docker compose up -d                 # KiCad 10 container (GUI at https://localhost:3001)
./hardware/scripts/build_sch.sh      # specs -> .kicad_sch + ERC
docker exec vanchor-kicad kicad-cli sch export netlist --format kicadsexpr \
    -o /config/vanchor-pcb/hardware/vanchor-helm.net /config/vanchor-pcb/hardware/vanchor-helm.kicad_sch
docker exec -e BASE_GND=0 vanchor-kicad python3 /config/vanchor-pcb/hardware/scripts/build_board.py
# route with freerouting-1.9 (see git history for the exact docker command),
# then: docker exec vanchor-kicad python3 /config/vanchor-pcb/hardware/scripts/import_routes.py
```

## Connector map

| Ref | Label | Wire to |
|---|---|---|
| J16 | LOGIC 12-48V | battery + / − (board logic + servo supply; ≥1.5 mm²) |
| J13 | THRUST DRV | external driver, IBT-2 pin order: **1 RPWM · 2 LPWM · 3 R_EN · 4 L_EN · 5 R_IS · 6 L_IS · 7 VCC(5V) · 8 GND** |
| J22 | SERVO MOTOR | 12 V worm gearmotor of the steering servo |
| J17 | 12V LINK | **12 V boats only**: wire link VIN→12V rail (omit U6) |
| J11 | AS5600 | 4-wire cable into servo housing: 3V3 GND SDA SCL (≤1 m, twisted) |
| J3–J7 | UART0/2/3/4/5 | GPS, compass, NMEA gear (3V3 TTL; ttyAMA0/2/3/4/5) |
| J8 | I2C1 spare | I²C sensors (bus shared with Pico link — keep short) |
| J10 | DISP PWR | official 7" touchscreen 5V/GND (DSI ribbon goes to the Pi itself) |
| J9 | FAN | 5 V fan |
| J2 | GPIO breakout | all 40 Pi pins 1:1 (DNP by default — fit if needed) |
| J12 | PICO UTIL | spare Pico I/O (DNP by default) |

Battery→motor power wiring (fat cables, ANL fuse) goes to the **external
driver**, not to this board.

## Mechanical

- The Pi mounts **under** the board on 4× M2.5 standoffs (~19-20 mm) with an
  **extra-tall 2×20 stacking header** (e.g. Adafruit 1979). Its USB/ETH tower
  (16 mm) clears the board; SD card and all Pi ports remain reachable from the
  sides. The Pico and all connectors live on the board top.
- 4× M3 corner mounting holes. No heatsink needed on this board.

## Power & safety notes

- F1 (10 A mini blade) fuses everything on this board. The thrust path is
  fused externally at the battery per your driver's rating.
- **Thrust**: GP12-15 drive the external driver's RPWM/LPWM/R_EN/L_EN at
  3.3 V (fine for BTS7960-class VIH ≈ 2.5 V). 100k pull-downs on both EN pins
  keep the driver disabled when the Pico is absent/in reset. R_IS/L_IS are
  mixed (2× 1k), loaded (20k), filtered and BAT54S-clamped into Pico ADC1.
- **Servo bridge**: 2× BTN8982TA (built-in protection). VM = 12 V rail: on
  24-48 V boats stall current is limited by U6 (4.5 A); on 12 V boats J17
  feeds it battery-direct.
- Telemetry: thrust current via the driver's IS pins (ADC1), servo current
  (ADC0), battery voltage (ADC2).
- Reverse polarity: IRF9540N high-side FET; SMCJ58A TVS; 2× 470 µF bulk.
- Buck modules are 50 V absolute max: fine for 12/24/36 V. **48 V systems:**
  check charging voltage < 50 V or fit a pre-regulator.
- Firmware contract: I²C slave 0x42, reg 0x00 CMD {pwm u8, dir u8, steer i8},
  reg 0x10 STATUS {angle f32, ok u8, wrap i8, state u8, vbat_mV u16,
  isense u16}; 800 ms watchdog → thrust 0, steering holds (worm self-locks).
  Pin deltas vs v2: thrust on **GP12=RPWM GP13=LPWM GP14=R_EN GP15=L_EN**;
  GP16/GP26 freed.
- The Pi can reflash the Pico in place: SWD on Pi GPIO24 (SWDIO) /
  GPIO25 (SWCLK) — openocd bcm2835gpio driver.

## Bring-up checklist

1. Visual + continuity: VIN↔GND, 5V↔GND, 12V↔GND not shorted.
2. No Pi/Pico fitted. Feed 12 V into J16 (J17 bridged): VIN LED lights;
   verify 5.0-5.2 V on J1 pins 2/4 and 12 V on the rail.
3. Fit the Pico only (no Pi): flash test firmware over USB, check I²C
   pull-ups (3V3 on SDA/SCL), exercise LED_STAT.
4. Fit the Pi. `i2cdetect -y 1` → device at 0x42.
5. Connect AS5600 cable: Pico reads angle; rotate servo shaft by hand.
6. Servo closed-loop test with the gearmotor on a bench supply.
7. Connect the external thrust driver to J13, small test motor on its
   outputs: verify PWM, direction, the EN failsafe (reset the Pico mid-run →
   driver must drop out) and IS telemetry on ADC1.
8. Only then wire the real trolling motor through the external driver.
