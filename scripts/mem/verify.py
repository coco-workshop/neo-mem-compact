#!/usr/bin/python3
"""Independent check of the finished memory board. Does NOT import design.py: pinouts are
re-entered from the datasheets (CY62167E 001-15607, 74x86, 74x574) and Anscomb's table."""
import math, re, subprocess, sys
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
    print(('PASS ' if cond else 'FAIL ') + msg); ok &= bool(cond)

CN6 = ['GND', '+5V', 'D9', 'D8', 'D10', 'D11', 'D14', 'D15', 'D13', 'D12', '~WE1', 'GND']
CN5 = ['GND', 'D2', 'D3', 'D1', '~WE0', 'D0', '~CAS', 'D7', 'D5', 'D4', 'D6', 'GND']
CN4 = ['GND', '~RAS', 'Z0', 'Z1', 'Z2', 'Z3', 'Z6', 'Z5', 'Z4', 'Z7', 'Z8', 'GND']
check([net[('J1', i)] for i in range(1, 25)] == CN6 + CN5, 'J1 matches CN6/CN5 traced pinout')
check([net[('J2', i)] for i in range(1, 13)] == CN4, 'J2 matches CN4 traced pinout')
check([net[('J3', i)] for i in (2, 4)] == ['GND', 'GND'] and {net[('J3', 1)], net[('J3', 3)]} == {'BANK0', 'BANK1'}, 'J3 2x2: bank lines on pins 1/3, ground on 2/4 (same as DAT J2; bank order is free)')
_j3 = {int(p.GetNumber()): p.GetPosition() for p in b.FindFootprintByReference('J3').Pads()}
check(_j3[1].y == _j3[3].y and _j3[2].y == _j3[4].y and _j3[1].y != _j3[2].y, 'J3 bank pins form one row, ground pins the other')
check({net[('R1', 1)], net[('R1', 2)]} == {'BANK0', 'GND'} and {net[('R2', 1)], net[('R2', 2)]} == {'BANK1', 'GND'},
      'R1/R2 pull BANK0/BANK1 low (no DAT board = bank 0 = 512K)')

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
# CY62167E TSOP-I: 11 ~WE, 15 ~BLE, 14 ~BHE, 26 ~CE1, 12 CE2, 28 ~OE, 47 BYTE, 37 VCC, 27/46 VSS
for we0, we1, exp in [(1, 1, 'read'), (0, 1, 'write low'), (1, 0, 'write high'), (0, 0, 'invalid')]:
    v = evaluate({'~WE0': we0, '~WE1': we1, '~RAS': 0})
    got = (v.get(net[('U1', 11)]), v.get(net[('U1', 15)]), v.get(net[('U1', 14)]))
    want = {'read': (1, 0, 0), 'write low': (0, 0, 1), 'write high': (0, 1, 0), 'invalid': (1, 1, 1)}[exp]
    check(got == want, '~WE0=%d ~WE1=%d -> SRAM ~WE,~BLE,~BHE = %s (%s)' % (we0, we1, got, exp))
for ras in (0, 1):
    v = evaluate({'~WE0': 1, '~WE1': 1, '~RAS': ras})
    check(v.get(net[('U3', 11)]) == 1 - ras and net[('U3', 11)] == net[('U4', 11)], 'U3/U4 CLK = NOT ~RAS (~RAS=%d)' % ras)

check(net[('U1', 26)] == '~CAS', 'SRAM ~CE1 driven by ~CAS')
check(net[('U1', 12)] == '+5V' and net[('U1', 47)] == '+5V', 'SRAM CE2 high, BYTE high (x16 mode)')
check(net[('U1', 28)] == 'GND', 'SRAM ~OE tied low')
check(net[('U1', 37)] == '+5V' and net[('U1', 27)] == net[('U1', 46)] == 'GND', 'SRAM power')
check(net[('U1', 10)] is None and net[('U1', 13)] is None, 'SRAM NC pins 10, 13 unconnected')
LO = [29, 31, 33, 35, 38, 40, 42, 44]; HI = [30, 32, 34, 36, 39, 41, 43, 45]
check(sorted(net[('U1', p)] for p in LO) == sorted('D%d' % i for i in range(8)), 'IO0-7 (~BLE lane) carry D0-D7 (bank 0, ~WE0)')
check(sorted(net[('U1', p)] for p in HI) == sorted('D%d' % i for i in range(8, 16)), 'IO8-15 (~BHE lane) carry D8-D15 (bank 1, ~WE1)')

