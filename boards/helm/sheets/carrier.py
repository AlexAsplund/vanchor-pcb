"""Page 1 — CARRIER: power entry + Orange Pi Zero 3 interface.

Merges the power and pi net-specs onto one readable A3 sheet. Connectivity
lives in power.py / pi.py (single source of truth); this module only
re-lays them out: functional rows, generous pitch, two-pin parts horizontal
(rot 90 for R/C/fuse symbols whose KiCad default is vertical).
"""
import power
import pi

SHEET_UUID = "c0000000-0000-4000-8000-000000000002"

TEXTS = [
    (30, 30, "POWER: 12V battery -> F1 -> reverse-FET -> VIN; XL4015 buck daughterboard U5 (set 5.1V first)"),
    (30, 38, "CARRIER: J1 -> 26-way IDC ribbon -> Orange Pi Zero 3 (powered through the ribbon, no USB-C)"),
    (30, 160, "ORANGE PI ZERO 3 HEADER + UART/I2C BREAKOUTS"),
]

LAYOUT = {
    # power chain, left to right
    "J16": (45, 70, 0), "F1": (95, 70, 90), "Q1": (150, 70, 0),
    "D4": (215, 70, 0), "D5": (275, 70, 0),
    "C1": (330, 70, 90), "C2": (375, 70, 90),
    "R1": (150, 108, 90), "R2": (215, 108, 90), "LED1": (275, 108, 180),
    "C3": (330, 108, 90),
    "U5": (60, 138, 0),
    "J5": (300, 132, 0), "R41": (345, 128, 90), "R42": (362, 150, 90),
    "#FLG01": (45, 255, 0), "#FLG02": (85, 255, 0), "#FLG03": (115, 255, 0),
    # Zero 3 header + breakout
    "J1": (70, 205, 0), "J2": (150, 205, 0),
    "J3": (235, 185, 0), "J4": (305, 185, 0),
    "J8": (235, 232, 0), "R5": (305, 220, 90), "R6": (305, 248, 90),
    "J9": (370, 185, 0), "F2": (370, 215, 90), "J10": (370, 245, 0),
    "#FLG04": (150, 255, 0),
}

COMPONENTS = []
for _c in power.COMPONENTS + pi.COMPONENTS:
    _c2 = dict(_c)
    _c2["at"] = LAYOUT[_c["ref"]]
    COMPONENTS.append(_c2)

# Drawn connections (generator draws wires; labels are kept once per net)
WIRES = [
    (("J16", "1"), ("F1", "1")),      # battery -> fuse
    (("F1", "2"), ("Q1", "2")),       # fuse -> reverse-FET drain
    (("J5", "1"), ("R41", "1")),      # N2K V+ -> tap link
    (("J5", "3"), ("R42", "1")),      # N2K shield -> bond link
    (("F2", "2"), ("J10", "1")),      # polyfuse -> aux 5V out
    (("R2", "2"), ("LED1", "2")),     # power LED chain
]
RAILS = [
    ("VIN", 88, [("Q1", "3"), ("D4", "1"), ("D5", "1"), ("C1", "1"), ("C2", "1"), ("R2", "1")]),
]
