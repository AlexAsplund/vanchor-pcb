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
         at=(60, 100, 0), pins={
            "1": "RPWM", "2": "LPWM", "3": "R_EN", "4": "L_EN",
            "5": "R_IS", "6": "L_IS", "7": "+5V", "8": "GND"}),
    dict(lib="Device:R", ref="R1", value="100k", fp=R_AX,
         at=grid(0), pins={"1": "R_EN", "2": "GND"}),
    dict(lib="Device:R", ref="R2", value="100k", fp=R_AX,
         at=grid(1), pins={"1": "L_EN", "2": "GND"}),

    # base bridge
    dict(lib="vanchor-helm:BTN8982TA", ref="U1", value="BTN8982TA", fp=TO263_7,
         at=(140, 90, 0), pins={"1": "GND", "2": "RPWM", "3": "R_EN",
                                "4": "MOT_A", "5": ".SR1", "6": "R_IS", "7": "VBAT"}),
    dict(lib="vanchor-helm:BTN8982TA", ref="U2", value="BTN8982TA", fp=TO263_7,
         at=(140, 150, 0), pins={"1": "GND", "2": "LPWM", "3": "L_EN",
                                 "4": "MOT_B", "5": ".SR2", "6": "L_IS", "7": "VBAT"}),
    dict(lib="Device:R", ref="R3", value="51k", fp=R_AX,
         at=grid(2), pins={"1": ".SR1", "2": "GND"}),
    dict(lib="Device:R", ref="R4", value="51k", fp=R_AX,
         at=grid(3), pins={"1": ".SR2", "2": "GND"}),

    # high-power parallel pair (DNP on base builds)
    dict(lib="vanchor-helm:BTN8982TA", ref="U3", value="BTN8982TA", fp=TO263_7, dnp=True,
         at=(230, 90, 0), pins={"1": "GND", "2": "RPWM", "3": "R_EN",
                                "4": "MOT_A", "5": ".SR3", "6": "R_IS", "7": "VBAT"}),
    dict(lib="vanchor-helm:BTN8982TA", ref="U4", value="BTN8982TA", fp=TO263_7, dnp=True,
         at=(230, 150, 0), pins={"1": "GND", "2": "LPWM", "3": "L_EN",
                                 "4": "MOT_B", "5": ".SR4", "6": "L_IS", "7": "VBAT"}),
    dict(lib="Device:R", ref="R7", value="51k", fp=R_AX, dnp=True,
         at=grid(4), pins={"1": ".SR3", "2": "GND"}),
    dict(lib="Device:R", ref="R8", value="51k", fp=R_AX, dnp=True,
         at=grid(5), pins={"1": ".SR4", "2": "GND"}),

    # IS loads: current-source outputs develop the sense voltage here
    dict(lib="Device:R", ref="R5", value="1k", fp=R_AX,
         at=grid(6), pins={"1": "R_IS", "2": "GND"}),
    dict(lib="Device:R", ref="R6", value="1k", fp=R_AX,
         at=grid(7), pins={"1": "L_IS", "2": "GND"}),

    # power conditioning
    dict(lib="Device:D_TVS", ref="D2", value="SMCJ33A", fp=SMC,
         at=grid(8), pins={"1": "VBAT", "2": "GND"}),
    dict(lib="Device:C_Polarized", ref="C1", value="2200u/35V", fp=CP_BULK,
         at=grid(9), pins={"1": "VBAT", "2": "GND"}),
    dict(lib="Device:C_Polarized", ref="C2", value="2200u/35V", fp=CP_BULK,
         at=grid(10), pins={"1": "VBAT", "2": "GND"}),
    dict(lib="Device:C", ref="C3", value="100n", fp=C_D,
         at=grid(11), pins={"1": "VBAT", "2": "GND"}),
    dict(lib="Device:C", ref="C4", value="100n", fp=C_D,
         at=grid(12), pins={"1": "VBAT", "2": "GND"}),
    dict(lib="Device:C", ref="C5", value="1u/100V film", fp=FILM,
         at=grid(13), pins={"1": "VBAT", "2": "GND"}),

    # cable-live indicator off the helm's 5V
    dict(lib="Device:R", ref="R9", value="1k", fp=R_AX,
         at=grid(14), pins={"1": "+5V", "2": ".LED_A"}),
    dict(lib="Device:LED", ref="D1", value="green", fp=LED5MM,
         at=grid(15), pins={"2": ".LED_A", "1": "GND"}),

    # ---- NMEA2000 node provision (ALL DNP: holes only, populate later) ----
    # Smart-node mode: fit U5 (Pico 2), U6 (TSR-1/R-78E5.0 SIP-3 regulator),
    # R12/R13 (1k ADC series) and a 3.3V CAN transceiver on J6; the node then
    # self-powers from VBAT and takes commands over NMEA2000 (can2040 on
    # GP18/GP19). Leave J1 unconnected in that mode. Dumb mode: leave all of
    # this unpopulated and drive via J1 as today. Same GPIO map as the helm
    # Pico: GP12-15 drive, GP26/27 sense, GP18/19 CAN.
    dict(lib="MCU_Module:RaspberryPi_Pico_Debug", ref="U5", value="Pico 2 (DNP)", dnp=True,
         fp="vanchor-helm:RaspberryPi_Pico_TH_SWD",
         at=(140, 210, 0), pins={
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
         at=(240, 200, 0), pins={"1": "VBAT", "2": "GND", "3": "+5V"}),
    dict(lib="Connector_Generic:Conn_01x04", ref="J6", value="CAN XCVR 3V3", fp=HDR1x8.replace("1x08", "1x04"),
         at=(280, 200, 0), pins={"1": "+3V3", "2": "GND", "3": "CAN_TX", "4": "CAN_RX"}),
    dict(lib="Connector_Generic:Conn_01x03", ref="J7", value="NMEA2000 PWR",
         fp="Connector_JST:JST_XH_B3B-XH-A_1x03_P2.50mm_Vertical",
         at=(320, 200, 0), pins={"1": "N2K_VP", "2": "GND", "3": "N2K_SHLD"}),
    dict(lib="Device:R", ref="R10", value="0R DNP", dnp=True,
         fp="Resistor_SMD:R_0805_2012Metric",
         at=(240, 240, 0), pins={"1": "N2K_VP", "2": "VBAT"}),
    dict(lib="Device:R", ref="R11", value="0R DNP", dnp=True,
         fp="Resistor_SMD:R_0805_2012Metric",
         at=(260, 240, 0), pins={"1": "N2K_SHLD", "2": "GND"}),
    dict(lib="Device:R", ref="R12", value="1k DNP", dnp=True,
         fp="Resistor_SMD:R_0805_2012Metric",
         at=(280, 240, 0), pins={"1": "R_IS", "2": "R_ADC"}),
    dict(lib="Device:R", ref="R13", value="1k DNP", dnp=True,
         fp="Resistor_SMD:R_0805_2012Metric",
         at=(300, 240, 0), pins={"1": "L_IS", "2": "L_ADC"}),

    # power lugs
    dict(lib="Connector_Generic:Conn_01x01", ref="J2", value="LUG BATT+", fp=LUG,
         at=(320, 90, 0), pins={"1": "VBAT"}),
    dict(lib="Connector_Generic:Conn_01x01", ref="J3", value="LUG BATT-", fp=LUG,
         at=(320, 120, 0), pins={"1": "GND"}),
    dict(lib="Connector_Generic:Conn_01x01", ref="J4", value="LUG MOT A", fp=LUG,
         at=(320, 150, 0), pins={"1": "MOT_A"}),
    dict(lib="Connector_Generic:Conn_01x01", ref="J5", value="LUG MOT B", fp=LUG,
         at=(320, 180, 0), pins={"1": "MOT_B"}),

    dict(lib="power:PWR_FLAG", ref="#FLG01", value="PWR_FLAG",
         at=grid(16), pins={"1": "VBAT"}),
    dict(lib="power:PWR_FLAG", ref="#FLG02", value="PWR_FLAG",
         at=grid(17), pins={"1": "GND"}),
    dict(lib="power:PWR_FLAG", ref="#FLG03", value="PWR_FLAG",
         at=grid(18), pins={"1": "+5V"}),
]
