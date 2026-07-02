#!/bin/sh
# Regenerate all schematic sheets from specs, embed symbols, run ERC.
# Run on the host: ./hardware/scripts/build_sch.sh
set -e
HW=/config/vanchor-pcb/hardware
ROOT_UUID=a0000000-0000-4000-8000-000000000001

for s in carrier control; do
  docker exec vanchor-kicad python3 $HW/scripts/gen_sheet.py \
    $HW/sheets/$s.py $HW/$s.kicad_sch vanchor-helm $ROOT_UUID
  docker exec vanchor-kicad python3 $HW/scripts/embed_symbols.py $HW/$s.kicad_sch
done

docker exec vanchor-kicad kicad-cli sch erc --exit-code-violations \
  -o /tmp/erc.rpt $HW/vanchor-helm.kicad_sch
