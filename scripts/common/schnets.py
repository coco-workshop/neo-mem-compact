#!/usr/bin/python3
"""Rename PCB nets to the names KiCad's schematic gives them (local labels: '/NAME',
'~X' -> '~{X}') so 'Update PCB from Schematic' matches 1:1, and point the Power net
class at the renamed supply nets.  usage: schnets.py board.kicad_pcb board.kicad_pro"""
import json, re, sys


def sch(n):
    if not n:
        return n
    return '/' + ('~{%s}' % n[1:] if n.startswith('~') else n)


def main(pcb, pro):
    t = open(pcb).read()
    if '(net 1 "/' in t:
        print('already renamed'); return
    t = re.sub(r'\(net (\d+) "([^"]*)"\)', lambda m: '(net %s "%s")' % (m.group(1), sch(m.group(2))), t)
    t = re.sub(r'\(net_name "([^"]*)"\)', lambda m: '(net_name "%s")' % sch(m.group(1)), t)
    open(pcb, 'w').write(t)
    p = json.load(open(pro))
    p['net_settings']['netclass_patterns'] = [{'netclass': 'Power', 'pattern': '/+5V'},
                                              {'netclass': 'Power', 'pattern': '/GND'}]
    json.dump(p, open(pro, 'w'), indent=2)
    print('renamed nets in', pcb)


if __name__ == '__main__':
    main(*sys.argv[1:])
