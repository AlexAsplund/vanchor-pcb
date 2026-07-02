# Vanchor Helm Board (v4)

Carrier PCB for the [vanchor-ng](../vanchor-ng) trolling-motor autopilot:
an **Orange Pi Zero 3** (autopilot computer) + **Raspberry Pi Pico 2**
(real-time motor controller, I²C slave) on one **125×95 mm 2-layer board
(standard 1 oz)**. Thrust power stays on an **external IBT-2/BTS7960-class
driver** (J13); the steering-servo bridge is on board. **12 V-only** (car
battery, 14.4 V charging) — the 5 V rail comes from a generic cheap buck
module on J14.

```
BATTERY 12V ──► J16 ─[F1 10A]─[reverse-FET]─ VIN ──┬─ J14: 5V buck module ── Pi + screen + fan
                                                   └────────────── servo bridge (direct)
Orange Pi Zero 3 (26-way IDC ribbon to J1, powered through the ribbon)
 ├─ I²C3 ── Pico 2 @0x42 ──┬─ GP12-15: RPWM/LPWM/R_EN/L_EN ──► J13 ──► EXTERNAL
 │                         │   (+ R_IS/L_IS current sense back)   THRUST DRIVER
 │                         ├─ RPWM/LPWM ──► 2x BTN8982TA ──► 12V worm-gear servo
 │                         └─ I²C ──► AS5600 encoder (cable, in servo housing)
 ├─ UART5 + UART2 ──► JST headers (GPS, compass, NMEA)
 └─ HDMI/USB screen on the module itself (aux 5V from J10)
```

Cost history: v1/v2 carried an on-board 800 W H-bridge; ten documented
cost-optimization passes (see `docs/cost-optimization-log.md`) brought a
12 V build from ~$111 to **~$41 per assembled board** (~$35 parts + ~$6 PCB).
The v2 on-board-bridge design remains available at git tag/commit `bf91c4a`.

## Boards

- `boards/helm/` — the helm/carrier board (Orange Pi Zero 3 + Pico 2, servo
  bridge, XL4015 buck daughterboard, PWM output header J13).
- `boards/thrust-driver/` — 12-24 V trolling-motor H-bridge (2-4× BTN8982TA),
  connects to helm J13 with a straight 8-wire cable. See its README for the
  base (~30 A) vs high-power (~50 A) variants and the solder-lane
  reinforcement technique.

## Repository layout

| Path | Content |
|---|---|
| `boards/helm/` | KiCad 10 project (schematic, board, custom symbols/footprints) |
| `boards/helm/sheets/*.py` | Net-spec sources — the schematic is **generated** from these |
| `boards/helm/scripts/` | Generators + gates (`build_sch.sh`, `build_board.py`, ERC/DRC helpers) |
| `boards/helm/fab/` | Gerbers, drill, BOM — upload these to PCBWay/JLCPCB |
| `docs/cost-optimization-log.md` | The 10 cost passes and their effect |
| `docs/superpowers/` | Design spec + implementation plan |
| `.claude/skills/` | kicad-happy review skills (vendored) |

## Regenerating the design

```sh
docker compose up -d                 # KiCad 10 container (GUI at https://localhost:3001)
./boards/helm/scripts/build_sch.sh      # specs -> .kicad_sch + ERC
docker exec vanchor-kicad kicad-cli sch export netlist --format kicadsexpr \
    -o /config/vanchor-pcb/boards/helm/vanchor-helm.net /config/vanchor-pcb/boards/helm/vanchor-helm.kicad_sch
docker exec -e BASE_GND=0 vanchor-kicad python3 /config/vanchor-pcb/boards/helm/scripts/build_board.py
# route with freerouting-1.9 (see git history for the exact docker command),
# then: docker exec vanchor-kicad python3 /config/vanchor-pcb/boards/helm/scripts/import_routes.py
```

## Connector map

| Ref | Label | Wire to |
|---|---|---|
| J16 | BATT 12V | battery + / − (board logic + servo supply; ≥1.5 mm²) |
| J13 | THRUST DRV | external driver, IBT-2 pin order: **1 RPWM · 2 LPWM · 3 R_EN · 4 L_EN · 5 R_IS · 6 L_IS · 7 VCC(5V) · 8 GND** |
| J22 | SERVO MOTOR | 12 V worm gearmotor of the steering servo |
| U5 | XL4015 BUCK | the module solders ON: pins into its 4 corner terminals, spacers, into the slotted pads (set 5.1 V first!) |
| J1 | OPI Z3 26-PIN | male header → 26-way 1:1 IDC ribbon (original-RPi style) to the Zero 3 |
| J11 | AS5600 | 4-wire cable into servo housing: 3V3 GND SDA SCL (≤1 m, twisted) |
| J3 | UART5 | GPS/compass/NMEA (3V3 TTL, PH2/PH3; enable `uart5` DT overlay) |
| J4 | UART2 | second serial device (PC5/PC6; enable `uart2` overlay; swap TX/RX at the JST if silent) |
| J8 | I2C3 spare | I²C sensors (bus shared with Pico link — keep short) |
| J10 | AUX 5V | fused 5 V for a screen or accessory |
| J9 | FAN | 5 V fan |
| J2 | GPIO breakout | all 40 Pi pins 1:1 (DNP by default — fit if needed) |
| J12 | PICO UTIL | spare Pico I/O (DNP by default) |

