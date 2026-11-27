import re

K = "C:/Program Files/KiCad/10.0/share/kicad"


def block(text, start):
    depth = 0
    i = start
    in_str = False
    while True:
        c = text[i]
        if in_str:
            if c == chr(92):
                i += 1
            elif c == '"':
                in_str = False
        else:
            if c == '"':
                in_str = True
            elif c == '(':
                depth += 1
            elif c == ')':
                depth -= 1
                if depth == 0:
                    return text[start:i + 1]
        i += 1


def pins(lib, name):
    t = open(f"{K}/symbols/{lib}.kicad_sym", encoding="utf-8").read()
    m = re.search(r'\(symbol "%s"' % re.escape(name), t)
    b = block(t, m.start())
    out = []
    for p in re.finditer(r'\(pin \S+ \S+\s+\(at ([-\d.]+) ([-\d.]+) (\d+)\).*?\(name "([^"]*)".*?\(number "([^"]+)"', b, re.S):
        out.append((p.group(5), p.group(4), p.group(1), p.group(2), p.group(3)))
    return out


if __name__ == "__main__":
    for lib, name in [("Isolator", "PC817"), ("Relay", "SANYOU_SRD_Form_C"),
                      ("Transistor_BJT", "BC547"), ("Diode", "1N4148"),
                      ("Device", "R"), ("Connector_Generic", "Conn_01x02")]:
        print(lib, name)
        for p in pins(lib, name):
            print("   pin", p[0], "name", p[1], "at", p[2], p[3], "angle", p[4])
