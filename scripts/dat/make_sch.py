#!/usr/bin/python3
"""DAT board schematic from design.py."""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, '..', 'common'))
import design as D
from schgen import Sheet, box

OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, '..', '..', 'boards', 'dat', 'hardware')
NAME = 'neo-mem-2048k-dat'

CPU_NAMES = {1: 'VSS', 2: '~NMI', 3: '~IRQ', 4: '~FIRQ', 5: 'BS', 6: 'BA', 7: 'VCC',
             **{8 + i: 'A%d' % i for i in range(16)},
             24: 'D7', 25: 'D6', 26: 'D5', 27: 'D4', 28: 'D3', 29: 'D2', 30: 'D1', 31: 'D0',
             32: 'R/~W', 33: 'BUSY', 34: 'E', 35: 'Q', 36: 'AVMA', 37: '~RESET', 38: 'LIC', 39: 'TSC', 40: '~HALT'}
cpu = box(14 * 2.54, [(p, CPU_NAMES[p], 'passive') for p in range(1, 21)],
          [(p, CPU_NAMES[p], 'passive') for p in range(40, 20, -1)])
io = sorted(D.CPLD_IO)
cpld = box(16 * 2.54,
           [(p, 'IO%d' % p, 'bidirectional') for p in io[:14]] + [None] +
           [(37, 'GCLK1', 'input'), (38, 'OE1', 'input'), (39, 'GCLR', 'input'), (40, 'OE2/GCLK2', 'input')],
           [(p, 'IO%d' % p, 'bidirectional') for p in io[14:]] + [None] +
           [(1, 'TDI', 'input'), (7, 'TMS', 'input'), (26, 'TCK', 'input'), (32, 'TDO', 'output')],
           [(p, 'VCC', 'power_in') for p in D.CPLD_VCC], [(p, 'GND', 'power_in') for p in D.CPLD_GND])
jtag = box(6 * 2.54, [(p, str(p), 'passive') for p in (1, 3, 5, 7, 9)], [(p, str(p), 'passive') for p in (2, 4, 6, 8, 10)])
conn3 = box(4 * 2.54, [(i, str(i), 'passive') for i in (1, 2, 3)], [])

s = Sheet(NAME, 'neomem', 'neo-mem-2048k-compact: DAT board')
s.add_box('CPU_interposer_40', cpu); s.add_box('ATF1504AS_TQFP44', cpld)
s.add_box('JTAG_2x05', jtag); s.add_box('Conn_01x03', conn3)
s.add_two_pin('C', 'C')
s.add_box('SolderJumper_3_Bridged12', box(6 * 2.54, [(1, '1 (+5V)', 'passive'), (2, '2 (common)', 'passive'), (3, '3 (GND)', 'passive')], []))
P = D.PARTS
s.place('J1', 'CPU_interposer_40', 76.2, 127.0, P['J1']['value'], P['J1']['fp'], D.CPU)
s.place('U1', 'ATF1504AS_TQFP44', 205.74, 116.84, P['U1']['value'], P['U1']['fp'], D.U1)
s.place('J3', 'JTAG_2x05', 309.88, 101.6, 'JTAG (ATDH1150USB / USB-Blaster)', P['J3']['fp'], D.JTAG)
s.place('J2', 'Conn_01x03', 309.88, 152.4, P['J2']['value'], P['J2']['fp'], D.J2)
s.place('JP1', 'SolderJumper_3_Bridged12', 309.88, 190.5, '1-2 = 2MB (as made), 2-3 = 512K', P['JP1']['fp'], P['JP1']['pins'])
for i, c in enumerate(D.CAPS):
    s.place(c, 'C', 172.72 + i * 12.7, 200.66, '100n', P[c]['fp'], {1: '+5V', 2: 'GND'})
s.place('#FLG01', 'PWR_FLAG', 241.3, 193.04, 'PWR_FLAG', '', {1: '+5V'})
s.place('#FLG02', 'PWR_FLAG', 254.0, 193.04, 'PWR_FLAG', '', {1: 'GND'})
for x, y, t in [
        (25.4, 30.48, 'DAT board: sits in the 6809/6309 socket; the CPU plugs into J1 on top. All CPU pins pass straight through.'),
        (25.4, 35.56, 'U1 shadows writes to $FFA0-$FFAF (D7:D6), $FF90 (MMU enable, MC3), $FF91 (task), $FF9B (video bank), $FFD8/9 (speed)'),
        (25.4, 40.64, 'and drives BANK1:0 = physical A20:A19 for each GIME slot. Logic: cpld/dat2m.v, pins: cpld/dat2m_top.v.'),
        (25.4, 45.72, 'CPLD IO pin numbers above carry the signals named on their labels (assignment chosen for routing).'),
        (25.4, 256.54, 'neo-mem-2048k-compact - CC BY-SA 4.0.')]:
    s.note(x, y, t)
print('labels/no-connects', s.write(os.path.join(OUT, NAME + '.kicad_sch'), os.path.join(OUT, 'neomem.kicad_sym')))
open(os.path.join(OUT, 'sym-lib-table'), 'w').write(
    '(sym_lib_table\n  (lib (name "neomem")(type "KiCad")(uri "${KIPRJMOD}/neomem.kicad_sym")(options "")(descr "neo-mem symbols"))\n)\n')
