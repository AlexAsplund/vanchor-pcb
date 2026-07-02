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
    (30, 40, "POWER: 12V battery in, protection, XL4015 5V buck on-board (U5)"),
    (30, 46, "U5: XL4015 module soldered on via pins + spacers; set 5.1V BEFORE fitting"),
    (30, 52, "Servo bridge runs on protected VIN directly (12V-only board)"),
]

COMPONENTS = [
    # NMEA2000 provision: CAN itself rides the Pico (can2040 on GP18/GP19,
    # transceiver module on J12 pins 1/8/6/7). J5 lands the drop cable's
    # power/shield conductors; CAN_H/L go to the module's screw terminals.
    # R41 (0R, DNP): fit to power the N2K backbone from VIN — add an inline
    # 2-3A fuse in the drop cable if you do. R42 (0R, DNP): shield-to-GND
    # at this node only if the network isn't grounded elsewhere.
    dict(lib="Connector_Generic:Conn_01x03", ref="J5", value="NMEA2000 PWR",
         fp="Connector_JST:JST_XH_B3B-XH-A_1x03_P2.50mm_Vertical",
         at=(40, 185, 0), pins={"1": "N2K_VP", "2": "GND", "3": "N2K_SHLD"}),
    dict(lib="Device:R", ref="R41", value="0R DNP", dnp=True,
         fp="Resistor_SMD:R_0805_2012Metric",
         at=(70, 185, 0), pins={"1": "N2K_VP", "2": "VIN"}),
    dict(lib="Device:R", ref="R42", value="0R DNP", dnp=True,
         fp="Resistor_SMD:R_0805_2012Metric",
         at=(90, 185, 0), pins={"1": "N2K_SHLD", "2": "GND"}),

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

    # XL4015 buck module soldered on as a daughterboard (pins + spacers)
    dict(lib="Connector_Generic:Conn_01x04", ref="U5", value="XL4015 5A", fp="vanchor-helm:XL4015_Module",
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
