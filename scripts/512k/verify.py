#!/usr/bin/python3
"""Independent check of the finished PCB. Does NOT import design.py: pinouts and the
socket table are re-entered here from the datasheets / Anscomb's traced table."""
import re, subprocess, sys
import pcbnew
from shapely.geometry import Polygon

PCB, SCH = sys.argv[1], sys.argv[2]
b = pcbnew.LoadBoard(PCB)
net = {}
for fp in b.GetFootprints():
    for p in fp.Pads():
        n = p.GetNetname()
        net[(fp.GetReference(), int(p.GetNumber()))] = re.sub(r'~\{(.*)\}', r'~\1', n.lstrip('/')) if n else None
ok = True
def check(cond, msg):
    global ok
    print(('PASS ' if cond else 'FAIL ') + msg)
    ok &= bool(cond)

# 1. sockets (CN6 -> J1 1-12, CN5 -> J1 13-24, CN4 -> J2)
CN6 = ['GND', '+5V', 'D9', 'D8', 'D10', 'D11', 'D14', 'D15', 'D13', 'D12', '~WE1', 'GND']
CN5 = ['GND', 'D2', 'D3', 'D1', '~WE0', 'D0', '~CAS', 'D7', 'D5', 'D4', 'D6', 'GND']
CN4 = ['GND', '~RAS', 'Z0', 'Z1', 'Z2', 'Z3', 'Z6', 'Z5', 'Z4', 'Z7', 'Z8', 'GND']
check([net[('J1', i)] for i in range(1, 25)] == CN6 + CN5, 'J1 matches CN6/CN5 traced pinout')
check([net[('J2', i)] for i in range(1, 13)] == CN4, 'J2 matches CN4 traced pinout')

# 2. simulate the 74x86 (gates: 1,2->3  4,5->6  9,10->8  12,13->11)
GATES = [(1, 2, 3), (4, 5, 6), (9, 10, 8), (12, 13, 11)]
check(net[('U2', 14)] == '+5V' and net[('U2', 7)] == 'GND', 'U2 power pins')
def evaluate(inputs):
    v = {'+5V': 1, 'GND': 0, **inputs}
    for _ in range(4):
        for a, bb, y in GATES:
            na, nb = net[('U2', a)], net[('U2', bb)]
            if na in v and nb in v:
                v[net[('U2', y)]] = v[na] ^ v[nb]
    return v
SR = {'CE': 6, 'WE': 17, 'BLE': 39, 'BHE': 40, 'OE': 41}
for we0, we1, exp in [(1, 1, 'read'), (0, 1, 'write low'), (1, 0, 'write high'), (0, 0, 'invalid')]:
    v = evaluate({'~WE0': we0, '~WE1': we1, '~RAS': 0})
    got = (v.get(net[('U1', SR['WE'])]), v.get(net[('U1', SR['BLE'])]), v.get(net[('U1', SR['BHE'])]))
    want = {'read': (1, 0, 0), 'write low': (0, 0, 1), 'write high': (0, 1, 0), 'invalid': (1, 1, 1)}[exp]
    check(got == want, '~WE0=%d ~WE1=%d -> SRAM ~WE,~BLE,~BHE = %s (%s)' % (we0, we1, got, exp))
for ras in (0, 1):
    v = evaluate({'~WE0': 1, '~WE1': 1, '~RAS': ras})
    check(v.get(net[('U3', 11)]) == 1 - ras and net[('U3', 11)] == net[('U4', 11)],
          'U3/U4 CLK = NOT ~RAS (~RAS=%d)' % ras)

# 3. SRAM control/power (JEDEC 256Kx16 TSOP-II)
check(net[('U1', 6)] == '~CAS', 'SRAM ~CE driven by ~CAS')
check(net[('U1', 41)] == 'GND', 'SRAM ~OE tied low')
check(net[('U1', 11)] == net[('U1', 33)] == '+5V' and net[('U1', 12)] == net[('U1', 34)] == 'GND', 'SRAM power')
LO = [7, 8, 9, 10, 13, 14, 15, 16]; HI = [29, 30, 31, 32, 35, 36, 37, 38]
check(sorted(net[('U1', p)] for p in LO) == sorted('D%d' % i for i in range(8)), 'IO0-7 (~BLE lane) carry D0-D7 (bank 0, ~WE0)')
check(sorted(net[('U1', p)] for p in HI) == sorted('D%d' % i for i in range(8, 16)), 'IO8-15 (~BHE lane) carry D8-D15 (bank 1, ~WE1)')

