#!/usr/bin/python3
"""Build neo-mem-512k-compact.kicad_pcb (unrouted) from design.py."""
import json, os, sys
import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, '..', '..', 'boards', '512k', 'hardware')
sys.path.insert(0, HERE)
import design as D

LIB = '/usr/share/kicad/footprints/'
mm = pcbnew.FromMM

# Absolute placements (mm, deg). J1/J2 identical to the proven cc3-512k board.
PLACE = {
    'J1': (98.298, 70.612, 0, True),
    'J2': (138.938, 134.112, 90, True),
    'U1': (108.0, 105.5, 0, False),
    'U3': (104.9, 123.0, None, False),      # '574s: D side faces J2 (down), Q side faces the SRAM
    'U4': (112.3, 123.0, None, False),
    'U2': (109.0, 88.0, 0, False),
    'C1': (100.45, 105.5, -90, False),
    'C2': (115.6, 105.5, 90, False),
    'C3': (114.2, 86.5, -90, False),
    'C4': (0, 0, 0, False),                 # placed next to U3/U4 pin 20 below
    'C5': (0, 0, 0, False),
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


def assign(fps):
    """Pick SRAM address/data pin permutations that minimise crossings."""
    U1, J1 = fps['U1'], fps['J1']
    a = {}
    # Low lane (left column, faces J1): monotonic in y.
    lo_nets = sorted([n for n in D.J1.values() if n in ['D%d' % i for i in range(8)]],
                     key=lambda n: padpos(J1, [k for k, v in D.J1.items() if v == n][0])[1])
    lo_pins = sorted(D.SRAM_LO_LANE, key=lambda p: padpos(U1, p)[1])
    a.update(dict(zip(lo_pins, lo_nets)))
    # High lane (right column): routes wrap over the top, so order is reversed.
    hi_nets = sorted([n for n in D.J1.values() if n in ['D%d' % i for i in range(8, 16)]],
                     key=lambda n: -padpos(J1, [k for k, v in D.J1.items() if v == n][0])[1])
    hi_pins = sorted(D.SRAM_HI_LANE, key=lambda p: padpos(U1, p)[1])
    a.update(dict(zip(hi_pins, hi_nets)))
    # Row bits: U3 outputs (top row) -> SRAM bottom address pins.
    rq = sorted([(padpos(fps[u], q), net) for u in ('U3', 'U4') for q, net in D.PARTS[u]['pins'].items()
                 if net.startswith('R') and net != 'RAS'])
    by_x_desc = [net for _, net in sorted(rq, key=lambda t: -t[0][0])]
    right_bottom = [23, 24, 25, 26, 27]
    left_bottom = [22, 21, 20, 19]
    for pin, net in zip(right_bottom, by_x_desc[:5]):
        a[pin] = net
    for pin, net in zip(left_bottom, list(reversed(by_x_desc[5:]))):
        a[pin] = net
    # Column bits: straight from J2 to the remaining address pins.
    zpins = [18, 5, 4, 3, 2, 1, 42, 43, 44]
    for pin, net in zip(zpins, D.ROW_ORDER[::-1]):
        a[pin] = net
    assert sorted(a) == sorted(D.SRAM_ADDR_PINS + D.SRAM_LO_LANE + D.SRAM_HI_LANE)
    return a


def main():
    os.makedirs(OUT, exist_ok=True)
    board = pcbnew.BOARD()
    fps = place(board)
    fix_connector(fps['J1'], (98.298, 70.612), (98.298, 129.032), 24)
    fix_connector(fps['J2'], (138.938, 134.112), (166.878, 134.112), 12)
    for u, c in (('U3', 'C4'), ('U4', 'C5')):
        orient_ff(fps[u])
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
        if ref.startswith('C'):
            r.SetLayer(pcbnew.F_Fab)
        elif ref.startswith('U'):
            r.SetPosition(fp.GetPosition())
            r.SetTextAngleDegrees(0)
        fp.Value().SetVisible(False)
    for ref, (x, y) in {'J1': (101.6, 70.1), 'J2': (136.6, 131.0)}.items():
        r = fps[ref].Reference(); r.SetLayer(pcbnew.B_SilkS)
        r.SetPosition(pcbnew.VECTOR2I(mm(x), mm(y)))
    # Silkscreen title
    t = pcbnew.PCB_TEXT(board)
    t.SetText('neo-mem-512k-compact\nCoCo 3 512K SRAM v2')
    t.SetPosition(pcbnew.VECTOR2I(mm(150), mm(129.6)))
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
    path = os.path.join(OUT, 'neo-mem-512k-compact.kicad_pcb')
    board.Save(path)
    area = 0.5 * abs(sum(OUTLINE[i][0] * OUTLINE[(i + 1) % len(OUTLINE)][1] -
                         OUTLINE[(i + 1) % len(OUTLINE)][0] * OUTLINE[i][1] for i in range(len(OUTLINE))))
    print('saved', path, 'area mm2 %.0f' % area, 'nets', len(nets))


if __name__ == '__main__':
    main()
