"""Manufacturer part numbers, merged into symbols as an MPN field by gen_sheet.

Jellybean passives (axial resistors, disc caps, 5mm LEDs, pin headers) are
deliberately left MPN-less: value + footprint fully specifies them and any
brand works. Everything identity-critical is pinned here.
"""

MPN = {
    # power
    "Q1": "IRF9540NPBF",                # Infineon P-FET 100V/23A TO-220
    "D4": "BZX85C12-TAP",               # Vishay 12V 1.3W zener
    "D5": "SMCJ58A",                    # Littelfuse/Bourns TVS, SMC
    "F1": "3568",                       # Keystone mini-blade fuse holder
    "U5": "Pololu 4091 (D36V50F5)",
    "U6": "Pololu 4095 (D36V50F12)",
    "C1": "EEU-FR1J471B",               # Panasonic 470uF 63V low-ESR radial 12.5mm
    "C2": "EEU-FR1J471B",
    "C3": "EEU-FR1E101",                # 100uF 25V (used on 5V rail)
    "C4": "EEU-FR1E101",
    "J16": "CUI TB007-508-02",
    "J17": "CUI TB007-508-02",
    # pi carrier
    "J1": "Adafruit 1979 (2x20 stacking, extra-tall ~19.5mm) or ESQ-120-39-G-D",
    "F2": "Bourns MF-R200",
    "J3": "JST B4B-XH-A(LF)(SN)", "J4": "JST B4B-XH-A(LF)(SN)",
    "J5": "JST B4B-XH-A(LF)(SN)", "J6": "JST B4B-XH-A(LF)(SN)",
    "J7": "JST B4B-XH-A(LF)(SN)", "J8": "JST B4B-XH-A(LF)(SN)",
    "J10": "JST B2B-XH-A(LF)(SN)",
    # mcu
    "U1": "Raspberry Pi Pico 2 (SC1632)",
    "D6": "BAT54S,215",                 # Nexperia
    # thrust
    "U2": "SN74AHCT125N",               # TI DIP-14
    "U3": "X9C103P",                    # Renesas 10k digipot DIP-8
    "U4": "MCP6002-I/P",                # Microchip DIP-8
    "Q2": "IRLZ44NPBF",
    "D7": "1N4007",
    "J13": "CUI TB007-508-03",
    "J14": "CUI TB007-508-02",
    # servo
    "D8": "BAT54S,215", "D9": "BAT54S,215",
    "D10": "BAT54S,215", "D11": "BAT54S,215",
    "J11": "JST B4B-XH-A(LF)(SN)",
}
