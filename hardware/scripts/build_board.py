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
W, H = 100.0, 120.0     # board size

# Geometry-critical parts, anchored by PAD position with auto-solved rotation.
# ref -> (pad-anchored target, {pad: expected offset from pad1 after rotation})
# J1 defines where the Pi sits: pad1 = Pi header pin1; even row toward Pi edge
# (top, -y); pins increase along +x. Pi mounting holes in MOUNTING must match.
# J1 is flipped to the board bottom: the Pi stacks BENEATH the carrier via an
# extra-tall (19.5mm) stacking header, HAT-style, clearing its USB/ETH tower.
# Viewed from the carrier top, the Pi below has even pins toward its board
# edge (-y) and pins increasing +x — reachable only with the bottom-side flip.
ANCHORED = {
    "J1": ((41.37, 26.77), {"2": (0, -2.54), "3": (2.54, 0)}, True),
    "U1": ((89.0, 33.0), {"2": (-2.54, 0), "40": (0, 17.78)}, False),  # Pico horizontal, pad1 right
}

# Everything else: ref -> (center x, center y, rot), courtyard-center placed.
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
    "U2": (48.0, 62.0, 270), "U3": (63.0, 62.0, 270), "U4": (75.0, 62.0, 270),
    "C6": (48.0, 70.0, 0), "C7": (62.0, 70.0, 0), "C9": (75.0, 70.0, 0),
    "R14": (84.0, 62.0, 90), "R15": (88.0, 62.0, 90),
    "C5": (94.0, 60.0, 90), "D6": (94.0, 66.0, 0),
    "R8": (46.0, 74.0, 0), "R9": (60.0, 74.0, 0), "R10": (74.0, 74.0, 0),
    "R11": (94.0, 50.0, 90), "R12": (98.0, 50.0, 90),
    # --- left-bottom: reverse protection chain ---
    "Q1": (8.0, 80.0, 0), "R1": (8.0, 85.5, 0),
    "D4": (22.0, 80.0, 0), "D5": (22.0, 85.0, 0),
    # --- conditioning strip y 78-88 ---
    "R18": (41.0, 80.0, 0), "R19": (41.0, 84.0, 0),
    "D8": (50.0, 80.0, 0), "D9": (50.0, 84.0, 0),
    "C12": (54.5, 81.0, 90), "C13": (58.0, 81.0, 90),
    "Q2": (66.0, 80.0, 0), "R16": (66.0, 86.5, 0),
    "R17": (74.0, 84.0, 90), "D7": (81.0, 83.5, 90),
    "JP1": (88.0, 79.0, 0), "C8": (91.0, 84.0, 90),
    "C10": (86.5, 84.0, 90), "C11": (96.7, 84.0, 90),
    # --- bottom row A: terminals, fuse, bulk caps ---
    "J16": (10.0, 96.0, 0), "F1": (22.0, 97.0, 90),
    "C1": (33.0, 96.0, 0), "C2": (46.0, 96.0, 0),
    "C3": (56.0, 96.0, 90), "C4": (63.0, 96.0, 90),
    "J13": (75.0, 96.0, 0), "J17": (90.0, 96.0, 0),
    "F2": (86.0, 104.0, 0), "J9": (96.0, 106.0, 0),
    # --- bottom row B: headers + contactor terminal ---
    "J12": (18.0, 108.0, 90), "J15": (44.0, 108.0, 90), "J14": (66.0, 109.0, 0),
}

MOUNTING = [
    # (footprint, x, y)
    ("MountingHole_3.2mm_M3", 5.0, 5.0), ("MountingHole_3.2mm_M3", 95.0, 5.0),
    ("MountingHole_3.2mm_M3", 5.0, 115.0), ("MountingHole_3.2mm_M3", 95.0, 115.0),
    ("MountingHole_2.7mm_M2.5", 36.5, 25.5), ("MountingHole_2.7mm_M2.5", 94.5, 25.5),
    ("MountingHole_2.7mm_M2.5", 36.5, 74.5), ("MountingHole_2.7mm_M2.5", 94.5, 74.5),
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


def main():
    board = pcbnew.LoadBoard(BOARD)

    comps, pin_net, net_names = parse_netlist(NETLIST)

    nets = {}
    for name in sorted(net_names):
        ni = pcbnew.NETINFO_ITEM(board, name)
        board.Add(ni)
        nets[name] = ni

    placed_refs = set(PLACE) | set(ANCHORED)
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
        else:
            x, y, rot = PLACE[ref]
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

    # GND pours both sides
    for layer in (pcbnew.F_Cu, pcbnew.B_Cu):
        zone = pcbnew.ZONE(board)
        zone.SetLayer(layer)
        zone.SetNet(nets["GND"])
        outline = zone.Outline()
        outline.NewOutline()
        for px, py in [(0, 0), (W, 0), (W, H), (0, H)]:
            outline.Append(mm(px, py))
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
