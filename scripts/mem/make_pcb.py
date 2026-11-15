#!/usr/bin/python3
"""Build the 2 MB memory board (unrouted) from design.py."""
import json, os, sys
import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, '..', '..', 'boards', '2048k-mem', 'hardware')
NAME = 'neo-mem-2048k-mem'
sys.path.insert(0, HERE)
import design as D

LIB = '/usr/share/kicad/footprints/'
mm = pcbnew.FromMM

# Absolute placements (mm, deg). J1/J2 identical to the proven cc3-512k board.
PLACE = {
    'J1': (98.298, 70.612, 0, True),
    'J2': (138.938, 134.112, 90, True),
    'U1': (108.5, 104.0, None, False),      # rotation chosen so the address row faces U3
    'U3': (104.9, 123.0, None, False),      # '574s: D side faces J2 (down), Q side faces the SRAM
    'U4': (112.3, 123.0, None, False),
    'U2': (109.0, 86.6, 0, False),
    'J3': (121.5, 131.6, 90, False),        # BANK0, BANK1, GND -> pins run +x
    'R1': (121.5, 128.2, 90, False),
    'R2': (124.04, 128.2, 90, False),
    'C1': (108.25, 92.2, 90, False),
    'C2': (114.2, 85.0, -90, False),
    'C3': (0, 0, 0, False),                 # placed next to U3/U4 pin 20 below
    'C4': (0, 0, 0, False),
}
OUTLINE = [(95.123, 69.977), (97.028, 68.072), (104.8, 68.072), (120.0, 83.272),
           (120.0, 127.0), (166.878, 127.0), (168.783, 128.905), (168.778, 134.747), (168.633, 135.474), (168.222, 136.091), (167.605, 136.502), (166.878, 136.647),
           (101.88, 136.652), (95.123, 129.895)]


def place(board):
    fps = {}
    for ref, p in D.PARTS.items():
        lib, name = p['fp'].split(':')
        fp = pcbnew.FootprintLoad(LIB + lib + '.pretty', name)
        fp.SetReference(ref)
        fp.SetValue(p['value'])
        fp.SetFPIDAsString(p['fp'])
        board.Add(fp)
        x, y, rot, back = PLACE[ref]
        fp.SetPosition(pcbnew.VECTOR2I(mm(x), mm(y)))
        fp.SetOrientationDegrees(rot or 0)
        if back:
            fp.Flip(fp.GetPosition(), False)
        fps[ref] = fp
    return fps


def padpos(fp, num):
    for p in fp.Pads():
        if p.GetNumber() == str(num):
            v = p.GetPosition()
            return v.x / 1e6, v.y / 1e6
    raise KeyError(num)


def fix_connector(fp, target_first, target_last, n):
    """Rotate a flipped header until pin1/pinN land on the traced socket positions."""
    for rot in (0, 90, 180, 270, -90):
        fp.SetOrientationDegrees(rot)
        a, b = padpos(fp, 1), padpos(fp, n)
        if (abs(a[0] - target_first[0]) < 0.01 and abs(a[1] - target_first[1]) < 0.01 and
                abs(b[0] - target_last[0]) < 0.01 and abs(b[1] - target_last[1]) < 0.01):
            return rot
    raise RuntimeError('cannot orient ' + fp.GetReference())


def orient_ff(fp):
    """'574 rows horizontal with the D inputs (pins 2-9) at the bottom."""
    for rot in (0, 90, 180, 270):
        fp.SetOrientationDegrees(rot)
        p2, p9, p19 = padpos(fp, 2), padpos(fp, 9), padpos(fp, 19)
        if abs(p2[1] - p9[1]) < 0.01 and p2[1] > p19[1]:
            return rot
    raise RuntimeError('cannot orient FF')


def orient_sram(fp):
    """Rows horizontal, address row (pins 1-24) at the bottom, facing U3."""
    for rot in (0, 90, 180, 270):
        fp.SetOrientationDegrees(rot)
        p1, p24, p25 = padpos(fp, 1), padpos(fp, 24), padpos(fp, 25)
        if abs(p1[1] - p24[1]) < 0.01 and p1[1] > p25[1]:
            return rot
    raise RuntimeError('cannot orient SRAM')


def assign(fps):
    """Permute SRAM address/data pins by geometry so routes don't cross."""
    U1, J1 = fps['U1'], fps['J1']
    jy = lambda n: padpos(J1, [k for k, v in D.J1.items() if v == n][0])[1]
    a = {}
    # D0-7 come up from the lower half of J1 around the left of the SRAM: nearest-first.
    lo_nets = sorted(['D%d' % i for i in range(8)], key=jy)
    a.update(dict(zip(sorted(D.SRAM_LO_LANE, key=lambda p: padpos(U1, p)[0]), lo_nets)))
    # D8-15 come down from the upper half of J1: nearest (lowest) first.
    hi_nets = sorted(['D%d' % i for i in range(8, 16)], key=lambda n: -jy(n))
    a.update(dict(zip(sorted(D.SRAM_HI_LANE, key=lambda p: padpos(U1, p)[0]), hi_nets)))
    # Latched bits (row + bank) from U3's top row go straight up into the address row.
    q = sorted([(padpos(fps[u], p)[0], n) for u in ('U3', 'U4') for p, n in D.PARTS[u]['pins'].items()
                if n[0] in 'RB' and n != 'RAS' and len(n) <= 2])
    p1_y = padpos(U1, 1)[1]
    bottom = sorted([p for p in D.SRAM_ADDR_PINS if abs(padpos(U1, p)[1] - p1_y) < 0.01],
                    key=lambda p: padpos(U1, p)[0])
    right = bottom[-len(q):]
    a.update(dict(zip(right, [n for _, n in q])))
    # Column bits from J2 take the remaining address pins, in J2 order left->right.
    rest = sorted(bottom[:-len(q)], key=lambda p: padpos(U1, p)[0]) + \
        sorted([p for p in D.SRAM_ADDR_PINS if p not in bottom], key=lambda p: padpos(U1, p)[0])
    zs = ['Z0', 'Z1', 'Z2', 'Z3', 'Z6', 'Z5', 'Z4', 'Z7', 'Z8']
    a.update(dict(zip(rest, zs)))
    assert sorted(a) == sorted(D.SRAM_ADDR_PINS + D.SRAM_LO_LANE + D.SRAM_HI_LANE), sorted(a)
    assert sorted(a.values()) == sorted(['D%d' % i for i in range(16)] + ['Z%d' % i for i in range(9)] +
                                        ['R%d' % i for i in range(9)] + ['B0', 'B1'])
    return a


