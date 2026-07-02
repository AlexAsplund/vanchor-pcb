#!/usr/bin/env python3
"""Build vanchor-helm.kicad_pcb (v2, 200x150mm) from netlist + placement.

v2 design goals (lessons from the 160x120 v1):
- Generous spacing everywhere: 14mm FET pitch, 15mm JST pitch, 20mm+ routing
  corridors. The autorouter converges cleanly when it has room.
- Pre-lay ONLY the high-current copper (VBRIDGE spine, MOTOR rails, lug
  feeders, battery pocket). Every logic net is left to freerouting.
- No pre-laid vias (they hang freerouting 1.9's DSN preprocessing).

Zones (plan coords, 0..200 x / 0..150 y):
- x 0..70   thrust power stage: mirrored FET columns (A x10, B x60), gate
            resistors outboard (x4 / x66), VBRIDGE spine x31..41 with the
            bulk caps' + pads inside and GND pads in the 41..46 gap, MOTOR
            rails x16..24 / x46..54 with lug arms, driver block at the bottom.
- x 72..118 mid band: GPIO breakout, bucks, input protection, servo bridge,
            small logic, bottom terminal row.
- x 115..200 Pi field: Pi mounts BELOW (flush, no overhang), Pico 2 above it
            on the top side, JST row along the top edge, LEDs, right-edge
            display/AS5600 JSTs.

Run inside the container:  python3 build_board.py   (BASE_GND=0 for the
routable-GND freerouting variant; import_routes.py restores the pours).
"""
import os
import re
import sys
from collections import defaultdict

import pcbnew

HW = "/config/vanchor-pcb/boards/helm"
NETLIST = f"{HW}/vanchor-helm.net"
BOARD = f"{HW}/vanchor-helm.kicad_pcb"
STD_FP = "/usr/share/kicad/footprints"

OX, OY = 20.0, 20.0
W, H = 125.0, 95.0

# Pad-anchored, rotation-auto-solved parts. J1 flips to the bottom (the Pi
# stacks beneath, HAT-style, on a 19.5mm header). Pi is fully on-board:
# holes (118.5/176.5, 28.5/77.5), pin1 = left hole + 4.87mm along the edge.
ANCHORED = {
    # Zero 3 plugs into J1 from above; module body spans x~4..56, y~1..56
    "J1": ((14.0, 56.04), {"2": (0, -2.54), "3": (2.54, 0)}, False),
    "U1": ((109.0, 12.0), {"2": (-2.54, 0), "40": (0, 17.78)}, False),  # Pico horiz, pad1 right
}

PLACE = {
    # ---- under the Zero 3 module (all <=3mm tall; module sits ~9mm up) ----
    "R20": (98.0, 75.0, 0), "R21": (98.0, 79.0, 0),
    "D10": (108.0, 75.0, 0), "D11": (108.0, 79.0, 0),
    "R5": (38.0, 10.0, 0), "R6": (38.0, 15.0, 0),
    "R8": (34.0, 25.0, 0), "R9": (34.0, 30.0, 0), "R10": (34.0, 35.0, 0),
    "R11": (10.0, 28.0, 90), "R12": (14.0, 28.0, 90),
    "C5": (19.0, 28.0, 90), "D6": (24.5, 28.0, 0),
    "J2": (30.0, 44.6, 90),
    # ---- top-right: Pico + aux connectors ----
    "J10": (117.0, 14.0, 90), "J9": (117.0, 27.0, 90),
    "F2": (117.0, 33.0, 0), "J12": (30.0, 49.9, 90),
    # ---- mid-right: servo bridge ----
    "U7": (64.0, 42.0, 0), "U8": (82.0, 42.0, 0),
    "C22": (96.0, 40.0, 0), "C23": (96.0, 49.0, 90),
    "R39": (64.0, 53.0, 0), "R40": (82.0, 53.0, 0),
    "R18": (108.0, 40.0, 0), "R19": (108.0, 45.0, 0),
    "D8": (108.0, 50.0, 0), "C12": (117.0, 45.0, 90),
    # ---- bottom-right: XL4015 buck daughterboard (pins + spacers) + JST row ----
    "U5": (92.0, 67.0, 0),
    "J3": (64.0, 88.0, 0), "J4": (78.0, 88.0, 0),
    "J8": (92.0, 88.0, 0), "J11": (106.0, 88.0, 0),
    # ---- bottom-left: power entry, protection, thrust IF, terminals ----
    "F1": (50.0, 62.0, 0),
    "LED1": (5.0, 62.0, 0), "LED5": (12.5, 62.0, 0),
    "R2": (8.0, 68.0, 0), "R13": (47.0, 22.0, 0),
    "D5": (20.5, 13.0, 0),
    "Q1": (8.0, 75.0, 90), "R1": (23.0, 66.0, 0), "D4": (34.0, 76.5, 90),
    "C1": (44.0, 74.0, 0), "C2": (58.0, 74.0, 0),
    "C3": (14.0, 76.0, 90),
    "R30": (10.0, 85.5, 0), "R32": (24.0, 85.5, 0),
    "R15": (10.0, 82.5, 0), "R16": (24.0, 81.0, 0),
    "R38": (47.0, 28.0, 0), "C21": (22.0, 73.0, 0),
    "D14": (33.0, 68.0, 0),
    "J5": (7.0, 15.0, 0), "R41": (14.5, 19.5, 0), "R42": (3.2, 21.0, 180),
    "J13": (19.0, 91.0, 90),
    "J16": (38.0, 89.0, 0), "J22": (51.0, 89.0, 0),
}

