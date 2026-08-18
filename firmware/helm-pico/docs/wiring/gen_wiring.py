#!/usr/bin/env python3
"""helm-pico DIY wiring — v4: fixed right-side stack, margins, legend."""

W, H = 1560, 1170
parts = []

def rect(x, y, w, h, fill, stroke="#333", rx=10, sw=2.5):
    parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" '
                 f'fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>')

def text(x, y, s, size=15, fill="#111", anchor="middle", bold=False):
    fw = ' font-weight="bold"' if bold else ""
    parts.append(f'<text x="{x}" y="{y}" font-size="{size}" fill="{fill}" '
                 f'text-anchor="{anchor}" font-family="Arial, sans-serif"{fw}>{s}</text>')

def wire(pts, color, sw=4):
    d = "M " + " L ".join(f"{x},{y}" for x, y in pts)
    parts.append(f'<path d="{d}" fill="none" stroke="{color}" stroke-width="{sw}" '
                 f'stroke-linejoin="round" stroke-linecap="round"/>')

def pin(x, y):
    parts.append(f'<rect x="{x-6}" y="{y-5}" width="12" height="10" fill="#ffd54f" stroke="#333" stroke-width="1"/>')

def arrow(x, y, dx, label, color):
    x2 = x + dx
    wire([(x, y), (x2, y)], color, 5)
    tip = 12 if dx > 0 else -12
    parts.append(f'<path d="M {x2},{y} l {-tip},-7 l 0,14 z" fill="{color}"/>')
    ax = x2 + (8 if dx > 0 else -8)
    anc = "start" if dx > 0 else "end"
    text(ax, y + 5, label, 14, "#111", anchor=anc, bold=True)

C = {"pwm_r": "#1565c0", "pwm_l": "#00acc1", "en": "#2e7d32", "v33": "#d32f2f",
     "gnd": "#212121", "sda": "#f9a825", "scl": "#7b1fa2", "hall": "#00838f"}

parts.append(f'<rect width="{W}" height="{H}" fill="#fbfbf9"/>')
text(W/2, 44, "vanchor helm controller — wiring (Raspberry Pi Pico 2 / Pico)", 25, "#111", bold=True)
text(W/2, 70, "( ) = physical pin number on the Pico", 14, "#777")

# ---------- Pico ----------
PX, PY, PW, PH = 670, 250, 220, 470
rect(PX, PY, PW, PH, "#1b5e20", "#0d3311", rx=14)
rect(PX + PW/2 - 26, PY - 16, 52, 30, "#9e9e9e", "#616161", rx=4)
text(PX + PW/2, 648, "Raspberry Pi", 16, "#e8f5e9", bold=True)
text(PX + PW/2, 670, "Pico 2 / Pico", 16, "#e8f5e9", bold=True)
wire([(PX + PW/2, PY - 16), (PX + PW/2, PY - 66)], "#455a64", 6)
text(PX + PW/2 + 14, PY - 48, "USB to the Raspberry Pi", 14, "#455a64", anchor="start", bold=True)
text(PX + PW/2 + 14, PY - 30, "(also powers the Pico)", 12, "#78909c", anchor="start")

LPINS = [("GP8", 11, 310), ("GP9", 12, 350), ("GP10", 14, 390), ("GP11", 15, 430)]
RPINS = [("GP12", 16, 310), ("GP13", 17, 350), ("GP14", 19, 390), ("GP15", 20, 430),
         ("GP6", 9, 520), ("GP7", 10, 560), ("GP0", 1, 610)]
lp, rp, bp = {}, {}, {}
for name, phys, y in LPINS:
    lp[name] = (PX, y); pin(PX - 3, y)
    text(PX + 10, y + 5, f"{name} ({phys})", 13.5, "#fff", anchor="start", bold=True)
for name, phys, y in RPINS:
    rp[name] = (PX + PW, y); pin(PX + PW + 3, y)
    text(PX + PW - 10, y + 5, f"{name} ({phys})", 13.5, "#fff", anchor="end", bold=True)
for name, phys, x in (("3V3", 36, 730), ("GND", 38, 830)):
    bp[name] = (x, PY + PH)
    parts.append(f'<rect x="{x-5}" y="{PY+PH-3}" width="10" height="12" fill="#ffd54f" stroke="#333" stroke-width="1"/>')
    text(x, PY + PH - 12, f"{name} ({phys})", 12.5, "#fff", bold=True)

