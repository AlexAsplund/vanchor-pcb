# Vanchor Helm Board — PCB design spec

**Date:** 2026-07-01
**Status:** approved for implementation (autonomous mode — decisions made from
vanchor-ng firmware/CAD context; alternatives documented inline)
**Reference:** `../vanchor-ng/firmware/` (protocol + engine/steering sketches),
`../vanchor-ng/cad/steering_BOM.md` (AS5600 servo unit), `vanchor.example.yaml`
(GPS/compass/motor serial devices, web UI).

## 1. Purpose

One PCB that replaces the loose-module wiring of vanchor-ng's hardware bridge:

- Carries a **Raspberry Pi 4/5** (40-pin) as the autopilot computer.
- Exposes **every GPIO UART** of the Pi on labelled connectors (GPS, compass,
  NMEA devices) plus a full 40-pin breakout.
- Hosts **one RP2350 (Pico 2) microcontroller** connected to the Pi over **I²C**
  (Pi = master, Pico = slave @ 0x42). The Pico runs both real-time jobs:
  - **Thrust**: drives an external commercial 12–48 V / 1500 W DC speed
    controller by digipot knob-hijack + a reversing contactor (exactly the
    firmware README's engine design — the 125 A path never touches this board).
  - **Steering servo**: onboard H-bridge driving the 12 V worm gearmotor of the
    custom servo, closed-loop PID on an **AS5600** encoder read over a cabled
    I²C connector.
- Powers an official **Raspberry Pi 7" DSI touchscreen** (5 V from the board;
  DSI ribbon goes straight to the Pi — no display signals cross the PCB).
- Runs from the boat battery, **12–48 V input**, with protection.

## 2. Approaches considered

**A. Motherboard-of-modules (CHOSEN).** The PCB is a 2-layer carrier that
integrates proven modules: Pi on stacking header, Pico 2 on headers, Pololu
D36V50Fx buck modules, IBT-2 (BTS7960) H-bridge module. Custom copper only for
protection, glue logic, digipot, relay driver, connectors.
*Pros:* hand-assemblable, each power part is pre-tested, replaceable after a
smoke event, matches the project's DIY style (printed gears, bought speed
controller). *Cons:* taller, slightly dearer per-unit.

**B. Fully integrated SMT (rejected for v1).** VNH5019 H-bridge, discrete 60 V
bucks, RP2350 chip on board; JLCPCB assembly.
*Pros:* compact, cheaper at volume. *Cons:* first-spin risk on the power
stages, not hand-repairable, longer design time. Sensible v2 once v1 is proven.

**C. Two-MCU split (rejected).** Mirroring the two-Nano firmware split.
The Pico 2 has two cores and plenty of pins; one I²C slave keeps the Pi-side
topology simple. Spare Pico GPIO are broken out if a second controller is ever
needed.

**On-board 1500 W bridge (rejected outright):** 125 A @ 12 V on a hobby 2-layer
board is a fire, not a feature. The firmware README's hijack approach is kept.

## 3. System architecture

```
BATTERY 12–48V ──[fuse]──[reverse-pol P-FET]──[TVS]──┬── BUCK1 5V/5A ── Pi 5V, touchscreen 5V, fan, HCT logic
                                                     └── BUCK2 12V/5A ── servo H-bridge B+, contactor coil
                                                         (jumper-bypass on 12V systems)

Raspberry Pi 4/5 (40-pin stacking header)
 ├─ I2C1 (GPIO2/3, 3.3V) ──────────────► Pico 2 I2C0 slave @0x42
 ├─ UART0/2/3/4/5 ─────────────────────► 5 labelled JST-XH headers (3V3/TX/RX/GND)
 ├─ full 40-pin breakout header
 └─ DSI + USB direct on the Pi itself (touchscreen ribbon, USB devices)

Pico 2 (RP2350)
 ├─ I2C1 master ── JST-XH cable ───────► AS5600 encoder (in servo housing)
 ├─ PWM ×2 + EN ──────────────────────► IBT-2 (BTS7960) module ──► 12V worm gearmotor
 ├─ IS ×2 ── ADC                        (current sense / stall)
 ├─ 74HCT125 (5V) ──► X9C103 digipot ──► external speed controller knob terminals
 ├─ MOSFET low-side driver ───────────► reversing DPDT contactor coil (12V)
 ├─ PWM-DAC (RC + MCP6002 @5V) ───────► alt. 0–5V throttle output (jumper-selected)
 └─ ADC ── divider ── battery voltage telemetry
```

