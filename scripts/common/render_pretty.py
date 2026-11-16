#!/usr/bin/python3
"""Photo-style 3D render of an assembled KiCad board.

The board itself is textured from the real copper / mask / silkscreen layers,
the parts come from the STEP export (KiCad 3D models).

usage: render_pretty.py board.kicad_pcb board.step out.png [elev azim width height]
env:   ZOOM (default 1.25), FINISH=enig|hasl (default enig), MASK=#rrggbb
"""
import math, os, subprocess, sys, tempfile
import numpy as np
import pyvista as pv
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from render3d import load, faces_with_colour  # noqa: E402

PXMM = 40  # texture resolution, pixels per mm


def hexrgb(h):
    h = h.lstrip('#'); return np.array([int(h[i:i + 2], 16) for i in (0, 2, 4)], float)


def layer_alpha(pcb, layer, tmp, mirror=False):
    svg = os.path.join(tmp, layer + '.svg'); png = os.path.join(tmp, layer + '.png')
    cmd = ['kicad-cli', 'pcb', 'export', 'svg', '--black-and-white', '--page-size-mode', '2',
           '--exclude-drawing-sheet', '--drill-shape-opt', '0', '-l', layer, '-o', svg, pcb]
    subprocess.run(cmd, check=True, capture_output=True)
    head = open(svg).read(2000)
    w_mm = float(head.split('width="')[1].split('mm')[0])
    subprocess.run(['rsvg-convert', '-w', str(int(round(w_mm * PXMM))), '-b', 'none', '-o', png, svg], check=True)
    a = np.asarray(Image.open(png).convert('RGBA')).astype(float)
    dark = (a[..., 3] / 255.0) * (1 - a[..., :3].mean(-1) / 255.0)  # black ink = 1
    return dark


def board_texture(pcb, side, tmp):
    """RGB texture (rows = pcb y downward) plus the pixel bbox of the board outline."""
    p = 'F' if side == 'top' else 'B'
    edge = layer_alpha(pcb, 'Edge.Cuts', tmp)
    cu = layer_alpha(pcb, p + '.Cu', tmp)
    mask = layer_alpha(pcb, p + '.Mask', tmp)          # ink = opening
    silk = layer_alpha(pcb, p + '.Silkscreen', tmp)
    ys, xs = np.nonzero(edge > 0.3)
    bbox = (xs.min(), ys.min(), xs.max() + 1, ys.max() + 1)

    m = hexrgb(os.environ.get('MASK', '#0c4026'))
    fr4 = hexrgb('#c9b27c')
    pad = hexrgb('#d9b25a') if os.environ.get('FINISH', 'enig') == 'enig' else hexrgb('#c8c8c8')
    silkc = hexrgb('#f2f2ee')
    img = np.empty(cu.shape + (3,))
    img[:] = m * 0.92
    cuu = cu[..., None]
    img = img * (1 - cuu) + (m * 1.35 + 6) * cuu                 # copper under mask shows lighter
    op = mask[..., None]
    opening = cuu * pad + (1 - cuu) * fr4
    img = img * (1 - op) + opening * op
    sk = (silk * (1 - mask))[..., None]
    img = img * (1 - sk) + silkc * sk
    # subtle mask sheen / noise so large areas don't look flat
    rng = np.random.default_rng(1)
    img += rng.normal(0, 2.0, img.shape[:2])[..., None]
    return np.clip(img, 0, 255).astype(np.uint8), bbox