# ---------- drivers ----------
def driver(x, title, pins_right):
    y, w, h = 250, 300, 330
    rect(x, y, w, h, "#0d47a1", "#082a60", rx=12)
    text(x + w/2, y + 30, title, 17, "#e3f2fd", bold=True)
    text(x + w/2, y + 52, "BTS7960 / IBT-2 driver", 13, "#90caf9")
    pins = {}
    for i, name in enumerate(["RPWM", "LPWM", "R_EN", "L_EN"]):
        py = 310 + i * 40
        if pins_right:
            pins[name] = (x + w, py); pin(x + w + 3, py)
            text(x + w - 12, py + 5, name, 14.5, "#fff", anchor="end", bold=True)
        else:
            pins[name] = (x, py); pin(x - 3, py)
            text(x + 12, py + 5, name, 14.5, "#fff", anchor="start", bold=True)
    for j, name in enumerate(["VCC", "GND"]):
        bx = x + (90 + j * 120 if pins_right else 40 + j * 60)
        pins[name] = (bx, y + h)
        parts.append(f'<rect x="{bx-5}" y="{y+h-3}" width="10" height="12" fill="#ffd54f" stroke="#333" stroke-width="1"/>')
        text(bx, y + h - 12, name, 13, "#fff", bold=True)
    ox = x if pins_right else x + w
    d = -60 if pins_right else 60
    arrow(ox, 480, d, "12 V +", "#ef6c00")
    arrow(ox, 515, d, "12 V −", "#424242")
    arrow(ox, 550, d, "motor", "#6d4c41")
    text(x + w/2, y + h - 40, "R_IS / L_IS: not connected", 12, "#90caf9")
    return pins

sd = driver(190, "Driver 1 — STEERING", True)
td = driver(1050, "Driver 2 — THRUST", False)

# ---------- signal wires ----------
for (a, b, col) in (("GP8", "RPWM", C["pwm_r"]), ("GP9", "LPWM", C["pwm_l"]),
                    ("GP10", "R_EN", C["en"]), ("GP11", "L_EN", C["en"])):
    wire([(lp[a][0] - 9, lp[a][1]), (sd[b][0] + 9, sd[b][1])], col)
for (a, b, col) in (("GP12", "RPWM", C["pwm_r"]), ("GP13", "LPWM", C["pwm_l"]),
                    ("GP14", "R_EN", C["en"]), ("GP15", "L_EN", C["en"])):
    wire([(rp[a][0] + 9, rp[a][1]), (td[b][0] - 9, td[b][1])], col)
for px_ in ((lp["GP10"][0] + sd["R_EN"][0]) / 2, (rp["GP14"][0] + td["R_EN"][0]) / 2):
    for py_ in (390, 430):
        parts.append(f'<circle cx="{px_}" cy="{py_}" r="9" fill="#fff" stroke="{C["en"]}" stroke-width="2.5"/>')
        text(px_, py_ + 4.5, "R", 12, C["en"], bold=True)

# ---------- AS5600 (below the thrust driver) ----------
ax, ay, aw, ah = 1200, 680, 240, 150
rect(ax, ay, aw, ah, "#4527a0", "#2a1465", rx=12)
text(ax + aw/2 + 14, ay + 52, "AS5600", 17, "#ede7f6", bold=True)
text(ax + aw/2 + 14, ay + 74, "steering encoder", 13, "#b39ddb")
text(ax + aw/2 + 14, ay + 96, "(magnet on the shaft)", 12, "#b39ddb")
apins = {}
for i, name in enumerate(["SDA", "SCL"]):
    py = ay + 40 + i * 40
    apins[name] = (ax, py); pin(ax - 3, py)
    text(ax + 12, py + 5, name, 14, "#fff", anchor="start", bold=True)
for j, name in enumerate(["VCC", "GND"]):
    bx = ax + 60 + j * 110
    apins[name] = (bx, ay + ah)
    parts.append(f'<rect x="{bx-5}" y="{ay+ah-3}" width="10" height="12" fill="#ffd54f" stroke="#333" stroke-width="1"/>')
    text(bx, ay + ah - 12, name, 13, "#fff", bold=True)
wire([(rp["GP6"][0] + 9, rp["GP6"][1]), (1000, rp["GP6"][1]), (1000, apins["SDA"][1]), (apins["SDA"][0] - 9, apins["SDA"][1])], C["sda"])
wire([(rp["GP7"][0] + 9, rp["GP7"][1]), (1016, rp["GP7"][1]), (1016, apins["SCL"][1]), (apins["SCL"][0] - 9, apins["SCL"][1])], C["scl"])

# ---------- hall (optional, below AS5600) ----------
hx, hy, hw, hh = 870, 880, 190, 100
rect(hx, hy, hw, hh, "#e0f2f1", "#00695c", rx=12)
text(hx + hw/2, hy + 48, "Hall — OPTIONAL", 14, "#00695c", bold=True)
text(hx + hw/2, hy + 66, "center magnet", 11.5, "#26a69a")
hpins = {}
hpins["OUT"] = (hx + 60, hy)
parts.append(f'<rect x="{hx+60-5}" y="{hy-3}" width="10" height="12" fill="#ffd54f" stroke="#00695c" stroke-width="1"/>')
text(hx + 60, hy + 22, "OUT", 12.5, "#00695c", bold=True)
for j, name in enumerate(["VCC", "GND"]):
    bx = hx + 100 + j * 60
    hpins[name] = (bx, hy + hh)
    parts.append(f'<rect x="{bx-5}" y="{hy+hh-3}" width="10" height="12" fill="#ffd54f" stroke="#00695c" stroke-width="1"/>')
    text(bx, hy + hh - 12, name, 12.5, "#00695c", bold=True)
