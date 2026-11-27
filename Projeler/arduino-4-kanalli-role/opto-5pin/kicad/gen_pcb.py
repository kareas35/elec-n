"""design.py'den DÜZELTİLMİŞ 5 pinli izoleli KiCad PCB üretir (pcbnew API).

  - J1: 1x05 kontrol soketi: 1=GND_A, 2=IN1(D4), 3=IN2(D5), 4=IN3(D6), 5=IN4(D7). 5V YOK.
  - J2: tek röle besleme girişi: pin1=harici +5V DC, pin2=GND_B. Arduino USB'den beslenir.
  - GND_A solda; GND_B / +5V_B sağda. X=64.5-67.0 mm bakırsız bariyer.
  - Arduino 5V girişi yoktur; Arduino USB'den beslenir.
  - Basit A* yönlendirici (0.25 mm ızgara, 2 katman, via).
"""
import heapq
import math
import os
import sys

import pcbnew

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from design import build_components, ZONE_NETS  # noqa: E402

KICAD_SHARE = "C:/Program Files/KiCad/10.0/share/kicad/footprints"
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "relay_4ch_5pin.kicad_pcb")

BOARD_W, BOARD_H = 190.0, 120.0
TRACK_W = 0.25
CLEAR = 0.2
VIA_D, VIA_DRILL = 0.6, 0.3
PITCH = 0.25

BARRIER_LO, BARRIER_HI = 64.5, 67.0

# Yerleşim (mm). Sol: kontrol/Arduino. Sağ: izole röle tarafı.
PLACE = {
    "J1": (8, 55, 0),        # 5 pinli kontrol soketi: 1=GND, 2..5=IN1..IN4
    "J2": (155, 108, 0),     # Tek röle besleme: 1=+5V DC, 2=GND
    "C1": (138, 108, 0),
    "C2": (124, 108, 0),
}
for k in range(1, 5):
    y = 18 + 24 * (k - 1)
    PLACE[f"Rled{k}"] = (30, y, 0)
    PLACE[f"U{k}"] = (62, y, 0)
    PLACE[f"Rpd{k}"] = (78, y, 0)
    PLACE[f"Q{k}"] = (95, y, 0)
    PLACE[f"D{k}"] = (104, y - 6, 0)
    PLACE[f"K{k}"] = (120, y, 0)
    PLACE[f"J{k + 2}"] = (155, y, 0)

SILK = [
    (7, 42, "J1 5P (5V YOK)"),
    (7, 45, "ARDUINO USB'DEN"),
    (7, 116, "J1: 1=GND 2=IN1(D4) 3=IN2(D5) 4=IN3(D6) 5=IN4(D7)"),
    (140, 117, "J2 +5V DC / GND"),
    (145, 8, "YUK COM/NO"),
    (58, 110, "IZOLASYON"),
]


def mm(v):
    return pcbnew.FromMM(v)


def V(x, y):
    return pcbnew.VECTOR2I(mm(x), mm(y))


def add_silk(board):
    for x, y, txt in SILK:
        t = pcbnew.PCB_TEXT(board)
        t.SetText(txt)
        t.SetPosition(V(x, y))
        t.SetLayer(pcbnew.F_SilkS)
        t.SetTextSize(pcbnew.VECTOR2I(mm(1.2), mm(1.2)))
        t.SetTextThickness(mm(0.18))
        try:
            t.SetHorizJustify(pcbnew.GR_TEXT_H_ALIGN_LEFT)
        except Exception:
            pass
        board.Add(t)