# two 74x574: 1 ~OE, 2-9 D1-D8, 10 GND, 11 CLK, 12-19 Q8-Q1, 20 VCC
FD, FQ = [2, 3, 4, 5, 6, 7, 8, 9], [19, 18, 17, 16, 15, 14, 13, 12]
q2d = {}
for u in ('U3', 'U4'):
    q2d.update({net[(u, q)]: net[(u, d)] for d, q in zip(FD, FQ) if net[(u, q)]})
A = [25, 24, 23, 22, 21, 20, 19, 18, 8, 7, 6, 5, 4, 3, 2, 1, 48, 17, 16, 9]   # A0..A19
an = [net[('U1', p)] for p in A]
check(len(set(an)) == 20 and None not in an, 'all 20 SRAM address pins used, each a different net')
direct = sorted(n for n in an if n.startswith('Z'))
latched = sorted(q2d.get(n) for n in an if not n.startswith('Z'))
Z = sorted('Z%d' % i for i in range(9))
check(direct == Z, 'column address: Z0-Z8 each wired directly to exactly one SRAM address pin')
check(latched == sorted(Z + ['BANK0', 'BANK1']), 'row address Z0-Z8 and BANK0/BANK1 each latched once into a unique SRAM address pin')
for u in ('U3', 'U4'):
    check(net[(u, 11)] == net[('U2', 11)] and net[(u, 1)] == 'GND', '%s clocked by RAS (U2 pin 11), outputs always enabled' % u)
    check(net[(u, 20)] == '+5V' and net[(u, 10)] == 'GND', '%s power pins' % u)
    check(all(net[(u, d)] in Z + ['BANK0', 'BANK1', 'GND'] for d in FD), '%s unused inputs tied to GND' % u)
caps = [f.GetReference() for f in b.GetFootprints() if f.GetReference().startswith('C')]
check(len(caps) == 4 and all({net[(c, 1)], net[(c, 2)]} == {'+5V', 'GND'} for c in caps), '4 decoupling caps across +5V/GND')

subprocess.run(['kicad-cli', 'sch', 'export', 'netlist', '--format', 'kicadsexpr', '-o', '/tmp/vm.net', SCH], capture_output=True)
t = open('/tmp/vm.net').read(); sch = {}
for m in re.finditer(r'\(net \(code "?\d+"?\) \(name "([^"]*)"\)(.*?)(?=\(net \(code|\Z)', t, re.S):
    for ref, pin in re.findall(r'\(node \(ref "([^"]+)"\) \(pin "([^"]+)"\)', m.group(2)):
        if not ref.startswith('#'):
            sch[(ref, int(pin))] = None if m.group(1).startswith('unconnected') else re.sub(r'~\{(.*)\}', r'~\1', m.group(1).lstrip('/'))
mism = [k for k in net if net[k] != sch.get(k)]
check(not mism, 'schematic netlist matches PCB pad-for-pad (%d pads)%s' % (len(net), '' if not mism else ' %s' % mism[:5]))

env = Polygon([(97.028, 68.072), (105.383, 68.072), (106.730, 68.630), (122.632, 84.532), (123.19, 85.879),
               (123.19, 110.209), (123.748, 111.556), (134.316, 122.124), (135.663, 122.682), (166.878, 122.682),
               (168.783, 124.587)] + [(166.878 + 1.905 * math.cos(math.radians(d)), 134.747 + 1.905 * math.sin(math.radians(d)))
                                      for d in range(0, 91)] +
              [(101.881, 136.652), (100.534, 136.094), (95.681, 131.241), (95.123, 129.894), (95.123, 69.977)])
segs = [((round(s.GetStart().x / 1e6, 3), round(s.GetStart().y / 1e6, 3)), (round(s.GetEnd().x / 1e6, 3), round(s.GetEnd().y / 1e6, 3)))
        for s in b.GetDrawings() if s.GetLayer() == pcbnew.Edge_Cuts]
pts = [segs[0][0], segs[0][1]]; rest = segs[1:]
while rest:
    nxt = next(sg for sg in rest if pts[-1] in sg); rest.remove(nxt); pts.append(nxt[1] if nxt[0] == pts[-1] else nxt[0])
mine = Polygon(pts[:-1])
check(env.buffer(0.01).contains(mine), 'outline inside the proven cc3-512k envelope (%.0f mm2)' % mine.area)
print('\nALL CHECKS PASSED' if ok else '\nSOME CHECKS FAILED')