# 4. address: 9 column bits direct, 9 row bits through U3 flip-flops
# two 74x574: 1 ~OE, 2-9 D1-D8, 10 GND, 11 CLK, 12-19 Q8-Q1, 20 VCC
FD, FQ = [2, 3, 4, 5, 6, 7, 8, 9], [19, 18, 17, 16, 15, 14, 13, 12]
q2d = {}
for u in ('U3', 'U4'):
    q2d.update({net[(u, q)]: net[(u, d)] for d, q in zip(FD, FQ) if net[(u, q)]})
A = [1, 2, 3, 4, 5, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 42, 43, 44]
col = [net[('U1', p)] for p in A if net[('U1', p)].startswith('Z')]
row = [q2d.get(net[('U1', p)]) for p in A if not net[('U1', p)].startswith('Z')]
Z = sorted('Z%d' % i for i in range(9))
check(sorted(col) == Z, 'column address: Z0-Z8 each on exactly one SRAM address pin')
check(sorted(r for r in row if r) == Z and len(row) == 9, 'row address: Z0-Z8 each latched once into a unique SRAM address pin')
for u in ('U3', 'U4'):
    check(net[(u, 11)] == net[('U2', 11)] and net[(u, 1)] == 'GND', '%s clocked by RAS (U2 pin 11), outputs always enabled' % u)
    check(net[(u, 20)] == '+5V' and net[(u, 10)] == 'GND', '%s power pins' % u)
    check(all(net[(u, d)] in Z + ['GND'] for d in FD), '%s unused inputs tied to GND' % u)
caps = [r for r in ('C1', 'C2', 'C3', 'C4', 'C5')]
check(all({net[(c, 1)], net[(c, 2)]} == {'+5V', 'GND'} for c in caps), '5 decoupling caps across +5V/GND')

# 5. schematic parity
out = subprocess.run(['kicad-cli', 'sch', 'export', 'netlist', '--format', 'kicadsexpr', '-o', '/tmp/v.net', SCH], capture_output=True)
t = open('/tmp/v.net').read()
sch = {}
for m in re.finditer(r'\(net \(code "?\d+"?\) \(name "([^"]*)"\)(.*?)(?=\(net \(code|\Z)', t, re.S):
    for ref, pin in re.findall(r'\(node \(ref "([^"]+)"\) \(pin "([^"]+)"\)', m.group(2)):
        if not ref.startswith('#'):
            sch[(ref, int(pin))] = None if m.group(1).startswith('unconnected') else re.sub(r'~\{(.*)\}', r'~\1', m.group(1).lstrip('/'))
mism = [k for k in net if net[k] != sch.get(k)]
check(not mism, 'schematic netlist matches PCB pad-for-pad (%d pads)' % len(net) + ('' if not mism else ' %s' % mism[:5]))

# 6. outline inside the proven cc3-512k envelope (Anscomb's vertices; chords sit inside his arcs)
env = Polygon([(97.028, 68.072), (105.383, 68.072), (106.730, 68.630), (122.632, 84.532), (123.19, 85.879),
               (123.19, 110.209), (123.748, 111.556), (134.316, 122.124), (135.663, 122.682), (166.878, 122.682),
               (168.783, 124.587), (168.783, 134.747), (168.776, 134.913), (168.754, 135.078), (168.718, 135.24), (168.668, 135.399), (168.605, 135.552), (168.528, 135.7), (168.438, 135.84), (168.337, 135.972), (168.225, 136.094), (168.103, 136.206), (167.971, 136.307), (167.83, 136.397), (167.683, 136.474), (167.53, 136.537), (167.371, 136.587), (167.209, 136.623), (167.044, 136.645), (166.878, 136.652), (101.881, 136.652), (100.534, 136.094),
               (95.681, 131.241), (95.123, 129.894), (95.123, 69.977)])
edges = [s for s in b.GetDrawings() if s.GetLayer() == pcbnew.Edge_Cuts]
segs = [((round(s.GetStart().x / 1e6, 3), round(s.GetStart().y / 1e6, 3)),
         (round(s.GetEnd().x / 1e6, 3), round(s.GetEnd().y / 1e6, 3))) for s in edges]
pts = [segs[0][0], segs[0][1]]; rest = segs[1:]
while rest:
    nxt = next(sg for sg in rest if pts[-1] in sg); rest.remove(nxt)
    pts.append(nxt[1] if nxt[0] == pts[-1] else nxt[0])
mine = Polygon(pts[:-1])
check(env.buffer(1e-3).contains(mine), 'outline inside original envelope: %.0f mm2 vs %.0f mm2 (%.0f%% smaller)'
      % (mine.area, env.area, 100 * (1 - mine.area / env.area)))
print('\nALL CHECKS PASSED' if ok else '\nSOME CHECKS FAILED')
