#!/usr/bin/env python3
"""Print pin number -> (name, electrical type) for symbols, for spec authoring."""
import sys
import re
sys.path.insert(0, "/config/vanchor-pcb/hardware/scripts")
from embed_symbols import load_lib, flatten, find_block  # noqa: E402


def pins(lib_id):
    lib, name = lib_id.split(":", 1)
    b = flatten(load_lib(lib), name)
    out = []
    for m in re.finditer(r'\(pin\s+(\w+)\s+\w+\s*[\n\s]*\(at', b):
        ps, pe = find_block(b, m.start())
        blk = b[ps:pe]
        num = re.search(r'\(number\s+"([^"]*)"', blk)
        nm = re.search(r'\(name\s+"([^"]*)"', blk)
        if num:
            out.append((num.group(1), nm.group(1) if nm else "?", m.group(1)))
    return sorted(out, key=lambda t: (len(t[0]), t[0]))


if __name__ == "__main__":
    for lid in sys.argv[1:]:
        print(lid)
        for p in pins(lid):
            print("   ", p)
