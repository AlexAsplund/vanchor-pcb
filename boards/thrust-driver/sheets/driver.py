"""Thrust driver board: 12-24V full-bridge for the trolling motor.

One sheet. J1 mirrors the helm board's J13 pin-for-pin (IBT-2 order), so a
straight 8-wire cable connects them. U1/U2 = base bridge (~30A cont);
U3/U4 + their SR resistors = DNP parallel pair for the high-power build
(fit for ~50A sustained; both pairs share IN/INH, each device has its own
slew-rate resistor; IS current sources sum into the shared 1k loads so the
helm's telemetry scaling is unchanged per-variant... halved kILIS effective
- note in firmware calibration).
"""
from common import R_AX, C_D, CP_BULK, SMC, TO263_7, HDR1x8, LED5MM, LUG, FILM, grid

SHEET_UUID = "d0000000-0000-4000-8000-000000000002"

TEXTS = [
    (30, 30, "THRUST DRIVER: 12-24V trolling-motor full bridge, controlled by helm J13 (1:1 cable)"),
    (30, 38, "Base build: U1+U2 (~30A cont). High power: also fit U3/U4 + R7/R8 (~50A)"),
    (30, 46, "Reinforce power lanes by soldering copper cable/braid onto the exposed solder lanes"),
]

COMPONENTS = [
    # control interface - identical pinout to helm J13
    dict(lib="Connector_Generic:Conn_01x08", ref="J1", value="HELM J13 1:1", fp=HDR1x8,
         at=(45, 95, 0), pins={
            "1": "RPWM", "2": "LPWM", "3": "R_EN", "4": "L_EN",
            "5": "R_IS", "6": "L_IS", "7": "+5V", "8": "GND"}),
    dict(lib="Device:R", ref="R1", value="100k", fp=R_AX,
         at=(130, 195, 90), pins={"1": "R_EN", "2": "GND"}),
    dict(lib="Device:R", ref="R2", value="100k", fp=R_AX,
         at=(174, 195, 90), pins={"1": "L_EN", "2": "GND"}),

    # base bridge
    dict(lib="vanchor-helm:BTN8982TA", ref="U1", value="BTN8982TA", fp=TO263_7,
         at=(135, 80, 0), pins={"1": "GND", "2": "RPWM", "3": "R_EN",
                                "4": "MOT_A", "5": ".SR1", "6": "R_IS", "7": "VBAT"}),
    dict(lib="vanchor-helm:BTN8982TA", ref="U2", value="BTN8982TA", fp=TO263_7,
         at=(135, 150, 0), pins={"1": "GND", "2": "LPWM", "3": "L_EN",
                                 "4": "MOT_B", "5": ".SR2", "6": "L_IS", "7": "VBAT"}),
    dict(lib="Device:R", ref="R3", value="51k", fp=R_AX,
         at=(218, 195, 90), pins={"1": ".SR1", "2": "GND"}),
    dict(lib="Device:R", ref="R4", value="51k", fp=R_AX,
         at=(262, 195, 90), pins={"1": ".SR2", "2": "GND"}),

    # high-power parallel pair (DNP on base builds)
    dict(lib="vanchor-helm:BTN8982TA", ref="U3", value="BTN8982TA", fp=TO263_7, dnp=True,
         at=(225, 80, 0), pins={"1": "GND", "2": "RPWM", "3": "R_EN",
                                "4": "MOT_A", "5": ".SR3", "6": "R_IS", "7": "VBAT"}),
    dict(lib="vanchor-helm:BTN8982TA", ref="U4", value="BTN8982TA", fp=TO263_7, dnp=True,
         at=(225, 150, 0), pins={"1": "GND", "2": "LPWM", "3": "L_EN",
                                 "4": "MOT_B", "5": ".SR4", "6": "L_IS", "7": "VBAT"}),
    dict(lib="Device:R", ref="R7", value="51k", fp=R_AX, dnp=True,
         at=(306, 195, 90), pins={"1": ".SR3", "2": "GND"}),
    dict(lib="Device:R", ref="R8", value="51k", fp=R_AX, dnp=True,
         at=(130, 220, 90), pins={"1": ".SR4", "2": "GND"}),

    # IS loads: current-source outputs develop the sense voltage here
    dict(lib="Device:R", ref="R5", value="1k", fp=R_AX,
         at=(174, 220, 90), pins={"1": "R_IS", "2": "GND"}),
    dict(lib="Device:R", ref="R6", value="1k", fp=R_AX,
         at=(218, 220, 90), pins={"1": "L_IS", "2": "GND"}),

    # power conditioning
    dict(lib="Device:D_TVS", ref="D2", value="SMCJ33A", fp=SMC,
         at=(322, 190, 0), pins={"1": "VBAT", "2": "GND"}),
    dict(lib="Device:C_Polarized", ref="C1", value="2200u/35V", fp=CP_BULK,
         at=(218, 245, 90), pins={"1": "VBAT", "2": "GND"}),
    dict(lib="Device:C_Polarized", ref="C2", value="2200u/35V", fp=CP_BULK,
         at=(258, 245, 90), pins={"1": "VBAT", "2": "GND"}),
    dict(lib="Device:C", ref="C3", value="100n", fp=C_D,
         at=(262, 220, 90), pins={"1": "VBAT", "2": "GND"}),
    dict(lib="Device:C", ref="C4", value="100n", fp=C_D,
         at=(306, 220, 90), pins={"1": "VBAT", "2": "GND"}),
    dict(lib="Device:C", ref="C5", value="1u/100V film", fp=FILM,
         at=(130, 245, 90), pins={"1": "VBAT", "2": "GND"}),

    # cable-live indicator off the helm's 5V
    dict(lib="Device:R", ref="R9", value="1k", fp=R_AX,
         at=(174, 245, 90), pins={"1": "+5V", "2": ".LED_A"}),
    dict(lib="Device:LED", ref="D1", value="green", fp=LED5MM,
         at=(374, 168, 0), pins={"2": ".LED_A", "1": "GND"}),

    # ---- NMEA2000 node provision (ALL DNP: holes only, populate later) ----
    # Smart-node mode: fit U5 (Pico 2), U6 (TSR-1/R-78E5.0 SIP-3 regulator),
    # R12/R13 (1k ADC series) and a 3.3V CAN transceiver on J6; the node then
    # self-powers from VBAT and takes commands over NMEA2000 (can2040 on
    # GP18/GP19). Leave J1 unconnected in that mode. Dumb mode: leave all of
    # this unpopulated and drive via J1 as today. Same GPIO map as the helm
    # Pico: GP12-15 drive, GP26/27 sense, GP18/19 CAN.
    dict(lib="MCU_Module:RaspberryPi_Pico_Debug", ref="U5", value="Pico 2 (DNP)", dnp=True,
         fp="vanchor-helm:RaspberryPi_Pico_TH_SWD",
         at=(70, 238, 0), pins={
            "3": "GND", "8": "GND", "13": "GND", "18": "GND", "23": "GND",
            "28": "GND", "33": "GND", "38": "GND",
            "16": "RPWM", "17": "LPWM", "19": "R_EN", "20": "L_EN",
            "24": "CAN_TX", "25": "CAN_RX",
            "31": "L_ADC", "32": "R_ADC",
            "36": "+3V3", "39": "+5V",
            **{str(n): None for n in (1, 2, 4, 5, 6, 7, 9, 10, 11, 12, 14, 15,
                                      21, 22, 26, 27, 29, 30, 34, 35, 37, 40)},
            "D1": None, "D2": None, "D3": None}),
    dict(lib="Converter_DCDC:TSR_1-2450", ref="U6", value="R-78E5.0-0.5 (DNP)", dnp=True,
         fp="Converter_DCDC:Converter_DCDC_TRACO_TSR-1_THT",
         at=(374, 195, 0), pins={"1": "VBAT", "2": "GND", "3": "+5V"}),
    dict(lib="Connector_Generic:Conn_01x04", ref="J6", value="CAN XCVR 3V3", fp=HDR1x8.replace("1x08", "1x04"),
         at=(330, 222, 0), pins={"1": "+3V3", "2": "GND", "3": "CAN_TX", "4": "CAN_RX"}),
    dict(lib="Connector_Generic:Conn_01x03", ref="J7", value="NMEA2000 PWR",
         fp="Connector_JST:JST_XH_B3B-XH-A_1x03_P2.50mm_Vertical",
         at=(374, 222, 0), pins={"1": "N2K_VP", "2": "GND", "3": "N2K_SHLD"}),
    dict(lib="Device:R", ref="R10", value="0R DNP", dnp=True,
         fp="Resistor_SMD:R_0805_2012Metric",
         at=(130, 267, 90), pins={"1": "N2K_VP", "2": "VBAT"}),
    dict(lib="Device:R", ref="R11", value="0R DNP", dnp=True,
         fp="Resistor_SMD:R_0805_2012Metric",
         at=(172, 267, 90), pins={"1": "N2K_SHLD", "2": "GND"}),
    dict(lib="Device:R", ref="R12", value="1k DNP", dnp=True,
         fp="Resistor_SMD:R_0805_2012Metric",
         at=(214, 267, 90), pins={"1": "R_IS", "2": "R_ADC"}),
    dict(lib="Device:R", ref="R13", value="1k DNP", dnp=True,
         fp="Resistor_SMD:R_0805_2012Metric",
         at=(254, 267, 90), pins={"1": "L_IS", "2": "L_ADC"}),

    # power lugs
    dict(lib="Connector_Generic:Conn_01x01", ref="J2", value="LUG BATT+", fp=LUG,
         at=(330, 75, 0), pins={"1": "VBAT"}),
    dict(lib="Connector_Generic:Conn_01x01", ref="J3", value="LUG BATT-", fp=LUG,
         at=(330, 105, 0), pins={"1": "GND"}),
    dict(lib="Connector_Generic:Conn_01x01", ref="J4", value="LUG MOT A", fp=LUG,
         at=(330, 135, 0), pins={"1": "MOT_A"}),
    dict(lib="Connector_Generic:Conn_01x01", ref="J5", value="LUG MOT B", fp=LUG,
         at=(330, 165, 0), pins={"1": "MOT_B"}),

    dict(lib="power:PWR_FLAG", ref="#FLG01", value="PWR_FLAG",
         at=(330, 42, 0), pins={"1": "VBAT"}),
    dict(lib="power:PWR_FLAG", ref="#FLG02", value="PWR_FLAG",
         at=(352, 42, 0), pins={"1": "GND"}),
    dict(lib="power:PWR_FLAG", ref="#FLG03", value="PWR_FLAG",
         at=(374, 42, 0), pins={"1": "+5V"}),
]

WIRES = [
    # DNP Pico smart-node hookup: CAN pair to the transceiver header,
    # IS sense through the 1k series resistors to the ADCs
    (("U5", "24"), ("J6", "3"), [("x", 106.68), ("y", 280.67), ("x", 283.21), ("y", 223.27)]),
    (("U5", "25"), ("J6", "4"), [("x", 104.14), ("y", 283.21), ("x", 287.02), ("y", 225.81)]),
    (("U5", "31"), ("R13", "2"), [("x", 111.76), ("y", 262.89)]),
    (("U5", "32"), ("R12", "2"), [("x", 109.22), ("y", 264.16)]),
]
