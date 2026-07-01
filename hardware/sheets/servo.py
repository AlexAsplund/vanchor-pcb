"""Servo sheet: ON-BOARD H-bridge (2x BTN8982TA half-bridges) for the 12V worm
gearmotor + the cabled AS5600 encoder connector (I2C1).

The BTN8982 pair speaks the exact BTS7960/IBT-2 interface the vanchor-ng
steering firmware already uses: RPWM/LPWM into IN, R_EN/L_EN into INH,
combined IS through one 1k sense resistor (only the driving side sources
current) filtered + clamped into the Pico ADC. VM = +12V rail.
"""
from common import XH2, XH4, TB2, R_AX, C_D, SOT23, grid

SHEET_UUID = "c0000000-0000-4000-8000-000000000006"

TEXTS = [
    (30, 40, "SERVO: on-board 2x BTN8982TA half-bridge (BTS7960-compatible interface), VM = +12V rail"),
    (30, 46, "AS5600 (in servo housing per vanchor-ng cad/) cabled to J11; keep lead <1m, 100kHz"),
    (30, 52, "24-48V boats: servo stall limited by BUCK2 (4.5A). 12V boats: J17 links VIN->12V, full stall current"),
]

COMPONENTS = [
    dict(lib="vanchor-helm:BTN8982TA", ref="U7", value="BTN8982TA",
         fp="Package_TO_SOT_SMD:TO-263-7_TabPin4",
         at=(70, 100, 0), pins={
            "1": "GND", "2": "RPWM", "3": "R_EN",
            "4": "SERVO_A", "5": ".SR_A", "6": ".SERVO_IS_RAW", "7": "+12V"}),
    dict(lib="vanchor-helm:BTN8982TA", ref="U8", value="BTN8982TA",
         fp="Package_TO_SOT_SMD:TO-263-7_TabPin4",
         at=(130, 100, 0), pins={
            "1": "GND", "2": "LPWM", "3": "L_EN",
            "4": "SERVO_B", "5": ".SR_B", "6": ".SERVO_IS_RAW", "7": "+12V"}),
    dict(lib="Device:R", ref="R39", value="51k", fp=R_AX,     # slew-rate set
         at=grid(0), pins={"1": ".SR_A", "2": "GND"}),
    dict(lib="Device:R", ref="R40", value="51k", fp=R_AX,
         at=grid(1), pins={"1": ".SR_B", "2": "GND"}),
    dict(lib="Device:C_Polarized", ref="C22", value="220u/25V",
         fp="Capacitor_THT:CP_Radial_D8.0mm_P3.50mm",
         at=grid(2), pins={"1": "+12V", "2": "GND"}),
    dict(lib="Device:C", ref="C23", value="100n", fp=C_D,
         at=grid(3), pins={"1": "+12V", "2": "GND"}),
    dict(lib="Connector_Generic:Conn_01x02", ref="J22", value="SERVO MOTOR", fp=TB2,
         at=(200, 100, 0), pins={"1": "SERVO_A", "2": "SERVO_B"}),

    # combined current sense: IS pins -> 1k to GND, filtered + clamped to ADC
    dict(lib="Device:R", ref="R19", value="1k", fp=R_AX,
         at=grid(4), pins={"1": ".SERVO_IS_RAW", "2": "GND"}),
    dict(lib="Device:R", ref="R18", value="10k", fp=R_AX,
         at=grid(5), pins={"1": ".SERVO_IS_RAW", "2": "SERVO_IS"}),
    dict(lib="Diode:BAT54S", ref="D8", value="BAT54S", fp=SOT23,
         at=grid(6), pins={"1": "GND", "2": "+3V3", "3": "SERVO_IS"}),
    dict(lib="Device:C", ref="C12", value="100n", fp=C_D,
         at=grid(7), pins={"1": "SERVO_IS", "2": "GND"}),

    # AS5600 encoder connector (unchanged)
    dict(lib="Device:R", ref="R20", value="100R", fp=R_AX,
         at=grid(8), pins={"1": "ENC_SDA", "2": ".ENC_SDA_J"}),
    dict(lib="Device:R", ref="R21", value="100R", fp=R_AX,
         at=grid(9), pins={"1": "ENC_SCL", "2": ".ENC_SCL_J"}),
    dict(lib="Diode:BAT54S", ref="D10", value="BAT54S", fp=SOT23,
         at=grid(10), pins={"1": "GND", "2": "+3V3", "3": ".ENC_SDA_J"}),
    dict(lib="Diode:BAT54S", ref="D11", value="BAT54S", fp=SOT23,
         at=grid(11), pins={"1": "GND", "2": "+3V3", "3": ".ENC_SCL_J"}),
    dict(lib="Connector_Generic:Conn_01x04", ref="J11", value="AS5600", fp=XH4,
         at=(200, 140, 0), pins={"1": "+3V3", "2": "GND", "3": ".ENC_SDA_J", "4": ".ENC_SCL_J"}),
]
