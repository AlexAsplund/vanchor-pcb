"""Raspberry Pi carrier sheet: 40-pin stacking header, full breakout, all five
GPIO UARTs on JST-XH, spare I2C, fan, fused display power, heartbeat LED.

J1 = stacking header the Pi mounts on; J2 = 1:1 breakout of all 40 pins.
UART headers carry Pi device names (Pi4: ttyAMA0/2/3/4/5, same GPIOs on Pi5).
"""
from common import PSOCK2x20, HDR2x20, XH2, XH4, HDR1x2, R_AX, LED5MM, POLYFUSE, grid

SHEET_UUID = "c0000000-0000-4000-8000-000000000003"

TEXTS = [
    (30, 40, "RASPBERRY PI 4/5 CARRIER: stacking header, UART breakouts, display power"),
    (30, 46, "DSI touchscreen: ribbon to Pi directly; 5V from J10. USB/HDMI on Pi itself."),
]

# Pi 40-pin header net map (BCM GPIO in comments)
PI40 = {
    "1": "3V3_PI", "2": "+5V",
    "3": "PI_SDA",            # GPIO2  I2C1 SDA -> Pico
    "4": "+5V",
    "5": "PI_SCL",            # GPIO3  I2C1 SCL -> Pico
    "6": "GND",
    "7": "UART3_TX",          # GPIO4
    "8": "UART0_TX",          # GPIO14
    "9": "GND",
    "10": "UART0_RX",         # GPIO15
    "11": "PI_PICO_RUN",      # GPIO17 -> Pico RUN (reset)
    "12": "PI_GPIO18",
    "13": "PI_GPIO27",
    "14": "GND",
    "15": "PI_GPIO22",
    "16": "PI_GPIO23",
    "17": "3V3_PI",
    "18": "PI_GPIO24",
    "19": "PI_GPIO10",
    "20": "GND",
    "21": "UART4_RX",         # GPIO9
    "22": "PI_GPIO25",
    "23": "PI_GPIO11",
    "24": "UART4_TX",         # GPIO8
    "25": "GND",
    "26": "PI_GPIO7",
    "27": "UART2_TX",         # GPIO0
    "28": "UART2_RX",         # GPIO1
    "29": "UART3_RX",         # GPIO5
    "30": "GND",
    "31": "PI_GPIO6",
    "32": "UART5_TX",         # GPIO12
    "33": "UART5_RX",         # GPIO13
    "34": "GND",
    "35": "PI_GPIO19",
    "36": "PI_GPIO16",
    "37": "PI_LED",           # GPIO26 heartbeat LED
    "38": "PI_GPIO20",
    "39": "GND",
    "40": "PI_GPIO21",
}

COMPONENTS = [
    dict(lib="Connector_Generic:Conn_02x20_Odd_Even", ref="J1", value="PI_40PIN_STACK",
         fp=PSOCK2x20, at=(70, 95, 0), pins=dict(PI40)),
    dict(lib="Connector_Generic:Conn_02x20_Odd_Even", ref="J2", value="PI_BREAKOUT",
         fp=HDR2x20, at=(150, 95, 0), pins=dict(PI40)),

    dict(lib="Connector_Generic:Conn_01x04", ref="J3", value="UART0 ttyAMA0", fp=XH4,
         at=(230, 70, 0), pins={"1": "3V3_PI", "2": "UART0_TX", "3": "UART0_RX", "4": "GND"}),
    dict(lib="Connector_Generic:Conn_01x04", ref="J4", value="UART2 ttyAMA2", fp=XH4,
         at=(260, 70, 0), pins={"1": "3V3_PI", "2": "UART2_TX", "3": "UART2_RX", "4": "GND"}),
    dict(lib="Connector_Generic:Conn_01x04", ref="J5", value="UART3 ttyAMA3", fp=XH4,
         at=(290, 70, 0), pins={"1": "3V3_PI", "2": "UART3_TX", "3": "UART3_RX", "4": "GND"}),
    dict(lib="Connector_Generic:Conn_01x04", ref="J6", value="UART4 ttyAMA4", fp=XH4,
         at=(320, 70, 0), pins={"1": "3V3_PI", "2": "UART4_TX", "3": "UART4_RX", "4": "GND"}),
    dict(lib="Connector_Generic:Conn_01x04", ref="J7", value="UART5 ttyAMA5", fp=XH4,
         at=(350, 70, 0), pins={"1": "3V3_PI", "2": "UART5_TX", "3": "UART5_RX", "4": "GND"}),

    dict(lib="Connector_Generic:Conn_01x04", ref="J8", value="I2C1 spare", fp=XH4,
         at=(230, 120, 0), pins={"1": "3V3_PI", "2": "PI_SDA", "3": "PI_SCL", "4": "GND"}),
    dict(lib="Device:R", ref="R5", value="2.2k", fp=R_AX, dnp=True,
         at=(260, 120, 0), pins={"1": "3V3_PI", "2": "PI_SDA"}),
    dict(lib="Device:R", ref="R6", value="2.2k", fp=R_AX, dnp=True,
         at=(290, 120, 0), pins={"1": "3V3_PI", "2": "PI_SCL"}),

    dict(lib="Connector_Generic:Conn_01x02", ref="J9", value="FAN 5V", fp=HDR1x2,
         at=(320, 120, 0), pins={"1": "+5V", "2": "GND"}),
    dict(lib="Device:Polyfuse", ref="F2", value="MF-R200 2A", fp=POLYFUSE,
         at=(350, 120, 0), pins={"1": "+5V", "2": "DISP_5V"}),
    dict(lib="Connector_Generic:Conn_01x02", ref="J10", value="DISP PWR 5V", fp=XH2,
         at=(380, 120, 0), pins={"1": "DISP_5V", "2": "GND"}),

    dict(lib="Device:R", ref="R7", value="1k", fp=R_AX,
         at=grid(0), pins={"1": "PI_LED", "2": ".LED4_A"}),
    dict(lib="Device:LED", ref="LED4", value="green", fp=LED5MM,
         at=grid(1), pins={"2": ".LED4_A", "1": "GND"}),
    dict(lib="power:PWR_FLAG", ref="#FLG04", value="PWR_FLAG",
         at=grid(2), pins={"1": "3V3_PI"}),
]
