#!/usr/bin/env python3
"""Embed library symbols into a .kicad_sch's lib_symbols block.

Scans the schematic for (lib_id "Lib:Name") references, extracts each symbol
from the KiCad standard libraries (or the project library), flattens derived
symbols (extends), renames to "Lib:Name", and rewrites the (lib_symbols ...)
section in place. Idempotent: regenerates the whole block every run.

Usage (inside the kicad container):
    python3 embed_symbols.py <schematic.kicad_sch> [more.kicad_sch ...]
"""
import re
import sys
import os

STD_DIR = "/usr/share/kicad/symbols"
PROJECT_LIBS = {
    "vanchor-helm": os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                 "..", "vanchor-helm-lib.kicad_sym"),
}


def find_block(text, start):
    """Return (start, end) of the balanced s-expr starting at text[start] == '('."""
    depth = 0
    i = start
    in_str = False
    while i < len(text):
        c = text[i]
        if in_str:
            if c == '\\':
                i += 2
                continue
            if c == '"':
                in_str = False
        elif c == '"':
            in_str = True
        elif c == '(':
            depth += 1
        elif c == ')':
            depth -= 1
            if depth == 0:
                return start, i + 1
        i += 1
    raise ValueError("unbalanced s-expression")


def extract_symbol(lib_text, name):
    """Extract the top-level (symbol "name" ...) block from a library file."""
    pat = re.compile(r'\(symbol\s+"%s"' % re.escape(name))
    m = pat.search(lib_text)
    if not m:
        return None
    s, e = find_block(lib_text, m.start())
    return lib_text[s:e]


def get_prop(block, prop):
    m = re.search(r'\(property\s+"%s"\s+"((?:[^"\\]|\\.)*)"' % re.escape(prop), block)
    return m.group(1) if m else None


def replace_prop_value(block, prop, value):
    pat = re.compile(r'(\(property\s+"%s"\s+")((?:[^"\\]|\\.)*)(")' % re.escape(prop))
    return pat.sub(lambda m: m.group(1) + value + m.group(3), block, count=1)


def flatten(lib_text, name):
    """Return symbol block for name; if derived via (extends), merge onto parent."""
    block = extract_symbol(lib_text, name)
    if block is None:
        return None
    m = re.search(r'\(extends\s+"([^"]+)"\)', block)
    if not m:
        return block
    parent_name = m.group(1)
    parent = flatten(lib_text, parent_name)
    if parent is None:
        raise ValueError(f"parent symbol {parent_name} not found for {name}")
    # rename parent block (outer name and unit sub-symbol names) to child name
    merged = parent.replace(f'(symbol "{parent_name}"', f'(symbol "{name}"', 1)
    merged = merged.replace(f'(symbol "{parent_name}_', f'(symbol "{name}_')
    # carry child's own property values over the parent's
    for prop in ("Value", "Footprint", "Datasheet", "Description", "Reference", "ki_keywords", "ki_fp_filters"):
        v = get_prop(block, prop)
        if v is not None:
            merged = replace_prop_value(merged, prop, v)
    return merged


def lib_file(libname):
    if libname in PROJECT_LIBS:
        return PROJECT_LIBS[libname]
    return os.path.join(STD_DIR, libname + ".kicad_sym")


_lib_cache = {}


def load_lib(libname):
    if libname not in _lib_cache:
        with open(lib_file(libname)) as f:
            _lib_cache[libname] = f.read()
    return _lib_cache[libname]


def embed(sch_path):
    with open(sch_path) as f:
        sch = f.read()

    lib_ids = sorted(set(re.findall(r'\(lib_id\s+"([^"]+)"\)', sch)))
    blocks = []
    for lib_id in lib_ids:
        libname, symname = lib_id.split(":", 1)
        text = load_lib(libname)
        block = flatten(text, symname)
        if block is None:
            raise SystemExit(f"{sch_path}: symbol {lib_id} not found in {lib_file(libname)}")
        # prefix outer name with lib nickname (unit sub-symbols stay unprefixed)
        block = block.replace(f'(symbol "{symname}"', f'(symbol "{lib_id}"', 1)
        # indent to lib_symbols level
        block = "\n".join("    " + line for line in block.splitlines())
        blocks.append(block)

    m = re.search(r'\(lib_symbols', sch)
    if not m:
        raise SystemExit(f"{sch_path}: no lib_symbols node")
    s, e = find_block(sch, m.start())
    if blocks:
        new_block = "(lib_symbols\n" + "\n".join(blocks) + "\n  )"
    else:
        new_block = "(lib_symbols)"
    sch = sch[:s] + new_block + sch[e:]

    with open(sch_path, "w") as f:
        f.write(sch)
    print(f"{sch_path}: embedded {len(blocks)} symbols")


if __name__ == "__main__":
    for path in sys.argv[1:]:
        embed(path)
