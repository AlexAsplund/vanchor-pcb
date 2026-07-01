"""Thrust sheet: ON-BOARD H-bridge for the trolling motor.

>= 800W @ 12V (~67A continuous), fwd/rev, battery 12-48V.
HIP4082 full-bridge gate driver + 8x IRF100P219 (100V ~2mOhm TO-220, two per
switch), ACS758-100B hall sensor in the battery leg, M5 bolt lugs for the
power connections. Pico drives AHI/BHI/ALI/BLI directly (VIH 2.5V); pull-downs
keep the bridge dead and DIS is pulled up (=disabled) whenever the Pico is
absent or in reset.

Power nets: VBAT_PWR (battery lug, upstream of ACS758; also feeds board logic
via F1 on the power sheet) -> ACS758 -> VBRIDGE (high-side drains).
MOTOR_A / MOTOR_B out on lugs. Low-side sources return to GND at the lug
star point (2oz pours carry the current; external ANL fuse at the battery).
"""
from common import R_AX, R_AX_V, C_D, TO220, DO41, SOT23, grid

SHEET_UUID = "c0000000-0000-4000-8000-000000000005"

FET = "Transistor_FET:IRLZ44N"  # symbol reused (G/D/S pins); value pins actual part
LUG = "vanchor-helm:Lug_M5"

TEXTS = [
    (30, 40, "THRUST: on-board H-bridge, >=800W @ 12V (67A cont), fwd/rev, 12-48V bus"),
    (30, 46, "HIP4082 + 8x IRF100P219 (2 per switch) + ACS758-100B battery-leg sense; M5 lugs"),
    (30, 52, "Bridge disabled unless Pico drives it: 100k pull-downs on inputs, DIS pulled up to 3V3"),
    (30, 58, "Heatsink bar across the FET row required; airflow recommended above 40A continuous"),
]


def fet(ref, gate_net, drain, source, i):
    return dict(lib=FET, ref=ref, value="IRF100P219", fp=TO220,
                at=grid(i, y0=215), pins={"1": gate_net, "2": drain, "3": source})


