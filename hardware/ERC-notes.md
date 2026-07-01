# ERC status & waivers

Gate: `kicad-cli sch erc --exit-code-violations --severity-error` → **0 errors** (2026-07-01).

Full report (`--exit-code-violations`, warnings included) has 3 waived warnings:

| Check | Symbol | Why waived |
|---|---|---|
| footprint_link_issues | U5, U6 (`vanchor-helm:Pololu_D36V50Fx`) | Custom footprint library is created in the board-generation task; resolved there. |
| lib_symbol_mismatch | D7 (`Diode:1N4007`) | Our embedder flattens derived symbols (1N4007 extends 1N4001); the flattened copy differs textually from the library's derived form but is electrically identical. |

Deliberate ERC-related design choices:

- The stock `MCU_Module:RaspberryPi_Pico` symbol types GND (pin 3) and AGND
  (pin 33) as *power output*, which conflicts with the GND PWR_FLAG and each
  other. The embedder retypes both to *passive* (see `PIN_TYPE_OVERRIDES` in
  `scripts/embed_symbols.py`); GND is driven by PWR_FLAG #FLG02.
- `+12V` has no PWR_FLAG: driven by U6 VOUT normally; with U6 DNP (12 V boats)
  the net contains no power-input pins, so no driver is required.
- Pi I²C pull-ups R5/R6 are DNP by design (Pi has fixed 1.8 kΩ on GPIO2/3).