def build_board():
    board = pcbnew.BOARD()
    comps = build_components()

    net_names = sorted({n for c in comps for n in c[4].values()} | ZONE_NETS)
    nets = {}
    for n in net_names:
        ni = pcbnew.NETINFO_ITEM(board, n)
        board.Add(ni)
        nets[n] = ni

    pts = [(0, 0), (BOARD_W, 0), (BOARD_W, BOARD_H), (0, BOARD_H)]
    for i in range(4):
        s = pcbnew.PCB_SHAPE(board)
        s.SetShape(pcbnew.SHAPE_T_SEGMENT)
        s.SetLayer(pcbnew.Edge_Cuts)
        s.SetWidth(mm(0.1))
        s.SetStart(V(*pts[i]))
        s.SetEnd(V(*pts[(i + 1) % 4]))
        board.Add(s)

    for ref, lib_id, value, fp_id, pinmap in comps:
        lib, name = fp_id.split(":")
        fp = pcbnew.FootprintLoad(f"{KICAD_SHARE}/{lib}.pretty", name)
        if fp is None:
            raise SystemExit(f"Footprint bulunamadı: {fp_id}")
        x, y, rot = PLACE[ref]
        fp.SetReference(ref)
        fp.SetValue(value)
        fp.SetPosition(V(x, y))
        if rot:
            fp.SetOrientationDegrees(rot)
        for pad in fp.Pads():
            num = pad.GetNumber()
            if num in pinmap:
                pad.SetNet(nets[pinmap[num]])
        board.Add(fp)

    add_silk(board)
    return board, nets


def add_zone(board, net, layer, rect):
    z = pcbnew.ZONE(board)
    z.SetLayer(layer)
    z.SetNet(net)
    z.SetIsFilled(True)
    ol = z.Outline()
    ol.NewOutline()
    for x, y in rect:
        ol.Append(mm(x), mm(y))
    board.Add(z)
    return z