Grounding: single common ground; battery −, external controller GND, and board
GND tie at the power-entry star point. Logic and motor returns on separate pours.

## 4. Subsystems

### 4.1 Power entry & rails
- Input 12–48 V on 5.08 mm screw terminal; **10 A blade-fuse holder** (board
  loads only: Pi+screen ≈3 A @5 V, servo ≤5 A @12 V ⇒ ≤4 A @12 V in, less at 48 V).
- Reverse polarity: P-FET high-side (100 V, e.g. SUM110P08/SQJ457EP class,
  gate zener-clamped 12 V + 100 k).
- **SMCJ58A** TVS across input after the FET; 2×470 µF/63 V bulk + 100 nF.
- **BUCK1**: Pololu **D36V50F5** module (5 V/5 A, 50 V max in) → Pi 5 V pins
  (2,4), touchscreen power connector (fused 2 A polyfuse), fan header, 74HCT125.
- **BUCK2**: Pololu **D36V50F12** module (12 V/5 A) → IBT-2 B+, contactor coil.
  On 12 V-battery boats BUCK2 is omitted and a 2-pin 5.08 mm screw-terminal
  link (rated for the 5 A servo load) bridges VIN→12 V rail instead.
- 3.3 V for Pico/AS5600 comes from the Pico's onboard regulator (VSYS←5 V).
- Note: 48 V nominal charging can exceed 50 V (buck max) — doc states 12/24/36 V
  battery systems use the modules directly; 48 V systems must be measured and,
  if >50 V, use the 60 V module variant (D36V28F5) or an external pre-regulator.

### 4.2 Raspberry Pi carrier
- 2×20 **stacking** header; Pi mounts over the board on M2.5 standoffs
  (footprint holes for Pi 4/5 pattern 58×49 mm).
- 5 V feed into pins 2/4 (bypasses USB-C; standard for embedded carriers).
- **UART headers** (JST-XH 4-pin: 3V3, TXD, RXD, GND), silkscreened with both
  GPIO numbers and Pi device names:
  | Header | GPIO | Pi 4 device | Pi 5 device |
  |---|---|---|---|
  | UART0 | 14/15 | ttyAMA0 | ttyAMA0 |
  | UART2 | 0/1 | ttyAMA2 | ttyAMA2 |
  | UART3 | 4/5 | ttyAMA3 | ttyAMA3 |
  | UART4 | 8/9 | ttyAMA4 | ttyAMA4 |
  | UART5 | 12/13 | ttyAMA5 | ttyAMA5 |
- Full 40-pin 2×20 breakout header beside the Pi (all pins pass through).
- 2-pin 5 V fan header.
- I²C1 (GPIO2/3) is the Pi↔Pico bus. The Pi has fixed 1.8 kΩ pulls on these
  pins, which is sufficient; board footprints for extra pulls are provided but
  **not populated** (avoids exceeding the 3 mA sink spec). Routed short, plus a
  spare I²C JST-XH for sensors (compass modules are often I²C).

### 4.3 Pico 2 controller
- **Pico 2 module** on 2×20 2.54 mm socket headers, USB edge accessible for
  firmware flashing (also wired: Pi GPIO → Pico RUN + BOOTSEL header pins for
  Pi-driven reflash).
- I2C0 (GP4/GP5) = slave to Pi. I2C1 (GP6/GP7) = master to AS5600 connector
  (4.7 kΩ pulls, 100 Ω series, ESD diodes near connector).
- Spare GPIO (≥8) + 3V3/GND on a utility header.

