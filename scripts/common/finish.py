#!/usr/bin/python3
"""Post-route clean-up: optional pour keepouts around footprints, removal of exactly the
track stubs DRC reports as dangling, refill, final DRC report.
usage: finish.py board.kicad_pcb report.txt [KEEPOUT_REF ...]"""
import re, sys
import pcbnew

mm = pcbnew.FromMM


def drc(path, rpt):
    b = pcbnew.LoadBoard(path)
    pcbnew.WriteDRCReport(b, rpt, pcbnew.EDA_UNITS_MILLIMETRES, True)
    return open(rpt).read()


def main(path, rpt, *keepouts):
    b = pcbnew.LoadBoard(path)
    for ref in keepouts:
        bb = b.FindFootprintByReference(ref).GetBoundingBox(False, False)
        for layer in (pcbnew.F_Cu, pcbnew.B_Cu):
            z = pcbnew.ZONE(b); z.SetIsRuleArea(True); z.SetDoNotAllowCopperPour(True)
            z.SetDoNotAllowTracks(False); z.SetDoNotAllowVias(False)
            z.SetDoNotAllowPads(False); z.SetDoNotAllowFootprints(False)
            z.SetLayer(layer); ol = z.Outline(); ol.NewOutline()
            m = mm(0.4)
            for x, y in ((bb.GetX() - m, bb.GetY() - m), (bb.GetRight() + m, bb.GetY() - m),
                         (bb.GetRight() + m, bb.GetBottom() + m), (bb.GetX() - m, bb.GetBottom() + m)):
                ol.Append(x, y)
            b.Add(z)
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    b.Save(path)
    for _ in range(6):
        txt = drc(path, rpt)
        stubs = re.findall(r'\[track_dangling\].*?\n.*?\n\s+@\(([\d.]+) mm, ([\d.]+) mm\): Track \[[^\]]*\] on (\S+), length ([\d.]+) mm', txt)
        vias = re.findall(r'\[via_dangling\].*?\n.*?\n\s+@\(([\d.]+) mm, ([\d.]+) mm\): Via', txt)
        if not stubs and not vias:
            break
        b = pcbnew.LoadBoard(path)
        tracks = [t for t in b.GetTracks() if t.Type() == pcbnew.PCB_TRACE_T]
        removed = 0
        for x, y, layer, length in set(stubs):
            p = (float(x), float(y))
            for t in tracks:
                ends = [(t.GetStart().x / 1e6, t.GetStart().y / 1e6), (t.GetEnd().x / 1e6, t.GetEnd().y / 1e6)]
                if (t.GetLayerName() == layer and abs(t.GetLength() / 1e6 - float(length)) < 0.002 and
                        any(abs(e[0] - p[0]) < 0.002 and abs(e[1] - p[1]) < 0.002 for e in ends)):
                    tracks.remove(t); b.Remove(t); removed += 1; break
        for x, y in set(vias):
            for v in [t for t in b.GetTracks() if t.Type() == pcbnew.PCB_VIA_T]:
                if abs(v.GetX() / 1e6 - float(x)) < 0.002 and abs(v.GetY() / 1e6 - float(y)) < 0.002:
                    b.Remove(v); removed += 1; break
        pcbnew.ZONE_FILLER(b).Fill(b.Zones())
        b.Save(path)
        print('removed %d dangling stub(s)' % removed)
    txt = drc(path, rpt)
    print(''.join(l for l in txt.splitlines(True) if l.startswith('** Found')), end='')


if __name__ == '__main__':
    main(*sys.argv[1:])
