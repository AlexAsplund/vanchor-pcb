"""Page 2 — CONTROL: Pico 2, thrust-driver interface, servo bridge.

Merges the mcu, thrust and servo net-specs onto one readable A3 sheet.
Connectivity lives in the source modules; this module only re-lays them
out (see carrier.py for the conventions).
"""
import mcu
import thrust
import servo

SHEET_UUID = "c0000000-0000-4000-8000-000000000004"

TEXTS = [
    (30, 30, "PICO 2: I2C slave 0x42 to the Zero 3; SWD reflash via ribbon pins 16/18, RUN on 12"),
    (30, 38, "THRUST: J13 = IBT-2 pin order to the external driver; EN pull-downs = failsafe off"),
    (30, 46, "SERVO: 2x BTN8982TA on protected VIN; AS5600 encoder cable on J11"),
    (175, 65, "THRUST DRIVER INTERFACE"),
    (30, 195, "PICO SUPPORT"),
    (30, 232, "SERVO BRIDGE + AS5600"),
]

LAYOUT = {
    # pico center, J12 to its left, J13 to its right (wired buses)
    "U1": (150, 118, 0),
    "J12": (52, 100, 0), "J13": (290, 100, 0),
    "R22": (150, 197, 90), "R23": (210, 197, 90), "C24": (268, 197, 90),
    "J11": (390, 95, 0), "J22": (390, 140, 0),
    "D14": (338, 95, 180),
    # thrust conditioning under J13
    "R30": (250, 152, 90), "R32": (295, 152, 90),
    "R15": (340, 152, 90), "R16": (382, 152, 90),
    "R38": (250, 182, 90), "C21": (295, 182, 90),
    "R20": (105, 182, 90), "R21": (150, 182, 90), "R13": (375, 182, 90),
    # pico support
    "R8": (45, 212, 90), "R9": (95, 212, 90), "R10": (145, 212, 90),
    "R11": (195, 212, 90), "R12": (245, 212, 90),
    "C5": (295, 212, 90), "D6": (340, 212, 180), "LED5": (385, 212, 0),
    # servo bridge
    "U7": (60, 252, 0), "U8": (135, 252, 0),
    "C22": (200, 250, 90), "C23": (245, 250, 90),
    "C12": (295, 245, 90), "D10": (340, 243, 180), "D11": (385, 243, 180),
    "R39": (45, 282, 90), "R40": (95, 282, 90),
    "R18": (145, 282, 90), "R19": (195, 282, 90), "D8": (245, 282, 180),
}

COMPONENTS = []
for _c in mcu.COMPONENTS + thrust.COMPONENTS + servo.COMPONENTS:
    _c2 = dict(_c)
    _c2["at"] = LAYOUT[_c["ref"]]
    COMPONENTS.append(_c2)

WIRES = [
    (("U7", "5"), ("R39", "1")),      # slew-rate resistors
    (("U8", "5"), ("R40", "1")),
    (("R13", "2"), ("LED5", "2")),    # status LED chain
    # pico -> J12 spare-GPIO breakout (GP0-3)
    (("U1", "1"), ("J12", "2"), [("x", 99.06), ("y", 93.65)]),
    (("U1", "2"), ("J12", "3"), [("x", 96.52), ("y", 96.19)]),
    (("U1", "4"), ("J12", "4"), [("x", 93.98), ("y", 98.73)]),
    (("U1", "5"), ("J12", "5"), [("x", 91.44), ("y", 101.27)]),
    # pico -> J13 thrust bus (nested staircase under the pico)
    (("U1", "16"), ("J13", "1"), [("x", 107.95), ("y", 176.53), ("x", 232.41), ("y", 91.11)]),
    (("U1", "17"), ("J13", "2"), [("x", 110.49), ("y", 172.72), ("x", 228.6), ("y", 93.65)]),
    (("U1", "19"), ("J13", "3"), [("x", 113.03), ("y", 168.91), ("x", 224.79), ("y", 96.19)]),
    (("U1", "20"), ("J13", "4"), [("x", 115.57), ("y", 165.1), ("x", 220.98), ("y", 98.73)]),
    # pico -> servo bridge inputs
    (("U1", "11"), ("U7", "2"), [("x", 88.9), ("y", 241.3)]),
    (("U1", "12"), ("U8", "2"), [("x", 91.44), ("y", 243.84)]),
    # pico -> status LED resistor
    (("U1", "22"), ("R13", "1"), [("x", 194.31), ("y", 86.36), ("x", 367)]),
    # pico ADC -> VBAT divider rail (over the thrust arrivals, down right of J13)
    (("U1", "34"), ("R11", "2"), [("x", 199.39), ("y", 88.9), ("x", 309.88), ("y", 204)]),
]
RAILS = [
    ("VBAT_SENSE", 204, [("R11", "2"), ("R12", "1"), ("C5", "1")]),
    ("HALL_ZERO", 190, [("R22", "1"), ("R23", "1"), ("C24", "1")]),
]
