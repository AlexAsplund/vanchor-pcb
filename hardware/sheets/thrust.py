"""Thrust interface sheet: X9C103 digipot knob-hijack of the external 1500W
speed controller + PWM-DAC alternative (JP1 selects), reversing contactor
driver. 74AHCT125 level-shifts the Pico's 3.3V to 5V for the X9C (VIH 3.5V).
"""
from common import DIP8, DIP14, R_AX, C_D, CP_S, TO220, DO41, TB2, TB3, SJ3, grid

SHEET_UUID = "c0000000-0000-4000-8000-000000000005"

TEXTS = [
    (30, 40, "THRUST: digipot hijack of external 12-48V/1500W controller (J13 replaces its 10k knob)"),
    (30, 46, "JP1: pad1-2 = digipot wiper (knob-type controllers), pad2-3 = buffered 0-5V PWM-DAC"),
    (30, 52, "J14: reversing DPDT contactor coil, 12V. Firmware switches at zero throttle only."),
]

COMPONENTS = [
    dict(lib="vanchor-helm:74AHCT125_flat", ref="U2", value="74AHCT125", fp=DIP14,
         at=(70, 100, 0), pins={
            "1": "GND", "2": "DP_INC_3", "3": "DP_INC_5",
            "4": "GND", "5": "DP_UD_3", "6": "DP_UD_5",
            "7": "GND", "8": "DP_CS_5", "9": "DP_CS_3", "10": "GND",
            "11": "THR_PWM_5", "12": "THR_PWM_3", "13": "GND", "14": "+5V"}),
    dict(lib="Device:C", ref="C6", value="100n", fp=C_D,
         at=grid(0), pins={"1": "+5V", "2": "GND"}),

    dict(lib="vanchor-helm:X9C103", ref="U3", value="X9C103", fp=DIP8,
         at=(140, 100, 0), pins={
            "1": "DP_INC_5", "2": "DP_UD_5", "3": ".KNOB_HI", "4": "GND",
            "5": ".DP_WIPER", "6": ".KNOB_LO", "7": "DP_CS_5", "8": "+5V"}),
    dict(lib="Device:C", ref="C7", value="100n", fp=C_D,
         at=grid(1), pins={"1": "+5V", "2": "GND"}),
    dict(lib="Device:R", ref="R14", value="10k", fp=R_AX,
         at=grid(2), pins={"1": "+5V", "2": "DP_CS_5"}),

    # PWM-DAC: 5V PWM -> RC -> unity buffer
    dict(lib="Device:R", ref="R15", value="1k", fp=R_AX,
         at=grid(3), pins={"1": "THR_PWM_5", "2": ".THR_ANA"}),
    dict(lib="Device:C_Polarized", ref="C8", value="10u", fp=CP_S,
         at=grid(4), pins={"1": ".THR_ANA", "2": "GND"}),
    dict(lib="vanchor-helm:MCP6002_flat", ref="U4", value="MCP6002-I/P", fp=DIP8,
         at=(210, 100, 0), pins={
            "1": ".THR_BUF", "2": ".THR_BUF", "3": ".THR_ANA", "4": "GND",
            "5": "GND", "6": ".U4B_FB", "7": ".U4B_FB", "8": "+5V"}),
    dict(lib="Device:C", ref="C9", value="100n", fp=C_D,
         at=grid(5), pins={"1": "+5V", "2": "GND"}),

    dict(lib="Jumper:SolderJumper_3_Open", ref="JP1", value="WIPER_SRC", fp=SJ3,
         at=(280, 100, 0), pins={"1": ".DP_WIPER", "2": ".KNOB_WIPER", "3": ".THR_BUF"}),
    dict(lib="Device:C", ref="C10", value="100n", fp=C_D,
         at=grid(6), pins={"1": ".KNOB_WIPER", "2": "GND"}),
    dict(lib="Device:C_Polarized", ref="C11", value="100u", fp=CP_S,
         at=grid(7), pins={"1": ".KNOB_WIPER", "2": "GND"}),
    dict(lib="Connector_Generic:Conn_01x03", ref="J13", value="KNOB (VH/W/VL)", fp=TB3,
         at=(340, 100, 0), pins={"1": ".KNOB_HI", "2": ".KNOB_WIPER", "3": ".KNOB_LO"}),

    # Reversing contactor low-side driver
    dict(lib="Device:R", ref="R16", value="100R", fp=R_AX,
         at=grid(8), pins={"1": "CONT_GATE_3", "2": ".Q2_G"}),
    dict(lib="Device:R", ref="R17", value="100k", fp=R_AX,
         at=grid(9), pins={"1": ".Q2_G", "2": "GND"}),
    dict(lib="Transistor_FET:IRLZ44N", ref="Q2", value="IRLZ44N", fp=TO220,
         at=(140, 160, 0), pins={"1": ".Q2_G", "2": ".CONT_SW", "3": "GND"}),
    dict(lib="Diode:1N4007", ref="D7", value="1N4007", fp=DO41,
         at=grid(10), pins={"1": "+12V", "2": ".CONT_SW"}),
    dict(lib="Connector_Generic:Conn_01x02", ref="J14", value="CONTACTOR 12V", fp=TB2,
         at=(210, 160, 0), pins={"1": "+12V", "2": ".CONT_SW"}),
]
