# Cost-optimization log — 10 passes (2026-07-02)

Baseline: v2 board, 200×150 mm 2-layer **2 oz**, ~$97 components + ~$14 PCB
per board (qty-5 PCB order, single-unit part prices).

| # | Pass | Change | Δ per board |
|---|------|--------|-------------|
| 1 | Value consolidation | R39/R40 51k → 47k (merges with R1's 47k; BTN8982 slew-rate spec allows 6.8k–51k). Distinct resistor values 14 → 13, one fewer order line. | ≈ $0 (order simplicity) |
| 2 | Indicator trim | 5 LEDs → 2. Kept: VIN power (LED1), Pico status (LED5). Dropped: +5V, +12V rail LEDs, Pi heartbeat (rails are provable with a meter; heartbeat is visible on the touchscreen). Frees Pi GPIO26. | −$0.25, −6 parts |
| 3 | Connector de-population | J2 (40-pin breakout) and J12 (Pico util) → DNP. Footprints stay for debugging; headers cost little but every hand-soldered joint costs build time (80 joints). | −$0.60, −88 joints |
| 4 | 12 V buck DNP | U6 (Pololu D36V50F12, $19.95) → DNP by default. On a 12 V-battery boat (this project), J17 gets a wire link and the battery feeds the 12 V rail directly. U6 is populated only for 24–48 V systems. | **−$19.95** |
| 5 | Protection audit | Q1/D4/D5 reverse-battery + TVS, servo IS conditioning, AS5600 line clamps (D10/D11 + R20/R21): all reviewed, all kept — each protects against a plausible marine-wiring fault for well under $1 total. | $0 (documented) |
| 6 | Connector audit | JST-XH ($0.09) and CUI terminal blocks ($0.37) reviewed against cheaper pin headers: kept — locking/screw connections earn their cost on a vibrating boat. Blade-fuse holder kept over 5×20 clips for the same reason. | $0 (documented) |
| 7 | Cost-driver analysis | Itemized the BOM: the on-board thrust bridge (8 FETs $27.60 + driver/sensor/bulk-caps ~$9) plus its consequences (2 oz copper ≈ +$6/board, ~40 % of board area, heatsink bar) accounted for **≈ $45/board**. Flagged for architectural review → pass 10. | (analysis) |
| 8 | Production path (doc) | For 100+ volume: migrate passives/diodes to SMD, replace Pico module with RP2350 + flash, panelize. Documented in this log; not applied to the hand-build design. | (future) |
| 9 | Voltage-variant BOM | 12 V-only builds may substitute 25 V-rated electrolytics for C1/C2 (470 µF): EEU-FR1E471 ≈ half the price of the 63 V part. Default BOM stays 63 V so the same board can go on 24–48 V systems. | −$0.60 (12 V variant) |
| 10 | **External thrust driver** | Removed the entire on-board H-bridge (8× IRF100P219, HIP4082, ACS758, bootstrap parts, 2200 µF bulk caps, TVS, film cap, M5 lugs — 34 parts). Replaced with **J13**, an 8-pin header with the standard IBT-2/BTS7960 pinout (RPWM, LPWM, R_EN, L_EN, R_IS, L_IS, 5 V, GND) driving the user's existing external driver. IS outputs are mixed and clamped into the Pico ADC, EN lines pull down so the driver stays dead when the Pico is absent. Board: 200×150 2 oz → **150×120 1 oz**. | **−$41 parts, −$8 PCB** |

## Result

| | v2 (on-board bridge) | v3 (after 10 passes) |
|---|---|---|
| Components (12 V build) | ~$97 | **~$35** |
| PCB (qty 5, per board) | ~$14 (2 oz, 200×150) | **~$6 (1 oz, 150×120)** |
| Hand-solder joints | ~480 | ~300 |
| Board size | 200×150 mm | 150×120 mm |
| Heatsink / 2 oz / lugs | required | none |
| **Per assembled board** | **~$111** | **~$41** |

External driver (already owned) carries all battery/motor current; the helm
board is now logic + servo only. Wiring: driver's 8-pin harness → J13
(pin 1 = RPWM, matches the silkscreen), battery 12 V → J16, servo motor →
J22, AS5600 cable → J11.

Firmware deltas (vanchor-ng): thrust moves from the HIP4082 pin set back to
the classic RPWM/LPWM/R_EN/L_EN interface on **GP12/GP13/GP14/GP15**
(THR_RPWM/THR_LPWM/THR_R_EN/THR_L_EN); THR_IS stays on GP27 (now the
external driver's IS mix); GP16 and GP26 are freed.

## v3.1 addendum — 12V-only commit (user decision, 2026-07-02)

With the thrust bridge external, the 48V input requirement died with it.
Board committed to 12V (car battery, 14.4V charging):

- **U5 (Pololu D36V50F5, $19.95) removed** → J14 header (VIN GND 5V GND) for
  a generic XL4015/LM2596-class buck module (~$2.50), strapped to the board
  via two M3 holes beside it. Set to 5.1V before fitting.
- **U6 + J17 removed entirely** — the servo bridge (BTN8982, 5.5-40V) runs
  straight off protected VIN.
- D5 TVS: SMCJ58A → **SMCJ18A** (proper 12V clamping); C1/C2 → 25V-rated;
  R2 LED resistor 15k/0.5W → 2.2k; VBAT divider rescaled 47k/10k
  (reuses existing values, kills the 6.8k and 100k-divider line items).

| | v3 | v3.1 |
|---|---|---|
| Components | ~$35 | **~$15 + $2.50 buck module ≈ $18** |
| Line items | 44 | 40 |
| Input range | 12-48V | 12V only (14.4V charging) |
