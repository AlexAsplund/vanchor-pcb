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

## DRC status (2026-07-02)

The board is fully placed, all power copper (VBRIDGE/MOTOR/GND/VBAT zones,
spines, lugs) is correct and connected, and 1900+ track segments are routed
(scripted freerouting pipeline + pre-laid power/critical tracks).

**Cosmetic warnings (waived):** `silk_overlap` / `silk_over_copper` /
`solder_mask_bridge` / `copper_sliver` — reference-designator text overlaps
and mask artifacts; no electrical effect. Tidy silk labels at leisure.

**Known issues — needs ~20-30 min of GUI touch-up before ordering**
(open http://localhost:3000, KiCad → the project → run DRC and walk the list):

All remaining items sit in the gate-driver strip (bottom of the power band,
x 30-95 / y 80-120) and the J1/J2 header field — an area too congested for the
blind CLI iteration used here:

1. `/thrust/BHO` (F.Cu, y115.5 run) crosses the +12V island link (x53.9) and
   MOTOR_B sense run — drag the BHO run to B.Cu or re-route its right leg.
2. `/thrust/ALO` east loop (x92.3, B.Cu) grazes R33/C1/F1 pads — nudge 1-2 mm.
3. `/thrust/DEL` leg (x50.5) crosses the +12V island jog — shift either 1 mm.
4. +12V corner feed (x31) vs MOTOR_A sense (x29.2): one crossing — move the
   +12V feed 1 mm east or drop its crossing segment to B.Cu.
5. Two dangling +12V stubs at (48-54, 110) — delete, then re-drag the island
   link to the west bootstrap leg (58.5, 84.9).
6. Two dangling 3V3_PI fragments near (52-65, 16) — delete.
7. `G_AL1` Q5↔R24 and `THR_AHI` R33 leg unrouted — two short interactive
   routes; J1 pin 6 GND needs one via to the B plane.
8. C17/U9 and R24/R1 courtyard grazes (<1 mm) — nudge C17 down, R24 left.

Everything else (94-net connectivity, ERC, power stage, footprints, fab
outputs) is verified by the scripted gates. After the touch-up, re-run:
`docker exec vanchor-kicad kicad-cli pcb drc --exit-code-violations ...`
and re-export with `hardware/scripts/export_fab.sh`.

## Design-rule settings

- Clearance 0.15 mm (PCBWay/JLC 2-layer minimum is 0.127 mm), min track 0.25.
- Power netclasses: HighCurrent 2.5 mm / Power 1.5-2.0 mm tracks.
- **Order in 2 oz copper** — the 67 A power zones are sized for it.
