#!/usr/bin/env python3
"""Netlist sanity gate: verify key nets exist with the expected pin counts.

Parses the KiCad s-expression netlist exported by
`kicad-cli sch export netlist --format kicadsexpr`.
"""
import re
import sys
from collections import defaultdict


def parse_nets(path):
    text = open(path).read()
    nets = defaultdict(list)
    for m in re.finditer(r'\(net\s+\(code\s+"?\d+"?\)\s+\(name\s+"([^"]+)"\)(.*?)(?=\(net\s+\(code|\Z)',
                         text, re.S):
        name = m.group(1)
        for n in re.finditer(r'\(node\s+\(ref\s+"([^"]+)"\)\s+\(pin\s+"([^"]+)"\)', m.group(2)):
            nets[name].append((n.group(1), n.group(2)))
    return nets


# net -> minimum expected pin count (global nets; local nets appear as /sheet/NAME)
EXPECTED = {
    "VIN": 6,          # Q1.S, D4, D5, C1, C2, U5, U6, J17, R11, R2, flag
    "GND": 20,
    "+5V": 8,          # U5.VOUT, J1x2, Pico VSYS, U2, U4, C3/C6/C9, F2, J9, J15
    "+12V": 4,         # U6.VOUT, J17, C4, R4, D7, J14
    "+3V3": 6,         # Pico 3V3, R9, R10, D6/D8-D11 K, J11, J12
    "3V3_PI": 9,       # J1 x2, J2 x2, J3..J8, R5, R6, flag
    "PI_SDA": 5,       # J1, J2, J8, R5, U1
    "PI_SCL": 5,
    "UART0_TX": 3, "UART0_RX": 3, "UART2_TX": 3, "UART2_RX": 3,
    "UART3_TX": 3, "UART3_RX": 3, "UART4_TX": 3, "UART4_RX": 3,
    "UART5_TX": 3, "UART5_RX": 3,
    "PI_PICO_RUN": 3,  # J1, J2, R8
    "ENC_SDA": 3, "ENC_SCL": 3,      # U1, pull-up, series R
    "RPWM": 3, "LPWM": 3, "R_EN": 3, "L_EN": 3,  # U1, J2? no — U1, J15 (+J2? no) => U1+J15=2... see note
    "ISENSE_R": 4, "ISENSE_L": 4,    # U1, R18/19, D8/9, C12/13
    "VBAT_SENSE": 5,                 # U1, R11, R12, C5, D6
    "DP_INC_3": 2, "DP_UD_3": 2, "DP_CS_3": 2, "THR_PWM_3": 2,
    "DP_INC_5": 2, "DP_UD_5": 2, "THR_PWM_5": 2,
    "DP_CS_5": 3,                    # U2, U3, R14
    "CONT_GATE_3": 2,
    "DISP_5V": 2,
    "LED_STAT": 2, "PI_LED": 3,
}
# RPWM/LPWM/R_EN/L_EN really are 2 pins (U1 + J15); fix expectation:
for n in ("RPWM", "LPWM", "R_EN", "L_EN"):
    EXPECTED[n] = 2


def main(netlist_path):
    nets = parse_nets(netlist_path)
    failures = []
    for net, minpins in EXPECTED.items():
        if net not in nets:
            failures.append(f"MISSING net {net}")
        elif len(nets[net]) < minpins:
            failures.append(f"net {net}: {len(nets[net])} pins < expected {minpins}: {nets[net]}")
    # every component pin should be somewhere: count total nodes
    total = sum(len(v) for v in nets.values())
    print(f"{len(nets)} nets, {total} connected pins")
    if failures:
        print("\n".join(failures))
        sys.exit(1)
    print("net check: PASS")


if __name__ == "__main__":
    main(sys.argv[1])
