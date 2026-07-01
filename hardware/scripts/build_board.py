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
    "Q3": (8.0, 28.0, 270), "Q4": (8.0, 40.0, 270),
    "Q5": (8.0, 58.0, 270), "Q6": (8.0, 70.0, 270),
    "Q7": (48.0, 28.0, 90), "Q8": (48.0, 40.0, 90),
    "Q9": (48.0, 58.0, 90), "Q10": (48.0, 70.0, 90),
    # vertical-mount gate resistors outboard of each column (at the G pads)
    "R22": (3.2, 25.5, 90), "R23": (3.2, 40.5, 90),
    "R24": (3.2, 55.5, 90), "R25": (3.2, 70.5, 90),
    "R26": (54.8, 25.5, 90), "R27": (54.8, 40.5, 90),
    "R28": (54.8, 55.5, 90), "R29": (54.8, 70.5, 90),
    # battery entry + hall sensor, top of the band
    "J18": (11.0, 14.0, 0),
    "U10": (30.0, 15.0, 180),
    # bulk + clamp on the centre spine
    "C18": (28.0, 50.0, 0), "C19": (28.0, 72.0, 0),
    "D15": (32.0, 86.0, 180), "C20": (26.8, 96.5, 90),
    # lugs
    "J19": (11.0, 90.0, 0), "J20": (45.0, 90.0, 0), "J21": (11.0, 105.0, 0),
    # driver block at the band bottom
    "U9": (33.0, 107.0, 270),
    "R30": (48.0, 116.0, 0), "R32": (55.5, 104.0, 90),
    "C16": (20.0, 115.0, 90), "C17": (24.5, 116.0, 0),
    "D12": (35.0, 116.0, 0), "D13": (52.0, 104.0, 90),
    "C14": (20.0, 86.0, 90), "C15": (23.5, 86.0, 90),
    # HIP logic pulldowns + ACS/servo ADC conditioning live outside the band
    "R33": (95.0, 106.0, 0), "R34": (95.0, 110.0, 0),
    "R35": (95.0, 114.0, 0), "R36": (108.0, 110.0, 0),
    "R37": (94.0, 36.0, 90), "R38": (94.0, 50.0, 90),
    "C21": (94.0, 62.0, 90), "D14": (94.0, 68.0, 0),
    # servo bridge (old DIP zone; coords absolute)
    "U7": (108.0, 62.0, 0), "U8": (126.0, 62.0, 0),
    "R39": (108.0, 74.0, 0), "R40": (126.0, 74.0, 0),
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
    "Q1": (8.0, 80.0, 0), "R1": (8.0, 85.5, 0),
    "D4": (22.0, 80.0, 0), "D5": (22.0, 85.0, 0),
    # --- conditioning strip y 78-88 ---
    # --- bottom row A: terminals, fuse, bulk caps ---
    "F1": (22.0, 97.0, 90),
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
    ("MountingHole_3.2mm_M3", 56.0, 5.0), ("MountingHole_3.2mm_M3", 60.0, 115.0),
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
        polys = []
        for ref, num in pads:
            px, py = pad_xy(ref, num)
            if px > rail_x1:
                x0, x1 = rail_x1 - 0.5, px + half_w
            else:
                x0, x1 = px - half_w, rail_x0 + 0.5
            polys.append([(x0, py - half_w), (x1, py - half_w),
                          (x1, py + half_w), (x0, py + half_w)])
        return polys

    def rect(x0, y0, x1, y1):
        return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]

    # VBRIDGE: centre spine (F short, B long incl. clamp/bulk pads), top wing
    # under the ACS, B fingers to the four high-side drains
    pz("VBRIDGE", pcbnew.F_Cu, rect(26.4, 20, 32, 96))
    pz("VBRIDGE", pcbnew.F_Cu, rect(31, 20, 37.4, 28))    # ACS IP- patch
    pz("VBRIDGE", pcbnew.B_Cu, rect(31, 20, 37.4, 28))
    pz("VBRIDGE", pcbnew.B_Cu, rect(26.4, 6, 32, 96))
    for poly in fingers_h(26.4, 32, [("Q3", "2"), ("Q4", "2"), ("Q7", "2"), ("Q8", "2")]):
        pz("VBRIDGE", pcbnew.B_Cu, poly)

    # MOTOR rails + lug arms; F fingers to high-side sources / low-side drains
    pz("MOTOR_A", pcbnew.F_Cu, rect(11, 27, 18, 82))
    pz("MOTOR_A", pcbnew.F_Cu, rect(4, 82, 18, 98))
    pz("MOTOR_A", pcbnew.B_Cu, rect(11, 42, 18, 82))
    pz("MOTOR_A", pcbnew.B_Cu, rect(4, 82, 18, 98))
    for poly in fingers_h(11, 18, [("Q3", "3"), ("Q4", "3"), ("Q5", "2"), ("Q6", "2")]):
        pz("MOTOR_A", pcbnew.F_Cu, poly)

    pz("MOTOR_B", pcbnew.F_Cu, rect(38, 22, 45, 82))
    pz("MOTOR_B", pcbnew.F_Cu, rect(38, 82, 52, 98))
    pz("MOTOR_B", pcbnew.B_Cu, rect(38, 42, 45, 82))
    pz("MOTOR_B", pcbnew.B_Cu, rect(38, 82, 52, 98))
    for poly in fingers_h(38, 45, [("Q7", "3"), ("Q8", "3"), ("Q9", "2"), ("Q10", "2")]):
        pz("MOTOR_B", pcbnew.F_Cu, poly)

    # battery pocket (lug + ACS IP+) and GND pocket (lug)
    pz("VBAT_PWR", pcbnew.F_Cu, rect(1, 1, 20, 18))
    pz("VBAT_PWR", pcbnew.F_Cu, rect(19, 16, 25.8, 28.5))  # reaches ACS IP+
    pz("VBAT_PWR", pcbnew.B_Cu, rect(1, 1, 20, 18))
    pz("VBAT_PWR", pcbnew.B_Cu, rect(19, 16, 25.8, 28.5))
    pz("GND", pcbnew.F_Cu, rect(1, 98.6, 19, 114))
    pz("GND", pcbnew.F_Cu, rect(25.5, 96.8, 35, 101.4))  # C20 GND relief
    # solid GND plane over the whole power band on B
    add_zone("GND", pcbnew.B_Cu, rect(0.6, 0.6, 56, 119.4), 1, solid=True)

    # GND pours both sides (base planes)
    for layer in (pcbnew.F_Cu, pcbnew.B_Cu):
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
