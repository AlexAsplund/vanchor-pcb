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
    "J11": (390, 95, 0), "J22": (75, 274, 0),
    "D14": (338, 84, 180),
    # thrust conditioning under J13
    "R30": (250, 152, 90), "R32": (295, 152, 90),
    "R15": (340, 152, 90), "R16": (382, 152, 90),
    "R38": (344, 182, 90), "C21": (386, 182, 90),
    "R20": (352, 106, 90), "R21": (352, 134, 90),
    "R13": (105, 180, 90), "LED5": (155, 180, 180),
    # pico support
    "R8": (45, 212, 90), "R9": (95, 212, 90), "R10": (145, 212, 90),
    "R11": (195, 212, 90), "R12": (245, 212, 90),
    "C5": (295, 212, 90), "D6": (340, 212, 180),
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
    # pico CAN pair -> J12 (over the top, down the left margin)
    (("U1", "24"), ("J12", "6"), [("x", 203.2), ("y", 69.85), ("x", 13.97), ("y", 103.81)]),
    (("U1", "25"), ("J12", "7"), [("x", 205.74), ("y", 67.31), ("x", 11.43), ("y", 106.35)]),
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
    # pico -> status LED resistor (over the top, down left of the pico)
    (("U1", "22"), ("R13", "1"), [("x", 194.31), ("y", 72.39), ("x", 101.19)]),
    # pico ADC -> VBAT divider rail (over the arrivals, down the right margin)
    (("U1", "34"), ("R11", "2"), [("x", 208.28), ("y", 88.9), ("x", 400.05), ("y", 204)]),
    # encoder series resistors -> AS5600 connector
    (("R20", "2"), ("J11", "3"), [("x", 368.3), ("y", 96.27)]),
    (("R21", "2"), ("J11", "4"), [("x", 370.84), ("y", 98.81)]),
    # servo bridge outputs -> motor terminal block (left of U7, U8 loops under)
    (("U7", "4"), ("J22", "1"), [("x", 78.74), ("y", 272.73)]),
    (("U8", "4"), ("J22", "2"), [("x", 166.37), ("y", 284.48), ("x", 61)]),
    # bridge IS -> sense divider top
    (("U8", "6"), ("R18", "1"), [("x", 153.67), ("y", 273.05), ("x", 133)]),
]
RAILS = [
    ("VBAT_SENSE", 204, [("R11", "2"), ("R12", "1"), ("C5", "1"), ("D6", "3")]),
    ("HALL_ZERO", 190, [("R22", "1"), ("R23", "1"), ("C24", "1")]),
    ("THR_IS", 156.21, [("R38", "1"), ("C21", "1"), ("R15", "2"), ("R16", "2")]),
]
