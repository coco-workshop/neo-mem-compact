"""DAT board netlist: CPU-socket interposer carrying an ATF1504AS (logic in cpld/dat2m.v).

J1 is a 40-pin interposer: a wire-wrap (long-tail) DIP-40 socket whose tails pass through
the board into the CoCo 3's CPU socket; the 6809/6309 plugs into its top. Every CPU pin
passes straight through - the CPLD only listens (all CPLD CPU-side pins are inputs).
"""
import json, os

# 6809E / 6309E pinout (only the pins we tap or power from)
CPU = {1: 'GND', 7: '+5V',
       **{8 + i: 'A%d' % i for i in range(16)},          # pins 8-23: A0-A15
       24: 'D7', 25: 'D6', 28: 'D3', 30: 'D1', 31: 'D0',
       32: 'RW', 34: 'E', 35: 'Q', 37: '~RESET'}

# ATF1504AS-10AU44 (TQFP-44) - same pinout as EPM7064 TQFP-44
CPLD_VCC = [9, 17, 29, 41]
CPLD_GND = [4, 16, 24, 36]
CPLD_JTAG = {1: 'TDI', 7: 'TMS', 26: 'TCK', 32: 'TDO'}
CPLD_DEDICATED = {37: 'E', 38: 'Q', 39: '~RESET', 40: 'RW'}   # GCLK1, OE1, GCLR, OE2/GCLK2
CPLD_IO = [2, 3, 5, 6, 8, 10, 11, 12, 13, 14, 15, 18, 19, 20, 21, 22, 23, 25, 27, 28,
           30, 31, 33, 34, 35, 42, 43, 44]
IO_SIGNALS = ['A%d' % i for i in range(16)] + ['D0', 'D1', 'D3', 'D6', 'D7', 'EN2M', 'BANK0', 'BANK1', 'LED_FASTn']

U1 = {p: '+5V' for p in CPLD_VCC}
U1.update({p: 'GND' for p in CPLD_GND})
U1.update(CPLD_JTAG)
U1.update(CPLD_DEDICATED)
_assign = os.path.join(os.path.dirname(__file__), 'assign.json')
if os.path.exists(_assign):
    U1.update({int(k): v for k, v in json.load(open(_assign)).items()})

# 10-pin JTAG, Atmel ATDH1150USB / Altera USB-Blaster layout
JTAG = {1: 'TCK', 2: 'GND', 3: 'TDO', 4: '+5V', 5: 'TMS', 9: 'TDI', 10: 'GND'}   # 6,7,8 NC
# Bank output to the memory board: G, G, B0, B1 (2.54 mm). The bank lines pass through
# 100R series resistors so a cable plugged in backwards can't short a CPLD output.
J2 = {1: 'GND', 2: 'GND', 3: 'B0', 4: 'B1'}
# Turbo LED header: case LED anode to pin 1 (+5V), cathode to pin 2; R3 limits the current.
J4 = {1: '+5V', 2: 'LED_K'}

PARTS = {
    'J1': dict(value='CPU interposer (40-pin wire-wrap socket)', fp='Package_DIP:DIP-40_W15.24mm', pins=CPU),
    'U1': dict(value='ATF1504AS-10AU44', fp='Package_QFP:TQFP-44_10x10mm_P0.8mm', pins=U1),
    'J2': dict(value='BANK out (G G B0 B1)', fp='Connector_PinHeader_2.54mm:PinHeader_1x04_P2.54mm_Vertical', pins=J2),
    'J4': dict(value='Turbo LED', fp='Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Vertical', pins=J4),
    'R1': dict(value='100', fp='Resistor_SMD:R_0402_1005Metric', pins={1: 'BANK0', 2: 'B0'}),
    'R2': dict(value='100', fp='Resistor_SMD:R_0402_1005Metric', pins={1: 'BANK1', 2: 'B1'}),
    'R3': dict(value='470', fp='Resistor_SMD:R_0402_1005Metric', pins={1: 'LED_K', 2: 'LED_FASTn'}),
    'J3': dict(value='JTAG', fp='Connector_PinHeader_2.54mm:PinHeader_2x05_P2.54mm_Vertical', pins=JTAG),
    # 3-pad solder jumper on the back, bridged 1-2 at the factory (EN2M = 1, 2 MB mode).
    # 512K mode: cut the 1-2 bridge and bridge 2-3 (EN2M = 0).
    'JP1': dict(value='2MB/512K', fp='Jumper:SolderJumper-3_P1.3mm_Bridged12_RoundedPad1.0x1.5mm', pins={1: '+5V', 2: 'EN2M', 3: 'GND'}),
}
CAPS = ['C1', 'C2', 'C3', 'C4']
for c in CAPS:
    PARTS[c] = dict(value='100n', fp='Capacitor_SMD:C_0402_1005Metric', pins={1: '+5V', 2: 'GND'})