### 4.4 Thrust interface (external 1500 W controller)
- **X9C103** digipot; INC/UD/CS driven through **74HCT125** (5 V, VIH 2 V — the
  X9C at 5 V needs >3.5 V highs, which 3.3 V Pico pins can't guarantee).
- Digipot pot terminals (VH/VW/VL) on a 3-pin screw terminal → replaces the
  controller's 10 kΩ knob. 100 nF + 100 µF across wiper output per firmware BOM.
- **PWM-DAC alternative** (controllers with 0–5 V throttle input): Pico PWM →
  1 kΩ/10 µF RC → MCP6002 follower (5 V) → same terminal via solder-jumper
  selection.
- **Reversing contactor driver**: logic N-FET (IRLML6344-class) low-side, 1N4007
  flyback, 12 V coil supply from BUCK2, 2-pin screw terminal to the external
  DPDT contactor. Firmware only switches at zero throttle (existing dead-time
  logic).
- Battery-side fuse + kill switch for the 1500 W path remain **off-board** on
  the battery feed, as in the firmware README.

### 4.5 Steering servo
- **IBT-2 (BTS7960) module** plugs its 8-pin signal header into a board socket;
  its own screw terminals take B+ (12 V rail) and the gearmotor M+/M−. Module
  mounting holes align with board standoffs.
- RPWM/LPWM/R_EN/L_EN from Pico (3.3 V is within BTS7960 VIH — the IBT-2 works
  at 3.3 V logic); R_IS/L_IS → Pico ADC via divider/clamp.
- **AS5600 connector**: JST-XH 4-pin (3V3, GND, SDA, SCL) → cable into the
  servo housing (per cad/steering_BOM.md, PG7 gland). Twisted/short, 100 kHz.

### 4.6 Touchscreen
- Official RPi 7" DSI touchscreen: ribbon to the Pi's DSI port directly.
- Board provides **DISP PWR** JST-XH 2-pin (5 V, 2 A polyfuse) to the screen.
- HDMI/USB touchscreens plug into the Pi's own ports (no board support needed).

### 4.7 Telemetry & indicators
- Battery voltage divider (100 k/6.8 k + clamp) → Pico ADC.
- LEDs: VIN (after protection), 5 V, 12 V, Pico status (GPIO), Pi heartbeat
  (GPIO via 40-pin).

## 5. Firmware contract (out of scope to implement, in scope to pin-map)

The Pi↔Pico I²C register map replaces the USB `CMD` protocol; the PID/hijack
logic ports from `engine.ino`/`steering.ino`. Proposed map (documented on
schematic): 0x00 CMD {pwm u8, dir u8, steer i8}, 0x10 STATUS {angle_deg f32,
feedback_ok u8, wrap_pct i8, state u8, vbat_mV u16, i_sense u16}, watchdog
800 ms → failsafe (thrust→0, steering holds). Firmware itself lives in
vanchor-ng later; this board only fixes the pinout.

## 6. Board outline & layout intent

- **Cost guideline (user):** as cheap as possible without quality loss; cheap
  at PCBWay-class fabs. Therefore: **2-layer, ≤100 × 100 mm** (the ~$5 price
  tier), 1.6 mm FR-4, HASL, green, no castellations; track/clearance kept
  ≥0.25 mm (well above cheap-tier minimums); all parts hand-solderable
  (TH + SOT-23 only), no stencil/assembly service needed.
- The IBT-2 H-bridge module mounts **off-board** (enclosure wall) and connects
  through a 1×8 pin header + dupont/crimp cable — saves ~20 cm² of board.
- M3 corner mounts; fits a printed/off-shelf IP-rated enclosure with PG
  glands (marine). The Pi mounts over the board (stacking header + standoffs);
  only low-profile parts under it.
- Zones: power entry left edge (screw terminals), bucks beside it; Pi footprint
  right half (SD + USB/HDMI toward board edges); Pico + logic centre;
  IBT-2 + motor terminals bottom-left; low-level connectors (UARTs, AS5600,
  I²C, display power) top edge, silkscreen-labelled.
- Motor/relay currents stay in the power zone; AS5600 and I²C routes keep away
  from PWM tracks; ground pour both sides, stitched.

## 7. Deliverables

1. KiCad 10 project in this repo (`hardware/`): hierarchical schematic
   (power / pi / mcu / thrust / servo sheets), ERC-clean.
2. PCB layout, DRC-clean, with the placement zones above, routed.
3. Fab outputs: Gerbers+drill (JLCPCB naming), BOM (CSV), assembly notes.
4. `README.md`: wiring guide (battery, controller hijack, contactor, servo,
   screen), jumper table, bring-up checklist.

## 8. Risks / open items

- **48 V systems**: buck modules max 50 V — flagged in §4.1; measured battery
  voltage must be <50 V or use the alternate module.
- Pi 5 without USB-PD negotiation caps its downstream USB current — acceptable
  for GPS dongles; heavy USB loads need a powered hub.
- AS5600 cable length: keep ≤1 m at 100 kHz; if the run grows, drop bus speed
  or add a P82B96 extender (footprint not included — YAGNI).
- X9C103 wiper terminals assume the hijacked controller's knob is a plain
  10 kΩ pot at ≤5 V referenced to common ground — verify on the actual unit
  before wiring (same caveat as the firmware README).
