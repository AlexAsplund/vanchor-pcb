#!/bin/sh
# Export fabrication outputs into boards/thrust-driver/fab/ (run on the host).
set -e
HW=/config/vanchor-pcb/boards/thrust-driver
FAB=$HW/fab

docker exec vanchor-kicad sh -c "mkdir -p $FAB/gerbers $FAB/renders"

# Gerbers + drill (PCBWay/JLC-compatible set); order the board in 2oz copper!
docker exec vanchor-kicad kicad-cli pcb export gerbers \
  --layers "F.Cu,B.Cu,F.Paste,B.Paste,F.SilkS,B.SilkS,F.Mask,B.Mask,Edge.Cuts" \
  -o $FAB/gerbers/ $HW/vanchor-thrust.kicad_pcb
docker exec vanchor-kicad kicad-cli pcb export drill \
  --format excellon --generate-map --map-format gerberx2 \
  -o $FAB/gerbers/ $HW/vanchor-thrust.kicad_pcb

# Position file (for reference; board is hand-assembled)
docker exec vanchor-kicad kicad-cli pcb export pos --units mm --side both \
  -o $FAB/vanchor-thrust.pos $HW/vanchor-thrust.kicad_pcb

# BOM (grouped, with MPN column) + schematic PDF
docker exec vanchor-kicad kicad-cli sch export bom \
  --fields "Reference,Value,Footprint,MPN,\${QUANTITY},\${DNP}" \
  --labels "Ref,Value,Footprint,MPN,Qty,DNP" --group-by "Value,Footprint,MPN" \
  -o $FAB/vanchor-thrust-bom.csv $HW/vanchor-thrust.kicad_sch
docker exec vanchor-kicad kicad-cli sch export pdf \
  -o $FAB/vanchor-thrust-schematic.pdf $HW/vanchor-thrust.kicad_sch

# Renders
docker exec vanchor-kicad kicad-cli pcb render --side top --background opaque \
  -o $FAB/renders/board-top.png $HW/vanchor-thrust.kicad_pcb
docker exec vanchor-kicad kicad-cli pcb render --side bottom --background opaque \
  -o $FAB/renders/board-bottom.png $HW/vanchor-thrust.kicad_pcb
docker exec vanchor-kicad kicad-cli pcb render --perspective --rotate "-30,20,-20" \
  --zoom 0.9 --background opaque \
  -o $FAB/renders/board-3d.png $HW/vanchor-thrust.kicad_pcb

# Zip the gerbers for upload
docker exec vanchor-kicad sh -c "cd $FAB/gerbers && rm -f ../vanchor-thrust-gerbers.zip && zip -q ../vanchor-thrust-gerbers.zip *"
echo "fab outputs in boards/thrust-driver/fab/"
