#!/usr/bin/python3
"""Unrouted pcb -> DSN (inset boundary) -> Freerouting -> routed pcb with GND pours + DRC.
usage: route.py in.kicad_pcb out.kicad_pcb [passes]"""
import os, re, shutil, subprocess, sys
import pcbnew
from shapely.geometry import Polygon

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from ses_import import main as ses_import

FR = os.environ.get('FREEROUTING_JAR', 'freerouting.jar')
EDGE = 0.3   # copper-to-edge clearance we want (mm)


def board_outline(b):
    segs = [((round(d.GetStart().x / 1e6, 4), round(d.GetStart().y / 1e6, 4)),
             (round(d.GetEnd().x / 1e6, 4), round(d.GetEnd().y / 1e6, 4)))
            for d in b.GetDrawings() if d.GetLayer() == pcbnew.Edge_Cuts]
    pts = [segs[0][0], segs[0][1]]; rest = segs[1:]
    while rest:
        nxt = next(sg for sg in rest if pts[-1] in sg); rest.remove(nxt)
        pts.append(nxt[1] if nxt[0] == pts[-1] else nxt[0])
    return pts[:-1]


def main(src, dst, passes='60', threads='1', zones='GND,GND'):
    src, dst = os.path.abspath(src), os.path.abspath(dst)
    work = os.path.join(os.path.dirname(dst), 'route_work')
    os.makedirs(work, exist_ok=True)
    dsn, ses = os.path.join(work, 'b.dsn'), os.path.join(work, 'b.ses')
    b = pcbnew.LoadBoard(src)
    OUTLINE = board_outline(b)
    pcbnew.ExportSpecctraDSN(b, dsn)
    # Inset the routing boundary so Freerouting keeps EDGE from the board edge.
    inner = Polygon(OUTLINE).buffer(-(EDGE - 0.1), join_style=2)
    coords = ' '.join('%.1f %.1f' % (x * 1000, -y * 1000) for x, y in list(inner.exterior.coords))
    txt = open(dsn).read()
    txt, n = re.subn(r'\(boundary\s*\(path pcb 0[^)]*\)\s*\)', '(boundary (path pcb 0 %s))' % coords, txt)
    assert n == 1, 'boundary not found'
    open(dsn, 'w').write(txt)
    log = subprocess.run(['java', '-jar', FR, '-de', dsn, '-do', ses, '-mp', passes, '-mt', threads,
                          '--gui.enabled=false'] + os.environ.get('FR_EXTRA', '').split(),
                         capture_output=True, text=True, timeout=int(os.environ.get('FR_TIMEOUT', '3000')))
    last = [l for l in log.stdout.splitlines() + log.stderr.splitlines() if 'unrouted' in l]
    print(last[-1][-160:] if last else log.stdout[-500:])
    shutil.copy(src, dst)
    shutil.copy(src.replace('.kicad_pcb', '.kicad_pro'), dst.replace('.kicad_pcb', '.kicad_pro'))
    ses_import(dst, ses, dst)

    # GND pours on both layers
    b = pcbnew.LoadBoard(dst)
    for layer, zn in zip((pcbnew.F_Cu, pcbnew.B_Cu), zones.split(',')):
        gnd = b.FindNet(zn)
        z = pcbnew.ZONE(b)
        z.SetLayer(layer)
        z.SetNet(gnd)
        z.SetLocalClearance(pcbnew.FromMM(0.2))
        z.SetMinThickness(pcbnew.FromMM(0.2))
        z.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL)
        z.SetThermalReliefGap(pcbnew.FromMM(0.25))
        z.SetThermalReliefSpokeWidth(pcbnew.FromMM(0.3))
        z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
        ol = z.Outline()
        ol.NewOutline()
        for x, y in OUTLINE:
            ol.Append(pcbnew.FromMM(x), pcbnew.FromMM(y))
        b.Add(z)
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    b.Save(dst)
    b = pcbnew.LoadBoard(dst)
    rpt = dst.replace('.kicad_pcb', '-drc.txt')
    pcbnew.WriteDRCReport(b, rpt, pcbnew.EDA_UNITS_MILLIMETRES, True)
    print(''.join(l for l in open(rpt) if l.startswith('** Found')))


if __name__ == '__main__':
    main(*sys.argv[1:])
