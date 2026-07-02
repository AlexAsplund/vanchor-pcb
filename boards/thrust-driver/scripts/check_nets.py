#!/usr/bin/env python3
"""Netlist gate for the thrust driver."""
import re
import sys
from collections import defaultdict


def parse_nets(path):
    text = open(path).read()
    nets = defaultdict(list)
    for m in re.finditer(r'\(net\s+\(code\s+"?\d+"?\)\s+\(name\s+"([^"]+)"\)(.*?)(?=\(net\s+\(code|\Z)',
                         text, re.S):
        for n in re.finditer(r'\(node\s+\(ref\s+"([^"]+)"\)\s+\(pin\s+"([^"]+)"\)', m.group(2)):
            nets[m.group(1)].append((n.group(1), n.group(2)))
    return nets


EXPECTED = {
    "VBAT": 8,     # 4x BTN VS, D2, C1, C2, C3, C4, C5, lug, flag
    "GND": 12,
    "MOT_A": 3, "MOT_B": 3,
    "RPWM": 3, "LPWM": 3,            # J1 + 2 BTN INs
    "R_EN": 4, "L_EN": 4,            # J1, 2 BTN INH, pulldown
    "R_IS": 4, "L_IS": 4,            # J1, 2 BTN IS, 1k load
    "+5V": 4,                        # J1, R9, U5.39, U6.3
    "+3V3": 2, "CAN_TX": 2, "CAN_RX": 2,
    "N2K_VP": 2, "N2K_SHLD": 2, "R_ADC": 2, "L_ADC": 2,
}


def main(path):
    nets = parse_nets(path)
    fails = []
    for net, minpins in EXPECTED.items():
        if net not in nets:
            fails.append(f"MISSING {net}")
        elif len(nets[net]) < minpins:
            fails.append(f"{net}: {len(nets[net])} < {minpins}: {nets[net]}")
    total = sum(len(v) for v in nets.values())
    print(f"{len(nets)} nets, {total} pins")
    if fails:
        print("\n".join(fails))
        sys.exit(1)
    print("net check: PASS")


if __name__ == "__main__":
    main(sys.argv[1])