Battery→motor power wiring (fat cables, ANL fuse) goes to the **external
driver**, not to this board.

## Mechanical

- The Zero 3 (pre-soldered pins-up variant) connects via a **standard
  26-way 1:1 IDC ribbon** (~$1.50, original-Raspberry-Pi style) from its
  header to J1 — match pin 1 (marked) on both ends. The module mounts
  wherever suits the enclosure; the two spare M3 holes near J1 can carry a
  small mounting plate.
- The module is powered through the ribbon 5 V pins — do **not** also plug
  USB-C power. Keep the ribbon short (≤15 cm) — it carries I²C and the
  module's supply. The 3.3 V for the JST headers comes from the module's
  regulator (keep attached loads under ~200 mA total).
- J1 pin 14 and J2 pin 9 are deliberately NC (each connector keeps four
  other ground pins; the header escape routing owns those corridors).
- J2/J12 are DNP debug breakouts whose outlines slightly overlap — populate
  at most one, or use a right-angle header on J12.
- 4× M3 corner mounting holes. No heatsink needed on this board.

## Power & safety notes

- F1 (10 A mini blade) fuses everything on this board. The thrust path is
  fused externally at the battery per your driver's rating.
- **Thrust**: GP12-15 drive the external driver's RPWM/LPWM/R_EN/L_EN at
  3.3 V (fine for BTS7960-class VIH ≈ 2.5 V). 100k pull-downs on both EN pins
  keep the driver disabled when the Pico is absent/in reset. R_IS/L_IS are
  mixed (2× 1k), loaded (20k), filtered and BAT54S-clamped into Pico ADC1.
- **Servo bridge**: 2× BTN8982TA (built-in protection), fed battery-direct
  from protected VIN. Board plumbing is sized for ~5 A continuous /
  ~10 A peak servo current (F1, terminal blocks, track widths).
- Telemetry: thrust current via the driver's IS pins (ADC1), servo current
  (ADC0), battery voltage (ADC2).
- Reverse polarity: IRF9540N high-side FET; SMCJ18A TVS (12 V clamp);
  2× 470 µF/25 V bulk.
- The buck module (U5) mounts as a daughterboard: solder 4 pins into the
  XL4015's corner terminals, slide 5-8 mm spacers on, solder into the
  slotted pads (slots absorb vendor hole-grid variance; nominal 49×18 mm —
  verify against your module). Set 5.1 V and load-test at 4 A BEFORE
  soldering it in. R20/R21/D10/D11 sit under the module's edge — fit them
  first.
- Firmware contract: I²C slave 0x42, reg 0x00 CMD {pwm u8, dir u8, steer i8},
  reg 0x10 STATUS {angle f32, ok u8, wrap i8, state u8, vbat_mV u16,
  isense u16}; 800 ms watchdog → thrust 0, steering holds (worm self-locks).
  Pin deltas vs v2: thrust on **GP12=RPWM GP13=LPWM GP14=R_EN GP15=L_EN**;
  GP16/GP26 freed.
- Zero 3 side: I²C3 (`i2c3` overlay) for the Pico link, `uart2`/`uart5`
  overlays for the JSTs; Pico RUN on PC11, SWD reflash via PC15 (SWDIO) /
  PC14 (SWCLK) — openocd sysfsgpio/libgpiod driver on the H618.

## Bring-up checklist

1. Visual + continuity: VIN↔GND, 5V↔GND, 12V↔GND not shorted.
2. No Zero 3/Pico fitted. Feed 12 V into J16: VIN LED lights; verify the
   buck module outputs 5.0-5.2 V on J1 pins 2/4.
3. Fit the Pico only (no Zero 3): flash test firmware over USB, check I²C
   pull-ups, exercise LED_STAT.
4. Plug in the Zero 3 (pin 1 to the marked corner!). `i2cdetect -y 3` →
   device at 0x42.
5. Connect AS5600 cable: Pico reads angle; rotate servo shaft by hand.
6. Servo closed-loop test with the gearmotor on a bench supply.
7. Connect the external thrust driver to J13, small test motor on its
   outputs: verify PWM, direction, the EN failsafe (reset the Pico mid-run →
   driver must drop out) and IS telemetry on ADC1.
8. Only then wire the real trolling motor through the external driver.
