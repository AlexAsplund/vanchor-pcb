"""Power entry sheet: battery input, protection, 5V/12V rails, indicators.

Implements spec §4.1 / plan power table:
BATT 12-48V -> fuse -> reverse-polarity P-FET -> TVS+bulk -> BUCK1 (5V) and
BUCK2 (12V, DNP on 12V boats where J17 screw link bridges VIN->12V instead).
"""
from common import (TB2, FUSE_BLADE, TO220, R_AX, DO41, SMC, CP_L, CP_S,
                    LED5MM, POLOLU_FP, grid)

SHEET_UUID = "c0000000-0000-4000-8000-000000000002"

TEXTS = [
    (30, 40, "POWER: 12-48V battery in, protection, 5V/5A + 12V/4.5A rails"),
    (30, 46, "12V-battery boats: omit U6 (DNP) and bridge J17 with a wire link"),
]

COMPONENTS = [
    dict(lib="Connector_Generic:Conn_01x02", ref="J16", value="BATT_12-48V", fp=TB2,
         at=(40, 70, 0), pins={"1": ".BATT_IN", "2": "GND"}),
    dict(lib="Device:Fuse", ref="F1", value="10A blade", fp=FUSE_BLADE,
         at=(70, 70, 0), pins={"1": ".BATT_IN", "2": ".VIN_RAW"}),
    dict(lib="Transistor_FET:IRF9540N", ref="Q1", value="IRF9540N", fp=TO220,
         at=(105, 70, 0), pins={"1": ".Q1_G", "2": ".VIN_RAW", "3": "VIN"}),
    dict(lib="Device:R", ref="R1", value="47k", fp=R_AX,
         at=(140, 70, 0), pins={"1": ".Q1_G", "2": "GND"}),
    dict(lib="Device:D_Zener", ref="D4", value="BZX85C12", fp=DO41,
         at=(170, 70, 0), pins={"1": "VIN", "2": ".Q1_G"}),
    dict(lib="Device:D_TVS", ref="D5", value="SMCJ58A", fp=SMC,
         at=(200, 70, 0), pins={"1": "VIN", "2": "GND"}),
    dict(lib="Device:C_Polarized", ref="C1", value="470u/63V", fp=CP_L,
         at=(230, 70, 0), pins={"1": "VIN", "2": "GND"}),
    dict(lib="Device:C_Polarized", ref="C2", value="470u/63V", fp=CP_L,
         at=(260, 70, 0), pins={"1": "VIN", "2": "GND"}),

    dict(lib="vanchor-helm:D36V50Fx", ref="U5", value="D36V50F5", fp=POLOLU_FP,
         at=(70, 120, 0), pins={"1": "VIN", "2": "GND", "3": "+5V",
                                "4": None, "5": None, "6": None}),
    dict(lib="vanchor-helm:D36V50Fx", ref="U6", value="D36V50F12", fp=POLOLU_FP,
         at=(140, 120, 0), pins={"1": "VIN", "2": "GND", "3": "+12V",
                                 "4": None, "5": None, "6": None}),
    dict(lib="Connector_Generic:Conn_01x02", ref="J17", value="12V_LINK", fp=TB2,
         at=(200, 120, 0), pins={"1": "VIN", "2": "+12V"}),
    dict(lib="Device:C_Polarized", ref="C3", value="100u",
         fp="Capacitor_THT:CP_Radial_D6.3mm_P2.50mm",
         at=(240, 120, 0), pins={"1": "+5V", "2": "GND"}),
    dict(lib="Device:C_Polarized", ref="C4", value="100u/25V",
         fp="Capacitor_THT:CP_Radial_D6.3mm_P2.50mm",
         at=(270, 120, 0), pins={"1": "+12V", "2": "GND"}),

    dict(lib="Device:R", ref="R2", value="15k/0.5W", fp=R_AX,
         at=grid(0), pins={"1": "VIN", "2": ".LED1_A"}),
    dict(lib="Device:LED", ref="LED1", value="green", fp=LED5MM,
         at=grid(1), pins={"2": ".LED1_A", "1": "GND"}),
    dict(lib="Device:R", ref="R3", value="1k", fp=R_AX,
         at=grid(2), pins={"1": "+5V", "2": ".LED2_A"}),
    dict(lib="Device:LED", ref="LED2", value="green", fp=LED5MM,
         at=grid(3), pins={"2": ".LED2_A", "1": "GND"}),
    dict(lib="Device:R", ref="R4", value="4.7k", fp=R_AX,
         at=grid(4), pins={"1": "+12V", "2": ".LED3_A"}),
    dict(lib="Device:LED", ref="LED3", value="green", fp=LED5MM,
         at=grid(5), pins={"2": ".LED3_A", "1": "GND"}),

    dict(lib="power:PWR_FLAG", ref="#FLG01", value="PWR_FLAG",
         at=grid(6), pins={"1": "VIN"}),
    dict(lib="power:PWR_FLAG", ref="#FLG02", value="PWR_FLAG",
         at=grid(7), pins={"1": "GND"}),
    # +12V needs no flag: U6 VOUT (power_out) drives it, and with U6 DNP the
    # net has no power_in pins at all (contactor coil + module leave via J14/J15).
]
