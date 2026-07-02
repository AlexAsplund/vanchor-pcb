# LLM PCB Design — methodology and hard-won pitfalls

How this repo's boards were designed end-to-end by an LLM agent with no
human CAD interaction: five routed, DRC-clean revisions (200×150 → 125×95)
using headless KiCad 10 + freerouting. This document is the distilled
playbook — read it before attempting changes the same way.

## Core principle: generate, don't draw

An LLM cannot see a schematic canvas or a board render usefully enough to
edit it interactively. Everything must be **text-generated and gate-checked**:

- **Schematic** = Python net-spec dicts (`sheets/*.py`: one dict per
  component: lib symbol, ref, value, footprint, pin→net map). A generator
  (`gen_sheet.py`) computes pin positions from embedded symbols and plants
  global/local labels. `.`-prefixed nets are sheet-local.
- **Board** = a placement table (`build_board.py`: ref → (x, y, rot),
  courtyard-center anchored) + zone/track primitives, regenerated from a
  skeleton string every run (never mutate incrementally — delete-loops in
  pcbnew segfault; a fresh file is deterministic).
- **Never claim a state without its gate**: ERC via
  `kicad-cli sch erc --severity-error --exit-code-violations`, a netlist
  pin-count gate (`check_nets.py` with expected min pins per critical
  net), and `kicad-cli pcb drc`. Parse the DRC report programmatically;
  the summary counts lie by omission (severity classes).

## The pipeline

```
sheets/*.py ──gen_sheet──► .kicad_sch ──ERC──► netlist ──pin-count gate──►
build_board.py (BASE_GND=0) ──placement DRC to zero──►
ExportSpecctraDSN ──freerouting 1.9 (docker+xvfb, -mp 40)──► .ses ──►
import_routes.py (SES import + GND pours + stitching vias) ──► final DRC
```

- `BASE_GND=0` omits the GND pours from the routing variant so freerouting
  routes logic-GND as tracks; the importer re-adds pours + 7 mm-grid
  stitching vias afterwards. Zone-covered nets are **invisible planes** to
  freerouting — any pad of a plane net that the pours won't reach needs a
  pre-laid stub before export.
- Iterate **placement DRC to zero** (courtyards, pads, edge) before ever
  routing. Courtyard sizes must be *measured* (`GetCourtyard().BBox()`),
  not assumed — datasheet-guessed courts caused every placement collision.

## Freerouting-specific traps (each cost a debugging session)

1. **v2.x never writes the SES** (plateau loop) — use **v1.9**, which
   needs X: run in `eclipse-temurin:21-jre` with
   `xvfb-run` + `libxext6 libxrender1 libxtst6 libxi6 libfreetype6 fontconfig`.
2. **Pre-laid vias hang v1.9's DSN preprocessing** (silent, right after
   "Multiple vias skipped"). Never put vias in the pre-route board; vias
   are fine to add *after* routing.
3. **Zero-length track segments also hang it** — guard chain-drawing
   helpers against consecutive identical points.
4. It **rounds a few µm under its clearance target**: board clearance
   0.14 mm with netclasses at 0.15 absorbs this. Expect 1–3 residual
   grazes per run anyway (lottery); they move every rerun, so fix them
   surgically, never by rerouting.
5. It threads pad channels **off-center** — the fix is recentering the
   crossing segment between the two pad edges (compute the channel from
   the measured pad positions/sizes).
6. Long (>60 mm) skinny nets get dropped nondeterministically. Pre-lay
   them as tracks along planned lanes. Design the lane set on paper first:
   nested entries (inner lane enters lower), and when two nets must cross,
   put them on opposite layers *by construction*.

## Surgical-edit discipline (the single most important lesson)

Blind coordinate edits into a routed board fail ~70 % of the time — the
field is dense and invisible. The working protocol:

1. **Probe first**: query all tracks/pads within ~2 mm of the intended
   path (`point-to-segment` distance scan). Only draw through corridors
   verified empty *on the target layer*.
