#!/usr/bin/env python3
"""Generate the project's custom footprints into hardware/footprints.pretty/.

1. Pololu_D36V50Fx — from the official dimension diagram (pololu.com file 0J1732):
   25.4 x 25.4 mm module, 12 holes (1.02 mm) in 2 rows x 6 cols at 2.54 pitch,
   outer row 1.27 mm from the pin edge, columns inset 6.35 mm from the sides,
   3 mounting holes (2.18 mm, for M2) inset 2.2 mm from edges.
   Column map (left->right, pin edge down): EN/PG | VRP | VIN | GND | GND | VOUT
   (PG is the inner-row hole of column 1; EN the outer-row one.)
   Pad numbers follow the project symbol: 1=VIN 2=GND 3=VOUT 4=EN 5=PG 6=VRP.

2. RaspberryPi_Pico_TH_SWD — stock Module:RaspberryPi_Pico_Common_THT plus the
   three debug through-holes (D1 SWCLK / D2 GND / D3 SWDIO). Debug hole
   positions come from the stock SMD footprint (D pads at (+-2.54, 23.9) from
   module centre); the THT footprint's origin is pad 1, module centre (8.89,
   24.13), so D1..D3 land at (6.35..11.43, 48.03).
"""
import os
import re

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "footprints.pretty")
STOCK_PICO = "/usr/share/kicad/footprints/Module.pretty/RaspberryPi_Pico_Common_THT.kicad_mod"


def pololu():
    pads = []

    def pad(num, x, y, shape="circle"):
        pads.append(
            f'  (pad "{num}" thru_hole {shape} (at {x} {y}) (size 1.8 1.8) '
            f'(drill 1.1) (layers "*.Cu" "*.Mask"))')

    cols = [-6.35, -3.81, -1.27, 1.27, 3.81, 6.35]
    outer, inner = 11.43, 8.89
    pad("4", cols[0], outer, "rect")   # EN
    pad("5", cols[0], inner)           # PG
    pad("6", cols[1], outer)
    pad("6", cols[1], inner)           # VRP
    pad("1", cols[2], outer)
    pad("1", cols[2], inner)           # VIN
    pad("2", cols[3], outer)
    pad("2", cols[3], inner)           # GND
    pad("2", cols[4], outer)
    pad("2", cols[4], inner)
    pad("3", cols[5], outer)
    pad("3", cols[5], inner)           # VOUT
    for mx, my in ((-10.5, 10.5), (10.5, 10.5), (10.5, -10.5)):
        pads.append(
            f'  (pad "" np_thru_hole circle (at {mx} {my}) (size 2.3 2.3) '
            f'(drill 2.3) (layers "*.Cu" "*.Mask"))')
    body = 12.7
    fp = f'''(footprint "Pololu_D36V50Fx"
  (version 20240108)
  (generator "gen_footprints")
  (layer "F.Cu")
  (descr "Pololu D36V50Fx step-down regulator module, 25.4x25.4mm, vertical pins on 2x6 grid")
  (tags "pololu buck regulator module")
  (attr through_hole)
  (property "Reference" "REF**" (at 0 -14.5 0) (layer "F.SilkS")
    (effects (font (size 1 1) (thickness 0.15))))
  (property "Value" "Pololu_D36V50Fx" (at 0 14.5 0) (layer "F.Fab")
    (effects (font (size 1 1) (thickness 0.15))))
  (fp_rect (start -{body} -{body}) (end {body} {body}) (stroke (width 0.12) (type default)) (fill none) (layer "F.SilkS"))
  (fp_rect (start -{body} -{body}) (end {body} {body}) (stroke (width 0.05) (type default)) (fill none) (layer "F.CrtYd"))
  (fp_rect (start -{body} -{body}) (end {body} {body}) (stroke (width 0.1) (type default)) (fill none) (layer "F.Fab"))
  (fp_text user "pin edge" (at 0 12.7 0) (layer "F.Fab") (effects (font (size 0.8 0.8) (thickness 0.12))))
{os.linesep.join(pads)}
)
'''
    return fp


def pico_swd():
    with open(STOCK_PICO) as f:
        src = f.read()
    src = src.replace('(footprint "RaspberryPi_Pico_Common_THT"',
                      '(footprint "RaspberryPi_Pico_TH_SWD"', 1)
    src = re.sub(r'\(property "Value"\s+"RaspberryPi_Pico[^"]*"',
                 '(property "Value" "RaspberryPi_Pico_TH_SWD"', src)
    # strip 3d model reference (path points at stock lib var; harmless but tidy)
    extra = []
    for num, x in (("D1", 6.35), ("D2", 8.89), ("D3", 11.43)):
        extra.append(
            f'\t(pad "{num}" thru_hole circle (at {x} 48.03) (size 1.5 1.5) '
            f'(drill 1.0) (layers "*.Cu" "*.Mask"))')
    # insert before final closing paren
    idx = src.rstrip().rfind(")")
    return src[:idx] + "\n".join(extra) + "\n" + src[idx:]


def main():
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "Pololu_D36V50Fx.kicad_mod"), "w") as f:
        f.write(pololu())
    with open(os.path.join(OUT, "RaspberryPi_Pico_TH_SWD.kicad_mod"), "w") as f:
        f.write(pico_swd())
    print("footprints written to", OUT)


if __name__ == "__main__":
    main()
