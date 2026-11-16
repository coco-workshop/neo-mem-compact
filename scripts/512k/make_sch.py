#!/usr/bin/python3
"""Generate neo-mem-512k-compact.kicad_sch (KiCad 7) from design.py.
Every pin gets a net label at its end, so connectivity is exactly design.py."""
import os, sys, uuid
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import design as D

OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, '..', '..', 'boards', '512k', 'hardware')
G = 2.54
U = lambda: str(uuid.uuid4())
ROOT = U()


def sch_net(n):
    """design.py net name -> KiCad label text (~X -> ~{X} overbar)."""
    return '~{%s}' % n[1:] if n.startswith('~') else n


def fmt_name(n):
    return '~{%s}' % n[1:] if n.startswith('~') else n


SRAM_NAMES = {1: 'A4', 2: 'A3', 3: 'A2', 4: 'A1', 5: 'A0', 6: '~CE', 11: 'VCC', 12: 'VSS', 17: '~WE',
              18: 'A17', 19: 'A16', 20: 'A15', 21: 'A14', 22: 'A13', 23: 'A12', 24: 'A11', 25: 'A10',
              26: 'A9', 27: 'A8', 28: 'NC', 33: 'VCC', 34: 'VSS', 39: '~BLE', 40: '~BHE', 41: '~OE',
              42: 'A7', 43: 'A6', 44: 'A5'}
for i, p in enumerate(D.SRAM_LO_LANE):
    SRAM_NAMES[p] = 'IO%d' % i
for i, p in enumerate(D.SRAM_HI_LANE):
    SRAM_NAMES[p] = 'IO%d' % (i + 8)

# symbol specs: name -> (width, left pins, right pins, top pins, bottom pins); pin = (num, name, type)
def sram_spec():
    left = [(next(k for k, v in SRAM_NAMES.items() if v == 'A%d' % i), 'A%d' % i, 'input') for i in range(18)]
    right = [(next(k for k, v in SRAM_NAMES.items() if v == 'IO%d' % i), 'IO%d' % i, 'bidirectional') for i in range(16)]
    right += [None, (6, '~CE', 'input'), (41, '~OE', 'input'), (17, '~WE', 'input'),
              (39, '~BLE', 'input'), (40, '~BHE', 'input')]
    return 20 * G, left, right, [(11, 'VCC', 'power_in'), (33, 'VCC', 'power_in')], \
        [(12, 'VSS', 'power_in'), (34, 'VSS', 'power_in'), (28, 'NC', 'no_connect')]

def xor_spec():
    left = [(1, '1A', 'input'), (2, '1B', 'input'), None, (4, '2A', 'input'), (5, '2B', 'input'), None,
            (9, '3A', 'input'), (10, '3B', 'input'), None, (12, '4A', 'input'), (13, '4B', 'input')]
    right = [None, (3, '1Y', 'output'), None, None, (6, '2Y', 'output'), None, None, (8, '3Y', 'output'),
             None, None, (11, '4Y', 'output')]
    return 10 * G, left, right, [(14, 'VCC', 'power_in')], [(7, 'GND', 'power_in')]

def ff_spec():
    left = [(p, 'D%d' % (i + 1), 'input') for i, p in enumerate(D.FF_D)] + [None, (11, 'CLK', 'input'), (1, '~OE', 'input')]
    right = [(p, 'Q%d' % (i + 1), 'tri_state') for i, p in enumerate(D.FF_Q)]
    return 10 * G, left, right, [(20, 'VCC', 'power_in')], [(10, 'GND', 'power_in')]

def conn_spec(n):
    return 4 * G, [(i, str(i), 'passive') for i in range(1, n + 1)], [], [], []

SYMS = {
    'SRAM_256Kx16': sram_spec(),
    '74AHCT86': xor_spec(),
    '74AHCT574': ff_spec(),
    'Conn_01x24': conn_spec(24),
    'Conn_01x12': conn_spec(12),
}


def pin_layout(spec):
    """Return list of (num, name, type, x, y, angle) in symbol coords (y up) and the body box."""
    w, left, right, top, bot = spec
    rows = max(len(left), len(right))
    h = (rows + 1) * G
    y0 = h / 2 - G
    pins = []
    for i, p in enumerate(left):
        if p: pins.append((*p, -w / 2 - G, round(y0 - i * G, 2), 0))
    for i, p in enumerate(right):
        if p: pins.append((*p, w / 2 + G, round(y0 - i * G, 2), 180))
    for i, p in enumerate(top):
        x = round((i - (len(top) - 1) / 2) * 2 * G, 2)
        pins.append((*p, x, h / 2 + G, 270))
    for i, p in enumerate(bot):
        x = round((i - (len(bot) - 1) / 2) * 2 * G, 2)
        pins.append((*p, x, -h / 2 - G, 90))
    return pins, (-w / 2, h / 2, w / 2, -h / 2)


def eff(size=1.27, hide=False, justify=None):
    j = ' (justify %s)' % justify if justify else ''
    return '(effects (font (size %s %s))%s%s)' % (size, size, j, ' hide' if hide else '')


