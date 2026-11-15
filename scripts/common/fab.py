#!/usr/bin/python3
"""Gerbers + drill + JLCPCB BOM/CPL + preview + schematic PDF for one board.
usage: fab.py <hardware dir> <name> <fab out dir> <docs dir> <bom.json>
bom.json: [[comment, "refs,...", footprint, lcsc], ...]; THT refs are left out of the CPL."""
import csv, json, os, subprocess, sys
from PIL import Image


def run(*a):
    subprocess.run(a, check=True, capture_output=True)


def main(hw, name, fab, docs, bomfile):
    pcb, sch = os.path.join(hw, name + '.kicad_pcb'), os.path.join(hw, name + '.kicad_sch')
    g = os.path.join(fab, 'gerbers'); os.makedirs(g, exist_ok=True); os.makedirs(docs, exist_ok=True)
    for f in os.listdir(g):
        os.remove(os.path.join(g, f))
    run('kicad-cli', 'pcb', 'export', 'gerbers', '-o', g + '/', '--layers',
        'F.Cu,B.Cu,F.Paste,B.Paste,F.SilkS,B.SilkS,F.Mask,B.Mask,Edge.Cuts', '--subtract-soldermask', '--no-x2', pcb)
    run('kicad-cli', 'pcb', 'export', 'drill', '-o', g + '/', '--format', 'excellon', '--excellon-units', 'mm',
        '--generate-map', '--map-format', 'gerberx2', pcb)
    z = os.path.join(fab, name + '_gerbers.zip')
    if os.path.exists(z):
        os.remove(z)
    run('sh', '-c', 'cd "%s" && zip -q "%s" *' % (g, os.path.abspath(z)))
    run('kicad-cli', 'pcb', 'export', 'pos', '-o', '/tmp/pos.csv', '--format', 'csv', '--units', 'mm', '--side', 'both', '--smd-only', pcb)
    bom = json.load(open(bomfile))
    smt = {r for row in bom if row[3] != 'THT' for r in row[1].split(',')}
    with open(os.path.join(fab, name + '_CPL_JLCPCB.csv'), 'w', newline='') as f:
        w = csv.writer(f); w.writerow(['Designator', 'Mid X', 'Mid Y', 'Layer', 'Rotation'])
        for r in csv.DictReader(open('/tmp/pos.csv')):
            if r['Ref'] in smt:
                w.writerow([r['Ref'], r['PosX'] + 'mm', r['PosY'] + 'mm', 'Top' if r['Side'] == 'top' else 'Bottom',
                            '%g' % (float(r['Rot']) % 360)])
    with open(os.path.join(fab, name + '_BOM_JLCPCB.csv'), 'w', newline='') as f:
        w = csv.writer(f); w.writerow(['Comment', 'Designator', 'Footprint', 'LCSC Part #'])
        for row in bom:
            if row[3] != 'THT':
                w.writerow(row)
    # previews: top and (mirrored) bottom side by side
    imgs = []
    for side, layers, extra in (('front', 'F.Cu,F.Mask,F.SilkS,Edge.Cuts', []), ('back', 'B.Cu,B.Mask,B.SilkS,Edge.Cuts', ['--mirror'])):
        svg = '/tmp/%s_%s.svg' % (name, side)
        run('kicad-cli', 'pcb', 'export', 'svg', '--layers', layers, *extra, '--exclude-drawing-sheet', '--page-size-mode', '2', '-o', svg, pcb)
        png = svg[:-4] + '.png'
        run('rsvg-convert', '-h', '900', '-b', '#1d1d1d', svg, '-o', png)
        imgs.append(Image.open(png))
    c = Image.new('RGB', (sum(i.width for i in imgs) + 40, max(i.height for i in imgs)), '#1d1d1d')
    x = 0
    for i in imgs:
        c.paste(i, (x, 0)); x += i.width + 40
    short = name.split('-')[-1]
    c.save(os.path.join(docs, short + '-preview.png'))
    run('kicad-cli', 'sch', 'export', 'pdf', '-o', os.path.join(docs, short + '-schematic.pdf'), sch)
    print('fab done for', name)


if __name__ == '__main__':
    main(*sys.argv[1:])
