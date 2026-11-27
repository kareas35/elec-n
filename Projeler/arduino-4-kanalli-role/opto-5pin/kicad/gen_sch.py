"""design.py'den KiCad 10 şematiği (.kicad_sch) üretir.
Bağlantılar net etiketleriyle yapılır; ayrıca 5V uyarı notları şemaya basılır.
"""
import os
import re
import uuid

from design import build_components, CHANNELS, NC_NETS, SCH_NOTES
from inspect_pins import pins, block, K

OUT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT = "relay_4ch_5pin"


def uid():
    return str(uuid.uuid4())


def lib_symbol_text(lib_id):
    lib, name = lib_id.split(":")
    text = open(f"{K}/symbols/{lib}.kicad_sym", encoding="utf-8").read()
    m = re.search(r'\(symbol "%s"' % re.escape(name), text)
    body = block(text, m.start())
    body = re.sub(r'\(symbol "%s"' % re.escape(name), f'(symbol "{lib}:{name}"', body, count=1)
    return body


def snap(v):
    return round(round(v / 1.27) * 1.27, 2)


def row_y(k):
    return snap(40 + (k - 1) * 55)


def placements():
    pos = {
        "J1": (snap(25), snap(65)),       # 5 pinli kontrol soketi: GND, IN1-IN4
        "J2": (snap(25), snap(285)),      # Tek röle besleme girişi: +5V DC / GND
        "C1": (snap(65), snap(285)),
        "C2": (snap(95), snap(285)),
    }
    for k in range(1, CHANNELS + 1):
        y = row_y(k)
        pos[f"Rled{k}"] = (snap(110), y)
        pos[f"U{k}"] = (snap(155), y)
        pos[f"Rpd{k}"] = (snap(200), y)
        pos[f"Q{k}"] = (snap(235), y)
        pos[f"D{k}"] = (snap(270), snap(y - 18))
        pos[f"K{k}"] = (snap(305), y)
        pos[f"J{k + 2}"] = (snap(365), y)
    return pos


def pin_points(lib_id, sx, sy):
    res = {}
    for num, _pname, px, py, _ang in pins(*lib_id.split(":")):
        res[num] = (round(sx + float(px), 3), round(sy - float(py), 3))
    return res


def build():
    comps = build_components()
    pos = placements()
    root = uid()

    lib_ids = sorted({c[1] for c in comps})
    lib_syms = "\n".join("    " + lib_symbol_text(l).replace("\n", "\n    ") for l in lib_ids)

    out = []
    out.append('(kicad_sch (version 20250114) (generator "eeschema") (generator_version "10.0")')
    out.append(f'  (uuid "{root}")')
    out.append('  (paper "A3")')
    out.append('  (title_block (title "4 Roleli Arduino Surucu - V2 / 5 Pinli") (rev "V2") '
               '(company "") (comment 1 "J1: 1=GND 2=IN1(D4) 3=IN2(D5) 4=IN3(D6) 5=IN4(D7)") '
               '(comment 2 "J2: PIN1=Harici +5V DC, PIN2=GND | Arduino USB | GND_A/GND_B izole"))')
    out.append("  (lib_symbols")
    out.append(lib_syms)
    out.append("  )")

    for x, y, text in SCH_NOTES:
        out.append(f'  (text "{text}" (at {x} {y} 0) (effects (font (size 1.6 1.6) (thickness 0.3)) '
                   f'(justify left bottom)) (uuid "{uid()}"))')

    labels = []
    nocon = []
    for ref, lib_id, value, footprint, pinmap in comps:
        sx, sy = pos[ref]
        pp = pin_points(lib_id, sx, sy)
        sym_uuid = uid()
        out.append(f'  (symbol (lib_id "{lib_id}") (at {sx} {sy} 0) (unit 1)')
        out.append('    (exclude_from_sim no) (in_bom yes) (on_board yes) (dnp no)')
        out.append(f'    (uuid "{sym_uuid}")')
        out.append(f'    (property "Reference" "{ref}" (at {sx} {sy - 6} 0) (effects (font (size 1.27 1.27))))')
        out.append(f'    (property "Value" "{value}" (at {sx} {sy + 6} 0) (effects (font (size 1.27 1.27))))')
        out.append(f'    (property "Footprint" "{footprint}" (at {sx} {sy} 0) (effects (font (size 1.27 1.27)) (hide yes)))')
        out.append(f'    (property "Datasheet" "~" (at {sx} {sy} 0) (effects (font (size 1.27 1.27)) (hide yes)))')
        for num in pp:
            out.append(f'    (pin "{num}" (uuid "{uid()}"))')
        out.append(f'    (instances (project "{PROJECT}" (path "/{root}" (reference "{ref}") (unit 1))))')
        out.append("  )")
        for num, net in pinmap.items():
            x, y = pp[num]
            if net in NC_NETS:
                nocon.append((x, y))
            else:
                labels.append((net, x, y))

    for x, y in nocon:
        out.append(f'  (no_connect (at {x} {y}) (uuid "{uid()}"))')
    for net, x, y in labels:
        out.append(f'  (label "{net}" (at {x} {y} 0) (fields_autoplaced yes)')
        out.append('    (effects (font (size 1.27 1.27)) (justify left bottom))')
        out.append(f'    (uuid "{uid()}"))')

    out.append('  (sheet_instances (path "/" (page "1")))')
    out.append(")")
    return "\n".join(out) + "\n"


if __name__ == "__main__":
    path = os.path.join(OUT_DIR, f"{PROJECT}.kicad_sch")
    with open(path, "w", encoding="utf-8") as f:
        f.write(build())
    print("yazıldı:", path)
