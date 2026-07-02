# vanchor-thrust — trolling-motor DC driver

95×75 mm 2-layer board. Full H-bridge for a 12–24 V brushed trolling motor,
controlled by the vanchor-helm board over one straight 8-wire cable. Two
build variants share the same PCB:

| Variant | Fit | Continuous current |
|---|---|---|
| Base | U1 + U2 (2× BTN8982TA) | ~30 A (with cable reinforcement, see below) |
| High power | also U3 + U4 + R7 + R8 | ~50 A |

## Cable to the helm board

J1 mirrors helm J13 **pin-for-pin** — crimp a straight 8-wire cable
(0.5–1 mm², keep it under ~2 m, twist RPWM/LPWM with GND spares if longer):

| Pin | Signal | Direction |
|---|---|---|
| 1 | RPWM | helm → driver |
| 2 | LPWM | helm → driver |
| 3 | R_EN | helm → driver |
| 4 | L_EN | helm → driver |
| 5 | R_IS (current sense A) | driver → helm |
| 6 | L_IS (current sense B) | driver → helm |
| 7 | +5V (logic, from helm buck) | helm → driver |
| 8 | GND | — |

The LED (D1) lights when the helm's 5 V arrives — a quick cable check.

## Power wiring

M5 lugs: BATT+ / BATT− on the left edge, MOT A / MOT B on the right.
Use 10 mm² (8 AWG) or thicker cable for the 50 A build. **Fuse the battery
lead externally** (ANL or MIDI, 40 A base / 60 A high power) close to the
battery. There is **no reverse-polarity protection** — double-check
polarity before connecting; reversed battery destroys the BTN8982s.
D2 (SMCJ33A) clamps inductive spikes; the board is 12–24 V only.

## Solder-lane reinforcement (required above ~15 A continuous)

The board is ordered in standard 1 oz copper — cheap, but the copper alone
won't carry 30–50 A. Every power lane (VBAT band + spine, MOT A, MOT B on
top; GND band on the bottom) has an exposed solder lane (no solder mask).
Before first high-power use:

1. Clean the lanes with IPA, apply flux.
2. Tin each lane with a wide tip.
3. Lay 4–10 mm² desoldered copper braid or stripped solid wire along the
   lane and solder it down continuously end-to-end.

With braid on all lanes the base build handles ~30 A continuous, the
high-power build ~50 A. The 202 "solder mask bridge" DRC warnings are these
lanes — intentional.

## Firmware note (high-power variant)

Each BTN8982's IS pin sources I_load/kILIS (~8500). Both devices of a side
feed the **same** 1 k sense resistor, so with U3/U4 fitted the sensed
voltage per ampere stays the same only if the halves share evenly — in
practice treat the effective kILIS as ~8500 with U1/U2 only and ~17000 per
device (halved reading) when paralleled. Calibrate `THR_IS` scaling in the
Pico firmware after choosing the variant.

## Assembly order

1. SMD: BTN8982s (U1/U2, plus U3/U4 for high power), D2.
2. Resistors: R1–R6, R9 (+ R7/R8 with U3/U4), diode D1.
3. C3/C4 ceramics, C5 film, then C1/C2 electrolytics (mind polarity).
4. Lugs J2–J5, header J1.
5. Solder-lane braid (see above), then bolt to a heatsink/baseplate through
   the two M3 holes with a thermal pad under the BTN tabs for >20 A use.

## Ordering

Same fab spec as the helm board: 2 layers, 1.6 mm FR-4, 1 oz copper,
HASL, 5/5 mil, 0.3 mm min drill, tented vias. Upload
`fab/vanchor-thrust-gerbers.zip`. ~$10-15 for 5 pcs at PCBWay/JLC.

## Design notes / DRC deviations

- `solder_mask_bridge` warnings (~200): intentional exposed solder lanes.
- `pth/npth_inside_courtyard`, `courtyards_overlap`: warnings only, from
  the lug/cap density; verified manually.
- The routed .kicad_pcb includes hand-placed link tracks and via-hops for
  the DNP-pair nets (RPWM/LPWM/R_EN/L_EN/R_IS/L_IS between U1/U2 and
  U3/U4) — regenerating the board from `scripts/build_board.py` requires
  re-running freerouting **and** re-applying equivalent patches; treat the
  checked-in board file as the source of truth.
