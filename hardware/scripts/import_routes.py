#!/usr/bin/env python3
"""Import the freerouting .ses session back into the board, refill zones, save."""
import pcbnew

BOARD = "/config/vanchor-pcb/hardware/vanchor-helm.kicad_pcb"
SES = "/config/vanchor-pcb/hardware/vanchor-helm.ses"

board = pcbnew.LoadBoard(BOARD)
ok = pcbnew.ImportSpecctraSES(board, SES)
print("SES import:", ok)
if not ok:
    raise SystemExit(1)
pcbnew.ZONE_FILLER(board).Fill(board.Zones())
pcbnew.SaveBoard(BOARD, board)
tracks = len([t for t in board.GetTracks()])
print(f"saved; {tracks} track segments/vias")
