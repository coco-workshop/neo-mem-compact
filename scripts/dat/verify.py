#!/usr/bin/python3
"""Independent check of the finished DAT board. Does NOT import design.py: the 6809E and
ATF1504AS-TQFP44 pinouts are re-entered here, and the CPLD pin constraints are read back
from cpld/dat2m_top.v and compared with what the copper actually connects."""
import re, subprocess, sys
import pcbnew

PCB, SCH, TOP = sys.argv[1], sys.argv[2], sys.argv[3]
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

# MC6809E / HD63C09E pinout
cpu = {1: 'GND', 7: '+5V', 24: 'D7', 25: 'D6', 26: None, 27: None, 28: 'D3', 29: None, 30: 'D1', 31: 'D0',
       32: 'RW', 34: 'E', 35: 'Q', 37: '~RESET'}
cpu.update({8 + i: 'A%d' % i for i in range(16)})
check(all(net[('J1', p)] == n for p, n in cpu.items()), 'J1 taps the right 6809E pins (A0-A15, D0/D1/D3/D6/D7, R/W, E, Q, /RESET, power)')
check(all(net[('J1', p)] is None for p in (2, 3, 4, 5, 6, 26, 27, 29, 33, 36, 38, 39, 40)),
      'unused CPU pins (interrupts, BA/BS, D2/D4/D5, BUSY, AVMA, LIC, TSC, HALT) untouched')

# ATF1504AS TQFP-44
check(all(net[('U1', p)] == '+5V' for p in (9, 17, 29, 41)) and all(net[('U1', p)] == 'GND' for p in (4, 16, 24, 36)), 'CPLD power pins')
check(net[('U1', 37)] == 'E', 'E on GCLK1 (pin 37), the global clock')
check(net[('U1', 39)] == '~RESET', '/RESET on GCLR (pin 39), the global clear')
jt = {1: 'TDI', 7: 'TMS', 26: 'TCK', 32: 'TDO'}
check(all(net[('U1', p)] == n for p, n in jt.items()), 'JTAG pins 1/7/26/32 = TDI/TMS/TCK/TDO')
hdr = {1: 'TCK', 2: 'GND', 3: 'TDO', 4: '+5V', 5: 'TMS', 9: 'TDI', 10: 'GND'}
check(all(net[('J3', p)] == n for p, n in hdr.items()) and all(net[('J3', p)] is None for p in (6, 7, 8)),
      'J3 follows the 10-pin Atmel ATDH1150USB / USB-Blaster layout')
check([net[('J2', i)] for i in (1, 2, 3, 4)] == ['GND', 'GND', 'B0', 'B1'], 'J2 = G, G, B, B (matches memory board J3)')
check({net[('R1', 1)], net[('R1', 2)]} == {'BANK0', 'B0'} and {net[('R2', 1)], net[('R2', 2)]} == {'BANK1', 'B1'},
      'BANK0/BANK1 reach J2 only through series resistors R1/R2')
check([net[('J4', 1)], net[('J4', 2)]] == ['+5V', 'LED_K'] and {net[('R3', 1)], net[('R3', 2)]} == {'LED_K', 'LED_FASTn'},
      'turbo LED header J4: +5V, cathode through R3 to the CPLD')
check([net[('JP1', i)] for i in (1, 2, 3)] == ['+5V', 'EN2M', 'GND'],
      'JP1: EN2M on the common pad, +5V (2MB, bridged as made) and GND (512K) either side')
jp = b.FindFootprintByReference('JP1')
check(jp.GetLayer() == pcbnew.B_Cu and 'Bridged12' in jp.GetFPIDAsString(), 'JP1 is the pre-bridged 1-2 type, on the back (no assembly)')

# Verilog pin constraints vs copper
v = open(TOP).read()
dirs = dict((n, d) for d, n in re.findall(r'^\s+(input|output)\s+wire\s+(\w+)', v, re.M))
locs = [(p, dirs.get(s), s) for s, p in re.findall(r'^//PIN:\s+(\w+)\s*:\s*(\d+)', v, re.M)]
alias = {'RW': 'RW', 'RESETn': '~RESET', 'ECLK': 'E', 'QCLK': 'Q'}
bad = [(p, s, net[('U1', int(p))]) for p, d, s in locs if net[('U1', int(p))] != alias.get(s, s)]
check(len(locs) == 29 and not bad, 'all 29 CPLD pin constraints in dat2m_top.v match the PCB%s' % ('' if not bad else ' %s' % bad))
outs = [s for p, d, s in locs if d == 'output']
check(sorted(outs) == ['BANK0', 'BANK1', 'LED_FASTn'], 'CPLD drives only BANK0/BANK1 and the LED - never the CPU bus')
used = {int(p) for p, d, s in locs}
check(not (used & set(jt)), 'no logic signal on a JTAG pin')
caps = [f.GetReference() for f in b.GetFootprints() if f.GetReference().startswith('C')]
check(len(caps) == 4 and all({net[(c, 1)], net[(c, 2)]} == {'+5V', 'GND'} for c in caps), 'one 100 nF cap per CPLD VCC pin')

subprocess.run(['kicad-cli', 'sch', 'export', 'netlist', '--format', 'kicadsexpr', '-o', '/tmp/vd.net', SCH], capture_output=True)
t = open('/tmp/vd.net').read(); sch = {}
for m in re.finditer(r'\(net \(code "?\d+"?\) \(name "([^"]*)"\)(.*?)(?=\(net \(code|\Z)', t, re.S):
    for ref, pin in re.findall(r'\(node \(ref "([^"]+)"\) \(pin "([^"]+)"\)', m.group(2)):
        if not ref.startswith('#'):
            sch[(ref, int(pin))] = None if m.group(1).startswith('unconnected') else re.sub(r'~\{(.*)\}', r'~\1', m.group(1).lstrip('/'))
mism = [k for k in net if net[k] != sch.get(k)]
check(not mism, 'schematic netlist matches PCB pad-for-pad (%d pads)%s' % (len(net), '' if not mism else ' %s' % mism[:5]))
bb = b.GetBoardEdgesBoundingBox()
print('     board %.1f x %.1f mm' % (bb.GetWidth() / 1e6, bb.GetHeight() / 1e6))
print('\nALL CHECKS PASSED' if ok else '\nSOME CHECKS FAILED')
