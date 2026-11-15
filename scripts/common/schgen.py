"""Tiny KiCad 7 schematic writer: box symbols + a net label on every pin end.
Connectivity is exactly the netmaps passed in, so the schematic can't drift from the PCB."""
import uuid

G = 2.54
U = lambda: str(uuid.uuid4())


def ovl(n):
    """design net / pin name -> KiCad text with overbar (~X -> ~{X})."""
    return '~{%s}' % n[1:] if n.startswith('~') else n


def eff(size=1.27, hide=False, justify=None):
    j = ' (justify %s)' % justify if justify else ''
    return '(effects (font (size %s %s))%s%s)' % (size, size, j, ' hide' if hide else '')


def box(width, left, right, top=(), bottom=()):
    """Symbol spec. Pins are (number, name, type); None leaves a gap row."""
    return (width, list(left), list(right), list(top), list(bottom))


def pin_layout(spec):
    w, left, right, top, bot = spec
    rows = max(len(left), len(right), 1)
    h = (rows + 1) * G
    y0 = h / 2 - G
    pins = []
    for i, p in enumerate(left):
        if p: pins.append((*p, -w / 2 - G, round(y0 - i * G, 2), 0))
    for i, p in enumerate(right):
        if p: pins.append((*p, w / 2 + G, round(y0 - i * G, 2), 180))
    for i, p in enumerate(top):
        pins.append((*p, round((i - (len(top) - 1) / 2) * 2 * G, 2), h / 2 + G, 270))
    for i, p in enumerate(bot):
        pins.append((*p, round((i - (len(bot) - 1) / 2) * 2 * G, 2), -h / 2 - G, 90))
    return pins, (-w / 2, h / 2, w / 2, -h / 2)


def lib_symbol(lib, name, spec):
    pins, (x0, y0, x1, y1) = pin_layout(spec)
    out = ['(symbol "%s:%s" (in_bom yes) (on_board yes)' % (lib, name),
           '(property "Reference" "U" (at 0 %.2f 0) %s)' % (y0 + 1.5, eff()),
           '(property "Value" "%s" (at 0 %.2f 0) %s)' % (name, y1 - 1.5, eff()),
           '(property "Footprint" "" (at 0 0 0) %s)' % eff(hide=True),
           '(property "Datasheet" "" (at 0 0 0) %s)' % eff(hide=True),
           '(symbol "%s_0_1" (rectangle (start %.2f %.2f) (end %.2f %.2f) (stroke (width 0.254) (type default)) (fill (type background))))' % (name, x0, y0, x1, y1),
           '(symbol "%s_1_1"' % name]
    for num, pname, ptype, x, y, a in pins:
        hide = ' hide' if ptype == 'no_connect' else ''
        out.append('(pin %s line (at %.2f %.2f %d) (length 2.54)%s (name "%s" %s) (number "%s" %s))'
                   % (ptype, x, y, a, hide, ovl(pname), eff(), num, eff()))
    out.append('))')
    return '\n'.join(out), pins


def two_pin(lib, name, prefix):
    s = '''(symbol "%s:%s" (pin_numbers hide) (pin_names (offset 0.254) hide) (in_bom yes) (on_board yes)
 (property "Reference" "%s" (at 1.6 1 0) %s) (property "Value" "%s" (at 1.6 -1.5 0) %s)
 (property "Footprint" "" (at 0 0 0) %s) (property "Datasheet" "" (at 0 0 0) %s)
 (symbol "%s_0_1" (rectangle (start -0.9 1.6) (end 0.9 -1.6) (stroke (width 0.25) (type default)) (fill (type none))))
 (symbol "%s_1_1" (pin passive line (at 0 3.81 270) (length 2.21) (name "~" %s) (number "1" %s))
  (pin passive line (at 0 -3.81 90) (length 2.21) (name "~" %s) (number "2" %s))))''' % (
        lib, name, prefix, eff(justify='left'), name, eff(justify='left'), eff(hide=True), eff(hide=True),
        name, name, eff(), eff(), eff(), eff())
    return s, [(1, '~', 'passive', 0, 3.81, 270), (2, '~', 'passive', 0, -3.81, 90)]


def pwr_flag(lib):
    s = '''(symbol "%s:PWR_FLAG" (power) (pin_numbers hide) (pin_names (offset 0) hide) (in_bom yes) (on_board yes)
 (property "Reference" "#FLG" (at 0 1.905 0) %s) (property "Value" "PWR_FLAG" (at 0 3.81 0) %s)
 (property "Footprint" "" (at 0 0 0) %s) (property "Datasheet" "" (at 0 0 0) %s)
 (symbol "PWR_FLAG_0_0" (pin power_out line (at 0 0 90) (length 0) (name "pwr" %s) (number "1" %s)))
 (symbol "PWR_FLAG_0_1" (polyline (pts (xy 0 0) (xy 0 1.27) (xy -1.016 1.905) (xy 0 2.54) (xy 1.016 1.905) (xy 0 1.27))
  (stroke (width 0) (type default)) (fill (type none)))))''' % (lib, eff(hide=True), eff(), eff(hide=True), eff(hide=True), eff(), eff())
    return s, [(1, 'pwr', 'power_out', 0, 0, 90)]


