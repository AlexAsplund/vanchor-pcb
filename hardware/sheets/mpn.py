"""Manufacturer part numbers, merged into symbols as an MPN field by gen_sheet.

Jellybean passives (axial resistors, disc caps, 5mm LEDs, pin headers) are
deliberately left MPN-less: value + footprint fully specifies them and any
brand works. Everything identity-critical is pinned here.
"""

MPN = {
    # power
    "Q1": "IRF9540NPBF",                # Infineon P-FET 100V/23A TO-220
    "D4": "BZX85C12-TAP",               # Vishay 12V 1.3W zener
    "D5": "SMCJ18A",                    # Littelfuse/Bourns TVS, SMC (12V system)
    "F1": "3568",                       # Keystone mini-blade fuse holder
    "C1": "EEU-FR1E471B",               # Panasonic 470uF 63V low-ESR radial 12.5mm
    "C2": "EEU-FR1E471B",
    "C3": "EEU-FR1E101",                # 100uF 25V (used on 5V rail)
    "C4": "EEU-FR1E101",
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
    # thrust (on-board H-bridge)
    "U9": "HIP4082IPZ",                 # Renesas full-bridge driver DIP-16
    "U10": "ACS758LCB-100B-PFF-T",      # Allegro 100A bidirectional hall sensor
    "Q3": "IRF100P219", "Q4": "IRF100P219", "Q5": "IRF100P219",
    "Q6": "IRF100P219", "Q7": "IRF100P219", "Q8": "IRF100P219",
    "Q9": "IRF100P219", "Q10": "IRF100P219",
    "D12": "UF4007", "D13": "UF4007",
    "D14": "BAT54S,215", "D15": "SMCJ58A",
    "C18": "UVR1J222MHD (2200uF/63V)", "C19": "UVR1J222MHD (2200uF/63V)",
    "C20": "MKT 1uF/100V (e.g. B32522C1105K)",
    "J18": "M5 bolt lug", "J19": "M5 bolt lug",
    "J20": "M5 bolt lug", "J21": "M5 bolt lug",
    # servo (on-board half-bridges)
    "U7": "BTN8982TA", "U8": "BTN8982TA",
    "J22": "CUI TB007-508-02",
    "C22": "EEU-FR1E221 (220uF/25V)",
    "D8": "BAT54S,215",
    "D10": "BAT54S,215", "D11": "BAT54S,215",
    "J11": "JST B4B-XH-A(LF)(SN)",
}