2. **Move, don't redraw**: for grazes, translate the offending segment's
   endpoints (and its neighbors' shared endpoints) by the minimum vector,
   staying within ~0.2 mm of the router's choice.
3. Every fix gets an immediate full DRC; regressions are reverted, not
   patched over.
4. If three consecutive surgical attempts fail, the geometry is telling
   you something — fix the *source* (placement/lanes) and rerun the
   pipeline instead.

## KiCad scripting traps

- Footprint auto-placement by courtyard center: 1×N/2×N connector
  footprints are **vertical at rot 0** — headers almost always want 90°.
- **Socket vs header footprints mirror their pin columns** — an in-place
  footprint swap silently lands pad numbers on wrong copper. Any
  socket↔header change requires re-placement *and* re-route.
- Anchored parts (modules whose pin 1 must land exactly) need pad-vector
  auto-rotation: try all rotations, verify two pad-delta vectors; if none
  fits, the part needs flipping — this is also how a mechanically
  impossible mirror-parity arrangement announces itself.
- Zone fills fragment: same-net zones/tracks that merely touch at edges
  produce islands flagged `unconnected_items`. Make every power-pad-to-rail
  connection an **explicit track**; never rely on fill adjacency. Between
  fine-pitch connector rows there is often *no* fill at all (void math).
- Fetch `GetNetsByName()` once at script start (SWIG object decays after
  board mutations).
- DRC exclusions via `.kicad_pro` are fragile from the CLI (serialization
  format undocumented; order/position sensitive). Prefer **design-honest
  fixes**: a genuinely unreachable redundant pad becomes NC in the
  schematic with a comment, not an exclusion.
- `kicad-cli pcb drc --format json` gives item UUIDs and exact positions —
  parse this, not the text report, when automating triage.

## Domain judgment the LLM must supply itself

- Datasheet geometry from memory is unreliable — measure pads from the
  loaded footprint (the ACS758's paired power legs and the BTN8982's
  split tab were both "surprises" vs assumption).
- Copper sizing: 2 oz + zones + explicit fat tracks for >20 A;
  netclass width ≠ enforced minimum (only board `min_track_width` is).
- Keep real-time/safety functions on a microcontroller, not the Linux SBC
  (PWM jitter, watchdog); verify claimed SBC capabilities (the Zero 3
  exposes *no* hardware PWM on its header — port-mux table, not marketing).
- Cost passes work best as an explicit numbered log with per-pass deltas;
  the big wins are architectural (removing a subsystem), not component
  substitutions.
- BOM ordering reality: distributor part matching fails on formatting
  (commas, value codes like `1K0` vs `102`), MOQ traps (reel-only lines),
  and dated MPNs. Expect 3–5 iterations with the human who has cart
  visibility; encode substitution notes *in* the order file.

## What worked well / what didn't

**Worked**: generated-everything workflow; gate-driven iteration;
autorouting with generous spacing (the 2× headroom of a bigger board cut
convergence from ~10 cycles to 1–2); probe-then-edit surgery; honest
deviation notes instead of silent waivers; docker-pinned toolchain.

**Didn't**: dense hand-routing lanes computed blind (v2's driver strip
consumed more effort than the rest of the board combined — the fix was
architectural: give the router room); in-place footprint swaps; trusting
any coordinate that wasn't measured from the file.

## Addendum (2026-07-02, learned on v4.2 + thrust driver)

- **Parse DRC severity, not category counts.** `solder_mask_bridge` and
  `copper_edge_clearance` are error-class by default; grep the report for
  `; error` per block. A "0 unconnected" summary with benign-looking
  category counts can still hide real errors.
- **pcbnew silent segfaults** extend beyond footprint removal: zone
  removal and zone-outline `SetVertex` also kill the interpreter without
  saving. Same cure: staged scripts — one destructive class per process,
  `SaveBoard` immediately, verify persistence with a fresh read-only load.
- **`ZONE.GetLayerName()` lies** (returns F.Cu for B-side zones). Filter
  zones by `IsOnLayer()`/priority/bbox instead.
- **Freerouting chokes on large slotted pads** (the XL4015 daughterboard):
  runs that converged in ~7 min ran >12 min without producing a SES.
  Root-cause fixes beat rerolls: pre-lay the nets it drops, relocate
  parts that create 100 mm nets, and re-run at `-mp 25-30`.
- **Orphan pour islands**: after deleting redundant routed GND tracks,
  point-in-bbox scan each pour piece for GND items with a TH/via link —
  pieces with only SMD items need a rescue stub + via from the pad itself.
- **Nesting hand-drawn buses**: for N parallel links from a pin row to
  staggered targets, same-order pairs need the *shallower* lane on the
  net whose exit is *east* of the other's target-drop; verify every
  lane-crosses-drop pair on paper before drawing (drops span from their
  lane to the pad — any lane passing a drop's x within that span crosses).
- **Fill connects same-net tracks to zones — but only where fill exists.**
  A track "in" a zone whose channel doesn't fill (clearance-starved) ends
  dangling; prefer landing bridges on pads/vias, not on fill.
