# ERC & DRC notes

## ERC: 0 errors

`kicad-cli sch erc --severity-error` → clean. Waived warnings:

(No waived warnings in the v4.1 two-page schematic.)

Deliberate ERC-related choices: Pico GND/AGND pins retyped passive (see
`PIN_TYPE_OVERRIDES` in `scripts/embed_symbols.py`); `+12V` needs no PWR_FLAG
(U6 VOUT drives it; with U6 DNP the net has no power-in pins); Pi I²C pull-ups
R5/R6 DNP by design. Schematic is 2 pages (carrier / control) generated
from merged net-specs; see sheets/carrier.py + control.py.

## DRC: 0 errors, 0 unconnected (v4 Orange Pi Zero 3 board, 2026-07-02)

The 125×95 mm v4 board (Orange Pi Zero 3 on a 26-pin socket, module on
top, low-profile parts underneath) is fully routed and passes DRC with
**zero errors and zero unconnected items**.

Documented deviations:
- `courtyards_overlap` severity set to warning: the J2/J12 DNP debug-header
  courtyards graze by 0.5 mm (the slot is 0.04 mm too small). Populate at
  most one, or fit J12 with a right-angle header. Hole-to-hole is clear.
- J1 pin 14 and J2 pin 9 are NC by design (schematic-level): the header
  escape field owns their corridors on both layers; each connector retains
  four ground pins.
- Clearance 0.14 mm (fab minimum 0.127): freerouting targets 0.15 exactly
  and rounds a few µm under; 0.14 absorbs that without touching the fab
  margin.

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