class Router:
    def __init__(self, board):
        self.board = board
        self.W = int(BOARD_W / PITCH) + 1
        self.H = int(BOARD_H / PITCH) + 1
        self.owner = [[[-1] * self.W for _ in range(self.H)] for _ in range(2)]
        self.net_ids = {}
        self.tracks = []
        self.vias = []

    def nid(self, name):
        if name is None:
            return -2
        if name not in self.net_ids:
            self.net_ids[name] = len(self.net_ids)
        return self.net_ids[name]

    def cell(self, x_mm, y_mm):
        return int(round(x_mm / PITCH)), int(round(y_mm / PITCH))

    def paint(self, layer, cx, cy, r, owner):
        for dy in range(-r, r + 1):
            for dx in range(-r, r + 1):
                if dx * dx + dy * dy > r * r + r:
                    continue
                x, y = cx + dx, cy + dy
                if 0 <= x < self.W and 0 <= y < self.H:
                    cur = self.owner[layer][y][x]
                    if cur == -1 or owner == -2:
                        self.owner[layer][y][x] = owner
                    elif cur != owner and cur != -2:
                        self.owner[layer][y][x] = -2

    def paint_rect(self, layer, cx, cy, rx, ry, owner):
        for y in range(cy - ry, cy + ry + 1):
            for x in range(cx - rx, cx + rx + 1):
                if 0 <= x < self.W and 0 <= y < self.H:
                    cur = self.owner[layer][y][x]
                    if cur == -1 or owner == -2:
                        self.owner[layer][y][x] = owner
                    elif cur != owner and cur != -2:
                        self.owner[layer][y][x] = -2

    def paint_board(self):
        edge = int(1.0 / PITCH)
        for layer in range(2):
            for y in range(self.H):
                for x in range(self.W):
                    if x < edge or y < edge or x > self.W - 1 - edge or y > self.H - 1 - edge:
                        self.owner[layer][y][x] = -2
        centers = []
        for fp in self.board.Footprints():
            for pad in fp.Pads():
                net = pad.GetNet()
                name = net.GetNetname() if net and net.GetNetCode() > 0 else None
                nid = self.nid(name)
                hw = pad.GetSize().x / 2 / 1e6
                hh = pad.GetSize().y / 2 / 1e6
                px, py = pad.GetPosition().x / 1e6, pad.GetPosition().y / 1e6
                rx = int(math.ceil((hw + CLEAR + TRACK_W / 2) / PITCH))
                ry = int(math.ceil((hh + CLEAR + TRACK_W / 2) / PITCH))
                cx, cy = self.cell(px, py)
                for layer in range(2):
                    self.paint_rect(layer, cx, cy, rx, ry, nid)
                centers.append((cx, cy, nid))
        for cx, cy, nid in centers:
            for layer in range(2):
                self.owner[layer][cy][cx] = nid
        bx0, bx1 = int(BARRIER_LO / PITCH), int(BARRIER_HI / PITCH)
        for layer in range(2):
            for y in range(self.H):
                for x in range(bx0, bx1 + 1):
                    self.owner[layer][y][x] = -2

    def via_ok(self, nid, x, y):
        r = int(math.ceil((VIA_D / 2 + CLEAR) / PITCH))
        for dy in range(-r, r + 1):
            for dx in range(-r, r + 1):
                if dx * dx + dy * dy > r * r:
                    continue
                xx, yy = x + dx, y + dy
                if not (0 <= xx < self.W and 0 <= yy < self.H):
                    return False
                for layer in range(2):
                    if self.owner[layer][yy][xx] not in (-1, nid):
                        return False
        return True

    def route_path(self, net, sources, targets):
        nid = self.nid(net)
        tset = set(targets)
        if not tset:
            return None

        def h(s):
            _, x, y = s
            return min(abs(x - tx) + abs(y - ty) for (_, tx, ty) in tset)

        openq = []
        best = {}
        came = {}
        for s in sources:
            best[s] = 0
            heapq.heappush(openq, (h(s), 0, s))
        found = None
        while openq:
            f, g, s = heapq.heappop(openq)
            if g != best.get(s):
                continue
            if s in tset:
                found = s
                break
            l, x, y = s
            nbrs = []
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nx, ny = x + dx, y + dy
                if 0 <= nx < self.W and 0 <= ny < self.H:
                    o = self.owner[l][ny][nx]
                    if o == -1 or o == nid:
                        nbrs.append(((l, nx, ny), 1.0))
            ol = 1 - l
            if self.via_ok(nid, x, y):
                nbrs.append(((ol, x, y), 6.0))
            for ns, c in nbrs:
                ng = g + c
                if ng < best.get(ns, 1e18):
                    best[ns] = ng
                    came[ns] = s
                    heapq.heappush(openq, (ng + h(ns), ng, ns))
        if found is None:
            return None
        path = [found]
        while path[-1] in came:
            path.append(came[path[-1]])
        path.reverse()
        return path

    def commit(self, net, path, pad_a_mm, pad_b_mm):
        nid = self.nid(net)
        netinfo = self.board.FindNet(net)
        pts = []
        for (l, x, y) in path:
            pts.append((l, x * PITCH, y * PITCH))
        if pad_a_mm:
            pts[0] = (pts[0][0], pad_a_mm[0], pad_a_mm[1])
        if pad_b_mm:
            pts[-1] = (pts[-1][0], pad_b_mm[0], pad_b_mm[1])

        run = [pts[0]]
        for p in pts[1:]:
            if p[0] != run[-1][0]:
                self._emit_run(netinfo, run)
                self._add_via(netinfo, (run[-1][0], run[-1][1], run[-1][2]))
                run = [p]
            else:
                run.append(p)
        self._emit_run(netinfo, run)

        for (l, x_mm, y_mm) in pts:
            cx, cy = self.cell(x_mm, y_mm)
            self.paint(l, cx, cy, int(math.ceil((TRACK_W / 2 + CLEAR) / PITCH)), nid)
        for i in range(1, len(pts)):
            if pts[i][0] != pts[i - 1][0]:
                cx, cy = self.cell(pts[i - 1][1], pts[i - 1][2])
                for layer in range(2):
                    self.paint(layer, cx, cy, int(math.ceil((VIA_D / 2 + CLEAR) / PITCH)), nid)
        return [(l, *self.cell(x, y)) for (l, x, y) in pts]

    def _emit_run(self, netinfo, run):
        if len(run) < 2:
            return
        keep = [run[0]]
        for i in range(1, len(run) - 1):
            a, b, c = keep[-1], run[i], run[i + 1]
            if (abs(b[1] - a[1]) < 1e-9 and abs(c[1] - b[1]) < 1e-9) or (abs(b[2] - a[2]) < 1e-9 and abs(c[2] - b[2]) < 1e-9):
                continue
            keep.append(b)
        keep.append(run[-1])
        for a, b in zip(keep, keep[1:]):
            self._add_track(netinfo, a, b)

    def _add_track(self, netinfo, a, b):
        if abs(a[1] - b[1]) < 1e-9 and abs(a[2] - b[2]) < 1e-9:
            return
        t = pcbnew.PCB_TRACK(self.board)
        t.SetStart(V(a[1], a[2]))
        t.SetEnd(V(b[1], b[2]))
        t.SetWidth(mm(TRACK_W))
        t.SetLayer(pcbnew.F_Cu if a[0] == 0 else pcbnew.B_Cu)
        t.SetNet(netinfo)
        self.board.Add(t)

    def _add_via(self, netinfo, p):
        v = pcbnew.PCB_VIA(self.board)
        v.SetPosition(V(p[1], p[2]))
        v.SetWidth(mm(VIA_D))
        v.SetDrill(mm(VIA_DRILL))
        v.SetNet(netinfo)
        self.board.Add(v)


