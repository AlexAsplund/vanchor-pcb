# ERC & DRC notes

## ERC: 0 errors

`kicad-cli sch erc --severity-error` → clean. Waived warnings:

| Check | Symbol | Why waived |
|---|---|---|
| lib_symbol_mismatch | D12, D13 (UF4007 on 1N4007 symbol) | Our embedder flattens derived symbols; electrically identical. |

Deliberate ERC-related choices: Pico GND/AGND pins retyped passive (see
`PIN_TYPE_OVERRIDES` in `scripts/embed_symbols.py`); `+12V` needs no PWR_FLAG
(U6 VOUT drives it; with U6 DNP the net has no power-in pins); Pi I²C pull-ups
R5/R6 DNP by design.

## DRC: 0 errors, 0 unconnected (v3 cost-optimized board, 2026-07-02)

The 150×120 mm v3 board (cost pass 10: external thrust driver on J13, no
on-board H-bridge) is fully routed and passes DRC with **zero errors and
zero unconnected items**. No touch-up is required before ordering. Two
SERVO_A feeder segments are deliberately 1.8 mm (vs the 2.5 mm class
default) where they parallel the +12V bottom lane — fine for the servo's
~5 A continuous draw on 1 oz copper.

Remaining warnings (cosmetic only, waived):

| Warning | Count | Why waived |
|---|---|---|
| silk_overlap | 36 | Reference-designator text overlapping other silk text; no electrical or assembly impact. |
| silk_over_copper | 2 | Ref text clipped by an exposed pad; cosmetic. |

## Design-rule settings

- Clearance 0.15 mm (PCBWay/JLC 2-layer minimum is 0.127 mm), min track 0.25.
- Netclasses: HighCurrent 2.5 mm (VIN, ±12V, servo), Power 1.5 mm.
- **Standard 1 oz copper is fine** — battery/motor current stays on the
  external thrust driver (cost pass 10); max on-board current is the servo
  bridge + Pi supply (~10 A on VIN).

## Regeneration

Everything is scripted: `sheets/*.py` → `gen_sheet.py` (schematic) →
`build_board.py` (placement + power copper; `BASE_GND=0` for the routing
variant) → freerouting 1.9 (Docker, xvfb) → `import_routes.py` (SES import +
GND pours + stitching) → DRC. See README for the exact commands.
