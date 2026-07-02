#!/usr/bin/env python3
"""Build vanchor-thrust.kicad_pcb (95x75mm) from netlist + placement.

Layout: BATT+ / BATT- lugs on the left edge, MOT_A / MOT_B lugs right.
BTN quad in the middle (U1/U3 top row = A side feeding MOT_A, U2/U4 bottom
row = B side). VBAT band across the top + a center spine; MOT zones east to
the lugs; GND via base pours (import script). F.Mask/B.Mask rect strips
expose bare copper along every power lane so the builder can solder copper
cable/braid on top instead of paying for thick copper.
"""
import os
import re
import sys

import pcbnew

DRV = "/config/vanchor-pcb/boards/thrust-driver"
HELM = "/config/vanchor-pcb/boards/helm"
NETLIST = f"{DRV}/vanchor-thrust.net"
BOARD = f"{DRV}/vanchor-thrust.kicad_pcb"
STD_FP = "/usr/share/kicad/footprints"

OX, OY = 20.0, 20.0
W, H = 95.0, 92.0

PLACE = {
    "J1": (3.5, 37.0, 0),
    "R1": (15.0, 24.0, 0), "R2": (15.0, 50.0, 0),
    "U1": (34.0, 24.0, 0), "U3": (54.0, 24.0, 0),
    "U2": (34.0, 50.0, 0), "U4": (54.0, 50.0, 0),
    "R3": (33.0, 34.0, 0), "R5": (33.0, 38.0, 0), "R4": (33.0, 42.0, 0),
    "R7": (55.0, 34.0, 0), "R6": (55.0, 38.0, 0), "R8": (55.0, 42.0, 0),
    "C1": (72.5, 37.0, 0), "C2": (15.0, 37.0, 0),
    "D2": (24.0, 8.0, 0), "C3": (34.0, 8.0, 0), "C5": (46.0, 8.0, 0), "C4": (58.0, 8.0, 0),
    "D1": (21.5, 63.6, 0), "R9": (34.0, 68.0, 0),
    "J2": (10.0, 12.0, 0), "J3": (10.0, 63.0, 0),
    # N2K node provision (v1.1): DNP Pico/reg/ADC-series + CAN/N2K connectors
    "U5": (40.0, 81.0, 90), "U6": (7.0, 78.5, 0),
    "J6": (75.0, 86.0, 0), "J7": (87.0, 80.5, 90),
    "R10": (81.0, 86.5, 90), "R11": (84.8, 89.3, 90),
    "R12": (22.8, 55.0, 270), "R13": (26.2, 58.2, 270),
    "J4": (85.0, 12.0, 0), "J5": (85.0, 63.0, 0),
}

MOUNTING = [
    ("MountingHole_3.2mm_M3", 47.0, 68.0), ("MountingHole_3.2mm_M3", 58.0, 68.0),
    ("MountingHole_3.2mm_M3", 68.0, 8.0), ("MountingHole_3.2mm_M3", 91.5, 71.0),
]

