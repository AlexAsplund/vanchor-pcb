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
    (30, 30, "POWER: 12V battery -> F1 -> reverse-FET -> VIN; generic 5V buck module on J14 (set 5.1V first)"),
    (30, 38, "CARRIER: J1 -> 26-way IDC ribbon -> Orange Pi Zero 3 (powered through the ribbon, no USB-C)"),
    (30, 160, "ORANGE PI ZERO 3 HEADER + UART/I2C BREAKOUTS"),
]

LAYOUT = {
    # power chain, left to right
    "J16": (45, 70, 0), "F1": (95, 70, 90), "Q1": (150, 70, 0),
    "D4": (215, 70, 0), "D5": (275, 70, 0),
    "C1": (330, 70, 90), "C2": (375, 70, 90),
    "R1": (150, 108, 90), "R2": (215, 108, 90), "LED1": (275, 108, 0),
    "C3": (330, 108, 90),
    "J14": (60, 138, 0),
    "#FLG01": (300, 138, 0), "#FLG02": (330, 138, 0), "#FLG03": (360, 138, 0),
    # Zero 3 header + breakout
    "J1": (70, 205, 0), "J2": (150, 205, 0),
    "J3": (235, 185, 0), "J4": (305, 185, 0),
    "J8": (235, 232, 0), "R5": (305, 224, 90), "R6": (305, 244, 90),
    "J9": (370, 185, 0), "F2": (370, 215, 90), "J10": (370, 245, 0),
    "#FLG04": (150, 255, 0),
}

COMPONENTS = []
for _c in power.COMPONENTS + pi.COMPONENTS:
    _c2 = dict(_c)
    _c2["at"] = LAYOUT[_c["ref"]]
    COMPONENTS.append(_c2)
