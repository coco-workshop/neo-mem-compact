#!/usr/bin/env python3
"""Check the fitted CPLD can never drive the CPU bus.

Usage: check_pins.py <dat.kicad_pcb> <cpld dir>

Reads the fitter's pin list (dat2m_top.io) and macrocell table (dat2m_top.fit)
and the PCB, and fails unless:
  * the only output pins are BANK0, BANK1 and LED_FASTn, each with its output
    enable listed in the macrocell table, and none of them is on a CPU-socket net;
  * every CPLD pin wired to a CPU-socket (J1) signal is fitted as an input;
  * every I/O pin the fitter left unused (it reports these as "must be
    unconnected") has no net on the PCB.
"""
import re, sys
import pcbnew

ALLOWED_OUT = {'BANK0', 'BANK1', 'LED_FASTn'}
POWER = {'GND', '+5V', 'VCC'}
# ATF1504AS TQFP-44: the 32 I/O pins (everything except power and the 4 dedicated inputs)
IO_PINS = {1, 2, 3, 5, 6, 7, 8, 10, 11, 12, 13, 14, 15, 18, 19, 20, 21, 22, 23, 25,
           26, 27, 28, 30, 31, 32, 33, 34, 35, 42, 43, 44}
JTAG = {'TDI', 'TMS', 'TCK', 'TDO'}


def norm(n):
    return n.lstrip('/').upper()


def main(pcb, cdir):
    fails, notes = [], []
    io = {}
    for m in re.finditer(r'"(\w+)"\s*:\s*(INPUT|OUTPUT|BIDIR)\w*_PIN\s*=\s*(\d+)', open(f'{cdir}/dat2m_top.io').read()):
        io[int(m.group(3))] = (m.group(1), m.group(2))
    mc = {}
    for line in open(f'{cdir}/dat2m_top.fit'):
        m = re.match(r'MC\d+\s+(\d+)\s+(on|--)?\s*(\S+)\s+(\S+)', line)
        if m and m.group(1) != '0':
            mc[int(m.group(1))] = (m.group(3), m.group(2) or '', m.group(4))

    outs = {n for n, k in io.values() if k != 'INPUT'}
    if outs != ALLOWED_OUT:
        fails.append(f'output pins are {sorted(outs)}, expected {sorted(ALLOWED_OUT)}')
    for p, (n, k) in io.items():
        if k == 'OUTPUT' and mc.get(p, ('', ''))[1] != 'on':
            fails.append(f'pin {p} {n}: output enable not "on" in the macrocell table')
        if k == 'INPUT' and p in mc and mc[p][2] != 'INPUT' and n not in JTAG:
            fails.append(f'pin {p} {n}: .io says INPUT but the macrocell table says {mc[p][2]}')

    b = pcbnew.LoadBoard(pcb)
    fp = {f.GetReference(): f for f in b.GetFootprints()}
    j1 = {norm(p.GetNetname()) for p in fp['J1'].Pads() if p.GetNetname()} - POWER
    u1 = {int(p.GetNumber()): norm(p.GetNetname()) for p in fp['U1'].Pads() if p.GetNumber().isdigit()}

    bus = 0
    for pin, net in sorted(u1.items()):
        if net in j1:
            bus += 1
            name, kind = io.get(pin, (None, None))
            if pin in (37, 38, 39, 40):
                continue  # dedicated inputs: no output driver in the silicon
            if kind != 'INPUT':
                fails.append(f'pin {pin} is on CPU net {net} but is fitted as {kind or "unused"}')
            elif norm(name) not in (net, 'ECLK' if net == 'E' else net, 'QCLK' if net == 'Q' else net):
                notes.append(f'pin {pin}: fitted signal {name} on net {net}')
    for n in ALLOWED_OUT:
        pins = [p for p, (nm, _) in io.items() if nm == n]
        for p in pins:
            if u1.get(p) in j1:
                fails.append(f'output {n} (pin {p}) is on CPU net {u1[p]}')
    used = set(io)
    for p in sorted(IO_PINS - used):
        if u1.get(p):
            fails.append(f'unused I/O pin {p} has net {u1[p]} (fitter says leave it unconnected)')

    print(f'CPLD pins on CPU-socket nets: {bus}, all inputs' if not fails else f'CPLD pins on CPU-socket nets: {bus}')
    print(f'Output pins: {sorted(outs)}')
    print(f'Unused I/O pins (unconnected): {sorted(IO_PINS - used)}')
    for n in notes:
        print('NOTE', n)
    for f in fails:
        print('FAIL', f)
    print('PIN DIRECTION CHECK PASSED' if not fails else 'PIN DIRECTION CHECK FAILED')
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main(*sys.argv[1:3]))
