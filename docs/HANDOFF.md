# Vanchor PCBs — Handoff (updated 2026-07-02)

## What this is

Two-board set for the vanchor-ng trolling-motor autopilot. System
diagrams (WiFi/tablet, NMEA0183/2000, HWT901B, servo, thrust):
**`docs/architecture.md`**.

### Helm board — rev **v4.2** (`boards/helm/`, 125×95, DRC 0/0)

- **Orange Pi Zero 3** (autopilot computer, Linux) via 26-way 1:1 IDC
  ribbon to J1 (2×13 male header); powered through the ribbon 5 V.
  **J2 = second SBC port**: same bus, classic RPi 26-pin positions — a
  Raspberry Pi (40-pin header pins 1–26) drops in instead. Fit ONE SBC.
- **Raspberry Pi Pico 2** on-board (real-time motor controller, I²C slave
  0x42 on the SBC's I²C3). PWM, AS5600 steering loop, 800 ms watchdog.
- **Thrust**: 8-wire cable from J13 to the companion thrust-driver board
  (or any IBT-2/BTS7960-class driver). Motor power never touches this board.
- **Steering servo**: on-board H-bridge, 2× BTN8982TA, protected VIN,
  ~5 A cont / 10 A peak plumbing.
- **Power**: 12 V only. J16 → F1 10 A → reverse-FET → VIN. 5 V from an
  **XL4015 module soldered on as a daughterboard (U5)**: pins + spacers
  into slotted pads; set 5.10 V and load-test at 4 A *before* soldering;
  fit R20/R21/D10/D11 (under its edge) first. Buy the 54×23 mm module
  variant.
- **NMEA2000**: can2040 on Pico GP18/19 → SN65HVD230 module jumpered to
  J12 (pins 1/8/6/7); drop-cable power/shield on J5 (R41/R42 0R options).
- **Sensors**: HWT901B AHRS on J3 (UART5); NMEA0183-TTL device on J4
  (UART2); AS5600 on J11; spare I²C on J8; fused aux 5 V (J10) + fan (J9).

### Thrust driver — rev **v1.1** (`boards/thrust-driver/`, 95×92, DRC 0/0)

- Full H-bridge, BTN8982TA: base build U1+U2 (~30 A), high-power adds
  U3/U4 + R7/R8 (~50 A). J1 mirrors helm J13 pin-for-pin.
- 1 oz copper + **exposed solder lanes** on every power lane — solder
  4–10 mm² copper braid along them for >15 A continuous (the ~200
  mask-aperture DRC hits are this feature; severity set to *ignore*).
- **NMEA2000 smart-node provision, all DNP**: Pico 2 (U5, same GPIO map
  as the helm Pico), SIP-3 5 V reg (U6 — R-78E5.0 at 12 V, R-78HE5.0 for
  24 V banks), CAN header J6, N2K power J7, ADC series R12/R13 (fit as
  10 k). Smart mode leaves J1 open. Details in its README.
- No reverse-battery protection (by design at these currents) — external
  ANL fuse, wire carefully.

## State of play

| Item | Status |
|---|---|
| Schematics | ERC 0 errors, generated from `boards/*/sheets/*.py`; netlist gates PASS |
| Boards | routed, DRC **0 errors / 0 unconnected** (severity-aware check) |
| Fab outputs | `boards/*/fab/` incl. gerber zips — upload as-is |
| Order specs | 2-layer, 1.6 mm, **1 oz**, HASL, 5/5 mil, 0.4 mm min hole, tented vias |
| Parts order | `bom/mouser-order.csv` v6 (helm); driver BOM in `boards/thrust-driver/fab/` |
| Off-Mouser | Zero 3 + XL4015 (AliExpress), Pico 2, SN65HVD230, PCBs (PCBWay) |
| Datasheet audit | 2026-07-02: all pinouts verified (BTN8982, Pico, OPi Zero 3 header vs Armbian DT dump, TVS/FET/clamp orientations). Fixes were docs-only. |

Version history (git): v1/v2 on-board 800 W bridge (`bf91c4a`), v3
external thrust driver, v3.1 12 V-only, v4 Orange Pi Zero 3, v4.1 ribbon
header, **v4.2 XL4015 daughterboard + N2K provision**; driver v1
(`258a7ac`), **v1.1 N2K node provision**. Cost log:
`docs/cost-optimization-log.md`.

## Known deviations (documented in `boards/helm/ERC-notes.md`)

- Helm J1 pins 14 & **20**, J2 pin 9: **NC by design** (escape-routing
  corridors; ≥3 ground pins remain per connector).
- J2/J12 courtyards graze 0.5 mm (both DNP; populate ≤1).
- R20/R21/D10/D11 sit inside U5's courtyard (module rides on spacers) —
  `pth_inside_courtyard` demoted to warning.
- Board clearance 0.14 mm (freerouting rounds under its 0.15 target).
- Driver: mask-aperture check *ignored* (intentional solder lanes); the
  routed `.kicad_pcb` files are **source of truth** — the build scripts
  regenerate placement but the surgical routing lives in the board files.
- Driver ERC reports 3 `pin_to_pin` errors: the paralleled BTN8982 OUT
  pins (U1‖U3, U2‖U4, high-power variant) are Power-output-to-Power-output
  by design. Waived — do not "fix".

## Open items for whoever continues

1. **Order**: PCBWay (both zips), Mouser CSV, AliExpress (Zero 3, XL4015).
   BTN line `BTN8982TAAUMA1`; 1 k = KOA `CF1/4CT52R102J`.
2. **Firmware**: WRITTEN — `firmware/helm-pico/` (Pico 2, pico-sdk). Speaks
   the vanchor-ng serial contract over USB-CDC (CMD/STEERD/THRUST in, A/E
   out, CRC-8); Pi needs only `motor_port=/dev/ttyACM0`. Host tests replay
   the golden protocol vectors. Cross-compile + flash + bring-up: its README.
   Pin map for reference: thrust GP12=RPWM GP13=LPWM GP14=R_EN
   GP15=L_EN; THR_IS GP27, SERVO_IS GP26, VBAT GP28; I²C-slave-0x42 path
   unused for now (USB is the control port).
   hall zero-index input on GP0 (J9.3, 10 k pullup + RC on board; UART0 fallback pair becomes GP16/GP1). **kILIS for BTN8982TA ≈ 22 700** (not the BTS7960's 8500) — rescale
   current telemetry. SBC overlays: `i2c3`, `uart5` (HWT901B), `uart2`.
   Pico SWD via ribbon pins 16/18 (PC15/PC14, openocd `linuxgpiod`),
   RUN on pin 12 (PC11). N2K stack: ttlappalainen/NMEA2000 + can2040 on
   core 1, Actisense-NGT-1 emulation over USB to Signal K.
3. **Assembly**: bring-up checklist at the end of `README.md`; driver
   assembly + braid technique in `boards/thrust-driver/README.md`.
   Ribbon: match pin-1 marks; never plug USB-C while ribbon-powered.
4. **Marine**: conformal-coat both boards (mask connectors and the
   driver's solder lanes first — braid must be soldered before coating).
5. **UART2 TX/RX direction** on SBC pins 11/13 is unverified on real
   hardware — hedged on silk ("swap at JST if silent").

## Regenerating / changing the design

Everything is generated — never hand-edit `.kicad_sch`. For the boards,
placement + power copper regenerate from `build_board.py`, but final
routing includes surgical tracks: treat the checked-in `.kicad_pcb` as
authoritative and patch it via pcbnew scripts (playbook:
`docs/llm-pcb-design.md`).

```sh
docker compose up -d                          # KiCad 10 (GUI: https://localhost:3001)
# 1. edit boards/<b>/sheets/*.py (nets) and/or scripts/build_board.py (placement)
./boards/helm/scripts/build_sch.sh            # schematic + ERC (helm)
docker exec vanchor-kicad kicad-cli sch export netlist --format kicadsexpr \
  -o .../vanchor-helm.net .../vanchor-helm.kicad_sch
docker exec vanchor-kicad python3 .../scripts/check_nets.py .../vanchor-helm.net
docker exec -e BASE_GND=0 vanchor-kicad python3 .../scripts/build_board.py
# 2. iterate placement DRC to zero, route (freerouting-1.9 in docker + xvfb,
#    -mp 25..40), import_routes.py, DRC. Driver board: same pattern with
#    boards/thrust-driver paths.
docker run --rm -v <dir>:/work eclipse-temurin:21-jre sh -c \
  "apt-get update -qq && apt-get install -y -qq xvfb libxext6 libxrender1 \
   libxtst6 libxi6 libfreetype6 fontconfig && xvfb-run -a java -jar \
   /work/freerouting-1.9.jar -de /work/<name>.dsn -do /work/<name>.ses -mp 30"
```

The container mounts this repo at `/config/vanchor-pcb`. Freerouting 1.9
jar: re-download from GitHub releases if missing (v2.x never writes SES).
Severity-aware DRC check: parse the report for `; error` (category counts
alone mislead — mask/edge checks are error-class by default).