class Sheet:
    def __init__(self, project, lib, title, paper='A3'):
        self.project, self.lib, self.title, self.paper = project, lib, title, paper
        self.root = U()
        self.libsyms, self.pins = {}, {}
        self.body, self.labels, self.ncs, self.texts = [], [], [], []

    def add_box(self, name, spec):
        self.libsyms[name], self.pins[name] = lib_symbol(self.lib, name, spec)

    def add_two_pin(self, name, prefix):
        self.libsyms[name], self.pins[name] = two_pin(self.lib, name, prefix)

    def place(self, ref, sym, x, y, value, fp, netmap):
        if sym == 'PWR_FLAG' and sym not in self.libsyms:
            self.libsyms[sym], self.pins[sym] = pwr_flag(self.lib)
        pins = self.pins[sym]
        small = len(pins) <= 2
        if small:
            rp, vp = (x + 1.6, y - 1, 'left'), (x + 1.6, y + 1.5, 'left')
        else:
            bx = max(abs(p[3]) for p in pins) - 2.54
            by = max([p[4] for p in pins if p[5] in (0, 180)] or [0]) + 2.54
            rp, vp = (x + bx, y - by - 6.5, 'right'), (x + bx, y - by - 4.2, 'right')
        flag = ref.startswith('#')
        props = ['(property "Reference" "%s" (at %.2f %.2f 0) %s)' % (ref, rp[0], rp[1], eff(justify=rp[2], hide=flag)),
                 '(property "Value" "%s" (at %.2f %.2f 0) %s)' % (value, vp[0], vp[1], eff(justify=vp[2])),
                 '(property "Footprint" "%s" (at %.2f %.2f 0) %s)' % (fp, x, y, eff(hide=True)),
                 '(property "Datasheet" "" (at %.2f %.2f 0) %s)' % (x, y, eff(hide=True))]
        yn = 'no' if flag else 'yes'
        self.body.append('(symbol (lib_id "%s:%s") (at %.2f %.2f 0) (unit 1) (in_bom %s) (on_board %s) (dnp no) (uuid %s)\n %s\n %s\n (instances (project "%s" (path "/%s" (reference "%s") (unit 1)))))'
                         % (self.lib, sym, x, y, yn, yn, U(), '\n '.join(props),
                            ' '.join('(pin "%s" (uuid %s))' % (p[0], U()) for p in pins), self.project, self.root, ref))
        for num, pname, ptype, px, py, a in pins:
            ax, ay = round(x + px, 2), round(y - py, 2)
            n = netmap.get(num)
            if n is None:
                self.ncs.append('(no_connect (at %.2f %.2f) (uuid %s))' % (ax, ay, U()))
                continue
            ang, just = {0: (180, 'right'), 180: (0, 'left'), 270: (90, 'left'), 90: (270, 'right')}[a]
            self.labels.append('(label "%s" (at %.2f %.2f %d) (fields_autoplaced) %s (uuid %s))'
                               % (ovl(n), ax, ay, ang, eff(justify=just + ' bottom' if ang in (0, 180) else just), U()))

    def note(self, x, y, s):
        self.texts.append('(text "%s" (at %.2f %.2f 0) %s (uuid %s))' % (s.replace('"', "'"), x, y, eff(justify='left bottom'), U()))

    def write(self, path, symlib_path=None, comment=''):
        lib = '\n'.join(self.libsyms.values())
        sch = '''(kicad_sch (version 20230121) (generator eeschema)
(uuid %s)
(paper "%s")
(title_block (title "%s") (rev "1") (comment 1 "%s"))
(lib_symbols
%s
)
%s
%s
%s
%s
(sheet_instances (path "/" (page "1")))
)
''' % (self.root, self.paper, self.title, comment, lib, '\n'.join(self.texts), '\n'.join(self.ncs),
       '\n'.join(self.labels), '\n'.join(self.body))
        open(path, 'w').write(sch)
        if symlib_path:
            open(symlib_path, 'w').write('(kicad_symbol_lib (version 20220914) (generator neo-mem)\n%s\n)\n'
                                         % lib.replace('"%s:' % self.lib, '"'))
        return len(self.labels), len(self.ncs)