# silkscreen legends
SILK_TEXTS = [
    (3.5, 24.0, "HELM J13", 1.0, 0),
    (10.0, 49.0, "RPWM LPWM REN LEN RIS LIS 5V GND", 0.8, 90),
    (10.0, 4.0, "BATT+", 1.2, 0), (10.0, 71.0, "BATT-", 1.2, 0),
    (85.0, 4.0, "MOT A", 1.2, 0), (85.0, 71.0, "MOT B", 1.2, 0),
    (46.0, 13.2, "12-24V  BASE:U1+U2 30A  HIGH PWR:+U3/U4 50A", 1.0, 0),
    (46.0, 63.5, "SOLDER CABLE/BRAID ON EXPOSED LANES FOR >30A", 1.0, 0),
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
        comps[ref] = {"fp": fp.group(1) if fp else "", "value": val.group(1) if val else "",
                      "dnp": '(property "dnp")' in body}
    pin_net = {}
    net_names = set()
    for m in re.finditer(r'\(net\s+\(code\s+"?\d+"?\)\s+\(name\s+"([^"]+)"\)(.*?)(?=\(net\s+\(code|\Z)', text, re.S):
        net_names.add(m.group(1))
        for n in re.finditer(r'\(node\s+\(ref\s+"([^"]+)"\)\s+\(pin\s+"([^"]+)"\)', m.group(2)):
            pin_net[(n.group(1), n.group(2))] = m.group(1)
    return comps, pin_net, net_names


def load_footprint(fpid):
    lib, name = fpid.split(":", 1)
    libpath = f"{HELM}/footprints.pretty" if lib == "vanchor-helm" else f"{STD_FP}/{lib}.pretty"
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

    placed = set(PLACE)
    missing = [r for r in comps if r not in placed and not r.startswith("#")]
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
        st.SetTextThickness(pcbnew.FromMM(0.15))
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

    def rect(x0, y0, x1, y1):
        return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]

    def pz(net, layer, pts):
        zprio[0] += 1
        zone = pcbnew.ZONE(board)
        zone.SetLayer(layer)
        zone.SetNet(nets[net])
        o = zone.Outline()
        o.NewOutline()
        for px, py in pts:
            o.Append(mm(px, py))
        zone.SetAssignedPriority(zprio[0])
        zone.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL)
        zone.SetMinThickness(pcbnew.FromMM(0.25))
        zone.SetThermalReliefGap(pcbnew.FromMM(0.5))
        zone.SetThermalReliefSpokeWidth(pcbnew.FromMM(1.0))
        zone.SetLocalClearance(pcbnew.FromMM(0.5))
        board.Add(zone)

    # VBAT: top band + center spine down between the BTN columns
    pz("VBAT", pcbnew.F_Cu, rect(2, 2, 76, 15))
    pz("VBAT", pcbnew.F_Cu, rect(41.6, 13.5, 46.4, 58))
    pz("VBAT", pcbnew.B_Cu, rect(2, 2, 76, 15))
    # MOT_A: over the top-row tabs, east to the lug
    pz("MOT_A", pcbnew.F_Cu, rect(33, 19, 92, 30.2))
    pz("MOT_A", pcbnew.F_Cu, rect(77, 4, 92, 29))
    # MOT_B mirrored at the bottom row
    pz("MOT_B", pcbnew.F_Cu, rect(33, 43.8, 92, 55))
    pz("MOT_B", pcbnew.F_Cu, rect(77, 46, 92, 71))
    # GND helpers: bottom band on B tying the BATT- lug region
    pz("GND", pcbnew.B_Cu, rect(2, 58, 76, 73))

    def add_track(net, layer, x0, y0, x1, y1, w):
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

    # VBAT into the VS pins (pin 7, bottom of each pin column) via the spine
    for ref in ("U1", "U3", "U2", "U4"):
        px, py = pad_xy(ref, "7")
        yl = py + 3.6          # below the 10.8mm-tall tab
        add_track("VBAT", pcbnew.F_Cu, 44, yl, px, yl, 2.0)
        add_track("VBAT", pcbnew.F_Cu, px, yl, px, py + 0.3, 1.2)
    # pad-4 column legs sit west of the MOT zones: strap them in
    add_track("MOT_A", pcbnew.F_Cu, 28.23, 24, 33.5, 24, 1.1)
    add_track("MOT_B", pcbnew.F_Cu, 28.23, 50, 33.5, 50, 1.1)

    # ---------------- solder-lane mask openings ----------------
    def mask_lane(layer, x0, y0, x1, y1):
        sh = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_RECTANGLE)
        sh.SetStart(mm(x0, y0))
        sh.SetEnd(mm(x1, y1))
        sh.SetLayer(layer)
        sh.SetFilled(True)
        sh.SetWidth(0)
        board.Add(sh)

    mask_lane(pcbnew.F_Mask, 16, 6.5, 72, 10.5)     # VBAT band
    mask_lane(pcbnew.F_Mask, 42.1, 16, 45.9, 56)    # VBAT spine
    mask_lane(pcbnew.F_Mask, 40, 22, 80, 26)        # MOT_A lane
    mask_lane(pcbnew.F_Mask, 82, 8, 86, 26)         # MOT_A arm
    mask_lane(pcbnew.F_Mask, 40, 48, 80, 52)        # MOT_B lane
    mask_lane(pcbnew.F_Mask, 82, 48, 86, 66)        # MOT_B arm
    mask_lane(pcbnew.B_Mask, 16, 62, 72, 68)        # GND band (B)

    if os.environ.get("BASE_GND") != "0":
        for layer in (pcbnew.F_Cu, pcbnew.B_Cu):
            zone = pcbnew.ZONE(board)
            zone.SetLayer(layer)
            zone.SetNet(nets["GND"])
            o = zone.Outline()
            o.NewOutline()
            for px, py in rect(0, 0, W, H):
                o.Append(mm(px, py))
            zone.SetAssignedPriority(0)
            zone.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL)
            zone.SetMinThickness(pcbnew.FromMM(0.25))
            board.Add(zone)

    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    pcbnew.SaveBoard(BOARD, board)
    print(f"placed {len([r for r in comps if not r.startswith('#')])} footprints, {len(nets)} nets")


if __name__ == "__main__":
    main()
