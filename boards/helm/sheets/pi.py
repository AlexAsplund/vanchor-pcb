"""Orange Pi Zero 3 carrier sheet (v4): 26-pin socket, UART JSTs, spare I2C,
fan, fused aux 5V.

J1 = 2x13 MALE header; the Zero 3 (pre-soldered pins-up variant) connects
via a standard 26-way 1:1 IDC ribbon (original-RPi style). Module is
powered THROUGH the ribbon 5V pins from the on-board buck — no USB-C.
J2 = 1:1 breakout of all 26 pins (DNP).

The Zero 3's 26-pin header exposes two usable UARTs (UART5 on PH2/PH3,
UART2 on PC5/PC6) plus TWI3 (I2C) — the Pico link rides TWI3. The H618
debug UART lives on the module's own separate 3-pin header. SWD reflash of
the Pico uses two PC GPIOs (pins 16/18); PICO RUN on pin 12.
"""
from common import HDR2x13, XH2, XH4, HDR1x2, R_AX, LED5MM, POLYFUSE, grid

SHEET_UUID = "c0000000-0000-4000-8000-000000000003"

TEXTS = [
    (30, 40, "ORANGE PI ZERO 3 CARRIER: J1 male header -> 26-way IDC ribbon to the module"),
    (30, 46, "Module is powered through header 5V pins - do NOT also plug USB-C power"),
    (30, 52, "UART TX/RX directions per OPi manual - if a device stays silent, swap TX/RX at the JST"),
]

# Orange Pi Zero 3 26-pin header net map (H618 port in comments)
PI26 = {
    "1": "3V3_PI", "2": "+5V",
    "3": "PI_SDA",            # PH5  TWI3-SDA -> Pico
    "4": "+5V",
    "5": "PI_SCL",            # PH4  TWI3-SCK -> Pico
    "6": "GND",
    "7": "OPI_PC9",
    "8": "UART5_TX",          # PH2
    "9": "GND",
    "10": "UART5_RX",         # PH3
    "11": "UART2_TX",         # PC6 (check DT overlay; swap at JST if needed)
    "12": "PI_PICO_RUN",      # PC11 -> Pico RUN (reset)
    "13": "UART2_RX",         # PC5
    "14": "GND",
    "15": "OPI_PC8",
    "16": "PI_GPIO24",        # PC15 -> Pico SWDIO
    "17": "3V3_PI",
    "18": "PI_GPIO25",        # PC14 -> Pico SWCLK
    "19": "OPI_MOSI",         # PH7  SPI1
    "20": "GND",
    "21": "OPI_MISO",         # PH8
    "22": "OPI_PC7",
    "23": "OPI_SCLK",         # PH6
    "24": "OPI_CS",           # PH9
    "25": "GND",
    "26": "OPI_PC10",
}

# Ground economy: J1.14, J1.20 and J2.9 are deliberately NC — each connector keeps
# four other GND pins (6/9/20/25 resp. 6/14/20/25); the escape routing under
# the header field claims those two pads' corridors.
J1_PINS = dict(PI26, **{"14": None, "20": None})
J2_PINS = dict(PI26, **{"9": None})

COMPONENTS = [
    dict(lib="Connector_Generic:Conn_02x13_Odd_Even", ref="J1", value="OPI_Z3_26PIN",
         fp=HDR2x13, at=(70, 95, 0), pins=J1_PINS),
    dict(lib="Connector_Generic:Conn_02x13_Odd_Even", ref="J2", value="OPI_BREAKOUT", dnp=True,
         fp=HDR2x13, at=(150, 95, 0), pins=J2_PINS),

    dict(lib="Connector_Generic:Conn_01x04", ref="J3", value="UART5 ttyAS5", fp=XH4,
         at=(230, 70, 0), pins={"1": "3V3_PI", "2": "UART5_TX", "3": "UART5_RX", "4": "GND"}),
    dict(lib="Connector_Generic:Conn_01x04", ref="J4", value="UART2 ttyAS2", fp=XH4,
         at=(260, 70, 0), pins={"1": "3V3_PI", "2": "UART2_TX", "3": "UART2_RX", "4": "GND"}),

    dict(lib="Connector_Generic:Conn_01x04", ref="J8", value="I2C3 spare", fp=XH4,
         at=(230, 120, 0), pins={"1": "3V3_PI", "2": "PI_SDA", "3": "PI_SCL", "4": "GND"}),
    dict(lib="Device:R", ref="R5", value="2.2k", fp=R_AX, dnp=True,
         at=(260, 120, 0), pins={"1": "3V3_PI", "2": "PI_SDA"}),
    dict(lib="Device:R", ref="R6", value="2.2k", fp=R_AX, dnp=True,
         at=(290, 120, 0), pins={"1": "3V3_PI", "2": "PI_SCL"}),

    dict(lib="Connector_Generic:Conn_01x02", ref="J9", value="FAN 5V", fp=HDR1x2,
         at=(320, 120, 0), pins={"1": "+5V", "2": "GND"}),
    dict(lib="Device:Polyfuse", ref="F2", value="MF-R250 2.5A", fp=POLYFUSE,
         at=(350, 120, 0), pins={"1": "+5V", "2": "DISP_5V"}),
    dict(lib="Connector_Generic:Conn_01x02", ref="J10", value="AUX 5V (screen)", fp=XH2,
         at=(380, 120, 0), pins={"1": "DISP_5V", "2": "GND"}),

    dict(lib="power:PWR_FLAG", ref="#FLG04", value="PWR_FLAG",
         at=grid(2), pins={"1": "3V3_PI"}),
]
