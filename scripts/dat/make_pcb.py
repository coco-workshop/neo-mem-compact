#!/usr/bin/python3
"""Build the DAT board (unrouted) from design.py; also writes the CPLD pin constraints."""
import json, os, sys
import numpy as np
import pcbnew
from scipy.optimize import linear_sum_assignment

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, '..', '..', 'boards', 'dat', 'hardware')
CPLD_DIR = os.path.join(HERE, '..', '..', 'boards', 'dat', 'cpld')
NAME = 'neo-mem-2048k-dat'
sys.path.insert(0, HERE)
import design as D

LIB = '/usr/share/kicad/footprints/'
mm = pcbnew.FromMM
X0, Y0 = 100.0, 60.0                       # CPU pin 1
PLACE = {
    'J1': (X0, Y0, 0),
    'U1': (X0 + 7.62, Y0 + 58.2, 0),
    'J3': (X0 + 1.3, Y0 + 72.6, 90),       # 2x5 JTAG: odd pins along +x, even row above
    'J2': (X0 + 15.24, Y0 + 66.7, 0),      # 1x4 bank header (G G B B), runs down +y
    'J4': (X0 + 18.9, Y0 + 66.7, 0),       # 1x2 turbo LED header beside it
    'R1': (X0 + 18.9, Y0 + 72.2, 90),
    'R2': (X0 + 18.9, Y0 + 74.2, 90),
    'R3': (X0 + 12.85, Y0 + 66.6, 90),
    'JP1': (X0 + 7.62, Y0 + 51.6, 0),      # back side, between the CPU rows
}
XR, YB = X0 + 20.3, Y0 + 76.4             # right edge of the CPLD end, bottom edge
# Same width as the CPU along its length; the CPLD end widens to the right for J4.
OUTLINE = [(X0 - 2.2, Y0 - 1.2), (X0 - 1.2, Y0 - 2.2), (X0 + 16.44, Y0 - 2.2), (X0 + 17.44, Y0 - 1.2),
           (X0 + 17.44, Y0 + 50.0), (X0 + 18.44, Y0 + 51.0), (XR - 1.0, Y0 + 51.0), (XR, Y0 + 52.0),
           (XR, YB - 1.0), (XR - 1.0, YB), (X0 - 1.2, YB), (X0 - 2.2, YB - 1.0)]


def padpos(fp, num):
    for p in fp.Pads():
        if p.GetNumber() == str(num):
            v = p.GetPosition()
            return v.x / 1e6, v.y / 1e6
    raise KeyError(num)


def load(board, ref):
    p = D.PARTS[ref]
    lib, name = p['fp'].split(':')
    fp = pcbnew.FootprintLoad(LIB + lib + '.pretty', name)
    fp.SetReference(ref); fp.SetValue(p['value']); fp.SetFPIDAsString(p['fp'])
    board.Add(fp)
    return fp


