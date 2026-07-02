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

## DRC: 0 errors, 0 unconnected (v2 board, 2026-07-02)

The 200×150 mm v2 board is fully routed (1,633 segments/vias) and passes DRC
with **zero errors and zero unconnected items**. No touch-up is required
before ordering.

Remaining warnings (cosmetic only, waived):

| Warning | Count | Why waived |
|---|---|---|
| silk_overlap | ~118 | Reference-designator text overlapping other silk text; no electrical or assembly impact. |
| silk_over_copper | 1 | Ref text clipped by an exposed pad; cosmetic. |
| copper_sliver | 3 | Thin zone-fill wisps on B.Cu at pour boundaries; etch fine or vanish, no reliability impact. |

## Design-rule settings

- Clearance 0.15 mm (PCBWay/JLC 2-layer minimum is 0.127 mm), min track 0.25.
- Netclasses: HighCurrent 2.5 mm, Power 1.5–2.0 mm; power stage carried by
  6 mm pre-laid spines plus solid zones.
- **Order in 2 oz copper** — the 67 A thrust-stage zones are sized for it.

## Regeneration

Everything is scripted: `sheets/*.py` → `gen_sheet.py` (schematic) →
`build_board.py` (placement + power copper; `BASE_GND=0` for the routing
variant) → freerouting 1.9 (Docker, xvfb) → `import_routes.py` (SES import +
GND pours + stitching) → DRC. See README for the exact commands.