COMPONENTS = [
    # --- gate driver ---
    dict(lib="Driver_FET:HIP4082xP", ref="U9", value="HIP4082IPZ",
         fp="Package_DIP:DIP-16_W7.62mm_Socket",
         at=(80, 110, 0), pins={
            "1": ".BHB", "2": "THR_BHI", "3": "THR_BLI", "4": "THR_ALI",
            "5": ".DEL", "6": "GND", "7": "THR_AHI", "8": "THR_DIS",
            "9": ".AHB", "10": ".AHO", "11": "MOTOR_A", "12": "+12V",
            "13": ".ALO", "14": ".BLO", "15": "MOTOR_B", "16": ".BHO"}),
    dict(lib="Device:R", ref="R30", value="150k", fp=R_AX,          # dead-time set
         at=grid(0), pins={"1": ".DEL", "2": "GND"}),
    dict(lib="Device:C", ref="C16", value="100n", fp=C_D,
         at=grid(1), pins={"1": "+12V", "2": "GND"}),
    dict(lib="Device:C_Polarized", ref="C17", value="10u/25V",
         fp="Capacitor_THT:CP_Radial_D5.0mm_P2.00mm",
         at=grid(2), pins={"1": "+12V", "2": "GND"}),

    # --- logic-input safety ---
    dict(lib="Device:R", ref="R33", value="100k", fp=R_AX,
         at=grid(3), pins={"1": "THR_AHI", "2": "GND"}),
    dict(lib="Device:R", ref="R34", value="100k", fp=R_AX,
         at=grid(4), pins={"1": "THR_BHI", "2": "GND"}),
    dict(lib="Device:R", ref="R35", value="100k", fp=R_AX,
         at=grid(5), pins={"1": "THR_ALI", "2": "GND"}),
    dict(lib="Device:R", ref="R36", value="100k", fp=R_AX,
         at=grid(6), pins={"1": "THR_BLI", "2": "GND"}),
    dict(lib="Device:R", ref="R32", value="10k", fp=R_AX,           # DIS pull-up = safe
         at=grid(7), pins={"1": "+3V3", "2": "THR_DIS"}),

    # --- bootstrap ---
    dict(lib="Diode:1N4007", ref="D12", value="UF4007", fp=DO41,
         at=grid(8), pins={"1": ".AHB", "2": "+12V"}),
    dict(lib="Diode:1N4007", ref="D13", value="UF4007", fp=DO41,
         at=grid(9), pins={"1": ".BHB", "2": "+12V"}),
    dict(lib="Device:C", ref="C14", value="1u/50V", fp=C_D,
         at=grid(10), pins={"1": ".AHB", "2": "MOTOR_A"}),
    dict(lib="Device:C", ref="C15", value="1u/50V", fp=C_D,
         at=grid(11), pins={"1": ".BHB", "2": "MOTOR_B"}),

    # --- gate resistors (two FETs per switch, one 10R each) ---
    dict(lib="Device:R", ref="R22", value="10R", fp=R_AX_V,
         at=grid(12), pins={"1": ".AHO", "2": ".G_AH1"}),
    dict(lib="Device:R", ref="R23", value="10R", fp=R_AX_V,
         at=grid(13), pins={"1": ".AHO", "2": ".G_AH2"}),
    dict(lib="Device:R", ref="R24", value="10R", fp=R_AX_V,
         at=grid(14), pins={"1": ".ALO", "2": ".G_AL1"}),
    dict(lib="Device:R", ref="R25", value="10R", fp=R_AX_V,
         at=grid(15), pins={"1": ".ALO", "2": ".G_AL2"}),
    dict(lib="Device:R", ref="R26", value="10R", fp=R_AX_V,
         at=grid(16), pins={"1": ".BHO", "2": ".G_BH1"}),
    dict(lib="Device:R", ref="R27", value="10R", fp=R_AX_V,
         at=grid(17), pins={"1": ".BHO", "2": ".G_BH2"}),
    dict(lib="Device:R", ref="R28", value="10R", fp=R_AX_V,
         at=grid(18), pins={"1": ".BLO", "2": ".G_BL1"}),
    dict(lib="Device:R", ref="R29", value="10R", fp=R_AX_V,
         at=grid(19), pins={"1": ".BLO", "2": ".G_BL2"}),

    # --- the bridge: A high (VBRIDGE->MOTOR_A), A low (MOTOR_A->GND), B likewise ---
    fet("Q3", ".G_AH1", "VBRIDGE", "MOTOR_A", 0),
    fet("Q4", ".G_AH2", "VBRIDGE", "MOTOR_A", 1),
    fet("Q5", ".G_AL1", "MOTOR_A", "GND", 2),
    fet("Q6", ".G_AL2", "MOTOR_A", "GND", 3),
    fet("Q7", ".G_BH1", "VBRIDGE", "MOTOR_B", 4),
    fet("Q8", ".G_BH2", "VBRIDGE", "MOTOR_B", 5),
    fet("Q9", ".G_BL1", "MOTOR_B", "GND", 6),
    fet("Q10", ".G_BL2", "MOTOR_B", "GND", 7),

    # --- battery-leg current sense ---
    dict(lib="Sensor_Current:ACS758xCB-100B-PFF", ref="U10", value="ACS758LCB-100B",
         fp="Sensor_Current:Allegro_CB_PFF",
         at=(200, 110, 0), pins={
            "1": "+5V", "2": "GND", "3": ".THR_IS_5V",
            "4": "VBAT_PWR", "5": "VBRIDGE"}),
    dict(lib="Device:R", ref="R37", value="10k", fp=R_AX,
         at=grid(20), pins={"1": ".THR_IS_5V", "2": "THR_IS"}),
    dict(lib="Device:R", ref="R38", value="20k", fp=R_AX,
         at=grid(21), pins={"1": "THR_IS", "2": "GND"}),
    dict(lib="Device:C", ref="C21", value="100n", fp=C_D,
         at=grid(22), pins={"1": "THR_IS", "2": "GND"}),
    dict(lib="Diode:BAT54S", ref="D14", value="BAT54S", fp=SOT23,
         at=grid(23), pins={"1": "GND", "2": "+3V3", "3": "THR_IS"}),

    # --- bridge bulk + clamp ---
    dict(lib="Device:C_Polarized", ref="C18", value="2200u/63V",
         fp="Capacitor_THT:CP_Radial_D18.0mm_P7.50mm",
         at=(260, 110, 0), pins={"1": "VBRIDGE", "2": "GND"}),
    dict(lib="Device:C_Polarized", ref="C19", value="2200u/63V",
         fp="Capacitor_THT:CP_Radial_D18.0mm_P7.50mm",
         at=(290, 110, 0), pins={"1": "VBRIDGE", "2": "GND"}),
    dict(lib="Device:C", ref="C20", value="1u/100V film", fp=C_D,
         at=grid(24), pins={"1": "VBRIDGE", "2": "GND"}),
    dict(lib="Device:D_TVS", ref="D15", value="SMCJ58A",
         fp="Diode_SMD:D_SMC",
         at=grid(25), pins={"1": "VBRIDGE", "2": "GND"}),

    # --- power lugs ---
    dict(lib="Connector_Generic:Conn_01x01", ref="J18", value="LUG BATT+", fp=LUG,
         at=(330, 90, 0), pins={"1": "VBAT_PWR"}),
    dict(lib="Connector_Generic:Conn_01x01", ref="J19", value="LUG MOTOR A", fp=LUG,
         at=(330, 110, 0), pins={"1": "MOTOR_A"}),
    dict(lib="Connector_Generic:Conn_01x01", ref="J20", value="LUG MOTOR B", fp=LUG,
         at=(330, 130, 0), pins={"1": "MOTOR_B"}),
    dict(lib="Connector_Generic:Conn_01x01", ref="J21", value="LUG GND", fp=LUG,
         at=(330, 150, 0), pins={"1": "GND"}),
]
