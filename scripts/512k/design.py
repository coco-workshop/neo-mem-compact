"""Single source of truth for the CoCo 3 512K compact SRAM board.

Everything (PCB generator, schematic generator, verification) imports this.
Logic (all signals active-low except RAS):
  ~BHE = ~WE0 XOR 1          (U2 gate A)
  ~WE  = ~WE1 XOR ~BHE       (U2 gate B)  == AND of ~WE0,~WE1 for valid states
  ~BLE = ~WE1 XOR 1          (U2 gate C)
  RAS  = ~RAS XOR 1          (U2 gate D)  -> rising edge clocks the U3/U4 row register
SRAM ~CE = ~CAS, ~OE = GND.
"""

# ---- CoCo 3 expansion sockets (traced by C. Anscomb) ---------------------
# J1 pins 1-12 -> CN6, pins 13-24 -> CN5 ; J2 -> CN4
J1 = {1: 'GND', 2: '+5V', 3: 'D9', 4: 'D8', 5: 'D10', 6: 'D11', 7: 'D14', 8: 'D15',
      9: 'D13', 10: 'D12', 11: '~WE1', 12: 'GND',
      13: 'GND', 14: 'D2', 15: 'D3', 16: 'D1', 17: '~WE0', 18: 'D0', 19: '~CAS',
      20: 'D7', 21: 'D5', 22: 'D4', 23: 'D6', 24: 'GND'}
J2 = {1: 'GND', 2: '~RAS', 3: 'Z0', 4: 'Z1', 5: 'Z2', 6: 'Z3', 7: 'Z6', 8: 'Z5',
      9: 'Z4', 10: 'Z7', 11: 'Z8', 12: 'GND'}

# ---- U2 74AHCT86 quad XOR (pin: net) --------------------------------------
U2 = {1: '+5V', 2: '~WE0', 3: '~BHE',          # gate A
      4: '~BHE', 5: '~WE1', 6: '~WE',           # gate B
      9: '~WE1', 10: '+5V', 8: '~BLE',          # gate C
      12: '~RAS', 13: '+5V', 11: 'RAS',         # gate D
      7: 'GND', 14: '+5V'}

# ---- U3/U4 74AHCT574 8-bit D flip-flops (row register) -------------------
# '574 pinout: 1 ~OE, 2-9 D1-D8, 10 GND, 11 CLK, 12-19 Q8-Q1, 20 VCC (Dn -> Q on pin 21-n)
FF_D = [2, 3, 4, 5, 6, 7, 8, 9]
FF_Q = [19, 18, 17, 16, 15, 14, 13, 12]
# Row bits, ordered so traces from J2 don't cross (J2 left->right: Z0 Z1 Z2 Z3 Z6 Z5 Z4 Z7 Z8).
ROW_ORDER = ['Z8', 'Z7', 'Z4', 'Z5', 'Z6', 'Z3', 'Z2', 'Z1', 'Z0']
U3 = {1: 'GND', 10: 'GND', 11: 'RAS', 20: '+5V'}
U4 = {1: 'GND', 10: 'GND', 11: 'RAS', 20: '+5V'}
for i, z in enumerate(ROW_ORDER):
    u = U3 if i < 8 else U4
    u[FF_D[i % 8]] = z
    u[FF_Q[i % 8]] = 'R' + z[1:]       # latched row bit, e.g. R8
for k in range(len(ROW_ORDER) - 8, 8):
    U4[FF_D[k]] = 'GND'                # unused inputs tied low

# ---- U1 CY62146ESL 256Kx16 SRAM (TSOP-II-44) -------------------------------
SRAM_FIXED = {6: '~CAS', 17: '~WE', 39: '~BLE', 40: '~BHE', 41: 'GND',
              11: '+5V', 33: '+5V', 12: 'GND', 34: 'GND'}
SRAM_ADDR_PINS = [1, 2, 3, 4, 5, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 42, 43, 44]
SRAM_LO_LANE = [7, 8, 9, 10, 13, 14, 15, 16]     # IO0-7, gated by ~BLE -> bank 0 (D0-7, ~WE0)
SRAM_HI_LANE = [29, 30, 31, 32, 35, 36, 37, 38]  # IO8-15, gated by ~BHE -> bank 1 (D8-15, ~WE1)
# Address/data permutation is filled in by the PCB generator (assign.json) and
# loaded here so every tool agrees.
import json, os
_here = os.path.dirname(__file__)
_assign = os.path.join(_here, 'assign.json')
U1 = dict(SRAM_FIXED)
if os.path.exists(_assign):
    U1.update({int(k): v for k, v in json.load(open(_assign)).items()})

# ---- Decoupling --------------------------------------------------------------
CAPS = ['C1', 'C2', 'C3', 'C4', 'C5']   # C1/C2 SRAM, C3 XOR, C4 U3, C5 U4

PARTS = {
    'U1': dict(value='CY62146ESL-45ZSXI', fp='Package_SO:TSOP-II-44_10.16x18.41mm_P0.8mm', pins=U1),
    'U2': dict(value='74AHCT86PW', fp='Package_SO:TSSOP-14_4.4x5mm_P0.65mm', pins=U2),
    'U3': dict(value='74AHCT574PW', fp='Package_SO:TSSOP-20_4.4x6.5mm_P0.65mm', pins=U3),
    'U4': dict(value='74AHCT574PW', fp='Package_SO:TSSOP-20_4.4x6.5mm_P0.65mm', pins=U4),
    'J1': dict(value='To CN6 (1-12) / CN5 (13-24)', fp='Connector_PinHeader_2.54mm:PinHeader_1x24_P2.54mm_Vertical', pins=J1),
    'J2': dict(value='To CN4', fp='Connector_PinHeader_2.54mm:PinHeader_1x12_P2.54mm_Vertical', pins=J2),
}
for c in CAPS:
    PARTS[c] = dict(value='100n', fp='Capacitor_SMD:C_0402_1005Metric', pins={1: '+5V', 2: 'GND'})

LCSC = {'U1': 'C2953196', 'U2': 'C554719', 'U3': 'C282328', 'U4': 'C282328', 'C': 'C1525'}
