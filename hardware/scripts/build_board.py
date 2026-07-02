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

HW = "/config/vanchor-pcb/hardware"
NETLIST = f"{HW}/vanchor-helm.net"
BOARD = f"{HW}/vanchor-helm.kicad_pcb"
STD_FP = "/usr/share/kicad/footprints"

OX, OY = 20.0, 20.0
W, H = 200.0, 150.0

# Pad-anchored, rotation-auto-solved parts. J1 flips to the bottom (the Pi
# stacks beneath, HAT-style, on a 19.5mm header). Pi is fully on-board:
# holes (118.5/176.5, 28.5/77.5), pin1 = left hole + 4.87mm along the edge.
ANCHORED = {
    "J1": ((123.37, 29.77), {"2": (0, -2.54), "3": (2.54, 0)}, True),
    "U1": ((168.0, 42.0), {"2": (-2.54, 0), "40": (0, 17.78)}, False),  # Pico horiz, pad1 right
}

PLACE = {
    # ---- thrust power stage (left band) ----
    "Q3": (10.0, 30.0, 270), "Q4": (10.0, 44.0, 270),
    "Q5": (10.0, 66.0, 270), "Q6": (10.0, 80.0, 270),
    "Q7": (60.0, 30.0, 90), "Q8": (60.0, 44.0, 90),
    "Q9": (60.0, 66.0, 90), "Q10": (60.0, 80.0, 90),
    "R22": (4.0, 27.5, 90), "R23": (4.0, 41.5, 90),
    "R24": (4.0, 63.5, 90), "R25": (4.0, 77.5, 90),
    "R26": (66.0, 32.5, 90), "R27": (66.0, 46.5, 90),
    "R28": (66.0, 68.5, 90), "R29": (66.0, 82.5, 90),
    "J18": (13.0, 13.0, 0),          # BATT+ lug
    "U10": (35.0, 16.0, 180),        # ACS758, IP+ west / IP- east
    "C18": (39.8, 57.0, 0), "C19": (39.8, 76.0, 0),   # +pad in spine, GND pad in gap
    "D15": (39.8, 90.0, 0), "C20": (39.5, 97.0, 0),
    "J19": (17.0, 104.0, 0), "J20": (53.0, 104.0, 0), "J21": (10.0, 132.0, 0),
    # driver block (open area at the band bottom)
    "U9": (45.0, 124.0, 270),
    "R30": (33.0, 135.0, 90), "R32": (74.0, 124.0, 90),
    "C16": (41.0, 135.0, 0), "C17": (50.0, 137.5, 0),
    "D12": (29.5, 124.0, 90), "D13": (65.0, 128.0, 90),
    "C14": (27.0, 141.0, 0), "C15": (66.0, 144.0, 0),   # bootstrap caps beside their diodes
    "R33": (72.0, 140.0, 90), "R34": (75.5, 140.0, 90),
    "R35": (79.0, 140.0, 90), "R36": (82.5, 140.0, 90),
    # ---- mid band ----
    "J2": (74.0, 48.0, 0),
    "U5": (94.0, 30.0, 0), "U6": (94.0, 62.0, 0),
    "Q1": (80.0, 84.0, 0), "R1": (80.0, 90.0, 0),
    "D4": (93.0, 84.0, 0), "D5": (93.0, 90.0, 0),
    # servo bridge
    "U7": (84.0, 112.0, 0), "U8": (102.0, 112.0, 0),
    "R39": (84.0, 124.0, 0), "R40": (102.0, 124.0, 0),
    "C22": (117.0, 106.0, 0), "C23": (117.0, 114.0, 90),
    "J22": (90.0, 140.0, 0),
    "R18": (122.0, 124.0, 0), "R19": (122.0, 128.0, 0),
    "D8": (122.0, 132.0, 0), "C12": (131.0, 128.0, 90),
    # pico support + telemetry conditioning
    "R8": (104.0, 95.0, 0), "R9": (104.0, 99.0, 0), "R10": (104.0, 103.0, 0),
    "R11": (110.0, 74.0, 90), "R12": (113.3, 74.0, 90),
    "C5": (111.0, 86.0, 90), "D6": (115.5, 86.0, 0),
    "R37": (111.0, 52.0, 90), "R38": (114.0, 52.0, 90),
    "C21": (111.0, 64.0, 90), "D14": (111.5, 44.0, 0),
    # ---- bottom terminal row ----
    "F1": (108.0, 141.0, 90), "J16": (122.0, 141.0, 0), "J17": (138.0, 141.0, 0),
    "C1": (152.0, 136.0, 0), "C2": (166.0, 136.0, 0),
    "C3": (176.0, 136.0, 90), "C4": (183.0, 136.0, 90),
    "F2": (176.0, 127.0, 0), "J9": (190.0, 136.0, 0),
    "J12": (155.0, 146.0, 90),
    # ---- top band: JSTs, LEDs, misc ----
    "J3": (111.0, 8.0, 0), "J4": (125.0, 8.0, 0), "J5": (139.0, 8.0, 0),
    "J6": (153.0, 8.0, 0), "J7": (167.0, 8.0, 0), "J8": (181.0, 8.0, 0),
    "J11": (189.0, 19.0, 90), "J10": (196.0, 60.0, 90),
    "LED1": (114.0, 17.0, 0), "LED2": (127.0, 17.0, 0), "LED3": (140.0, 17.0, 0),
    "LED4": (153.0, 17.0, 0), "LED5": (166.0, 17.0, 0),
    "R2": (114.0, 22.0, 0), "R3": (127.0, 22.0, 0), "R4": (140.0, 22.0, 0),
    "R7": (153.0, 22.0, 0), "R13": (166.0, 22.0, 0),
    "R5": (86.0, 10.0, 0), "R6": (86.0, 14.0, 0),
    "R20": (178.0, 17.5, 90), "R21": (182.0, 17.5, 90),
    "D10": (186.0, 28.0, 0), "D11": (186.0, 32.0, 0),
}

