"""Pico 2 controller sheet: I2C slave to Pi, I2C master to AS5600, PWM to
H-bridge, digipot/contactor control lines, battery telemetry, utility header.

Pin allocation per plan (Pico 2 module is pin-compatible with the Pico symbol).
"""
from common import PICO_FP, R_AX, C_D, SOT23, LED5MM, HDR1x8, grid

SHEET_UUID = "c0000000-0000-4000-8000-000000000004"

TEXTS = [
    (30, 40, "MCU: Pico 2 (RP2350) - I2C0 slave @0x42 to Pi, I2C1 master to AS5600"),
    (30, 46, "Firmware map: 0x00 CMD {pwm,dir,steer} / 0x10 STATUS {angle,ok,wrap,state,vbat,isense}; 800ms watchdog"),
    (30, 52, "Pico soldered directly (low profile, sits under the Pi). Pi reflashes it via SWD on GPIO24/25 (openocd)."),
]

COMPONENTS = [
    dict(lib="MCU_Module:RaspberryPi_Pico_Debug", ref="U1", value="Pico 2", fp=PICO_FP,
         at=(80, 110, 0), pins={
            "1": "PICO_GP0", "2": "PICO_GP1", "3": "GND",
            "4": "PICO_GP2", "5": "PICO_GP3",
            "6": "PI_SDA", "7": "PI_SCL", "8": "GND",
            "9": "ENC_SDA", "10": "ENC_SCL",
            "11": "RPWM", "12": "LPWM", "13": "GND",
            "14": "R_EN", "15": "L_EN",
            "16": "THR_RPWM", "17": "THR_LPWM", "18": "GND",
            "19": "THR_R_EN", "20": "THR_L_EN",
            "21": None, "22": "LED_STAT", "23": "GND",
            "24": "PICO_GP18", "25": "PICO_GP19", "26": None,
            "27": None, "28": "GND", "29": None,  # GP20-22 unused
            "30": ".PICO_RUN",
            "31": "SERVO_IS", "32": "THR_IS",
            "33": "GND", "34": "VBAT_SENSE",
            "35": None,          # ADC_VREF: module's onboard filter
            "36": "+3V3", "37": None,  # 3V3_EN: pulled up on module
            "38": "GND", "39": "+5V", "40": None,  # VBUS unused (no USB power in)
            "D1": "PI_GPIO25",   # SWCLK <- Pi (openocd bcm2835gpio reflash)
            "D2": "GND",
            "D3": "PI_GPIO24",   # SWDIO <-> Pi
         }),

    dict(lib="Device:R", ref="R8", value="1k", fp=R_AX,
         at=grid(0), pins={"1": "PI_PICO_RUN", "2": ".PICO_RUN"}),
    dict(lib="Device:R", ref="R9", value="4.7k", fp=R_AX,
         at=grid(1), pins={"1": "+3V3", "2": "ENC_SDA"}),
    dict(lib="Device:R", ref="R10", value="4.7k", fp=R_AX,
         at=grid(2), pins={"1": "+3V3", "2": "ENC_SCL"}),

    # Battery voltage telemetry: 48V max -> 3.06V at ADC
    dict(lib="Device:R", ref="R11", value="100k", fp=R_AX,
         at=grid(3), pins={"1": "VIN", "2": "VBAT_SENSE"}),
    dict(lib="Device:R", ref="R12", value="6.8k", fp=R_AX,
         at=grid(4), pins={"1": "VBAT_SENSE", "2": "GND"}),
    dict(lib="Device:C", ref="C5", value="100n", fp=C_D,
         at=grid(5), pins={"1": "VBAT_SENSE", "2": "GND"}),
    dict(lib="Diode:BAT54S", ref="D6", value="BAT54S", fp=SOT23,
         at=grid(6), pins={"1": "GND", "2": "+3V3", "3": "VBAT_SENSE"}),

    dict(lib="Device:R", ref="R13", value="1k", fp=R_AX,
         at=grid(7), pins={"1": "LED_STAT", "2": ".LED5_A"}),
    dict(lib="Device:LED", ref="LED5", value="yellow", fp=LED5MM,
         at=grid(8), pins={"2": ".LED5_A", "1": "GND"}),

    dict(lib="Connector_Generic:Conn_01x08", ref="J12", value="PICO UTIL", fp=HDR1x8, dnp=True,
         at=(200, 110, 0), pins={
            "1": "+3V3", "2": "PICO_GP0", "3": "PICO_GP1", "4": "PICO_GP2",
            "5": "PICO_GP3", "6": "PICO_GP18", "7": "PICO_GP19", "8": "GND"}),
]
