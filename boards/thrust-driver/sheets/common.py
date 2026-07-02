"""Shared footprint constants for the thrust-driver board."""
R_AX = "Resistor_THT:R_Axial_DIN0207_L6.3mm_D2.5mm_P10.16mm_Horizontal"
C_D = "Capacitor_THT:C_Disc_D5.0mm_W2.5mm_P5.00mm"
CP_BULK = "Capacitor_THT:CP_Radial_D18.0mm_P7.50mm"
SMC = "Diode_SMD:D_SMC"
TO263_7 = "Package_TO_SOT_SMD:TO-263-7_TabPin4"
HDR1x8 = "Connector_PinHeader_2.54mm:PinHeader_1x08_P2.54mm_Vertical"
LED5MM = "LED_THT:LED_D5.0mm"
LUG = "vanchor-helm:Lug_M5"
FILM = "Capacitor_THT:C_Rect_L13.0mm_W6.0mm_P10.00mm"


def grid(i, x0=40, y0=170, dx=42, dy=45, per_row=9):
    return (x0 + (i % per_row) * dx, y0 + (i // per_row) * dy, 0)
