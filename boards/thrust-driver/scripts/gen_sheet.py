#!/usr/bin/env python3
"""Generate a .kicad_sch sheet from a compact component/net spec.

A sheet spec is a python file defining:
    SHEET_UUID  = "…"                      stable uuid for this sheet file
    COMPONENTS  = [ dict(lib=, ref=, value=, fp=, at=(x, y, rot),
                         pins={ "1": "NET" | None, … },   # None = no-connect
                         dnp=False, mirror=None), … ]
    TEXTS       = [ (x, y, "annotation"), … ]              # optional

Every pin of every symbol MUST appear in pins{} (net or None) — the generator
fails otherwise, so a forgotten pin is impossible. Connectivity is made with
global labels placed on the pin ends (netlist-style schematic); KiCad derives
nets directly from them, and cross-sheet nets connect by label name.

Usage (inside container): python3 gen_sheet.py <spec.py> <out.kicad_sch> <project_name> <root_uuid>
"""
import re
import sys
import uuid
import importlib.util

sys.path.insert(0, "/config/vanchor-pcb/boards/helm/scripts")
from embed_symbols import load_lib, flatten, find_block  # noqa: E402


def stable_uuid(*parts):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, "vanchor-helm:" + ":".join(map(str, parts))))


def parse_pins(symbol_block):
    """Return {number: (x, y, angle)} for all pins of a flattened symbol block."""
    pins = {}
    for m in re.finditer(r'\(pin\s+\w+\s+\w+\s*[\n\s]*\(at\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\)', symbol_block):
        pins_at = (float(m.group(1)), float(m.group(2)), float(m.group(3)))
        ps, pe = find_block(symbol_block, m.start())
        block = symbol_block[ps:pe]
        nm = re.search(r'\(number\s+"([^"]+)"', block)
        if nm:
            pins[nm.group(1)] = pins_at
    return pins


def rot_ccw(x, y, deg):
    deg = deg % 360
    if deg == 0:
        return x, y
    if deg == 90:
        return -y, x
    if deg == 180:
        return -x, -y
    if deg == 270:
        return y, -x
    raise ValueError(deg)


def pin_abs(inst_x, inst_y, inst_rot, mirror, px, py, pang):
    """Absolute sheet position + visual free-direction angle of a pin."""
    if mirror == 'x':      # mirror across x-axis (flip vertically) before rotation
        py = -py
        pang = (360 - pang) % 360 if pang in (90, 270) else pang
        pang = (180 - pang) % 360 if pang in (0, 180) else pang
    elif mirror == 'y':
        px = -px
        pang = (180 - pang) % 360 if pang in (0, 180) else pang
        pang = (360 - pang) % 360 if pang in (90, 270) else pang
    rx, ry = rot_ccw(px, py, inst_rot)
    ang = (pang + inst_rot) % 360
    return inst_x + rx, inst_y - ry, ang


def snap(v, g=1.27):
    """Snap to the 1.27mm schematic connection grid (avoids endpoint_off_grid)."""
    return round(v / g) * g


def fmt(v):
    s = f"{v:.4f}".rstrip('0').rstrip('.')
    return s if s else "0"


