# Vanchor Helm Board — Handoff (2026-07-02)

## What this is

Carrier PCB for the vanchor-ng trolling-motor autopilot. Current revision
**v4.1**: 125×95 mm, 2-layer 1 oz, DRC-clean (0 errors / 0 unconnected).

- **Orange Pi Zero 3** (autopilot computer, Linux) — connects via a 26-way
  1:1 IDC ribbon to J1 (2×13 male header); powered through the ribbon 5 V.
- **Raspberry Pi Pico 2** on-board (real-time motor controller, I²C slave
  0x42 on the Zero 3's I²C3). Runs PWM, AS5600 steering loop, watchdog.
- **Thrust**: external IBT-2/BTS7960-class driver on J13 (8-pin, IBT-2 pin
  order). Battery/motor power never touches this board.
- **Steering servo**: on-board H-bridge, 2× BTN8982TA, fed from protected
  VIN. ~5 A continuous / 10 A peak plumbing.
- **Power**: 12 V only (car battery). J16 in → F1 10 A → reverse-FET → VIN.
  5 V rail from a generic buck module on J14 (VIN GND 5V GND).

## State of play

| Item | Status |
|---|---|
| Schematic | ERC 0 errors; generated from `hardware/sheets/*.py` |
| Board | routed, DRC 0/0; silk-only warnings (see `hardware/ERC-notes.md`) |
| Fab outputs | `hardware/fab/` incl. `vanchor-helm-gerbers.zip` (upload as-is) |
| PCB order specs | 125×95, 2-layer, 1.6 mm, **1 oz**, HASL, 5/5 mil, 0.4 mm min hole, **tented vias** |
| Parts order | `bom/mouser-order.csv` (v6) — all-Mouser, matched by user except noted subs |
| Not in any cart | Orange Pi Zero 3 + XL4015 buck ×2 (AliExpress), PCBs (PCBWay) |

Version history (all in git): v1/v2 on-board 800 W H-bridge (`bf91c4a`),
v3 external thrust driver ($41/board, `bc85d2a`), v3.1 12 V-only + cheap
buck (`357fd39`), v4 Orange Pi Zero 3 (`61010d3`), v4.1 ribbon header
(`de319ba`). Cost log: `docs/cost-optimization-log.md`.

## Known deviations (all documented in `hardware/ERC-notes.md`)

- J1.14 and J2.9 (one GND pin each) are **NC by design** — corridors owned
  by header escape routing; 4 ground pins remain per connector.
- J2/J12 courtyards graze 0.5 mm (both DNP debug headers; populate ≤1).
- Board clearance 0.14 mm (freerouting rounds ~2 µm under its 0.15 target;
  fab min is 0.127).
- Two SERVO_A feeder segments at 1.8 mm (fine at servo current).

## Open items for whoever continues

1. **Order**: PCBWay (specs above), Mouser CSV, AliExpress (Zero 3 + XL4015).
   BTN line: user chose `BTN8982TAAUMA1` (same part, ordering code).
   1 k resistors: KOA `CF1/4CT52R102J`. XH headers: Würth 619-series
   alternates discussed and mateable with the JST housings in the cart.
2. **Buck setup**: set XL4015 to 5.10 V and load-test at 4 A *before*
   wiring to J14. Strap to the M3 holes beside J14.
3. **Firmware (vanchor-ng)**: thrust pins now GP12=RPWM GP13=LPWM
   GP14=R_EN GP15=L_EN; THR_IS on GP27 (external driver IS mix); servo
   unchanged; I²C slave 0x42. Zero 3 side: enable `i2c3`, `uart2`, `uart5`
   DT overlays; Pico SWD reflash via ribbon pins 16/18 (PC15/PC14, openocd
   `linuxgpiod`), RUN on pin 12 (PC11). If a BTN8980/8962 was substituted,
   recalibrate kILIS in the servo current telemetry.
4. **Assembly**: bring-up checklist at the end of `README.md`. Ribbon:
   match pin-1 marks both ends; never plug USB-C while ribbon-powered.
5. **Marine**: conformal-coat the assembled board (mask connectors first).

## Regenerating / changing the design

Everything is generated — never hand-edit `.kicad_sch`/`.kicad_pcb`.

```sh
docker compose up -d                          # KiCad 10 (GUI: https://localhost:3001)
# 1. edit hardware/sheets/*.py (nets) and/or build_board.py (placement)
./hardware/scripts/build_sch.sh               # schematic + ERC
docker exec vanchor-kicad kicad-cli sch export netlist --format kicadsexpr \
  -o .../vanchor-helm.net .../vanchor-helm.kicad_sch
docker exec vanchor-kicad python3 .../scripts/check_nets.py .../vanchor-helm.net
docker exec -e BASE_GND=0 vanchor-kicad python3 .../scripts/build_board.py
# 2. iterate placement DRC to zero non-routing violations, then route:
#    export DSN (pcbnew.ExportSpecctraDSN), run freerouting-1.9 (see below),
#    import_routes.py, DRC. Full pitfall playbook: docs/llm-pcb-design.md
docker run --rm -v <dir>:/work eclipse-temurin:21-jre sh -c \
  "apt-get update -qq && apt-get install -y -qq xvfb libxext6 libxrender1 \
   libxtst6 libxi6 libfreetype6 fontconfig && xvfb-run -a java -jar \
   /work/freerouting-1.9.jar -de /work/vanchor-helm.dsn -do /work/vanchor-helm.ses -mp 40"
```

The container mounts this repo at `/config/vanchor-pcb`. Freerouting 1.9
jar lives in the session scratchpad — re-download from the freerouting
GitHub releases if missing (v2.x is broken: never writes the SES).
