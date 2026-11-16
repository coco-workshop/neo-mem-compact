#!/usr/bin/python3
"""Regenerate the assembled-board renders in boards/*/docs/.

Needs KiCad 7 (kicad-cli), rsvg-convert, pyvista and OCP.  KiCad's STEP models
are fetched once from github.com/KiCad/kicad-packages3D into $KICAD3D
(default ~/.cache/kicad-3d) when they are not already there.

usage: render_all.py [512k|2048k-mem|dat ...]
"""
import os, re, subprocess, sys, tempfile, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
LIB = os.environ.get('KICAD3D', os.path.expanduser('~/.cache/kicad-3d'))
RAW = 'https://raw.githubusercontent.com/KiCad/kicad-packages3D/master/'
SOCKET = 'Package_DIP.3dshapes/DIP-40_W15.24mm_Socket.step'
CPU = 'Package_DIP.3dshapes/DIP-40_W15.24mm.step'

BOARDS = {   # name: (pcb, [(output, elev, azim, cpu fitted)])
    '512k': ('boards/512k/hardware/neo-mem-512k-compact.kicad_pcb',
             [('boards/512k/docs/render.png', 42, -55, False)]),
    '2048k-mem': ('boards/2048k-mem/hardware/neo-mem-2048k-mem.kicad_pcb',
                  [('boards/2048k-mem/docs/render.png', 42, -55, False)]),
    'dat': ('boards/dat/hardware/neo-mem-2048k-dat.kicad_pcb',
            [('boards/dat/docs/render.png', 40, -120, False),
             ('boards/dat/docs/render-cpu.png', 36, -62, True)]),
}


def model(rel):
    path = os.path.join(LIB, rel)
    if not os.path.exists(path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        print('fetching', rel)
        urllib.request.urlretrieve(RAW + rel, path)
    return path


def render_copy(pcb, dst, cpu):
    t = open(pcb).read()

    def sub(m):
        rel = m.group(1)[:-4] + '.step'
        if rel == CPU:   # J1 is the CPU socket: show the socket, optionally with a CPU in it
            s = '(model "%s"\n      (offset (xyz 0 0 0)) (scale (xyz 1 1 1)) (rotate (xyz 0 0 0)))' % model(SOCKET)
            if cpu:
                s += '\n    (model "%s"\n      (offset (xyz 0 0 3.2)) (scale (xyz 1 1 1)) (rotate (xyz 0 0 0)))' % model(CPU)
            return s
        return '(model "%s"%s' % (model(rel), m.group(2))

    t = re.sub(r'\(model "\$\{KICAD\d_3DMODEL_DIR\}/([^"]+)"(\s*\(offset[^\n]*\n\s*\(scale[^\n]*\n\s*\(rotate[^\n]*\n\s*\))',
               sub, t)
    open(dst, 'w').write(t)


def main(names):
    tmp = tempfile.mkdtemp()
    for name in names or BOARDS:
        pcb, shots = BOARDS[name]
        for out, elev, azim, cpu in shots:
            base = os.path.join(tmp, '%s%s' % (name, '-cpu' if cpu else ''))
            render_copy(os.path.join(ROOT, pcb), base + '.kicad_pcb', cpu)
            subprocess.run(['kicad-cli', 'pcb', 'export', 'step', '--subst-models', '-f',
                            '-o', base + '.step', base + '.kicad_pcb'], check=True, capture_output=True)
            subprocess.run([sys.executable, os.path.join(HERE, 'render_pretty.py'), base + '.kicad_pcb',
                            base + '.step', os.path.join(ROOT, out), str(elev), str(azim)], check=True)


if __name__ == '__main__':
    main(sys.argv[1:])