def main(spec_path, out_path, project, root_uuid):
    import os
    sys.path.insert(0, os.path.dirname(os.path.abspath(spec_path)))
    spec = importlib.util.spec_from_file_location("sheetspec", spec_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    sheet_uuid = mod.SHEET_UUID
    comps = mod.COMPONENTS
    texts = getattr(mod, "TEXTS", [])
    inst_path = f"/{root_uuid}/{sheet_uuid}" if root_uuid != sheet_uuid else f"/{root_uuid}"

    # collect + flatten symbol defs
    lib_blocks = {}
    for c in comps:
        lib_id = c["lib"]
        if lib_id in lib_blocks:
            continue
        libname, symname = lib_id.split(":", 1)
        block = flatten(load_lib(libname), symname)
        if block is None:
            raise SystemExit(f"symbol {lib_id} not found")
        lib_blocks[lib_id] = block

    pin_maps = {lib_id: parse_pins(b) for lib_id, b in lib_blocks.items()}

    sym_nodes, label_nodes, nc_nodes = [], [], []
    pin_records, pin_pos = [], {}
    for c in comps:
        lib_id, ref = c["lib"], c["ref"]
        x, y, rot = c["at"]
        x, y = snap(x), snap(y)
        mirror = c.get("mirror")
        pmap = pin_maps[lib_id]
        want = set(c["pins"].keys())
        have = set(pmap.keys())
        if want != have:
            raise SystemExit(f"{ref} ({lib_id}): pins mismatch — spec has {sorted(want - have)} extra, missing {sorted(have - want)}")
        u = stable_uuid("sym", sheet_uuid, ref)
        mirror_sexp = f" (mirror {mirror})" if mirror else ""
        dnp = "yes" if c.get("dnp") else "no"
        # ref above / value below the symbol's actual vertical extent
        # (fixed +/-7.62 clips tall connectors: pins land on the text)
        if pmap:
            if rot in (90, 270):
                ext = max(abs(px) for px, _, _ in pmap.values())
            else:
                ext = max(abs(py) for _, py, _ in pmap.values())
        else:
            ext = 0
        text_off = max(7.62, ext + 3.81)
        # BAT54S: the COM pin label occupies the space above the part, so
        # stack ref+value below it instead of straddling.
        if lib_id.endswith("BAT54S"):
            ref_at = (x, y + text_off)
            val_at = (x, y + text_off + 3.81)
        else:
            ref_at = (x, y - text_off)
            val_at = (x, y + text_off)
        # per-part override for refs that would collide with wires/labels
        ref_at = getattr(mod, "REF_POS", {}).get(ref, ref_at)
        props = [
            ("Reference", ref, ref_at[0], ref_at[1], False),
            ("Value", c.get("value", ""), val_at[0], val_at[1], False),
            ("Footprint", c.get("fp", ""), x, y, True),
            ("Datasheet", "", x, y, True),
        ]
        fields = dict(c.get("fields", {}))
        try:
            from mpn import MPN
            if ref in MPN and "MPN" not in fields:
                fields["MPN"] = MPN[ref]
        except ImportError:
            pass
        for fname, fval in fields.items():
            props.append((fname, fval, x, y, True))
        prop_s = "\n".join(
            f'''    (property "{pn}" "{pv}" (at {fmt(px)} {fmt(py)} 0)
      (effects (font (size 1.27 1.27)){" (hide yes)" if hide else ""}))'''
            for pn, pv, px, py, hide in props)
        pin_s = "\n".join(
            f'    (pin "{num}" (uuid "{stable_uuid("pin", sheet_uuid, ref, num)}"))'
            for num in sorted(c["pins"]))
        sym_nodes.append(f'''  (symbol (lib_id "{lib_id}") (at {fmt(x)} {fmt(y)} {rot}){mirror_sexp} (unit 1)
    (exclude_from_sim no) (in_bom yes) (on_board yes) (dnp {dnp})
    (uuid "{u}")
{prop_s}
{pin_s}
    (instances (project "{project}" (path "{inst_path}" (reference "{ref}") (unit 1))))
  )''')

        for num, net in c["pins"].items():
            px, py, pang = pmap[num]
            ax, ay, aang = pin_abs(x, y, rot, mirror, px, py, pang)
            pin_pos[(ref, num)] = (ax, ay)
            if net is None:
                nc_nodes.append(f'  (no_connect (at {fmt(ax)} {fmt(ay)}) (uuid "{stable_uuid("nc", sheet_uuid, ref, num)}"))')
                continue
            pin_records.append((ref, num, net, ax, ay, aang))

    # ---- wires & rails (declared in the spec as WIRES / RAILS) ----
    wires = getattr(mod, "WIRES", [])
    rails = getattr(mod, "RAILS", [])
    wire_nodes, junction_nodes = [], []
    wired = set()

    def emit_seg(x1, y1, x2, y2, key):
        wire_nodes.append(
            f'  (wire (pts (xy {fmt(x1)} {fmt(y1)}) (xy {fmt(x2)} {fmt(y2)}))\n'
            f'    (stroke (width 0) (type default)) (uuid "{stable_uuid("wire", sheet_uuid, *key)}"))')

    for wi, entry in enumerate(wires):
        a, b = entry[0], entry[1]
        wps = entry[2] if len(entry) > 2 else []
        if a not in pin_pos or b not in pin_pos:
            raise SystemExit(f"WIRES: unknown endpoint {a} or {b}")
        cx, cy = pin_pos[a]
        x2, y2 = pin_pos[b]
        si = 0
        for axis, val in wps:  # turtle waypoints: ("x", v) / ("y", v)
            nx, ny = (val, cy) if axis == "x" else (cx, val)
            if abs(nx - cx) > 0.01 or abs(ny - cy) > 0.01:
                emit_seg(cx, cy, nx, ny, ("w", wi, si))
                si += 1
            cx, cy = nx, ny
        if abs(cx - x2) < 0.01 or abs(cy - y2) < 0.01:
            if abs(cx - x2) > 0.01 or abs(cy - y2) > 0.01:
                emit_seg(cx, cy, x2, y2, ("w", wi, si))
        else:
            emit_seg(cx, cy, x2, cy, ("w", wi, si))
            emit_seg(x2, cy, x2, y2, ("w", wi, si + 1))
        wired.add(b)  # keep the label on endpoint a: the cluster stays named

    for ri, (rnet, ry, ends) in enumerate(rails):
        ry = snap(ry)
        xs = []
        for e in ends:
            if e not in pin_pos:
                raise SystemExit(f"RAILS: unknown endpoint {e}")
            ex, ey = pin_pos[e]
            emit_seg(ex, ey, ex, ry, ("rs", ri, e[0], e[1]))
            junction_nodes.append(
                f'  (junction (at {fmt(ex)} {fmt(ry)}) (diameter 0) (color 0 0 0 0)\n'
                f'    (uuid "{stable_uuid("junc", sheet_uuid, ri, e[0], e[1])}"))')
            xs.append(ex)
            if e != ends[0]:
                wired.add(e)  # first endpoint keeps its label -> named cluster
        emit_seg(min(xs), ry, max(xs), ry, ("rr", ri))

    # labels: skip wired pins, but keep at least one label per net
    label_counts = {}
    for ref, num, net, ax, ay, aang in pin_records:
        if (ref, num) not in wired:
            label_counts[net] = label_counts.get(net, 0) + 1
    for ref, num, net, ax, ay, aang in pin_records:
        if (ref, num) in wired:
            continue
        if True:  # emit label
            if net.startswith("."):  # sheet-local net
                name = net[1:]
                lang = (aang + 180) % 360
                label_uuid = stable_uuid("lbl", sheet_uuid, ref, num, net)
                label_nodes.append(f'''  (label "{name}" (at {fmt(ax)} {fmt(ay)} {lang}) (fields_autoplaced yes)
    (effects (font (size 1.27 1.27)) (justify {"left" if lang == 0 else "right" if lang == 180 else "left"}))
    (uuid "{label_uuid}")
  )''')
            else:
                lang = (aang + 180) % 360
                label_uuid = stable_uuid("lbl", sheet_uuid, ref, num, net)
                label_nodes.append(f'''  (global_label "{net}" (shape passive) (at {fmt(ax)} {fmt(ay)} {lang}) (fields_autoplaced yes)
    (effects (font (size 1.27 1.27)) (justify {"left" if lang == 0 else "right" if lang == 180 else "left"}))
    (uuid "{label_uuid}")
    (property "Intersheetrefs" "${{INTERSHEET_REFS}}" (at {fmt(ax)} {fmt(ay)} 0)
      (effects (font (size 1.27 1.27)) (hide yes)))
  )''')

    text_nodes = [
        f'''  (text "{t[2]}" (exclude_from_sim no) (at {fmt(t[0])} {fmt(t[1])} 0)
    (effects (font (size 2 2) (bold yes)) (justify left bottom))
    (uuid "{stable_uuid("txt", sheet_uuid, i)}")
  )''' for i, t in enumerate(texts)]

    sch = f'''(kicad_sch
  (version 20231120)
  (generator "eeschema")
  (generator_version "8.0")
  (uuid "{sheet_uuid}")
  (paper "A3")
  (lib_symbols)
{chr(10).join(text_nodes)}
{chr(10).join(sym_nodes)}
{chr(10).join(wire_nodes)}
{chr(10).join(junction_nodes)}
{chr(10).join(label_nodes)}
{chr(10).join(nc_nodes)}
)
'''
    with open(out_path, "w") as f:
        f.write(sch)
    print(f"{out_path}: {len(comps)} symbols, {len(label_nodes)} labels, {len(nc_nodes)} no-connects")


if __name__ == "__main__":
    main(*sys.argv[1:5])
