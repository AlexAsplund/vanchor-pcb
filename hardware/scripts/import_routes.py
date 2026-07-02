#!/usr/bin/env python3
"""Import the freerouting .ses session, add GND stitching vias, refill, save."""
import pcbnew

BOARD = "/config/vanchor-pcb/hardware/vanchor-helm.kicad_pcb"
SES = "/config/vanchor-pcb/hardware/vanchor-helm.ses"
OX, OY = 20.0, 20.0

# The board file must be the exact BASE_GND=0 variant the DSN was exported
# from; the session replaces its routing 1:1. Base GND pours are added HERE,
# after import, so they never round-trip through freerouting.
board = pcbnew.LoadBoard(BOARD)
ok = pcbnew.ImportSpecctraSES(board, SES)
print("SES import:", ok)
if not ok:
    raise SystemExit(1)

W, H = 160.0, 120.0
have_base = any(z.GetNetname() == "GND" and not z.GetZoneName() and
                z.GetAssignedPriority() == 0 for z in board.Zones())
if not have_base:
    gndnet = board.GetNetsByName()["GND"]

    def add_gnd_zone(layer, pts, priority, solid):
        zone = pcbnew.ZONE(board)
        zone.SetLayer(layer)
        zone.SetNet(gndnet)
        outline = zone.Outline()
        outline.NewOutline()
        for px, py in pts:
            outline.Append(pcbnew.VECTOR2I_MM(OX + px, OY + py))
        zone.SetAssignedPriority(priority)
        zone.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL if solid
                              else pcbnew.ZONE_CONNECTION_THERMAL)
        zone.SetMinThickness(pcbnew.FromMM(0.25))
        zone.SetThermalReliefGap(pcbnew.FromMM(0.5))
        zone.SetThermalReliefSpokeWidth(pcbnew.FromMM(1.0))
        zone.SetLocalClearance(pcbnew.FromMM(0.5))
        board.Add(zone)

    # power-band GND copper (was omitted in the routable-GND export variant)

    for layer in (pcbnew.F_Cu, pcbnew.B_Cu):
        zone = pcbnew.ZONE(board)
        zone.SetLayer(layer)
        zone.SetNet(gndnet)
        outline = zone.Outline()
        outline.NewOutline()
        for px, py in [(0, 0), (W, 0), (W, H), (0, H)]:
            outline.Append(pcbnew.VECTOR2I_MM(OX + px, OY + py))
        zone.SetAssignedPriority(0)
        zone.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL)
        zone.SetMinThickness(pcbnew.FromMM(0.25))
        zone.SetThermalReliefGap(pcbnew.FromMM(0.5))
        zone.SetThermalReliefSpokeWidth(pcbnew.FromMM(1.0))
        zone.SetLocalClearance(pcbnew.FromMM(0.5))
        board.Add(zone)
    print("base GND pours added")

filler = pcbnew.ZONE_FILLER(board)
filler.Fill(board.Zones())

# GND stitching: grid vias wherever BOTH GND planes have copper (bridges pour
# fragments created by routed tracks; TH clearance handled by testing margin)
gnd = board.GetNetsByName()["GND"]
fz = [z for z in board.Zones() if z.GetNetname() == "GND" and z.IsOnLayer(pcbnew.F_Cu)]
bz = [z for z in board.Zones() if z.GetNetname() == "GND" and z.IsOnLayer(pcbnew.B_Cu)]


def filled(zs, layer, x, y):
    pt = pcbnew.VECTOR2I_MM(OX + x, OY + y)
    return any(z.HitTestFilledArea(layer, pt, 0) for z in zs)


def area_ok(zs, layer, x, y, m=0.7):
    return all(filled(zs, layer, x + dx, y + dy)
               for dx in (-m, 0, m) for dy in (-m, 0, m))


# keep stitching vias clear of the power lugs (hole-to-hole spacing)
lugs = []
for fp in board.GetFootprints():
    if fp.GetReference() in ("J18", "J19", "J20", "J21"):
        p0 = fp.GetPosition()
        lugs.append((pcbnew.ToMM(p0.x) - OX, pcbnew.ToMM(p0.y) - OY))

added = 0
for xi in range(4, 157, 7):
    for yi in range(4, 117, 7):
        if any((xi - lx) ** 2 + (yi - ly) ** 2 < 8 ** 2 for lx, ly in lugs):
            continue
        if area_ok(fz, pcbnew.F_Cu, xi, yi) and area_ok(bz, pcbnew.B_Cu, xi, yi):
            via = pcbnew.PCB_VIA(board)
            via.SetPosition(pcbnew.VECTOR2I_MM(OX + xi, OY + yi))
            via.SetDrill(pcbnew.FromMM(0.4))
            via.SetWidth(pcbnew.FromMM(0.8))
            via.SetNet(gnd)
            board.Add(via)
            added += 1
print(f"stitching vias: {added}")

filler.Fill(board.Zones())
pcbnew.SaveBoard(BOARD, board)
tracks = len([t for t in board.GetTracks()])
print(f"saved; {tracks} track segments/vias")
