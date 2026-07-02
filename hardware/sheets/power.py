"""Power entry sheet: 12V battery input, protection, 5V rail (v3.1).

12V-ONLY revision (external thrust driver removed the 48V requirement):
BATT 12V (14.4V charging) -> fuse -> reverse-polarity P-FET -> TVS+bulk ->
J14 header for a generic cheap 5V buck module (XL4015/LM2596-class, mounted
beside it). The servo bridge runs straight off protected VIN — no 12V buck,
no link jumper.
"""
from common import (TB2, FUSE_BLADE, TO220, R_AX, DO41, SMC, CP_L, CP_S,
                    LED5MM, HDR1x4, grid)

SHEET_UUID = "c0000000-0000-4000-8000-000000000002"

TEXTS = [
    (30, 40, "POWER: 12V battery in, protection, generic 5V buck on J14"),
    (30, 46, "J14: VIN GND 5V GND - wire to an XL4015/LM2596-class module, set 5.1V BEFORE fitting"),
    (30, 52, "Servo bridge runs on protected VIN directly (12V-only board)"),
]

COMPONENTS = [
    # Logic feed: its own small terminal, wired externally to the BATT+ lug
    # (or a separate house battery). Keeps the 67A pour region free of a
    # logic trace and keeps board draw out of the ACS758 reading.
    dict(lib="Connector_Generic:Conn_01x02", ref="J16", value="BATT 12V", fp=TB2,
         at=(40, 70, 0), pins={"1": ".BATT_IN", "2": "GND"}),
    dict(lib="Device:Fuse", ref="F1", value="10A blade", fp=FUSE_BLADE,
         at=(70, 70, 0), pins={"1": ".BATT_IN", "2": ".VIN_RAW"}),
    dict(lib="Transistor_FET:IRF9540N", ref="Q1", value="IRF9540N", fp=TO220,
         at=(105, 70, 0), pins={"1": ".Q1_G", "2": ".VIN_RAW", "3": "VIN"}),
    dict(lib="Device:R", ref="R1", value="47k", fp=R_AX,
         at=(140, 70, 0), pins={"1": ".Q1_G", "2": "GND"}),
    dict(lib="Device:D_Zener", ref="D4", value="BZX85C12", fp=DO41,
         at=(170, 70, 0), pins={"1": "VIN", "2": ".Q1_G"}),
    dict(lib="Device:D_TVS", ref="D5", value="SMCJ18A", fp=SMC,
         at=(200, 70, 0), pins={"1": "VIN", "2": "GND"}),
    dict(lib="Device:C_Polarized", ref="C1", value="470u/25V", fp=CP_L,
         at=(230, 70, 0), pins={"1": "VIN", "2": "GND"}),
    dict(lib="Device:C_Polarized", ref="C2", value="470u/25V", fp=CP_L,
         at=(260, 70, 0), pins={"1": "VIN", "2": "GND"}),

    # generic 5V buck module lands here (wires or header pins)
    dict(lib="Connector_Generic:Conn_01x04", ref="J14", value="BUCK 5V", fp=HDR1x4,
         at=(70, 120, 0), pins={"1": "VIN", "2": "GND", "3": "+5V", "4": "GND"}),
    dict(lib="Device:C_Polarized", ref="C3", value="100u",
         fp="Capacitor_THT:CP_Radial_D6.3mm_P2.50mm",
         at=(240, 120, 0), pins={"1": "+5V", "2": "GND"}),

    dict(lib="Device:R", ref="R2", value="2.2k", fp=R_AX,
         at=grid(0), pins={"1": "VIN", "2": ".LED1_A"}),
    dict(lib="Device:LED", ref="LED1", value="green", fp=LED5MM,
         at=grid(1), pins={"2": ".LED1_A", "1": "GND"}),

    dict(lib="power:PWR_FLAG", ref="#FLG01", value="PWR_FLAG",
         at=grid(6), pins={"1": "VIN"}),
    dict(lib="power:PWR_FLAG", ref="#FLG02", value="PWR_FLAG",
         at=grid(7), pins={"1": "GND"}),
    dict(lib="power:PWR_FLAG", ref="#FLG03", value="PWR_FLAG",
         at=grid(8), pins={"1": "+5V"}),
    # +5V needs a flag now: it enters via connector J14 (no power_out pin).
]