wire([(rp["GP0"][0] + 9, rp["GP0"][1]), (hpins["OUT"][0], rp["GP0"][1]), (hpins["OUT"][0], hy - 3)], C["hall"])

# ---------- power rails ----------
RY1, RY2 = 1030, 1080
wire([(190, RY1), (1420, RY1)], C["v33"], 7)
text(160, RY1 + 5, "3.3 V", 16, C["v33"], anchor="end", bold=True)
wire([(190, RY2), (1420, RY2)], C["gnd"], 7)
text(160, RY2 + 5, "GND", 16, C["gnd"], anchor="end", bold=True)
def drop(p, rail_y, col):
    wire([(p[0], p[1] + 10), (p[0], rail_y)], col)
    parts.append(f'<circle cx="{p[0]}" cy="{rail_y}" r="5.5" fill="{col}"/>')
drop(bp["3V3"], RY1, C["v33"]); drop(bp["GND"], RY2, C["gnd"])
drop(sd["VCC"], RY1, C["v33"]); drop(sd["GND"], RY2, C["gnd"])
drop(td["VCC"], RY1, C["v33"]); drop(td["GND"], RY2, C["gnd"])
drop(apins["VCC"], RY1, C["v33"]); drop(apins["GND"], RY2, C["gnd"])
drop(hpins["VCC"], RY1, C["v33"]); drop(hpins["GND"], RY2, C["gnd"])
text(770, 1125, "Connect every VCC to 3.3 V and every GND together.  The 12 V battery connects ONLY to the two drivers.", 14, "#555")

# ---------- inset ----------
ix, iy = 60, 84
rect(ix, iy, 370, 160, "#fff8e1", "#c9a227", rx=10)
text(ix + 185, iy + 26, "R  =  100k resistor  (4 pieces)", 15.5, "#8d6e00", bold=True)
text(ix + 185, iy + 46, "keeps the motors OFF while the Pico boots", 12.5, "#8d6e00")
# mini-schematic: EN wire left->right, junction dot, resistor down to ground
wy = iy + 74
wire([(ix + 30, wy), (ix + 340, wy)], C["en"], 4)
text(ix + 30, wy - 10, "from Pico", 12, C["en"], anchor="start", bold=True)
text(ix + 340, wy - 10, "to driver EN", 12, C["en"], anchor="end", bold=True)
jx = ix + 185
parts.append(f'<circle cx="{jx}" cy="{wy}" r="6" fill="{C["en"]}"/>')
wire([(jx, wy), (jx, wy + 16)], C["en"], 3)
rect(jx - 12, wy + 16, 24, 34, "#fff3e0", "#8d6e63", rx=4, sw=2)
text(jx + 20, wy + 39, "100k", 13, "#5d4037", anchor="start", bold=True)
wire([(jx, wy + 50), (jx, wy + 64)], C["gnd"], 3)
# standard ground symbol (three shrinking bars)
wire([(jx - 16, wy + 64), (jx + 16, wy + 64)], C["gnd"], 4)
wire([(jx - 10, wy + 71), (jx + 10, wy + 71)], C["gnd"], 4)
wire([(jx - 4, wy + 78), (jx + 4, wy + 78)], C["gnd"], 4)
text(jx + 26, wy + 72, "GND", 13, "#111", anchor="start", bold=True)

# ---------- legend ----------
gx, gy = 1160, 100
rect(gx, gy, 300, 160, "#ffffff", "#999", rx=10)
text(gx + 150, gy + 26, "Wire colors", 15, "#111", bold=True)
rows = [([C["pwm_r"]], "RPWM"), ([C["pwm_l"]], "LPWM"), ([C["en"]], "Enable (EN)"),
        ([C["sda"], C["scl"]], "SDA / SCL"), ([C["v33"], C["gnd"]], "3.3 V / GND"),
        ([C["hall"]], "Hall (optional)")]
for i, (cols, name) in enumerate(rows):
    yy = gy + 50 + i * 19
    for k, col in enumerate(cols):
        wire([(gx + 20 + k * 26, yy - 5), (gx + 40 + k * 26, yy - 5)], col, 5)
    text(gx + 80, yy, name, 13, "#222", anchor="start")

svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
       f'viewBox="0 0 {W} {H}">' + "".join(parts) + "</svg>")
import pathlib
pathlib.Path("helm-wiring.svg").write_text(svg)
print("v4 written")