def lib_symbol(name, spec):
    pins, (x0, y0, x1, y1) = pin_layout(spec)
    out = ['(symbol "cc3:%s" (in_bom yes) (on_board yes)' % name,
           '(property "Reference" "U" (at 0 %.2f 0) %s)' % (y0 + 1.5, eff()),
           '(property "Value" "%s" (at 0 %.2f 0) %s)' % (name, y1 - 1.5, eff()),
           '(property "Footprint" "" (at 0 0 0) %s)' % eff(hide=True),
           '(property "Datasheet" "" (at 0 0 0) %s)' % eff(hide=True),
           '(symbol "%s_0_1" (rectangle (start %.2f %.2f) (end %.2f %.2f) (stroke (width 0.254) (type default)) (fill (type background))))' % (name, x0, y0, x1, y1),
           '(symbol "%s_1_1"' % name]
    for num, pname, ptype, x, y, a in pins:
        hide = ' hide' if ptype == 'no_connect' else ''
        out.append('(pin %s line (at %.2f %.2f %d) (length 2.54)%s (name "%s" %s) (number "%s" %s))'
                   % (ptype, x, y, a, hide, fmt_name(pname), eff(), num, eff()))
    out.append('))')
    return '\n'.join(out), pins


CAP = '''(symbol "cc3:C" (pin_numbers hide) (pin_names (offset 0.254) hide) (in_bom yes) (on_board yes)
 (property "Reference" "C" (at 1.6 1 0) %s) (property "Value" "C" (at 1.6 -1.5 0) %s)
 (property "Footprint" "" (at 0 0 0) %s) (property "Datasheet" "" (at 0 0 0) %s)
 (symbol "C_0_1" (polyline (pts (xy -1.524 -0.508) (xy 1.524 -0.508)) (stroke (width 0.3) (type default)) (fill (type none)))
  (polyline (pts (xy -1.524 0.508) (xy 1.524 0.508)) (stroke (width 0.3) (type default)) (fill (type none))))
 (symbol "C_1_1" (pin passive line (at 0 3.81 270) (length 3.302) (name "~" %s) (number "1" %s))
  (pin passive line (at 0 -3.81 90) (length 3.302) (name "~" %s) (number "2" %s))))''' % (
    eff(justify='left'), eff(justify='left'), eff(hide=True), eff(hide=True), eff(), eff(), eff(), eff())
CAP_PINS = [(1, '~', 'passive', 0, 3.81, 270), (2, '~', 'passive', 0, -3.81, 90)]

FLAG = '''(symbol "cc3:PWR_FLAG" (power) (pin_numbers hide) (pin_names (offset 0) hide) (in_bom yes) (on_board yes)
 (property "Reference" "#FLG" (at 0 1.905 0) %s) (property "Value" "PWR_FLAG" (at 0 3.81 0) %s)
 (property "Footprint" "" (at 0 0 0) %s) (property "Datasheet" "" (at 0 0 0) %s)
 (symbol "PWR_FLAG_0_0" (pin power_out line (at 0 0 90) (length 0) (name "pwr" %s) (number "1" %s)))
 (symbol "PWR_FLAG_0_1" (polyline (pts (xy 0 0) (xy 0 1.27) (xy -1.016 1.905) (xy 0 2.54) (xy 1.016 1.905) (xy 0 1.27))
  (stroke (width 0) (type default)) (fill (type none)))))''' % (eff(hide=True), eff(), eff(hide=True), eff(hide=True), eff(), eff())


