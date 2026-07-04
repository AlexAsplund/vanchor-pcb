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
    # pico + big connectors
    "U1": (95, 120, 0),
    "J12": (195, 100, 0), "J13": (255, 100, 0),
    "R22": (165, 195, 90), "R23": (180, 195, 90), "C24": (195, 195, 90),
    "J11": (390, 95, 0), "J22": (390, 140, 0),
    "D14": (330, 95, 0),
    # thrust conditioning
    "R30": (200, 152, 90), "R32": (250, 152, 90),
    "R15": (300, 152, 90), "R16": (350, 152, 90),
    "R38": (195, 182, 90), "C21": (240, 182, 90),
    "R20": (285, 182, 90), "R21": (330, 182, 90), "R13": (375, 182, 90),
    # pico support
    "R8": (45, 212, 90), "R9": (95, 212, 90), "R10": (145, 212, 90),
    "R11": (195, 212, 90), "R12": (245, 212, 90),
    "C5": (295, 212, 90), "D6": (340, 212, 0), "LED5": (385, 212, 0),
    # servo bridge
    "U7": (60, 252, 0), "U8": (135, 252, 0),
    "C22": (200, 250, 90), "C23": (245, 250, 90),
    "C12": (295, 245, 90), "D10": (340, 243, 0), "D11": (385, 243, 0),
    "R39": (45, 282, 90), "R40": (95, 282, 90),
    "R18": (145, 282, 90), "R19": (195, 282, 90), "D8": (245, 282, 0),
}

COMPONENTS = []
for _c in mcu.COMPONENTS + thrust.COMPONENTS + servo.COMPONENTS:
    _c2 = dict(_c)
    _c2["at"] = LAYOUT[_c["ref"]]
    COMPONENTS.append(_c2)
