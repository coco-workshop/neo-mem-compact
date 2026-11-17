"""Memory board netlist: single source of truth (PCB, schematic, verify all use it).

CoCo 3 2 MB SRAM board. Plugs into CN4/CN5/CN6 exactly like the 512K board; two extra
address bits (BANK0/BANK1 = physical A19/A20) arrive from the DAT board on J3 and are
latched together with the row address on the falling edge of /RAS. With nothing on J3,
R1/R2 pull BANK low and the board behaves as a normal 512K expansion.

Logic (active-low signals):
  ~BHE = ~WE0 XOR 1   ~BLE = ~WE1 XOR 1   ~WE = ~WE1 XOR ~BHE   RAS = ~RAS XOR 1
  SRAM ~CE1 = ~CAS, CE2 = 1, ~OE = 0, BYTE = 1 (x16)
"""
import json, os

J1 = {1: 'GND', 2: '+5V', 3: 'D9', 4: 'D8', 5: 'D10', 6: 'D11', 7: 'D14', 8: 'D15',
      9: 'D13', 10: 'D12', 11: '~WE1', 12: 'GND',
      13: 'GND', 14: 'D2', 15: 'D3', 16: 'D1', 17: '~WE0', 18: 'D0', 19: '~CAS',
      20: 'D7', 21: 'D5', 22: 'D4', 23: 'D6', 24: 'GND'}
J2 = {1: 'GND', 2: '~RAS', 3: 'Z0', 4: 'Z1', 5: 'Z2', 6: 'Z3', 7: 'Z6', 8: 'Z5',
      9: 'Z4', 10: 'Z7', 11: 'Z8', 12: 'GND'}
# Bank input: a 2x2 header with the same layout as the GIME-Z's bank header and the DAT
# board's J2 - one row carries the two bank lines, the other row is ground. Which bank line
# is A19 and which is A20 doesn't matter (swapping them only reorders memory), so the
# header is turned to put the bank pins where the routing needs them.
J3 = {1: 'BANK1', 2: 'GND', 3: 'BANK0', 4: 'GND'}

U2 = {1: '+5V', 2: '~WE0', 3: '~BHE',
      4: '~BHE', 5: '~WE1', 6: '~WE',
      9: '~WE1', 10: '+5V', 8: '~BLE',
      12: '~RAS', 13: '+5V', 11: 'RAS',
      7: 'GND', 14: '+5V'}

# Row/bank register: two 74AHCT574 (8-bit D flip-flops, TSSOP-20), clocked by RAS.
# '574 pinout: 1 ~OE, 2-9 D1-D8, 10 GND, 11 CLK, 12-19 Q8-Q1, 20 VCC (Dn -> Q on pin 21-n)
FF_D = [2, 3, 4, 5, 6, 7, 8, 9]
FF_Q = [19, 18, 17, 16, 15, 14, 13, 12]
ROW_ORDER = ['Z8', 'Z7', 'Z4', 'Z5', 'Z6', 'Z3', 'Z2', 'Z1', 'Z0']   # J2 order, no crossings
LATCHED = ROW_ORDER + ['BANK0', 'BANK1']                               # 11 bits over U3 + U4
U3 = {1: 'GND', 10: 'GND', 11: 'RAS', 20: '+5V'}
U4 = {1: 'GND', 10: 'GND', 11: 'RAS', 20: '+5V'}
for i, n in enumerate(LATCHED):
    u = U3 if i < 8 else U4
    k = i % 8
    u[FF_D[k]] = n
    u[FF_Q[k]] = ('R' + n[1:]) if n.startswith('Z') else ('B' + n[-1])   # R0..R8, B0, B1
for k in range(len(LATCHED) - 8, 8):
    U4[FF_D[k]] = 'GND'                                                  # unused inputs tied low

# CY62167ELL-45ZXI, 48-pin TSOP I (datasheet 001-15607)
SRAM_ADDR = {25: 'A0', 24: 'A1', 23: 'A2', 22: 'A3', 21: 'A4', 20: 'A5', 19: 'A6', 18: 'A7',
             8: 'A8', 7: 'A9', 6: 'A10', 5: 'A11', 4: 'A12', 3: 'A13', 2: 'A14', 1: 'A15',
             48: 'A16', 17: 'A17', 16: 'A18', 9: 'A19'}
SRAM_ADDR_PINS = sorted(SRAM_ADDR)
SRAM_LO_LANE = [29, 31, 33, 35, 38, 40, 42, 44]   # IO0-7  (~BLE) -> D0-D7, bank 0, ~WE0
SRAM_HI_LANE = [30, 32, 34, 36, 39, 41, 43, 45]   # IO8-15 (~BHE) -> D8-D15, bank 1, ~WE1
SRAM_FIXED = {26: '~CAS', 12: '+5V', 28: 'GND', 47: '+5V', 11: '~WE', 14: '~BHE', 15: '~BLE',
              37: '+5V', 27: 'GND', 46: 'GND'}     # 10, 13 = NC
U1 = dict(SRAM_FIXED)
_assign = os.path.join(os.path.dirname(__file__), 'assign.json')
if os.path.exists(_assign):
    U1.update({int(k): v for k, v in json.load(open(_assign)).items()})

CAPS = ['C1', 'C2', 'C3', 'C4']   # C1 SRAM, C2 XOR, C3 U3, C4 U4
PARTS = {
    'U1': dict(value='CY62167ELL-45ZXI', fp='Package_SO:TSOP-I-48_18.4x12mm_P0.5mm', pins=U1),
    'U2': dict(value='74AHCT86PW', fp='Package_SO:TSSOP-14_4.4x5mm_P0.65mm', pins=U2),
    'U3': dict(value='74AHCT574PW', fp='Package_SO:TSSOP-20_4.4x6.5mm_P0.65mm', pins=U3),
    'U4': dict(value='74AHCT574PW', fp='Package_SO:TSSOP-20_4.4x6.5mm_P0.65mm', pins=U4),
    'J1': dict(value='To CN6 (1-12) / CN5 (13-24)', fp='Connector_PinHeader_2.54mm:PinHeader_1x24_P2.54mm_Vertical', pins=J1),
    'J2': dict(value='To CN4', fp='Connector_PinHeader_2.54mm:PinHeader_1x12_P2.54mm_Vertical', pins=J2),
    'J3': dict(value='BANK in 2x2 (B row / G row)', fp='Connector_PinHeader_2.54mm:PinHeader_2x02_P2.54mm_Vertical', pins=J3),
    'R1': dict(value='10k', fp='Resistor_SMD:R_0402_1005Metric', pins={1: 'BANK0', 2: 'GND'}),
    'R2': dict(value='10k', fp='Resistor_SMD:R_0402_1005Metric', pins={1: 'BANK1', 2: 'GND'}),
}
for c in CAPS:
    PARTS[c] = dict(value='100n', fp='Capacitor_SMD:C_0402_1005Metric', pins={1: '+5V', 2: 'GND'})
