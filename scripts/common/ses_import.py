#!/usr/bin/python3
"""Import a Freerouting .ses into a .kicad_pcb (KiCad 7's ImportSpecctraSES needs the GUI).
usage: ses_import.py board.kicad_pcb routes.ses out.kicad_pcb"""
import re, sys
import pcbnew


def parse(text):
    toks = re.findall(r'\(|\)|"[^"]*"|[^\s()]+', text)
    stack, cur = [], []
    for t in toks:
        if t == '(':
            stack.append(cur); cur = []
        elif t == ')':
            done = cur; cur = stack.pop(); cur.append(done)
        else:
            cur.append(t.strip('"'))
    return cur[0]


def find(node, key):
    for c in node:
        if isinstance(c, list) and c and c[0] == key:
            yield c


def main(pcb, ses, out):
    tree = parse(open(ses).read())
    routes = next(find(tree, 'routes'))
    res = next(find(routes, 'resolution'))
    scale = {'um': 1e3, 'mil': 25400.0, 'mm': 1e6}[res[1]] / float(res[2])   # -> nm
    b = pcbnew.LoadBoard(pcb)
    for t in list(b.GetTracks()):
        b.Remove(t)
    layers = {'F.Cu': pcbnew.F_Cu, 'B.Cu': pcbnew.B_Cu}
    pt = lambda x, y: pcbnew.VECTOR2I(int(float(x) * scale), int(-float(y) * scale))
    nw, nv = 0, 0
    for netnode in find(next(find(routes, 'network_out')), 'net'):
        net = b.FindNet(netnode[1])
        for w in find(netnode, 'wire'):
            p = next(find(w, 'path'))
            layer, width, coords = p[1], float(p[2]) * scale, p[3:]
            xy = [pt(coords[i], coords[i + 1]) for i in range(0, len(coords), 2)]
            for a, c in zip(xy, xy[1:]):
                t = pcbnew.PCB_TRACK(b)
                t.SetStart(a); t.SetEnd(c); t.SetWidth(int(width))
                t.SetLayer(layers[layer]); t.SetNet(net)
                b.Add(t); nw += 1
        for v in find(netnode, 'via'):
            m = re.search(r'(\d+):(\d+)_um', v[1])
            dia, drill = (int(m.group(1)) * 1000, int(m.group(2)) * 1000) if m else (600000, 300000)
            via = pcbnew.PCB_VIA(b)
            via.SetPosition(pt(v[2], v[3]))
            via.SetWidth(dia); via.SetDrill(drill)
            via.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
            via.SetNet(net)
            b.Add(via); nv += 1
    b.Save(out)
    print('segments', nw, 'vias', nv)


if __name__ == '__main__':
    main(*sys.argv[1:4])
