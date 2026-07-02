"""Thrust sheet: interface header for an EXTERNAL thrust driver (pass 10).

The on-board 800W H-bridge was removed in cost pass 10 — the user already
owns a suitable external driver (IBT-2 / BTS7960-class). J13 carries the
standard 8-pin control interface; battery and motor power never touch this
board. Pico drives RPWM/LPWM/R_EN/L_EN at 3.3V (VIH ~2.5V on BTS7960-class
inputs); 100k pull-downs keep the driver disabled whenever the Pico is
absent or in reset. The driver's R_IS/L_IS current-sense outputs are mixed
through 1k each into THR_IS with a 20k load, RC filter and BAT54S clamp
ahead of the Pico ADC.
"""
from common import R_AX, C_D, SOT23, HDR1x8, grid

SHEET_UUID = "c0000000-0000-4000-8000-000000000005"

TEXTS = [
    (30, 40, "THRUST: control header for external driver (IBT-2 / BTS7960-class)"),
    (30, 46, "J13 pinout matches the common IBT-2 module: RPWM LPWM R_EN L_EN R_IS L_IS VCC GND"),
    (30, 52, "Driver held disabled by 100k pull-downs unless the Pico actively enables it"),
    (30, 58, "Battery/motor power stays on the external driver - only logic on this board"),
]

COMPONENTS = [
    dict(lib="Connector_Generic:Conn_01x08", ref="J13", value="THRUST DRV", fp=HDR1x8,
         at=(70, 100, 0), pins={
            "1": "THR_RPWM", "2": "THR_LPWM",
            "3": "THR_R_EN", "4": "THR_L_EN",
            "5": ".R_IS", "6": ".L_IS",
            "7": "+5V", "8": "GND"}),

    # enable pull-downs: driver dead unless Pico drives EN high
    dict(lib="Device:R", ref="R30", value="100k", fp=R_AX,
         at=grid(0), pins={"1": "THR_R_EN", "2": "GND"}),
    dict(lib="Device:R", ref="R32", value="100k", fp=R_AX,
         at=grid(1), pins={"1": "THR_L_EN", "2": "GND"}),

    # IS mix -> THR_IS -> Pico ADC (GP27)
    dict(lib="Device:R", ref="R15", value="1k", fp=R_AX,
         at=grid(2), pins={"1": ".R_IS", "2": "THR_IS"}),
    dict(lib="Device:R", ref="R16", value="1k", fp=R_AX,
         at=grid(3), pins={"1": ".L_IS", "2": "THR_IS"}),
    dict(lib="Device:R", ref="R38", value="20k", fp=R_AX,
         at=grid(4), pins={"1": "THR_IS", "2": "GND"}),
    dict(lib="Device:C", ref="C21", value="100n", fp=C_D,
         at=grid(5), pins={"1": "THR_IS", "2": "GND"}),
    dict(lib="Diode:BAT54S", ref="D14", value="BAT54S", fp=SOT23,
         at=grid(6), pins={"1": "GND", "2": "+3V3", "3": "THR_IS"}),
]