def route_all(board):
    rt = Router(board)
    rt.paint_board()
    by_net = {}
    for fp in board.Footprints():
        ref = fp.GetReference()
        for pad in fp.Pads():
            net = pad.GetNet()
            if not net or net.GetNetCode() == 0:
                continue
            name = net.GetNetname()
            if name in ZONE_NETS:
                continue
            by_net.setdefault(name, []).append((pad, ref))

    ok, fail = [], []
    for net, pads in sorted(by_net.items()):
        if len(pads) < 2:
            continue
        first, fref = pads[0]
        p0 = (first.GetPosition().x / 1e6, first.GetPosition().y / 1e6)
        cx, cy = rt.cell(*p0)
        tree = [(0, cx, cy), (1, cx, cy)]
        for pad, ref in pads[1:]:
            px, py = pad.GetPosition().x / 1e6, pad.GetPosition().y / 1e6
            tx, ty = rt.cell(px, py)
            targets = [(0, tx, ty), (1, tx, ty)]
            path = rt.route_path(net, tree, targets)
            if path is None:
                fail.append((net, ref, pad.GetNumber()))
                continue
            cells = rt.commit(net, path, None, (px, py))
            for c in cells:
                tree.append(c)
            tree.append((0, tx, ty))
            tree.append((1, tx, ty))
            ok.append((net, ref, pad.GetNumber()))
    return ok, fail


def main():
    board, nets = build_board()
    add_zone(board, nets["GND_A"], pcbnew.B_Cu,
             [(1, 1), (BARRIER_LO - 0.5, 1), (BARRIER_LO - 0.5, BOARD_H - 1), (1, BOARD_H - 1)])
    add_zone(board, nets["GND_B"], pcbnew.B_Cu,
             [(BARRIER_HI + 0.5, 1), (BOARD_W - 1, 1), (BOARD_W - 1, BOARD_H - 1), (BARRIER_HI + 0.5, BOARD_H - 1)])
    add_zone(board, nets["+5V_B"], pcbnew.F_Cu,
             [(BARRIER_HI + 0.5, 1), (BOARD_W - 1, 1), (BOARD_W - 1, BOARD_H - 1), (BARRIER_HI + 0.5, BOARD_H - 1)])
    ok, fail = route_all(board)
    print("bağlanan:", len(ok), "başarısız:", len(fail))
    for f in fail:
        print("  FAIL", f)
    filler = pcbnew.ZONE_FILLER(board)
    filler.Fill(board.Zones())
    board.Save(OUT)
    print("yazıldı:", OUT)


if __name__ == "__main__":
    main()