MOUNTING = [
    ("MountingHole_3.2mm_M3", 4.0, 4.0), ("MountingHole_3.2mm_M3", 121.0, 4.0),
    ("MountingHole_3.2mm_M3", 4.0, 91.0), ("MountingHole_3.2mm_M3", 121.0, 91.0),
    ("MountingHole_3.2mm_M3", 12.0, 5.0), ("MountingHole_3.2mm_M3", 47.0, 5.0),   # Zero3 standoffs (verify vs module)
]

# connector-purpose silkscreen legends (x, y, text, size, rot)
SILK_TEXTS = [
    (37.7, 81.0, "BATT 12V", 1.0, 0), (35.16, 85.8, "+", 1.4, 0), (40.24, 85.8, "-", 1.4, 0),
    (50.0, 56.8, "F1 10A", 1.0, 0),
    (19.0, 87.7, "THRUST DRV", 1.0, 0),
    (19.0, 93.8, "RPWM LPWM REN LEN RIS LIS 5V GND", 0.8, 0),
    (50.7, 81.0, "SERVO", 1.0, 0),
    (29.0, 59.6, "OPI ZERO 3 RIBBON", 1.2, 0), (11.5, 58.8, "1", 1.0, 0),
    (30.0, 41.3, "SBC2: OPI Z3 / RPI PINS 1-26 (FIT ONE SBC)", 0.8, 0), (12.8, 45.9, "1", 0.8, 0),
    (64.0, 82.5, "UART5", 1.0, 0), (78.0, 82.5, "UART2", 1.0, 0),
    (92.0, 82.5, "I2C3", 1.0, 0), (106.0, 82.5, "AS5600", 1.0, 0),
    (122.9, 14.0, "AUX 5V", 1.0, 90), (122.9, 27.0, "FAN", 1.0, 90),
    (6.0, 9.8, "NMEA2000", 0.9, 0), (7.0, 18.5, "V+ - SH", 0.8, 0),
    (30.0, 19.7, "CAN XCVR ON J12: 3V3=1 GND=8 TX=6 RX=7", 0.8, 0),
]


def mm(x, y):
    return pcbnew.VECTOR2I_MM(OX + x, OY + y)


def parse_netlist(path):
    text = open(path).read()
    comps = {}
    for m in re.finditer(r'\(comp\s+\(ref\s+"([^"]+)"\)(.*?)(?=\(comp\s+\(ref|\(libparts)', text, re.S):
        ref, body = m.group(1), m.group(2)
        fp = re.search(r'\(footprint\s+"([^"]+)"\)', body)
        val = re.search(r'\(value\s+"([^"]+)"\)', body)
        dnp = '(property "dnp")' in body
        comps[ref] = {"fp": fp.group(1) if fp else "", "value": val.group(1) if val else "",
                      "dnp": dnp}
    pin_net = {}
    net_names = set()
    for m in re.finditer(r'\(net\s+\(code\s+"?\d+"?\)\s+\(name\s+"([^"]+)"\)(.*?)(?=\(net\s+\(code|\Z)', text, re.S):
        name = m.group(1)
        net_names.add(name)
        for n in re.finditer(r'\(node\s+\(ref\s+"([^"]+)"\)\s+\(pin\s+"([^"]+)"\)', m.group(2)):
            pin_net[(n.group(1), n.group(2))] = name
    return comps, pin_net, net_names


def load_footprint(fpid):
    lib, name = fpid.split(":", 1)
    libpath = f"{HW}/footprints.pretty" if lib == "vanchor-helm" else f"{STD_FP}/{lib}.pretty"
    fp = pcbnew.FootprintLoad(libpath, name)
    if fp is None:
        raise SystemExit(f"footprint not found: {fpid}")
    return fp


