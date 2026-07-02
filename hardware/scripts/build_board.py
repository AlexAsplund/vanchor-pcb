#!/usr/bin/env python3
"""Build vanchor-helm.kicad_pcb from the exported netlist + placement table.

Run inside the container:
    python3 build_board.py

Placement philosophy (board plan coords, 0..100 x, 0..110 y, origin top-left;
absolute board coords add OFFSET):
- Pi 4/5 mounts flat over the right/centre of the board on 11 mm stacking
  header J1; its USB/ETH end overhangs the right board edge. All 4 standoffs
  on-board. Only low-profile parts (<9 mm) under the Pi.
- Top band: JST connector row (UARTs, I2C). Right edge: AS5600 + display JSTs.
- Left band: J2 GPIO breakout column + the two Pololu buck modules.
- Bottom band: screw terminals (battery, knob, 12V link, contactor), fuse,
  bulk caps, fan, then header row (J12 utility, J15 IBT-2).
- Under Pi: Pico (soldered direct), DIP sockets, flat TO-220s, passives.
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

OX, OY = 20.0, 20.0     # board origin offset in page coords
W, H = 160.0, 120.0     # board size (power stage adds a 58mm left band)
XS = 58.0               # x-shift applied to the pre-revision layout

# Geometry-critical parts, anchored by PAD position with auto-solved rotation.
# ref -> (pad-anchored target, {pad: expected offset from pad1 after rotation})
# J1 defines where the Pi sits: pad1 = Pi header pin1; even row toward Pi edge
# (top, -y); pins increase along +x. Pi mounting holes in MOUNTING must match.
# J1 is flipped to the board bottom: the Pi stacks BENEATH the carrier via an
# extra-tall (19.5mm) stacking header, HAT-style, clearing its USB/ETH tower.
# Viewed from the carrier top, the Pi below has even pins toward its board
# edge (-y) and pins increasing +x — reachable only with the bottom-side flip.
ANCHORED = {
    "J1": ((41.37 + 58, 26.77), {"2": (0, -2.54), "3": (2.54, 0)}, True),
    "U1": ((89.0 + 58, 33.0), {"2": (-2.54, 0), "40": (0, 17.78)}, False),  # Pico horizontal, pad1 right
}

# New power stage (absolute coords in the new left band, x 0..56, NOT shifted)
POWER_PLACE = {
    # A switch column (x=8) and mirrored B column (x=48); high pair on top
    "Q3": (8.0, 32.0, 270), "Q4": (8.0, 44.0, 270),
    "Q5": (8.0, 62.0, 270), "Q6": (8.0, 74.0, 270),
    "Q7": (48.0, 32.0, 90), "Q8": (48.0, 44.0, 90),
    "Q9": (48.0, 62.0, 90), "Q10": (48.0, 74.0, 90),
    # vertical-mount gate resistors outboard of each column (at the G pads)
    "R22": (3.2, 26.0, 90), "R23": (3.2, 40.0, 90),
    "R24": (59.0, 90.0, 90), "R25": (59.0, 103.0, 90),
    "R26": (54.8, 30.0, 90), "R27": (54.8, 44.0, 90),
    "R28": (54.8, 60.0, 90), "R29": (54.8, 74.0, 90),
    # battery entry + hall sensor, top of the band
    "J18": (11.0, 14.0, 0),
    "U10": (30.0, 14.0, 180),
    # bulk + clamp on the centre spine
    "C18": (31.0, 50.0, 0), "C19": (31.0, 72.0, 0),
    "D15": (32.0, 86.0, 0), "C20": (27.3, 96.5, 270),
    # lugs
    "J19": (11.0, 90.0, 0), "J20": (45.0, 90.0, 0), "J21": (11.0, 105.0, 0),
    # driver block at the band bottom
    "U9": (33.0, 107.0, 270),
    "R30": (46.0, 112.0, 90), "R32": (55.5, 104.0, 90),
    "C16": (28.5, 116.5, 180), "C17": (37.3, 114.3, 90),
    "D12": (23.8, 94.0, 90), "D13": (55.6, 90.0, 90),
    "C14": (20.0, 86.0, 90), "C15": (49.0, 81.0, 180),
    # HIP logic pulldowns + ACS/servo ADC conditioning live outside the band
    "R33": (95.0, 106.0, 0), "R34": (95.0, 110.0, 0),
    "R35": (95.0, 114.0, 0), "R36": (108.0, 110.0, 0),
    "R37": (94.0, 36.0, 90), "R38": (94.0, 50.0, 90),
    "C21": (94.0, 62.0, 90), "D14": (94.0, 68.0, 0),
    # servo bridge (old DIP zone; coords absolute)
    "U7": (108.0, 62.0, 0), "U8": (126.0, 62.0, 0),
    "R39": (111.0, 76.0, 0), "R40": (126.0, 74.0, 0),
    "C22": (140.0, 62.0, 0), "C23": (140.0, 70.0, 90),
    "J22": (133.0, 96.0, 0),
    "R18": (117.0, 86.0, 0), "R19": (117.0, 90.0, 0),
    "D8": (106.0, 86.0, 0), "C12": (96.0, 84.0, 90),
}

# Everything else: ref -> (center x, center y, rot), courtyard-center placed.
# These coordinates predate the power-stage revision and are shifted +XS at
# placement time.
# Coordinates were tiled against measured courtyard bboxes (see git history);
# the DRC courtyard check is the enforcement gate.
PLACE = {
    "J2": (4.5, 48.0, 0),         # GPIO breakout column, left edge
    # --- top band: JST row ---
    "J3":  (16.0, 7.0, 0), "J4": (29.5, 7.0, 0), "J5": (43.0, 7.0, 0),
    "J6":  (56.5, 7.0, 0), "J7": (70.0, 7.0, 0), "J8": (83.5, 7.0, 0),
    # --- right edge, above Pi zone ---
    "J11": (96.0, 15.5, 90), "J10": (96.0, 36.0, 90),
    "R20": (86.0, 12.0, 0), "R21": (86.0, 15.5, 0),
    "D10": (86.0, 19.0, 0), "D11": (90.5, 19.0, 0),
    # --- LED row + resistors ---
    "LED1": (22.0, 15.0, 0), "LED2": (35.0, 15.0, 0), "LED3": (48.0, 15.0, 0),
    "LED4": (61.0, 15.0, 0), "LED5": (74.0, 15.0, 0),
    "R2": (24.0, 20.5, 0), "R3": (37.0, 20.5, 0), "R4": (50.0, 20.5, 0),
    "R7": (63.0, 20.5, 0), "R13": (76.0, 20.5, 0),
    "R5": (11.0, 19.0, 0), "R6": (11.0, 15.0, 0),
    # --- left band ---
    "U5": (20.5, 35.0, 0), "U6": (20.5, 63.0, 0),
    # --- centre (Pi is BELOW the board here; top side is unrestricted) ---
    "C5": (94.0, 60.0, 90), "D6": (94.0, 66.0, 0),
    "R8": (46.0, 82.0, 0), "R9": (60.0, 82.0, 0), "R10": (74.0, 82.0, 0),
    "R11": (94.0, 50.0, 90), "R12": (98.0, 50.0, 90),
    # --- left-bottom: reverse protection chain ---
    "Q1": (8.0, 80.0, 0), "R1": (8.0, 88.0, 0),
    "D4": (22.0, 80.0, 0), "D5": (22.0, 85.0, 0),
    # --- conditioning strip y 78-88 ---
    # --- bottom row A: terminals, fuse, bulk caps ---
    "J16": (10.0, 96.0, 0), "F1": (22.0, 97.0, 90),
    "C1": (33.0, 96.0, 0), "C2": (46.0, 96.0, 0),
    "C3": (56.0, 96.0, 90), "C4": (63.0, 96.0, 90),
    "J17": (90.0, 96.0, 0),
    "F2": (86.0, 104.0, 0), "J9": (96.0, 106.0, 0),
    # --- bottom row B: headers + contactor terminal ---
    "J12": (18.0, 108.0, 90), }

MOUNTING = [
    # (footprint, x, y) — absolute, new 160x120 outline
    ("MountingHole_3.2mm_M3", 5.0, 5.0), ("MountingHole_3.2mm_M3", 155.0, 5.0),
    ("MountingHole_3.2mm_M3", 5.0, 115.0), ("MountingHole_3.2mm_M3", 155.0, 115.0),
    ("MountingHole_3.2mm_M3", 56.0, 5.0),
    ("MountingHole_2.7mm_M2.5", 94.5, 25.5), ("MountingHole_2.7mm_M2.5", 152.5, 25.5),
    ("MountingHole_2.7mm_M2.5", 94.5, 74.5), ("MountingHole_2.7mm_M2.5", 152.5, 74.5),
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
        dnp = '(property "dnp")' in body or '(field (name "DNP")' in body
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
    if lib == "vanchor-helm":
        libpath = f"{HW}/footprints.pretty"
    else:
        libpath = f"{STD_FP}/{lib}.pretty"
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
    (32 "B.Adhes" user "B.Adhesive")
    (33 "F.Adhes" user "F.Adhesive")
    (34 "B.Paste" user)
    (35 "F.Paste" user)
    (36 "B.SilkS" user "B.Silkscreen")
    (37 "F.SilkS" user "F.Silkscreen")
    (38 "B.Mask" user)
    (39 "F.Mask" user)
    (40 "Dwgs.User" user "User.Drawings")
    (41 "Cmts.User" user "User.Comments")
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
    # regenerate from a clean canvas every run
    with open(BOARD, "w") as f:
        f.write(SKELETON)
    board = pcbnew.LoadBoard(BOARD)

    comps, pin_net, net_names = parse_netlist(NETLIST)

    nets = {}
    for name in sorted(net_names):
        ni = pcbnew.NETINFO_ITEM(board, name)
        board.Add(ni)
        nets[name] = ni

    placed_refs = set(PLACE) | set(ANCHORED) | set(POWER_PLACE)
    missing = [r for r in comps if r not in placed_refs and not r.startswith("#")]
    unplaced = [r for r in placed_refs if r not in comps]
    if unplaced:
        raise SystemExit(f"placement refs not in netlist: {unplaced}")
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
                raise SystemExit(f"{ref}: no rotation satisfies pad-vector constraints")
            delta = mm(tx, ty) - pad_pos(fp, "1")
            fp.SetPosition(fp.GetPosition() + delta)
        elif ref in POWER_PLACE:
            x, y, rot = POWER_PLACE[ref]
            fp.SetOrientationDegrees(rot)
            court = fp.GetCourtyard(pcbnew.F_CrtYd)
            if court.OutlineCount():
                bb = court.BBox()
            else:
                bb = fp.GetBoundingBox(False)
            center = bb.GetCenter()
            fp.SetPosition(fp.GetPosition() + (mm(x, y) - center))
        else:
            x, y, rot = PLACE[ref]
            x += XS
            fp.SetOrientationDegrees(rot)
            court = fp.GetCourtyard(pcbnew.F_CrtYd)
            if court.OutlineCount():
                bb = court.BBox()
            else:
                bb = fp.GetBoundingBox(False)
            center = bb.GetCenter()
            fp.SetPosition(fp.GetPosition() + (mm(x, y) - center))

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

    # board outline
    pts = [(0, 0), (W, 0), (W, H), (0, H)]
    for i in range(4):
        seg = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_SEGMENT)
        seg.SetStart(mm(*pts[i]))
        seg.SetEnd(mm(*pts[(i + 1) % 4]))
        seg.SetLayer(pcbnew.Edge_Cuts)
        seg.SetWidth(pcbnew.FromMM(0.1))
        board.Add(seg)

    def pad_xy(ref, num):
        for fp in board.GetFootprints():
            if fp.GetReference() == ref:
                p = pad_pos(fp, num)
                return pcbnew.ToMM(p.x) - OX, pcbnew.ToMM(p.y) - OY
        raise SystemExit(f"no footprint {ref}")

    def add_zone(net, layer, pts, priority=0, solid=False):
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
        return zone

    def band_with_fingers(y_top, y_bot, x_l, x_r, finger_pads, half_w=1.1):
        """Rectangle band plus vertical fingers reaching the listed pad centres
        (fingers keep 0.4mm+ to the neighbouring 2.54mm-pitch pads)."""
        pts = [(x_l, y_top), (x_r, y_top), (x_r, y_bot)]
        below = [rp for rp in finger_pads if pad_xy(*rp)[1] >= y_bot]
        above = [rp for rp in finger_pads if pad_xy(*rp)[1] < y_top]
        for ref, num in sorted(below, key=lambda rp: -pad_xy(*rp)[0]):
            px, py = pad_xy(ref, num)
            pts += [(px + half_w, y_bot), (px + half_w, py + half_w),
                    (px - half_w, py + half_w), (px - half_w, y_bot)]
        pts.append((x_l, y_bot))
        pts.append((x_l, y_top))
        for ref, num in sorted(above, key=lambda rp: pad_xy(*rp)[0]):
            px, py = pad_xy(ref, num)
            pts += [(px - half_w, y_top), (px - half_w, py - half_w),
                    (px + half_w, py - half_w), (px + half_w, y_top)]
        return pts

    # ---- power-stage copper (2oz, solid zones) ----
    # Mirrored columns: A switch at x=8, B at x=48; VBRIDGE centre spine on
    # both layers with B-side fingers to the high-side drains; MOTOR rails on
    # F (paralleled on B below the finger band) with arms to the bolt lugs;
    # low-side sources land in the solid B-side GND plane.
    zprio = [10]

    def pz(net, layer, pts):
        zprio[0] += 1
        add_zone(net, layer, pts, zprio[0], solid=True)

    def fingers_h(rail_x0, rail_x1, pads, half_w=1.1):
        """Fingers span the full rail width so the same-net fills merge."""
        polys = []
        for ref, num in pads:
            px, py = pad_xy(ref, num)
            x0 = min(px - half_w, rail_x0)
            x1 = max(px + half_w, rail_x1)
            polys.append([(x0, py - half_w), (x1, py - half_w),
                          (x1, py + half_w), (x0, py + half_w)])
        return polys

    def rect(x0, y0, x1, y1):
        return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]

    # VBRIDGE: centre spine (F short, B long incl. clamp/bulk pads), top wing
    # under the ACS, B fingers to the four high-side drains
    pz("VBRIDGE", pcbnew.F_Cu, rect(26.4, 29, 32, 96))
    pz("VBRIDGE", pcbnew.F_Cu, rect(31, 16, 40.2, 24))    # ACS IP- patch
    pz("VBRIDGE", pcbnew.B_Cu, rect(31, 16, 40.2, 24))
    pz("VBRIDGE", pcbnew.B_Cu, rect(26.4, 6, 32, 96))
    for poly in fingers_h(26.4, 32, [("Q3", "2"), ("Q4", "2"), ("Q7", "2"), ("Q8", "2")]):
        pz("VBRIDGE", pcbnew.B_Cu, poly)

    # MOTOR rails + lug arms; F fingers to high-side sources / low-side drains
    pz("MOTOR_A", pcbnew.F_Cu, rect(11, 31, 18, 82))
    pz("MOTOR_A", pcbnew.F_Cu, rect(4, 78.5, 18, 98))
    pz("MOTOR_A", pcbnew.B_Cu, rect(11, 42, 18, 82))
    pz("MOTOR_A", pcbnew.B_Cu, rect(4, 78.5, 18, 98))
    for poly in fingers_h(11, 18, [("Q3", "3"), ("Q4", "3"), ("Q5", "2"), ("Q6", "2")]):
        pz("MOTOR_A", pcbnew.F_Cu, poly)

    pz("MOTOR_B", pcbnew.F_Cu, rect(38, 27.4, 45, 82))
    pz("MOTOR_B", pcbnew.F_Cu, rect(38, 78.5, 52, 98))
    pz("MOTOR_B", pcbnew.B_Cu, rect(38, 42, 45, 82))
    pz("MOTOR_B", pcbnew.B_Cu, rect(38, 78.5, 52, 98))
    for poly in fingers_h(38, 45, [("Q7", "3"), ("Q8", "3"), ("Q9", "2"), ("Q10", "2")]):
        pz("MOTOR_B", pcbnew.F_Cu, poly)

    # battery pocket (lug + ACS IP+) and GND pocket (lug)
    pz("VBAT_PWR", pcbnew.F_Cu, rect(1, 1, 20, 18))
    pz("VBAT_PWR", pcbnew.F_Cu, rect(19, 12, 27.9, 28.4))  # reaches ACS IP+
    pz("VBAT_PWR", pcbnew.B_Cu, rect(1, 1, 20, 18))
    pz("VBAT_PWR", pcbnew.B_Cu, rect(19, 12, 27.9, 28.4))
    if os.environ.get("BASE_GND") != "0":
        pz("GND", pcbnew.F_Cu, rect(1, 98.6, 19, 114))
        pz("GND", pcbnew.F_Cu, rect(25.5, 96.8, 35, 101.4))  # C20 GND relief
        # solid GND plane over the whole power band on B
        add_zone("GND", pcbnew.B_Cu, rect(0.6, 0.6, 56, 119.4), 1, solid=True)

    # ---- pre-laid power tracks (freerouting keeps existing wiring fixed;
    # they guarantee net continuity even where signal tracks slice the fills) ----
    def add_track(net, layer, x0, y0, x1, y1, w):
        t = pcbnew.PCB_TRACK(board)
        t.SetStart(mm(x0, y0))
        t.SetEnd(mm(x1, y1))
        t.SetWidth(pcbnew.FromMM(w))
        t.SetLayer(layer)
        t.SetNet(nets[net])
        board.Add(t)

    def chain(net, layer, pts, w):
        for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
            if abs(x1 - x0) < 0.01 and abs(y1 - y0) < 0.01:
                continue   # zero-length segments hang freerouting
            add_track(net, layer, x0, y0, x1, y1, w)

    # STRIP env: comma list of chains to include (aho,alo,bho,del,p12,gnd1,j14)
    # or unset = all
    strip_sel = os.environ.get("STRIP", "aho,alo,bho,del,p12,gnd1,j14").split(",")

    def want(k):
        return k in strip_sel

    # VBRIDGE spine both layers + stubs
    chain("VBRIDGE", pcbnew.B_Cu, [(29.2, 31), (29.2, 94)], 5.0)
    chain("VBRIDGE", pcbnew.F_Cu, [(29.2, 31), (29.2, 94)], 5.0)
    chain("VBRIDGE", pcbnew.B_Cu, [(32, 20), (32, 32)], 2.5)  # patch->spine link
    for ref in ("Q3", "Q4", "Q7", "Q8"):
        px, py = pad_xy(ref, "2")
        add_track("VBRIDGE", pcbnew.B_Cu, px, py, 29.2, py, 2.2)
    for ref, num in (("C18", "1"), ("C19", "1"), ("D15", "1")):
        px, py = pad_xy(ref, num)
        add_track("VBRIDGE", pcbnew.F_Cu, px, py, 29.2, py, 1.8)

    # MOTOR rails + lug drops + FET stubs
    chain("MOTOR_A", pcbnew.F_Cu, [(14.5, 33), (14.5, 89), (11, 89), (11, 90)], 5.0)
    chain("MOTOR_A", pcbnew.B_Cu, [(14.5, 48.5), (14.5, 89), (11, 89), (11, 90)], 5.0)
    for ref, num in (("Q3", "3"), ("Q4", "3"), ("Q5", "2"), ("Q6", "2")):
        px, py = pad_xy(ref, num)
        add_track("MOTOR_A", pcbnew.F_Cu, px, py, 14.5, py, 2.2)
    px, py = pad_xy("C14", "2")
    add_track("MOTOR_A", pcbnew.F_Cu, px, py, 14.5, py, 1.8)

    chain("MOTOR_B", pcbnew.F_Cu, [(41.5, 30), (41.5, 89), (45, 89), (45, 90)], 5.0)
    chain("MOTOR_B", pcbnew.B_Cu, [(41.5, 48.5), (41.5, 89), (45, 89), (45, 90)], 5.0)
    for ref, num in (("Q7", "3"), ("Q8", "3"), ("Q9", "2"), ("Q10", "2")):
        px, py = pad_xy(ref, num)
        add_track("MOTOR_B", pcbnew.F_Cu, px, py, 41.5, py, 2.2)
    px, py = pad_xy("C15", "2")
    add_track("MOTOR_B", pcbnew.F_Cu, px, py, 41.5, py, 1.8)

    # GND: lug feeder into the band plane (low-side sources connect via the
    # solid priority-1 B plane directly)
    chain("GND", pcbnew.B_Cu, [(11, 105), (11, 101)], 5.6)

    # VBAT: lug -> ACS IP+
    bx, by = pad_xy("J18", "1")
    chain("VBAT_PWR", pcbnew.F_Cu, [(bx, by), (23, by), (23, 19)], 4.0)
    chain("VBAT_PWR", pcbnew.B_Cu, [(bx, by), (23, by), (23, 19)], 4.0)

    # HIP4082 AHS/BHS phase-sense pins into the motor arms (plane nets)
    p11x, p11y = pad_xy("U9", "11")
    chain("MOTOR_A", pcbnew.F_Cu,
          [(p11x, p11y), (p11x, 119.1), (2.5, 119.1), (2.5, 95), (6, 95)], 0.5)
    p15x, p15y = pad_xy("U9", "15")
    chain("MOTOR_B", pcbnew.F_Cu,
          [(p15x, p15y), (p15x, 119.1), (52.9, 119.1), (52.9, 95), (50, 95)], 0.5)

    # +12V trunk from BUCK2 outer VOUT pad to the servo bridge VS pin
    u6pads = [pad for fp in board.GetFootprints() if fp.GetReference() == "U6"
              for pad in fp.Pads() if pad.GetNumber() == "3"]
    u6p = max(u6pads, key=lambda pad: pad.GetPosition().y).GetPosition()
    u6x, u6y = pcbnew.ToMM(u6p.x) - OX, pcbnew.ToMM(u6p.y) - OY
    u7x, u7y = pad_xy("U7", "7")
    chain("+12V", pcbnew.F_Cu,
          [(u6x, u6y), (u6x, 78.1), (u7x, 78.1), (u7x, u7y + 0.4)], 0.6)
    # west leg: feeds the bootstrap diode anodes (D13 direct, D12 via spur)
    d13x, d13y = pad_xy("D13", "2")
    chain("+12V", pcbnew.F_Cu,
          [(u6x, u6y), (u6x, 76.4), (58.5, 76.4), (58.5, d13y), (d13x, d13y)], 0.6)
    c17x2, c17y2 = pad_xy("C17", "1")
    d12x, d12y = pad_xy("D12", "2")
    chain("+12V", pcbnew.F_Cu,
          [(c17x2, c17y2), (21.9, c17y2), (21.9, d12y), (d12x, d12y)], 0.5)

    # +12V for the +12V LED resistor (unroutable for the autorouter 5x)
    r4x, r4y = pad_xy("R4", "1")
    j17x, j17y = pad_xy("J17", "2")
    if want("p12"):
        chain("+12V", pcbnew.F_Cu,
              [(r4x, r4y), (r4x, 9.6), (157.7, 9.6), (157.7, 90),
               (j17x, 90), (j17x, j17y)], 0.5)

    if want("j14"):
        # J1 pin 14 GND: hand-routed stub into open pour area (no via — a
        # pre-laid via makes freerouting 1.9 hang in DSN preprocessing)
        j14x, j14y = pad_xy("J1", "14")
        chain("GND", pcbnew.F_Cu,
              [(j14x, j14y), (j14x, 22.6), (98, 22.6), (98, 19.2)], 0.5)

    # ---- driver-strip pre-lays (coherent lane plan; no crossings) ----

    # Lanes: F y106.4 = +12V inter-row feed; F y104.9 = DEL; F y110.6/x53.9 =
    # +12V island link; B y112.5/x21.8/y119.1/x1.0 = AHO (outer-left);
    # B y113.6/x21.15/y118.35/x1.7 = ALO (inner-left); B x41.9/y119.1/x57.3 =
    # BHO; F x29.2 & x39.4..52.9 = the two AHS/BHS sense runs.
    p10x, p10y = pad_xy("U9", "10")
    r22x, r22y = pad_xy("R22", "1")
    r23x, r23y = pad_xy("R23", "1")
    if want("aho"):
        chain("/thrust/AHO", pcbnew.B_Cu,
              [(p10x, p10y), (p10x, 112.5), (18.75, 112.5), (18.75, 119.1),
               (1.0, 119.1), (1.0, r22y), (r22x, r22y)], 0.35)
        add_track("/thrust/AHO", pcbnew.B_Cu, 1.0, r23y, r23x, r23y, 0.35)

    p13x, p13y = pad_xy("U9", "13")
    r24x, r24y = pad_xy("R24", "1")
    r25x, r25y = pad_xy("R25", "1")
    if want("alo"):
        # ALO exits east around J12/C1, descends at x92.3, approaches each
        # gate resistor from the side away from its GND pad
        _, r24gy = pad_xy("R24", "2")
        _, r25gy = pad_xy("R25", "2")
        a24 = r24y + (2.3 if r24y > r24gy else -2.3)
        a25 = r25y + (2.3 if r25y > r25gy else -2.3)
        chain("/thrust/ALO", pcbnew.B_Cu,
              [(p13x, p13y), (p13x, 118.5), (92.3, 118.5), (92.3, a24),
               (59, a24), (59, r24y)], 0.35)
        chain("/thrust/ALO", pcbnew.B_Cu,
              [(92.3, a25), (60.4, a25), (60.4, r25y), (r25x, r25y)], 0.35)

    p16x, p16y = pad_xy("U9", "16")
    r26x, r26y = pad_xy("R26", "1")
    r27x, r27y = pad_xy("R27", "1")
    if want("bho"):
        chain("/thrust/BHO", pcbnew.F_Cu,
              [(p16x, p16y), (p16x, 115.5), (57.3, 115.5), (57.3, r26y), (r26x, r26y)], 0.35)
        add_track("/thrust/BHO", pcbnew.F_Cu, 57.3, r27y, r27x, r27y, 0.35)

    # DEL resistor: inter-row lane above the +12V feed onto R30's DEL pad,
    # approaching so we never cross its GND pad
    p5x, p5y = pad_xy("U9", "5")
    r30x, r30y = pad_xy("R30", "1")
    _, r30gy = pad_xy("R30", "2")
    if want("del"):
        if abs(r30y - 104.9) <= abs(r30gy - 104.9):
            chain("/thrust/DEL", pcbnew.F_Cu,
                  [(p5x, p5y), (p5x, 104.9), (r30x, 104.9), (r30x, r30y)], 0.4)
        else:
            chain("/thrust/DEL", pcbnew.F_Cu,
                  [(p5x, p5y), (p5x, 104.9), (50.5, 104.9), (50.5, r30y),
                   (r30x, r30y)], 0.4)

    # +12V: C16/C17 stack share a pad column; inter-row feed to U9.12; island
    # link runs east between the sense drops, then down the x53.9 lane
    c16x, c16y = pad_xy("C16", "1")
    c17x, c17y = pad_xy("C17", "1")
    u9x, u9y = pad_xy("U9", "12")
    if want("p12"):
        # C16 (bottom row) feeds U9.12 east of the A-sense drop; C17 joins
        # along y117.8; island link runs the inter-row + x53.9 lane
        chain("+12V", pcbnew.F_Cu,
              [(c16x, c16y), (c16x, 112.4), (u9x, 112.4), (u9x, u9y)], 0.5)
        chain("+12V", pcbnew.F_Cu,
              [(c17x, c17y), (35.8, c17y), (35.8, 112.4), (u9x, 112.4)], 0.5)
        chain("+12V", pcbnew.F_Cu,
              [(u9x, u9y), (u9x, 106.4), (44.3, 106.4), (44.3, 110.2),
               (51.9, 110.2)], 0.4)
        chain("+12V", pcbnew.B_Cu, [(51.9, 110.2), (53.9, 110.2)], 0.4)
        chain("+12V", pcbnew.F_Cu,
              [(53.9, 110.2), (53.9, 82.7), (58.5, 82.7), (58.5, 84.9)], 0.4)
    if want("gnd1"):
        # GND band<->base bridge above the escape seam
        add_track("GND", pcbnew.B_Cu, 52, 16, 70, 16, 2.0)

    # +12V for the +12V LED resistor (unroutable for the autorouter 5x)
    r4x, r4y = pad_xy("R4", "1")
    j17x, j17y = pad_xy("J17", "2")
    if want("p12"):
        chain("+12V", pcbnew.F_Cu,
              [(r4x, r4y), (r4x, 9.6), (157.7, 9.6), (157.7, 90),
               (j17x, 90), (j17x, j17y)], 0.5)

    if want("j14"):
        # J1 pin 14 GND: hand-routed stub into open pour area (no via — a
        # pre-laid via makes freerouting 1.9 hang in DSN preprocessing)
        j14x, j14y = pad_xy("J1", "14")
        chain("GND", pcbnew.F_Cu,
              [(j14x, j14y), (j14x, 22.6), (98, 22.6), (98, 19.2)], 0.5)

    # top-edge routing keepout (freerouting keeps planting vias at the edge)
    for klayer in (pcbnew.F_Cu, pcbnew.B_Cu):
        ka = pcbnew.ZONE(board)
        ka.SetIsRuleArea(True)
        ka.SetDoNotAllowTracks(True)
        ka.SetDoNotAllowVias(True)
        ka.SetDoNotAllowZoneFills(False)
        ka.SetLayer(klayer)
        ko = ka.Outline()
        ko.NewOutline()
        for px, py in [(58, 0), (158, 0), (158, 1.3), (58, 1.3)]:
            ko.Append(mm(px, py))
        board.Add(ka)

    # GND pours both sides (base planes). BASE_GND=0 omits them so the DSN
    # export makes freerouting route logic-GND pads as tracks (the power-band
    # GND planes above always stay: the low-side FETs need them).
    base_layers = () if os.environ.get("BASE_GND") == "0" else (pcbnew.F_Cu, pcbnew.B_Cu)
    for layer in base_layers:
        zone = pcbnew.ZONE(board)
        zone.SetLayer(layer)
        zone.SetNet(nets["GND"])
        outline = zone.Outline()
        outline.NewOutline()
        for px, py in [(0, 0), (W, 0), (W, H), (0, H)]:
            outline.Append(mm(px, py))
        zone.SetAssignedPriority(0)
        zone.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL)
        zone.SetMinThickness(pcbnew.FromMM(0.25))
        zone.SetThermalReliefGap(pcbnew.FromMM(0.5))
        zone.SetThermalReliefSpokeWidth(pcbnew.FromMM(1.0))
        zone.SetLocalClearance(pcbnew.FromMM(0.5))
        board.Add(zone)

    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    pcbnew.SaveBoard(BOARD, board)

    # report
    print(f"placed {len([r for r in comps if not r.startswith('#')])} footprints, "
          f"{len(MOUNTING)} mounting holes, {len(nets)} nets")


if __name__ == "__main__":
    main()