def main(pcb, step, png, elev='38', azim='-62', w='2400', h='1800'):
    st, ct, doc = load(step)
    parts = faces_with_colour(st, ct)

    # board colour = colour of the largest horizontal face
    def xy_area(v):
        return np.ptp(v[:, 0]) * np.ptp(v[:, 1])
    big = max(parts, key=lambda p: xy_area(p[0]) if np.ptp(p[0][:, 2]) < 1e-3 else 0)
    bcol = big[2]
    board = [p for p in parts if p[2] == bcol]
    bv = np.vstack([p[0] for p in board])
    x0, x1 = bv[:, 0].min(), bv[:, 0].max(); y0, y1 = bv[:, 1].min(), bv[:, 1].max()
    zt, zb = bv[:, 2].max(), bv[:, 2].min()

    tmp = tempfile.mkdtemp()
    tex = {}
    for side in ('top', 'bot'):
        img, (px0, py0, px1, py1) = board_texture(pcb, side, tmp)
        H, W = img.shape[:2]
        tex[side] = (pv.Texture(img), (px0, py0, px1, py1, W, H))

    pv.OFF_SCREEN = True
    pl = pv.Plotter(off_screen=True, window_size=(int(w), int(h)), lighting='none')
    pl.set_background('white')

    def uv(v, side):
        px0, py0, px1, py1, W, H = tex[side][1]
        # step x -> pixel x ; step y is pcb -y so top of image == y1
        u = (px0 + (v[:, 0] - x0) / (x1 - x0) * (px1 - px0)) / W
        r = py0 + (y1 - v[:, 1]) / (y1 - y0) * (py1 - py0)
        return np.c_[u, 1 - r / H]

    groups = {}
    for v, t, c in parts:
        if c == bcol:
            if np.ptp(v[:, 2]) < 1e-3 and abs(v[0, 2] - zt) < 1e-3:
                groups.setdefault('top', []).append((v + [0, 0, 0.002], t)); continue
            if np.ptp(v[:, 2]) < 1e-3 and abs(v[0, 2] - zb) < 1e-3:
                groups.setdefault('bot', []).append((v - [0, 0, 0.002], t)); continue
            groups.setdefault('edge', []).append((v, t)); continue
        groups.setdefault(tuple(round(x, 3) for x in c), []).append((v, t))

    def merge(items):
        vs, fs, off = [], [], 0
        for v, t in items:
            vs.append(v); fs.append(np.hstack([np.full((len(t), 1), 3), t + off])); off += len(v)
        return pv.PolyData(np.vstack(vs), np.vstack(fs).ravel())

    for key, items in groups.items():
        mesh = merge(items)
        if key in ('top', 'bot'):
            mesh.active_texture_coordinates = uv(mesh.points, key)
            pl.add_mesh(mesh, texture=tex[key][0], ambient=0.25, diffuse=0.8, specular=0.35, specular_power=40)
        elif key == 'edge':
            pl.add_mesh(mesh, color=(0.62, 0.55, 0.36), ambient=0.25, diffuse=0.8)
        else:
            c = np.array(key)
            if max(c) < 0.12:                       # black plastic: lift a little so it reads
                c = c * 0.5 + 0.07
                pl.add_mesh(mesh, color=c, ambient=0.2, diffuse=0.75, specular=0.25, specular_power=15)
            elif c[0] > 0.6 and c[2] < 0.45:        # gold pins
                pl.add_mesh(mesh, color=(0.86, 0.68, 0.30), ambient=0.25, diffuse=0.7, specular=0.9,
                            specular_power=60, smooth_shading=True)
            elif min(c) > 0.55:                     # tin / silver leads
                pl.add_mesh(mesh, color=(0.80, 0.80, 0.82), ambient=0.25, diffuse=0.7, specular=0.9,
                            specular_power=60, smooth_shading=True)
            else:
                pl.add_mesh(mesh, color=c, ambient=0.25, diffuse=0.75, specular=0.3, specular_power=20)

    ctr = np.array([(x0 + x1) / 2, (y0 + y1) / 2, (zt + zb) / 2])
    size = math.hypot(x1 - x0, y1 - y0)
    e, a = math.radians(float(elev)), math.radians(float(azim))
    d = np.array([math.cos(e) * math.cos(a), math.cos(e) * math.sin(a), math.sin(e)])
    # three-point lighting
    for dirv, inten, col in ((d + [-0.6, 0.3, 0.9], 0.85, 'white'), (d + [0.9, -0.2, 0.2], 0.35, '#dfe8ff'),
                             ([0, 0, 1], 0.35, 'white'), (-d + [0, 0, 0.6], 0.25, '#fff4e0')):
        lt = pv.Light(position=tuple(ctr + np.array(dirv) * size * 4), focal_point=tuple(ctr),
                      intensity=inten, color=col)
        pl.add_light(lt)
    pl.camera_position = [tuple(ctr + d * size * 3), tuple(ctr), (0, 0, 1)]
    pl.camera.view_angle = 25
    pl.reset_camera()
    pl.camera.zoom(float(os.environ.get('ZOOM', '1.0')))
    pl.enable_anti_aliasing('ssaa')
    img = Image.fromarray(pl.screenshot(transparent_background=True, return_img=True))
    compose(img, png)
    print('rendered', png)


def compose(img, png, margin=0.07):
    """Crop to the board, then put it on a soft studio backdrop with a drop shadow."""
    from PIL import ImageFilter
    a = np.asarray(img)[..., 3]
    ys, xs = np.nonzero(a > 8)
    img = img.crop((xs.min(), ys.min(), xs.max() + 1, ys.max() + 1))
    w, h = img.size
    m = int(max(w, h) * margin)
    W, H = w + 2 * m, h + 2 * m
    yy = np.linspace(0, 1, H)[:, None, None]
    top, bot = hexrgb('#dfe3ea'), hexrgb('#f7f8fa')
    bg = np.broadcast_to(top * (1 - yy) + bot * yy, (H, W, 3)).astype(np.uint8)
    out = Image.fromarray(bg.copy()).convert('RGBA')
    sh = Image.new('L', (W, H), 0)
    sh.paste(img.split()[3].point(lambda v: int(v * 0.45)), (m + int(m * 0.15), m + int(m * 0.25)))
    sh = sh.filter(ImageFilter.GaussianBlur(m * 0.25))
    out.paste(Image.new('RGBA', (W, H), (20, 25, 35, 255)), (0, 0), sh)
    out.alpha_composite(img, (m, m))
    out.convert('RGB').save(png)


if __name__ == '__main__':
    main(*sys.argv[1:])
