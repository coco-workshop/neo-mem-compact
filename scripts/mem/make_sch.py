#!/usr/bin/python3
"""Memory board schematic from design.py."""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, '..', 'common'))
import design as D
from schgen import Sheet, box

OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, '..', '..', 'boards', '2048k-mem', 'hardware')
NAME = 'neo-mem-2048k-mem'

names = {**{p: n for p, n in D.SRAM_ADDR.items()},
         **{p: 'IO%d' % i for i, p in enumerate(D.SRAM_LO_LANE)},
         **{p: 'IO%d' % (i + 8) for i, p in enumerate(D.SRAM_HI_LANE)}}
sram = box(22 * 2.54,
           [(next(p for p, n in D.SRAM_ADDR.items() if n == 'A%d' % i), 'A%d' % i, 'input') for i in range(20)],
           [(p, names[p], 'bidirectional') for p in D.SRAM_LO_LANE] + [(p, names[p], 'bidirectional') for p in D.SRAM_HI_LANE] +
           [None, (26, '~CE1', 'input'), (12, 'CE2', 'input'), (28, '~OE', 'input'), (11, '~WE', 'input'),
            (15, '~BLE', 'input'), (14, '~BHE', 'input'), (47, 'BYTE', 'input')],
           [(37, 'VCC', 'power_in')], [(27, 'VSS', 'power_in'), (46, 'VSS', 'power_in'),
                                       (10, 'NC', 'no_connect'), (13, 'NC', 'no_connect')])
xor = box(10 * 2.54,
          [(1, '1A', 'input'), (2, '1B', 'input'), None, (4, '2A', 'input'), (5, '2B', 'input'), None,
           (9, '3A', 'input'), (10, '3B', 'input'), None, (12, '4A', 'input'), (13, '4B', 'input')],
          [None, (3, '1Y', 'output'), None, None, (6, '2Y', 'output'), None, None, (8, '3Y', 'output'),
           None, None, (11, '4Y', 'output')], [(14, 'VCC', 'power_in')], [(7, 'GND', 'power_in')])
ff = box(10 * 2.54,
         [(p, 'D%d' % (i + 1), 'input') for i, p in enumerate(D.FF_D)] + [None, (11, 'CLK', 'input'), (1, '~OE', 'input')],
         [(p, 'Q%d' % (i + 1), 'tri_state') for i, p in enumerate(D.FF_Q)],
         [(20, 'VCC', 'power_in')], [(10, 'GND', 'power_in')])
conn = lambda n: box(4 * 2.54, [(i, str(i), 'passive') for i in range(1, n + 1)], [])

s = Sheet(NAME, 'neomem', 'neo-mem-2048k-compact: memory board')
s.add_box('SRAM_1Mx16', sram); s.add_box('74AHCT86', xor); s.add_box('74AHCT574', ff)
for n in (24, 12, 4):
    s.add_box('Conn_01x%02d' % n, conn(n))
s.add_two_pin('C', 'C'); s.add_two_pin('R', 'R')
P = D.PARTS
s.place('J1', 'Conn_01x24', 40.64, 96.52, P['J1']['value'], P['J1']['fp'], D.J1)
s.place('J2', 'Conn_01x12', 40.64, 162.56, P['J2']['value'], P['J2']['fp'], D.J2)
s.place('J3', 'Conn_01x04', 40.64, 220.98, P['J3']['value'], P['J3']['fp'], D.J3)
s.place('U2', '74AHCT86', 116.84, 71.12, P['U2']['value'], P['U2']['fp'], D.U2)
s.place('U3', '74AHCT574', 116.84, 147.32, P['U3']['value'], P['U3']['fp'], D.U3)
s.place('U4', '74AHCT574', 116.84, 190.5, P['U4']['value'], P['U4']['fp'], D.U4)
s.place('U1', 'SRAM_1Mx16', 241.3, 116.84, P['U1']['value'], P['U1']['fp'], D.U1)
for i, ref in enumerate(['R1', 'R2']):
    s.place(ref, 'R', 76.2 + i * 12.7, 220.98, '10k', P[ref]['fp'], P[ref]['pins'])
for i, c in enumerate(D.CAPS):
    s.place(c, 'C', 210.82 + i * 12.7, 200.66, '100n', P[c]['fp'], {1: '+5V', 2: 'GND'})
s.place('#FLG01', 'PWR_FLAG', 287.02, 193.04, 'PWR_FLAG', '', {1: '+5V'})
s.place('#FLG02', 'PWR_FLAG', 299.72, 193.04, 'PWR_FLAG', '', {1: 'GND'})
for x, y, t in [
        (25.4, 30.48, 'CoCo 3 2 MB SRAM expansion - memory board (plugs into CN4/CN5/CN6)'),
        (25.4, 35.56, 'Remove IC16-IC19 and cut C65, C66 first (as for any 512K upgrade).'),
        (25.4, 40.64, 'J3 (G G B0 B1) takes BANK0/BANK1 (physical A19/A20) from the DAT board. Unconnected: R1/R2 pull low = 512K mode.'),
        (160.02, 30.48, 'Write logic (active low): ~BHE = ~WE0 XOR 1   ~BLE = ~WE1 XOR 1   ~WE = ~WE1 XOR ~BHE'),
        (160.02, 35.56, 'RAS = ~RAS XOR 1 clocks U3/U4: row address (9 bits) and BANK1:0 latched on the falling edge of ~RAS.'),
        (160.02, 40.64, 'SRAM ~CE1 = ~CAS, CE2 = BYTE = 1 (x16), ~OE = 0. Address/data pin order is permuted for routing.'),
        (25.4, 256.54, 'Derived from cc3-512k by Ciaran Anscomb (CC BY-SA 4.0), logic per Jim Brain. This design is CC BY-SA 4.0.')]:
    s.note(x, y, t)
print('labels/no-connects', s.write(os.path.join(OUT, NAME + '.kicad_sch'), os.path.join(OUT, 'neomem.kicad_sym'),
                                   'Derived from gitlab.com/sixxie/cc3-512k (CC BY-SA 4.0)'))
open(os.path.join(OUT, 'sym-lib-table'), 'w').write(
    '(sym_lib_table\n  (lib (name "neomem")(type "KiCad")(uri "${KIPRJMOD}/neomem.kicad_sym")(options "")(descr "neo-mem symbols"))\n)\n')