def main():
    os.makedirs(OUT, exist_ok=True)
    board = pcbnew.BOARD()
    fps = place(board)
    fix_connector(fps['J1'], (98.298, 70.612), (98.298, 129.032), 24)
    fix_connector(fps['J2'], (138.938, 134.112), (166.878, 134.112), 12)
    print('SRAM rotation', orient_sram(fps['U1']))
    for u, c in (('U3', 'C3'), ('U4', 'C4')):
        print(u, 'rotation', orient_ff(fps[u]))
        x, y = padpos(fps[u], 20)
        fps[c].SetPosition(pcbnew.VECTOR2I(mm(x), mm(y - 1.55)))   # just above the VCC pin
        fps[c].SetOrientationDegrees(0)

    a = assign(fps)
    json.dump({str(k): v for k, v in sorted(a.items())}, open(os.path.join(HERE, 'assign.json'), 'w'), indent=1)
    import importlib; importlib.reload(D)

    nets = {}
    def net(name):
        if name not in nets:
            n = pcbnew.NETINFO_ITEM(board, name)
            board.Add(n)
            nets[name] = n
        return nets[name]
    for ref, p in D.PARTS.items():
        for pad in fps[ref].Pads():
            name = p['pins'].get(int(pad.GetNumber()))
            if name:
                pad.SetNet(net(name))

    for i in range(len(OUTLINE)):
        s = pcbnew.PCB_SHAPE(board)
        s.SetShape(pcbnew.SHAPE_T_SEGMENT)
        s.SetStart(pcbnew.VECTOR2I(mm(OUTLINE[i][0]), mm(OUTLINE[i][1])))
        e = OUTLINE[(i + 1) % len(OUTLINE)]
        s.SetEnd(pcbnew.VECTOR2I(mm(e[0]), mm(e[1])))
        s.SetLayer(pcbnew.Edge_Cuts)
        s.SetWidth(mm(0.05))
        board.Add(s)

    # Tidy silkscreen: IC refs centred in the body, 0402 cap refs on fab only.
    for ref, fp in fps.items():
        r = fp.Reference()
        r.SetTextSize(pcbnew.VECTOR2I(mm(0.8), mm(0.8)))
        r.SetTextThickness(mm(0.12))
        if ref[0] in 'CR':
            r.SetLayer(pcbnew.F_Fab)
        elif ref.startswith('U'):
            r.SetPosition(fp.GetPosition())
            r.SetTextAngleDegrees(0)
        fp.Value().SetVisible(False)
    for ref, (x, y) in {'J1': (101.6, 70.1), 'J2': (136.6, 131.0)}.items():
        r = fps[ref].Reference(); r.SetLayer(pcbnew.B_SilkS)
        r.SetPosition(pcbnew.VECTOR2I(mm(x), mm(y)))
    fps['J3'].Reference().SetLayer(pcbnew.F_Fab)
    lab = pcbnew.PCB_TEXT(board); lab.SetText('B0 B1 G'); lab.SetLayer(pcbnew.F_SilkS)
    lab.SetPosition(pcbnew.VECTOR2I(mm(124.04), mm(135.4)))
    lab.SetTextSize(pcbnew.VECTOR2I(mm(0.8), mm(0.8))); lab.SetTextThickness(mm(0.12)); board.Add(lab)
    # Silkscreen title
    t = pcbnew.PCB_TEXT(board)
    t.SetText('neo-mem-2048k-compact\nCoCo 3 2MB SRAM v1')
    t.SetPosition(pcbnew.VECTOR2I(mm(153), mm(129.6)))
    t.SetLayer(pcbnew.F_SilkS)
    t.SetTextSize(pcbnew.VECTOR2I(mm(1.0), mm(1.0)))
    t.SetTextThickness(mm(0.15))
    board.Add(t)

    ds = board.GetDesignSettings()
    ds.m_TrackMinWidth = mm(0.15)
    ds.m_MinClearance = mm(0.15)
    ds.m_ViasMinSize = mm(0.5)
    ds.m_MinThroughDrill = mm(0.3)
    ds.m_CopperEdgeClearance = mm(0.3)
    path = os.path.join(OUT, NAME + '.kicad_pcb')
    board.Save(path)
    area = 0.5 * abs(sum(OUTLINE[i][0] * OUTLINE[(i + 1) % len(OUTLINE)][1] -
                         OUTLINE[(i + 1) % len(OUTLINE)][0] * OUTLINE[i][1] for i in range(len(OUTLINE))))
    print('saved', path, 'area mm2 %.0f' % area, 'nets', len(nets))


if __name__ == '__main__':
    main()
