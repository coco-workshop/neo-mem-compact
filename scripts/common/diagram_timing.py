# Writes docs/diagrams/dat-timing.svg (run: python3 scripts/common/diagram_timing.py)
import os
S = 78          # slot width
X0 = 190        # waveform start
out = []
def T(x, y, s, **k):
    a = ' '.join('%s="%s"' % (kk.replace('_', '-'), v) for kk, v in k.items())
    out.append('<text x="%g" y="%g" %s>%s</text>' % (x, y, a, s))
def wave(y, edges, start, n, label, col='#1a202c'):
    # edges: list of (slot position, level) ; level 1 = high
    hi, lo = y - 14, y + 14
    pts, lvl = [], start
    pts.append((X0, hi if lvl else lo))
    for pos, l in edges:
        x = X0 + pos * S
        pts.append((x, hi if lvl else lo)); pts.append((x, hi if l else lo)); lvl = l
    pts.append((X0 + n * S, hi if lvl else lo))
    out.append('<polyline points="%s" fill="none" stroke="%s" stroke-width="2.5"/>' % (' '.join('%g,%g' % p for p in pts), col))
    T(X0 - 14, y + 5, label, text_anchor='end', font_weight='bold', fill='#2d3748')
def panel(y, title, sub, slots, E, Q, n):
    T(30, y, title, font_size=17, font_weight='bold', fill='#1a202c')
    T(30, y + 20, sub, fill='#4a5568', font_size=13)
    ys = y + 52
    T(X0 - 14, ys + 6, 'GIME slot', text_anchor='end', font_weight='bold', fill='#2d3748')
    for i, s in enumerate(slots):
        c = {'video': ('#ebf8ff', '#2b6cb0'), 'CPU': ('#fffaf0', '#c05621'), 'idle': ('#f7fafc', '#a0aec0')}[s]
        out.append('<rect x="%g" y="%g" width="%g" height="28" rx="5" fill="%s" stroke="%s"/>' % (X0 + i * S + 2, ys - 14, S - 4, c[0], c[1]))
        T(X0 + i * S + S / 2, ys + 5, s, text_anchor='middle', fill=c[1], font_size=13, font_weight='bold')
    wave(ys + 50, E, 0, n, 'E')
    wave(ys + 95, Q, 0, n, 'Q')
    yb = ys + 140
    T(X0 - 14, yb + 5, 'BANK lines', text_anchor='end', font_weight='bold', fill='#2d3748')
    for i, s in enumerate(slots):
        cpu = s == 'CPU'
        c = ('#fbd38d', '#c05621', 'CPU bank') if cpu else ('#bee3f8', '#2b6cb0', 'video bank')
        out.append('<polygon points="%g,%g %g,%g %g,%g %g,%g %g,%g %g,%g" fill="%s" stroke="%s"/>' % (
            X0 + i * S + 4, yb, X0 + i * S + 10, yb - 12, X0 + (i + 1) * S - 6, yb - 12, X0 + (i + 1) * S, yb,
            X0 + (i + 1) * S - 6, yb + 12, X0 + i * S + 10, yb + 12, c[0], c[1]))
        T(X0 + i * S + S / 2 + 2, yb + 4, c[2], text_anchor='middle', font_size=11, fill='#1a202c')
    # E falling edges
    for p in range(0, n + 1, 2 if n == 4 else 4):
        x = X0 + p * S
        out.append('<line x1="%g" y1="%g" x2="%g" y2="%g" stroke="#a0aec0" stroke-dasharray="3 4"/>' % (x, ys - 20, x, yb + 18))
    return yb

W, H = 900, 630
yb1 = panel(110, 'Fast mode (1.79 MHz):  video, CPU',
            'CPU slot = E high', ['video', 'CPU'] * 2, [(1, 1), (2, 0), (3, 1), (4, 0)], [(0.5, 1), (1.5, 0), (2.5, 1), (3.5, 0)], 4)
T(X0 + 4 * S + 30, 180, 'Each GIME memory slot is', font_size=13, fill='#4a5568')
T(X0 + 4 * S + 30, 198, '~280 ns (3.58 MHz) in both modes.', font_size=13, fill='#4a5568')
T(X0 + 4 * S + 30, 228, 'Dashed lines: E falling edges.', font_size=13, fill='#4a5568')
T(X0 + 4 * S + 30, 258, 'The memory board latches the', font_size=13, fill='#4a5568')
T(X0 + 4 * S + 30, 276, 'BANK lines when /RAS falls', font_size=13, fill='#4a5568')
T(X0 + 4 * S + 30, 294, 'in each slot.', font_size=13, fill='#4a5568')
panel(370, 'Slow mode (0.89 MHz):  video, idle, video, CPU',
      'CPU slot = E high and Q low', ['video', 'idle', 'video', 'CPU'] * 2,
      [(2, 1), (4, 0), (6, 1), (8, 0)], [(1, 1), (3, 0), (5, 1), (7, 0)], 8)
T(30, 608, 'CPU bank = bits 7:6 of the active MMU register (bank 0 if the MMU is off, or for $FExx with MC3 set).   Video bank = $FF9B bits 1:0.',
  font_size=12, fill='#4a5568')
svg = ('<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="0 0 %d %d" font-family="Helvetica, Arial, sans-serif" font-size="14">\n'
       '<rect width="%d" height="%d" rx="14" fill="#ffffff"/>\n'
       '<text x="30" y="38" font-size="20" font-weight="bold" fill="#1a202c">How the DAT board picks the bank for each memory slot</text>\n'
       '<text x="30" y="60" fill="#4a5568">The CPU slot is always the one that ends when E falls.</text>\n' % (W, H, W, H, W, H)
       + '\n'.join(out) + '\n</svg>\n')
open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'docs', 'diagrams', 'dat-timing.svg'), 'w').write(svg)
