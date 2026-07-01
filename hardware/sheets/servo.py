"""Servo sheet: header to off-board IBT-2 (BTS7960) H-bridge module driving the
12V worm gearmotor, current-sense conditioning, and the cabled AS5600 encoder
connector (I2C1) with series/ESD protection.
"""
from common import HDR1x8, XH4, R_AX, C_D, SOT23, grid

SHEET_UUID = "c0000000-0000-4000-8000-000000000006"

TEXTS = [
    (30, 40, "SERVO: IBT-2 module off-board via J15 cable; motor power from 12V rail (B+/B- on module)"),
    (30, 46, "AS5600 (in servo housing per vanchor-ng cad/) cabled to J11; keep lead <1m, 100kHz"),
]

COMPONENTS = [
    dict(lib="Connector_Generic:Conn_01x08", ref="J15", value="IBT-2", fp=HDR1x8,
         at=(70, 100, 0), pins={
            "1": "RPWM", "2": "LPWM", "3": "R_EN", "4": "L_EN",
            "5": ".RIS_RAW", "6": ".LIS_RAW", "7": "+5V", "8": "GND"}),
    dict(lib="Device:R", ref="R18", value="10k", fp=R_AX,
         at=grid(0), pins={"1": ".RIS_RAW", "2": "ISENSE_R"}),
    dict(lib="Device:R", ref="R19", value="10k", fp=R_AX,
         at=grid(1), pins={"1": ".LIS_RAW", "2": "ISENSE_L"}),
    dict(lib="Diode:BAT54S", ref="D8", value="BAT54S", fp=SOT23,
         at=grid(2), pins={"1": "GND", "2": "+3V3", "3": "ISENSE_R"}),
    dict(lib="Diode:BAT54S", ref="D9", value="BAT54S", fp=SOT23,
         at=grid(3), pins={"1": "GND", "2": "+3V3", "3": "ISENSE_L"}),
    dict(lib="Device:C", ref="C12", value="100n", fp=C_D,
         at=grid(4), pins={"1": "ISENSE_R", "2": "GND"}),
    dict(lib="Device:C", ref="C13", value="100n", fp=C_D,
         at=grid(5), pins={"1": "ISENSE_L", "2": "GND"}),

    dict(lib="Device:R", ref="R20", value="100R", fp=R_AX,
         at=grid(6), pins={"1": "ENC_SDA", "2": ".ENC_SDA_J"}),
    dict(lib="Device:R", ref="R21", value="100R", fp=R_AX,
         at=grid(7), pins={"1": "ENC_SCL", "2": ".ENC_SCL_J"}),
    dict(lib="Diode:BAT54S", ref="D10", value="BAT54S", fp=SOT23,
         at=grid(8), pins={"1": "GND", "2": "+3V3", "3": ".ENC_SDA_J"}),
    dict(lib="Diode:BAT54S", ref="D11", value="BAT54S", fp=SOT23,
         at=grid(9), pins={"1": "GND", "2": "+3V3", "3": ".ENC_SCL_J"}),
    dict(lib="Connector_Generic:Conn_01x04", ref="J11", value="AS5600", fp=XH4,
         at=(200, 100, 0), pins={"1": "+3V3", "2": "GND", "3": ".ENC_SDA_J", "4": ".ENC_SCL_J"}),
]
