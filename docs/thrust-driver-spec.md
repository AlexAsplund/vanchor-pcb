# Vanchor Thrust Driver Board — spec (v1, 2026-07-02)

Companion power board to the Helm Board: the "external IBT-2-class driver"
that helm J13 expects — now designed in-house so the pair just works.

## Requirements (user)

- Drive a 12–24 V trolling motor, fwd/rev, covering the normal thrust range
  (30 lb → 55 lb class ≈ 30–50 A max draw at 12 V).
- **Variants**: a lower-power base build and a higher-power build from the
  same PCB.
- **Direct-connect** to the helm board's J13 with a plain cable — identical
  pinout, no adapters, no firmware changes ("just work").
- Thick copper NOT required — the user reinforces the power lanes by
  soldering copper cable/braid along exposed traces.

## Design

- **Control interface J1** (1×8 pin header, *identical* to helm J13):
  `1 RPWM · 2 LPWM · 3 R_EN · 4 L_EN · 5 R_IS · 6 L_IS · 7 VCC(5V) · 8 GND`.
  A straight 8-wire cable (ribbon or Dupont) maps helm J13 pin-for-pin.
  3.3 V PWM from the Pico drives the bridges directly (VIH ≈ 2.5 V).
  100k pull-downs on R_EN/L_EN (belt-and-braces with the helm's own).
- **Bridge**: 2× **BTN8982TA** half-bridges = one full H-bridge
  (base variant, ~30 A continuous / 55 A peak with modest airflow).
  **High-power variant**: second parallel pair (U3/U4, DNP on base builds)
  — each device gets its own slew-rate resistor (51 k) and IS resistor;
  IN/INH driven common per side. Doubles thermal capacity for sustained
  ~50 A on the bigger motors.
- **Current sense**: each side's IS pin(s) into a 1 k load to GND; the tap
  goes to header pins 5/6. Scaling (kILIS ≈ 8500): 30 A → ~3.5 V, matching
  the helm's existing IS mix/divider chain into the Pico ADC.
- **Power**: BATT+ / BATT− / MOT_A / MOT_B on **M5 bolt lugs**;
  2× 2200 µF/35 V low-ESR bulk + 100 nF ceramics + 1 µF/100 V film across
  the bridge; **SMCJ33A** TVS (fits 24 V systems incl. charging, still
  protective at 12 V). External fusing at the battery (ANL, sized to motor).
- **Copper strategy** (per user): 2-layer **1 oz**, wide pours for
  VBAT/MOT_A/MOT_B/GND, plus **solder-lane mask openings** — bare-copper
  strips along each power lane so 4–10 mm² copper wire/braid can be
  soldered directly on top for the high-current builds.
- Status LED on the header's 5 V (shows the control cable is live).
- Board ≈ 80×60 mm, same generation pipeline as the helm board.

## Deliberately NOT included

- No microcontroller, no logic supply (runs entirely off the helm's
  control signals + its own battery power) — keeps it dumb and robust.
- No reverse-battery protection at these currents (a series element would
  dissipate more than the bridge); wire carefully, fuse externally.
- No thermal shutdown circuitry beyond the BTN chips' built-in protection.

## As-built deltas (v1.1, 2026-07-02)

The finished board (`boards/thrust-driver/`) deviates from this spec in:

- **Board is 95×92 mm** (not ~80×60): the extra area carries the NMEA2000
  smart-node provision — DNP Pico 2 (U5) wired in parallel with J1's
  control nets, SIP-3 5 V regulator (U6), CAN transceiver header (J6),
  N2K power/shield connector (J7) and ADC series resistors (R12/R13).
  Dumb mode (this spec) is unchanged: populate nothing, drive via J1.
- **kILIS correction**: BTN8982TA sense ratio is ~**22 700** typ (the
  8500 figure below is the BTS7960's) → 30 A ≈ 1.3 V across the 1 k
  loads, not 3.5 V. Rescale firmware telemetry accordingly.
- 4 mounting holes (2 mid-board under/near the bridge, 2 in the node
  strip), not lug-corner mounting.
- SR resistors fitted as 51 k; mask-aperture DRC check set to *ignore*
  (the solder lanes are the point). Full details: the board README.