def main():
    os.makedirs(OUT, exist_ok=True)
    board = pcbnew.BOARD()
    fps = {}
    for ref in D.PARTS:
        if ref.startswith('C'):
            continue
        fp = load(board, ref)
        x, y, rot = PLACE[ref]
        fp.SetPosition(pcbnew.VECTOR2I(mm(x), mm(y)))
        fp.SetOrientationDegrees(rot)
        if ref == 'JP1':
            fp.Flip(fp.GetPosition(), False)
        fps[ref] = fp
    # wire-wrap socket tails are 0.64 mm square: open the DIP holes to 1.0 mm
    for p in fps['J1'].Pads():
        p.SetDrillSize(pcbnew.VECTOR2I(mm(1.0), mm(1.0)))
        p.SetSize(pcbnew.VECTOR2I(mm(1.7), mm(1.7)))
    assert padpos(fps['J1'], 1) == (X0, Y0) and abs(padpos(fps['J1'], 21)[1] - (Y0 + 48.26)) < 0.01

    # decoupling: one cap just outside each CPLD VCC pin
    U = fps['U1']; cx, cy = PLACE['U1'][:2]
    for c, vp in zip(D.CAPS, D.CPLD_VCC):
        px, py = padpos(U, vp)
        dx, dy = px - cx, py - cy
        if abs(dx) > abs(dy):   # left/right side: cap vertical, outside the pad
            x, y, rot = px + (1.75 if dx > 0 else -1.75), py, 90 if dx > 0 else -90
        else:
            x, y, rot = px, py + (1.75 if dy > 0 else -1.75), 0 if dy > 0 else 180
        fp = load(board, c)
        fp.SetPosition(pcbnew.VECTOR2I(mm(x), mm(y))); fp.SetOrientationDegrees(rot)
        fps[c] = fp

    # CPLD pin assignment: Hungarian on distance from each signal's source pad
    def src(sig):
        if sig in ('BANK0', 'BANK1'):
            return padpos(fps['J2'], {'BANK0': 3, 'BANK1': 4}[sig])
        if sig == 'LED_FASTn':
            return padpos(fps['J4'], 2)
        if sig == 'EN2M':
            return padpos(fps['JP1'], 2)
        return padpos(fps['J1'], next(k for k, v in D.CPU.items() if v == sig))
    # The assignment in assign.json is frozen: it is the one the CPLD logic was fitted
    # with. Only if it is missing is a new one chosen (and the logic must be refitted).
    apath = os.path.join(HERE, 'assign.json')
    if os.path.exists(apath):
        a = {int(k): v for k, v in json.load(open(apath)).items()}
    else:
        sigs, pins = D.IO_SIGNALS, D.CPLD_IO
        cost = np.array([[np.hypot(*(np.subtract(src(s), padpos(U, p)))) for p in pins] for s in sigs])
        r, c = linear_sum_assignment(cost)
        a = {pins[j]: sigs[i] for i, j in zip(r, c)}
        json.dump({str(k): v for k, v in sorted(a.items())}, open(apath, 'w'), indent=1)
        import importlib; importlib.reload(D)
    assert sorted(a.values()) == sorted(D.IO_SIGNALS), 'assign.json does not cover IO_SIGNALS'

    nets = {}
    def net(name):
        if name not in nets:
            n = pcbnew.NETINFO_ITEM(board, name); board.Add(n); nets[name] = n
        return nets[name]
    for ref, p in D.PARTS.items():
        for pad in fps[ref].Pads():
            name = p['pins'].get(int(pad.GetNumber()))
            if name:
                pad.SetNet(net(name))

    for i in range(len(OUTLINE)):
        s = pcbnew.PCB_SHAPE(board); s.SetShape(pcbnew.SHAPE_T_SEGMENT)
        a0, e = OUTLINE[i], OUTLINE[(i + 1) % len(OUTLINE)]
        s.SetStart(pcbnew.VECTOR2I(mm(a0[0]), mm(a0[1]))); s.SetEnd(pcbnew.VECTOR2I(mm(e[0]), mm(e[1])))
        s.SetLayer(pcbnew.Edge_Cuts); s.SetWidth(mm(0.05)); board.Add(s)

    for ref, fp in fps.items():
        rf = fp.Reference()
        rf.SetTextSize(pcbnew.VECTOR2I(mm(0.8), mm(0.8))); rf.SetTextThickness(mm(0.12))
        if ref[0] in 'CRT' or ref in ('JP1', 'J1'):
            rf.SetLayer(pcbnew.F_Fab)
        elif ref == 'U1':
            rf.SetPosition(fp.GetPosition()); rf.SetTextAngleDegrees(0)
        fp.Value().SetVisible(False)
    for r_ in ('J2', 'J3', 'J4'):
        fps[r_].Reference().SetLayer(pcbnew.F_Fab)

    def text(s, x, y, size=0.8, angle=0, back=False):
        t = pcbnew.PCB_TEXT(board); t.SetText(s); t.SetLayer(pcbnew.B_SilkS if back else pcbnew.F_SilkS)
        if back: t.SetMirrored(True)
        t.SetPosition(pcbnew.VECTOR2I(mm(x), mm(y))); t.SetTextAngleDegrees(angle)
        t.SetTextSize(pcbnew.VECTOR2I(mm(size), mm(size))); t.SetTextThickness(mm(size * 0.15))
        board.Add(t)
    text('neo-mem-2048k-compact', X0 + 7.62, Y0 + 20.0, 1.0, 90)
    text('DAT board v2', X0 + 9.5, Y0 + 20.0, 1.0, 90)
    text('CPU pin 1', X0 + 5.6, Y0 + 0.0, 0.8)
    text('JTAG', X0 + 6.4, Y0 + 74.9, 0.8, back=True)
    for i, t_ in enumerate(('G', 'G', 'B', 'B')):                 # back silk beside J2
        text(t_, X0 + 13.6, Y0 + 69.24 + 2.54 * (i - 1), 0.8, back=True)
    text('LED', X0 + 18.9, Y0 + 64.4, 0.8, back=True)
    text('+', X0 + 17.4, Y0 + 63.9, 0.8, back=True)
    text('512K  JP1  2MB', X0 + 7.62, Y0 + 49.6, 0.8, back=True)  # reads correctly from the back: pad 1 (2MB) is on the right

    ds = board.GetDesignSettings()
    ds.m_TrackMinWidth = mm(0.15); ds.m_MinClearance = mm(0.15)
    ds.m_ViasMinSize = mm(0.5); ds.m_MinThroughDrill = mm(0.3); ds.m_CopperEdgeClearance = mm(0.3)
    path = os.path.join(OUT, NAME + '.kicad_pcb')
    board.Save(path)

    # fitter pin constraints, generated from the same assignment the board uses
    sigpin = {v: k for k, v in a.items()}
    sigpin.update({'ECLK': 37, 'QCLK': 38, 'RESETn': 39, 'RW': 40})
    vname = lambda s: s
    ins = ['A%d' % i for i in range(16)] + ['D0', 'D1', 'D3', 'D6', 'D7', 'RW', 'ECLK', 'QCLK', 'RESETn', 'EN2M']
    outs = ['BANK0', 'BANK1', 'LED_FASTn']
    lines = ['// AUTO-GENERATED by scripts/dat/make_pcb.py - pin numbers must match the PCB.',
             '// Build with cpld/build.sh (hoglet67/atf15xx_yosys + Atmel fit1504 from ProChip 5.0.x).',
             '// E and Q are named ECLK/QCLK here: top-level ports called E or Q collide with',
             '// cell pin names and make fit1504 reject the EDIF netlist.',
             '`include "dat2m.v"', '',
             'module dat2m_top (',
             ',\n'.join(['    input  wire %s' % s_ for s_ in ins] + ['    output wire %s' % s_ for s_ in outs]),
             ');',
             '    dat2m core (.A({%s}),' % ', '.join('A%d' % i for i in range(15, -1, -1)),
             '                .D0(D0), .D1(D1), .D3(D3), .D6(D6), .D7(D7), .RW(RW), .E(ECLK), .Q(QCLK),',
             '                .RESETn(RESETn), .EN2M(EN2M), .BANK({BANK1, BANK0}), .LED_FASTn(LED_FASTn));',
             'endmodule', '',
             '// Pin assignment (ATF1504AS TQFP-44). JTAG: 1 TDI, 7 TMS, 26 TCK, 32 TDO.',
             '//PIN: CHIP "dat2m_top" ASSIGNED TO AN TQFP44']
    lines += ['//PIN: %-10s : %d' % (s_, sigpin[s_]) for s_ in ins + outs]
    lines.append('')
    open(os.path.join(CPLD_DIR, 'dat2m_top.v'), 'w').write('\n'.join(lines))
    print('saved', path, 'nets', len(nets))


if __name__ == '__main__':
    main()