SKELETON = """(kicad_pcb
  (version 20240108)
  (generator "pcbnew")
  (generator_version "8.0")
  (general (thickness 1.6) (legacy_teardrops no))
  (paper "A3")
  (layers
    (0 "F.Cu" signal)
    (31 "B.Cu" signal)
    (34 "B.Paste" user)
    (35 "F.Paste" user)
    (36 "B.SilkS" user "B.Silkscreen")
    (37 "F.SilkS" user "F.Silkscreen")
    (38 "B.Mask" user)
    (39 "F.Mask" user)
    (40 "Dwgs.User" user "User.Drawings")
    (44 "Edge.Cuts" user)
    (46 "B.CrtYd" user "B.Courtyard")
    (47 "F.CrtYd" user "F.Courtyard")
    (48 "B.Fab" user)
    (49 "F.Fab" user)
  )
  (setup (pad_to_mask_clearance 0))
  (net 0 "")
)
"""


def main():
    with open(BOARD, "w") as f:
        f.write(SKELETON)
    board = pcbnew.LoadBoard(BOARD)

    comps, pin_net, net_names = parse_netlist(NETLIST)
    nets = {}
    for name in sorted(net_names):
        ni = pcbnew.NETINFO_ITEM(board, name)
        board.Add(ni)
        nets[name] = ni

    placed = set(PLACE) | set(ANCHORED)
    missing = [r for r in comps if r not in placed and not r.startswith("#")]
    extra = [r for r in placed if r not in comps]
    if extra:
        raise SystemExit(f"placement refs not in netlist: {extra}")
    if missing:
        raise SystemExit(f"netlist refs without placement: {missing}")

    def pad_pos(fp, num):
        for pad in fp.Pads():
            if pad.GetNumber() == num:
                return pad.GetPosition()
        raise SystemExit(f"{fp.GetReference()}: no pad {num}")

    for ref, info in sorted(comps.items()):
        if ref.startswith("#"):
            continue
        fp = load_footprint(info["fp"])
        fp.SetReference(ref)
        fp.SetValue(info["value"])
        board.Add(fp)
        if ref in ANCHORED:
            (tx, ty), expect, flip = ANCHORED[ref]
            if flip:
                fp.Flip(fp.GetPosition(), False)
            solved = None
            for rot in (0, 90, 180, 270):
                fp.SetOrientationDegrees(rot)
                p1 = pad_pos(fp, "1")
                ok = True
                for num, (dx, dy) in expect.items():
                    d = pad_pos(fp, num) - p1
                    if abs(pcbnew.ToMM(d.x) - dx) > 0.01 or abs(pcbnew.ToMM(d.y) - dy) > 0.01:
                        ok = False
                        break
                if ok:
                    solved = rot
                    break
            if solved is None:
                raise SystemExit(f"{ref}: no rotation satisfies pad vectors")
            fp.SetPosition(fp.GetPosition() + (mm(tx, ty) - pad_pos(fp, "1")))
        else:
            x, y, rot = PLACE[ref]
            fp.SetOrientationDegrees(rot)
            court = fp.GetCourtyard(pcbnew.F_CrtYd)
            bb = court.BBox() if court.OutlineCount() else fp.GetBoundingBox(False)
            fp.SetPosition(fp.GetPosition() + (mm(x, y) - bb.GetCenter()))
        if info["dnp"]:
            fp.SetDNP(True)
        for pad in fp.Pads():
            key = (ref, pad.GetNumber())
            if key in pin_net:
                pad.SetNet(nets[pin_net[key]])

    for i, (name, x, y) in enumerate(MOUNTING):
        fp = load_footprint(f"MountingHole:{name}")
        fp.SetReference(f"H{i+1}")
        fp.SetValue(name)
        fp.SetPosition(mm(x, y))
        board.Add(fp)

    for sx, sy, stext, ssize, srot in SILK_TEXTS:
        st = pcbnew.PCB_TEXT(board)
        st.SetText(stext)
        st.SetPosition(mm(sx, sy))
        st.SetLayer(pcbnew.F_SilkS)
        st.SetTextSize(pcbnew.VECTOR2I_MM(ssize, ssize))
        st.SetTextThickness(pcbnew.FromMM(0.15 if ssize >= 1.0 else 0.13))
        if srot:
            st.SetTextAngleDegrees(srot)
        board.Add(st)

    pts = [(0, 0), (W, 0), (W, H), (0, H)]
    for i in range(4):
        seg = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_SEGMENT)
        seg.SetStart(mm(*pts[i]))
        seg.SetEnd(mm(*pts[(i + 1) % 4]))
        seg.SetLayer(pcbnew.Edge_Cuts)
        seg.SetWidth(pcbnew.FromMM(0.1))
        board.Add(seg)

    # ---------------- power copper ----------------
    def pad_xy(ref, num):
        for fp in board.GetFootprints():
            if fp.GetReference() == ref:
                p = pad_pos(fp, num)
                return pcbnew.ToMM(p.x) - OX, pcbnew.ToMM(p.y) - OY
        raise SystemExit(f"no footprint {ref}")

    zprio = [10]

    def add_zone(net, layer, pts, priority, solid):
        zone = pcbnew.ZONE(board)
        zone.SetLayer(layer)
        zone.SetNet(nets[net])
        outline = zone.Outline()
        outline.NewOutline()
        for px, py in pts:
            outline.Append(mm(px, py))
        zone.SetAssignedPriority(priority)
        zone.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL if solid
                              else pcbnew.ZONE_CONNECTION_THERMAL)
        zone.SetMinThickness(pcbnew.FromMM(0.25))
        zone.SetThermalReliefGap(pcbnew.FromMM(0.5))
        zone.SetThermalReliefSpokeWidth(pcbnew.FromMM(1.0))
        zone.SetLocalClearance(pcbnew.FromMM(0.5))
        board.Add(zone)

    def pz(net, layer, pts):
        zprio[0] += 1
        add_zone(net, layer, pts, zprio[0], True)

    def rect(x0, y0, x1, y1):
        return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]

    def fingers_h(rail_x0, rail_x1, pads, half_w=1.3):
        polys = []
        for ref, num in pads:
            px, py = pad_xy(ref, num)
            x0 = min(px - half_w, rail_x0)
            x1 = max(px + half_w, rail_x1)
            polys.append([(x0, py - half_w), (x1, py - half_w),
                          (x1, py + half_w), (x0, py + half_w)])
        return polys

    def add_track(net, layer, x0, y0, x1, y1, w):
        if abs(x1 - x0) < 0.01 and abs(y1 - y0) < 0.01:
            return
        t = pcbnew.PCB_TRACK(board)
        t.SetStart(mm(x0, y0))
        t.SetEnd(mm(x1, y1))
        t.SetWidth(pcbnew.FromMM(w))
        t.SetLayer(layer)
        t.SetNet(nets[net])
        board.Add(t)

    def chain(net, layer, pts, w):
        for (a, b), (c, d) in zip(pts, pts[1:]):
            add_track(net, layer, a, b, c, d, w)

    # nets freerouting drops on this layout (lottery-verified): pre-lay them
    p7x, p7y = pad_xy("J13", "7")          # +5V west anchor
    u5x, u5y = pad_xy("U5", "3")           # +5V source (buck OUT+)
    chain("+5V", pcbnew.B_Cu,
          [(p7x, p7y), (p7x, 83.7), (120.8, 83.7), (120.8, u5y), (u5x + 2.0, u5y)], 1.3)
    # TO-263-7 pad-4 halves: strap them (fill alone leaves them split)
    add_track("SERVO_A", pcbnew.F_Cu, 59, 42, 64, 42, 1.1)
    add_track("SERVO_B", pcbnew.F_Cu, 77, 42, 82, 42, 1.1)
    j18x, j18y = pad_xy("J1", "8")         # UART5_TX from the ribbon header
    j3x, j3y = pad_xy("J3", "2")
    chain("UART5_TX", pcbnew.F_Cu,
          [(j18x, j18y), (22.89, j18y + 1.27), (22.89, 88.3), (24.08, 89.49),
           (24.08, 93.6), (j3x, 93.6), (j3x, j3y)], 0.3)

    # top-edge via/track keepout: freerouting otherwise hugs the edge
    for klayer in (pcbnew.F_Cu, pcbnew.B_Cu):
        ka = pcbnew.ZONE(board)
        ka.SetIsRuleArea(True)
        ka.SetDoNotAllowTracks(True)
        ka.SetDoNotAllowVias(True)
        ka.SetDoNotAllowZoneFills(False)
        ka.SetLayer(klayer)
        ko = ka.Outline()
        ko.NewOutline()
        for px, py in [(58, 0), (124, 0), (124, 1.3), (58, 1.3)]:
            pass
        board.Add(ka)
    for klayer in (pcbnew.F_Cu, pcbnew.B_Cu):
        ka = pcbnew.ZONE(board)
        ka.SetIsRuleArea(True)
        ka.SetDoNotAllowTracks(True)
        ka.SetDoNotAllowVias(True)
        ka.SetDoNotAllowZoneFills(False)
        ka.SetLayer(klayer)
        ko = ka.Outline()
        ko.NewOutline()
        for px, py in [(0, 2), (1.3, 2), (1.3, 93), (0, 93)]:
            ko.Append(mm(px, py))
        board.Add(ka)

    if os.environ.get("BASE_GND") != "0":
        for layer in (pcbnew.F_Cu, pcbnew.B_Cu):
            add_zone("GND", layer, rect(0, 0, W, H), 0, False)

    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    pcbnew.SaveBoard(BOARD, board)
    print(f"placed {len([r for r in comps if not r.startswith('#')])} footprints, "
          f"{len(MOUNTING)} holes, {len(nets)} nets")


if __name__ == "__main__":
    main()