def main():
    lib, pins_of = [], {}
    for name, spec in SYMS.items():
        s, pins = lib_symbol(name, spec)
        lib.append(s); pins_of[name] = pins
    lib += [CAP, FLAG]
    pins_of['C'] = CAP_PINS
    pins_of['PWR_FLAG'] = [(1, 'pwr', 'power_out', 0, 0, 90)]

    body, labels, ncs = [], [], []

    def inst(ref, sym, x, y, value, fp, netmap, extra=''):
        pins = pins_of[sym]
        if sym in ('C', 'PWR_FLAG'):
            rp, vp = (x, y - 1, 'left'), (x + 2, y + 1.5, 'left')
        else:
            bx = max(abs(p[3]) for p in pins) - 2.54          # body half-width
            by = max(p[4] for p in pins if p[5] in (0, 180)) + 2.54   # body top
            rp = (x + bx, y - by - 6.5, 'right'); vp = (x + bx, y - by - 4.2, 'right')
        props = ['(property "Reference" "%s" (at %.2f %.2f 0) %s)' % (ref, rp[0], rp[1], eff(justify=rp[2])),
                 '(property "Value" "%s" (at %.2f %.2f 0) %s)' % (value, vp[0], vp[1], eff(justify=vp[2])),
                 '(property "Footprint" "%s" (at %.2f %.2f 0) %s)' % (fp, x, y, eff(hide=True)),
                 '(property "Datasheet" "" (at %.2f %.2f 0) %s)' % (x, y, eff(hide=True))] + ([extra] if extra else [])
        body.append('(symbol (lib_id "cc3:%s") (at %.2f %.2f 0) (unit 1) (in_bom %s) (on_board %s) (dnp no) (uuid %s)\n %s\n %s\n (instances (project "neo-mem-512k-compact" (path "/%s" (reference "%s") (unit 1)))))'
                    % (sym, x, y, 'no' if sym == 'PWR_FLAG' else 'yes', 'no' if sym == 'PWR_FLAG' else 'yes', U(), '\n '.join(props),
                       ' '.join('(pin "%s" (uuid %s))' % (p[0], U()) for p in pins), ROOT, ref))
        for num, pname, ptype, px, py, a in pins:
            ax, ay = round(x + px, 2), round(y - py, 2)
            net = netmap.get(num)
            if net is None:
                ncs.append('(no_connect (at %.2f %.2f) (uuid %s))' % (ax, ay, U()))
                continue
            # label points away from the body
            ang, just = {0: (180, 'right'), 180: (0, 'left'), 270: (90, 'left'), 90: (270, 'right')}[a]
            labels.append('(label "%s" (at %.2f %.2f %d) (fields_autoplaced) %s (uuid %s))'
                          % (sch_net(net), ax, ay, ang, eff(justify=just + ' bottom' if ang in (0, 180) else just), U()))

    P = D.PARTS
    inst('J1', 'Conn_01x24', 40.64, 88.9, P['J1']['value'], P['J1']['fp'], D.J1)
    inst('J2', 'Conn_01x12', 40.64, 152.4, P['J2']['value'], P['J2']['fp'], D.J2)
    inst('U2', '74AHCT86', 106.68, 63.5, P['U2']['value'], P['U2']['fp'], D.U2)
    inst('U3', '74AHCT574', 106.68, 132.08, P['U3']['value'], P['U3']['fp'], D.U3)
    inst('U4', '74AHCT574', 106.68, 172.72, P['U4']['value'], P['U4']['fp'], D.U4)
    inst('U1', 'SRAM_256Kx16', 205.74, 101.6, P['U1']['value'], P['U1']['fp'], D.U1)
    for i, c in enumerate(D.CAPS):
        inst(c, 'C', 172.72 + i * 12.7, 165.1, '100n', P[c]['fp'], {1: '+5V', 2: 'GND'})
    inst('#FLG01', 'PWR_FLAG', 241.3, 157.48, 'PWR_FLAG', '', {1: '+5V'})
    inst('#FLG02', 'PWR_FLAG', 254.0, 157.48, 'PWR_FLAG', '', {1: 'GND'})

    notes = [
        (25.4, 30.48, 'neo-mem-compact: 512K memory board v2 (CoCo 3 512K SRAM)'),
        (25.4, 35.56, 'Fits CN4/CN5/CN6. Remove IC16-IC19 and cut C65, C66 first (as for any 512K upgrade).'),
        (139.7, 30.48, 'Write logic (all active low):  ~BHE = ~WE0 XOR 1   ~BLE = ~WE1 XOR 1   ~WE = ~WE1 XOR ~BHE'),
        (139.7, 35.56, 'Invalid ~WE0=~WE1=0 gives ~WE=1 (no write). RAS = ~RAS XOR 1 clocks the row register on ~RAS fall.'),
        (139.7, 40.64, 'SRAM ~CE = ~CAS (column address valid only while ~CAS low); ~OE tied low.'),
        (139.7, 45.72, 'Address/data pin order on U1 is permuted for routing; any consistent, unique mapping works.'),
        (25.4, 187.96, 'Based on the cc3-512k design by Ciaran Anscomb (CC BY-SA 4.0) - logic per Jim Brain. This derivative is also CC BY-SA 4.0.'),
    ]
    texts = ['(text "%s" (at %.2f %.2f 0) %s (uuid %s))' % (t, x, y, eff(justify='left bottom'), U()) for x, y, t in notes]

    sch = '''(kicad_sch (version 20230121) (generator eeschema)
(uuid %s)
(paper "A3")
(title_block (title "neo-mem-compact: 512K memory board v2") (rev "2") (comment 1 "Derived from gitlab.com/sixxie/cc3-512k (CC BY-SA 4.0)"))
(lib_symbols
%s
)
%s
%s
%s
%s
(sheet_instances (path "/" (page "1")))
)
''' % (ROOT, '\n'.join(lib), '\n'.join(texts), '\n'.join(ncs), '\n'.join(labels), '\n'.join(body))
    path = os.path.join(OUT, 'neo-mem-512k-compact.kicad_sch')
    open(path, 'w').write(sch)
    # project-local symbol library for editing
    open(os.path.join(OUT, 'cc3.kicad_sym'), 'w').write(
        '(kicad_symbol_lib (version 20220914) (generator cc3gen)\n%s\n)\n' % '\n'.join(lib).replace('"cc3:', '"'))
    open(os.path.join(OUT, 'sym-lib-table'), 'w').write(
        '(sym_lib_table\n  (lib (name "cc3")(type "KiCad")(uri "${KIPRJMOD}/cc3.kicad_sym")(options "")(descr "CoCo 3 512K symbols"))\n)\n')
    print('wrote', path, len(labels), 'labels', len(ncs), 'no-connects')


if __name__ == '__main__':
    main()