MOUNTING = [
    ("MountingHole_3.2mm_M3", 5.0, 5.0), ("MountingHole_3.2mm_M3", 195.0, 5.0),
    ("MountingHole_3.2mm_M3", 5.0, 145.0), ("MountingHole_3.2mm_M3", 195.0, 145.0),
    ("MountingHole_3.2mm_M3", 100.0, 5.0), ("MountingHole_3.2mm_M3", 100.0, 145.0),
    ("MountingHole_2.7mm_M2.5", 118.5, 28.5), ("MountingHole_2.7mm_M2.5", 176.5, 28.5),
    ("MountingHole_2.7mm_M2.5", 118.5, 77.5), ("MountingHole_2.7mm_M2.5", 176.5, 77.5),
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

    # VBRIDGE: spine (F+B), ACS IP- patch, B fingers to the high-side drains
    pz("VBRIDGE", pcbnew.F_Cu, rect(31, 30, 41, 118))
    pz("VBRIDGE", pcbnew.B_Cu, rect(31, 30, 41, 118))
    pz("VBRIDGE", pcbnew.B_Cu, rect(35.6, 26, 41, 30.5))
    pz("VBRIDGE", pcbnew.F_Cu, rect(35.4, 20, 44.8, 31.5))
    pz("VBRIDGE", pcbnew.B_Cu, rect(35.4, 20, 44.8, 31.5))
    for poly in fingers_h(31, 41, [("Q3", "2"), ("Q4", "2"), ("Q7", "2"), ("Q8", "2")]):
        pz("VBRIDGE", pcbnew.B_Cu, poly)

    # MOTOR rails + lug arms; F fingers to high-S / low-D pads
    pz("MOTOR_A", pcbnew.F_Cu, rect(16, 26, 24, 96))
    pz("MOTOR_A", pcbnew.F_Cu, rect(10, 94, 24, 114))
    pz("MOTOR_A", pcbnew.B_Cu, rect(16, 48, 24, 96))
    pz("MOTOR_A", pcbnew.B_Cu, rect(10, 94, 24, 114))
    pz("MOTOR_A", pcbnew.F_Cu, rect(21, 94, 27.3, 118))
    for poly in fingers_h(16, 24, [("Q3", "3"), ("Q4", "3"), ("Q5", "2"), ("Q6", "2")]):
        pz("MOTOR_A", pcbnew.F_Cu, poly)
    pz("MOTOR_B", pcbnew.F_Cu, rect(46, 26, 54, 96))
    pz("MOTOR_B", pcbnew.F_Cu, rect(46, 94, 61.0, 114))
    pz("MOTOR_B", pcbnew.B_Cu, rect(46, 48, 54, 96))
    pz("MOTOR_B", pcbnew.B_Cu, rect(46, 94, 61.0, 114))
    for poly in fingers_h(46, 54, [("Q7", "3"), ("Q8", "3"), ("Q9", "2"), ("Q10", "2")]):
        pz("MOTOR_B", pcbnew.F_Cu, poly)

    # battery pocket + GND lug pocket
    pz("VBAT_PWR", pcbnew.F_Cu, rect(1, 1, 24, 20))
    pz("VBAT_PWR", pcbnew.B_Cu, rect(1, 1, 24, 20))
    pz("VBAT_PWR", pcbnew.F_Cu, rect(18, 1, 31.9, 9.5))
    pz("VBAT_PWR", pcbnew.B_Cu, rect(18, 1, 31.9, 9.5))
    pz("VBAT_PWR", pcbnew.F_Cu, rect(25.2, 6, 34.6, 29))
    pz("VBAT_PWR", pcbnew.B_Cu, rect(25.2, 6, 34.6, 29))
    if os.environ.get("BASE_GND") != "0":
        pz("GND", pcbnew.F_Cu, rect(1, 120, 20, 143))
        add_zone("GND", pcbnew.B_Cu, rect(0.6, 0.6, 70, 149.4), 1, True)

    # ---------------- pre-laid fat tracks (power only, no vias) ----------------
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

    chain("VBRIDGE", pcbnew.B_Cu, [(36, 31), (36, 112)], 6.0)
    chain("VBRIDGE", pcbnew.F_Cu, [(36, 31), (36, 112)], 6.0)
    chain("MOTOR_A", pcbnew.F_Cu, [(20, 28), (20, 96), (17, 100), (17, 104)], 6.0)
    chain("MOTOR_A", pcbnew.B_Cu, [(20, 50), (20, 96), (17, 100), (17, 104)], 6.0)
    chain("MOTOR_B", pcbnew.F_Cu, [(50, 28), (50, 96), (53, 100), (53, 104)], 6.0)
    chain("MOTOR_B", pcbnew.B_Cu, [(50, 50), (50, 96), (53, 100), (53, 104)], 6.0)
    gx, gy = pad_xy("J21", "1")
    chain("GND", pcbnew.B_Cu, [(gx, gy), (gx, 121)], 6.0)
    # HIP4082 AHS/BHS sense pins into the motor arms (plane nets are
    # invisible to freerouting, so these two need pre-laid stubs)
    ax, ay = pad_xy("U9", "11")
    chain("MOTOR_A", pcbnew.F_Cu,
          [(ax, ay), (ax, 131.8), (26.5, 131.8), (26.5, 117)], 0.8)
    add_track("MOTOR_A", pcbnew.F_Cu, 17, 104, 26.5, 117, 2.0)
    bx2, by2 = pad_xy("U9", "15")
    chain("MOTOR_B", pcbnew.F_Cu, [(bx2, by2), (bx2, 133), (60.5, 133), (60.5, 107)], 0.8)
    # J1 pins 2/4 are both +5V and adjacent: bond them so the autorouter
    # only has to reach one of them
    j2x, j2y = pad_xy("J1", "2")
    j4x, j4y = pad_xy("J1", "4")
    add_track("+5V", pcbnew.F_Cu, j2x, j2y, j4x, j4y, 0.8)

    # explicit pad-to-rail joins (zone fills alone leave fill-margin islands)
    for ref, num in (("Q3", "3"), ("Q4", "3"), ("Q5", "2"), ("Q6", "2")):
        px, py = pad_xy(ref, num)
        add_track("MOTOR_A", pcbnew.F_Cu, px, py, 20, py, 2.0)
    for ref, num in (("Q7", "3"), ("Q8", "3"), ("Q9", "2"), ("Q10", "2")):
        px, py = pad_xy(ref, num)
        add_track("MOTOR_B", pcbnew.F_Cu, px, py, 50, py, 2.0)
    for ref, num in (("Q3", "2"), ("Q4", "2"), ("Q7", "2"), ("Q8", "2")):
        px, py = pad_xy(ref, num)
        add_track("VBRIDGE", pcbnew.B_Cu, px, py, 36, py, 2.0)
    for ref in ("C18", "C19", "D15", "C20"):
        px, py = pad_xy(ref, "1")
        add_track("VBRIDGE", pcbnew.F_Cu, px, py, 36, py, 2.0)

    # AHO: the one >60mm gate-driver run freerouting drops intermittently
    p10x, p10y = pad_xy("U9", "10")
    r22x, r22y = pad_xy("R22", "1")
    chain("/thrust/AHO", pcbnew.B_Cu,
          [(p10x, p10y), (p10x, 131.35), (24.9, 131.35), (24.9, 114.9),
           (7.4, 114.9), (7.4, r22y), (r22x, r22y)], 0.4)

    # ALO: the mirror-image long gate run, on F via the east loop and the
    # y115.9 corridor (clears the B-side AHO lanes by layer)
    p13x, p13y = pad_xy("U9", "13")
    r24x, r24y = pad_xy("R24", "1")
    chain("/thrust/ALO", pcbnew.F_Cu,
          [(p13x, p13y), (p13x, 133.2), (23.3, 133.2), (23.3, 115.9),
           (6.3, 115.9), (6.3, r24y), (r24x, r24y)], 0.4)
    # GND band<->rest bridges across the x70 seam (B side, in open corridors)
    add_track("GND", pcbnew.B_Cu, 64, 5, 82, 5, 2.0)
    add_track("GND", pcbnew.B_Cu, 64, 98, 80, 98, 2.0)

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
        for px, py in [(75, 0), (199, 0), (199, 1.3), (75, 1.3)]:
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
