#!/usr/bin/env python3
"""Import the freerouting .ses session, add GND stitching vias, refill, save."""
import pcbnew

BOARD = "/config/vanchor-pcb/hardware/vanchor-helm.kicad_pcb"
SES = "/config/vanchor-pcb/hardware/vanchor-helm.ses"
OX, OY = 20.0, 20.0

board = pcbnew.LoadBoard(BOARD)
ok = pcbnew.ImportSpecctraSES(board, SES)
print("SES import:", ok)
if not ok:
    raise SystemExit(1)
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


added = 0
for xi in range(4, 157, 7):
    for yi in range(4, 117, 7):
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
