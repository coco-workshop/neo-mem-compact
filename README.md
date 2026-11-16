# neo-mem-compact

Compact surface-mount RAM expansions for the Tandy Color Computer 3. They plug into
the CN4/CN5/CN6 expansion sockets (and, for 2 MB, the CPU socket).

| Board | What it does | Main parts |
|---|---|---|
| [**512K**](boards/512k) | 512K upgrade on its own | CY62146ESL 256K×16 SRAM, 74AHCT86, 2× 74x574 |
| [**2048K memory**](boards/2048k-mem) | 2 MB of RAM; works as a plain 512K board on its own | CY62167ELL 1M×16 SRAM, 74AHCT86, 2× 74x574 |
| [**DAT**](boards/dat) | Sits under the CPU and supplies the extra address bits the 2048K board needs | ATF1504AS CPLD |

**Which to build:**
* **512K:** the 512K board. It's the cheapest option.
* **2 MB:** the 2048K memory board plus the DAT board, joined by a 4-wire cable
  (both headers are G, G, B, B).
  The memory board also runs alone as 512K, so you can fit it first and add the DAT
  board later.

| 512K | 2048K memory | DAT |
|---|---|---|
| ![512K](boards/512k/docs/preview.png) | ![2048K memory](boards/2048k-mem/docs/preview.png) | ![DAT](boards/dat/docs/preview.png) |

**Status: not yet built.** All three boards pass DRC, and each finished PCB was
checked independently against datasheet pinouts (`boards/*/docs/`). The DAT board's
CPLD logic passes a cycle-level simulation in both CPU speed modes, both as written
and after fitting into the chip.

## Repository layout
| Path | Contents |
|---|---|
| `boards/<board>/hardware` | KiCad 7 project (opens in KiCad 7, 8 and 9) |
| `boards/<board>/fab` | Gerbers + drill (zip), JLCPCB BOM and placement (CPL) files |
| `boards/<board>/docs` | Schematic PDF, preview, DRC and verification reports |
| `boards/dat/cpld` | CPLD logic, testbench, fitted `dat2m_top.jed`, build script |
| `scripts/512k`, `scripts/mem`, `scripts/dat` | Each board's design definition, generators and independent checker |
| `scripts/common` | Routing, clean-up, fab-output and rendering tools shared by all boards |

## How the memory boards work
Both memory boards replace the CoCo 3's four DRAMs with one 16-bit SRAM.
* The GIME multiplexes row and column addresses onto the same pins. Two '574
  flip-flops (U3/U4) latch the row address on the falling edge of /RAS, clocked
  through one XOR gate (`RAS = ~RAS XOR 1`). That gate delay centres the sampling
  point on the row-address hold time. On the 2048K board the same flip-flops also
  latch the two bank bits from the DAT board.
* Flip-flops are used rather than transparent latches ('573), so the row address
  holds after /RAS rises and can't change mid-cycle even if /CAS outlasts /RAS.
* `~BHE = ~WE0 XOR 1`, `~BLE = ~WE1 XOR 1`, `~WE = ~WE1 XOR ~BHE`
  (Jim Brain's simplification). If both write lines are ever low at once (an
  invalid state), the result is "no write".
* SRAM `~CE` = `/CAS`, `~OE` = GND. The chip only responds while the column address
  is valid, so glitches on the address lines or write logic before /CAS falls are
  ignored, and page-mode accesses are safe.
* SRAM address pins, and the data pins within each byte lane, are permuted to
  simplify routing. Any consistent one-to-one mapping works.
* The 2048K board's R1/R2 pull the bank bits low, so with no DAT board connected it
  works as an ordinary 512K board.

## How the DAT board works (2 MB)
The GIME's MMU registers are only 6 bits wide, so it can only address 512K
(64 × 8K blocks). Every CoCo 3 2 MB upgrade, from the original Disto kit onward, adds a board on the CPU bus that keeps the missing top two bits
of each MMU register and supplies them as physical address lines A20:A19.

The CPLD only listens to the CPU bus; the only signals it drives are the two bank lines.

| Register | Kept by the DAT board |
|---|---|
| `$FFA0–$FFAF` | bits 7:6 of all 16 MMU registers (the GIME keeps bits 5:0) |
| `$FF90` | bit 6 (MMU enable), bit 3 (MC3, the constant `$FExx` page) |
| `$FF91` | bit 0 (task select) |
| `$FF9B` | bits 1:0, the video bank (the Disto convention, as used by NitrOS-9) |
| `$FFD8/$FFD9` | CPU speed, used to find the CPU slot |

For each GIME memory slot it outputs either the CPU bank or the video bank:
* **CPU slots:** `mmu[task, A15:A13]` bits 7:6. It outputs bank 0 when the MMU is
  off, and for `$FExx` when MC3 is set (matching the GIME).
* **Video slots:** `$FF9B` bits 1:0.

The GIME runs memory slots at a fixed ~3.58 MHz. Counting from E's falling edge, the
fast-mode pattern is video, CPU, and the slow-mode pattern is video, idle, video,
CPU. So the CPU slot is always the one that ends when E falls: "E high" in fast
mode, "E high and Q low" in slow mode. (This matches Tony Distefano's description of
the Disto 2-Meg kit.)

All of these registers are write-only (reads come from the GIME as usual) and are
cleared by /RESET, so a reset machine is a plain 512K CoCo 3 until software writes
bits 7:6.

**Turbo LED:** J4 (+5V, cathode through R3) drives a case LED that lights whenever
the CPU runs fast: any write to `$FFD9` turns it on; `$FFD8` or /RESET turns it off.

**512K mode:** solder jumper **JP1** on the back of the DAT board selects the mode.
It ships bridged 1–2 (2 MB). Re-bridge it 2–3 to force bank 0, for any old program
that writes junk into bits 7:6 of the MMU registers.

The DAT board doesn't buffer or protect the CPU bus. Its two bank outputs pass
through 100 Ω resistors (R1/R2), so a cable plugged in backwards can't short them.

## Fitting
1. **Memory board (either size):** remove the four DRAMs (IC16–IC19) and cut C65 and
   C66. On a PAL machine they're left of the GIME; on an NTSC machine they're nearer
   the DRAM sockets. J1 goes into CN6/CN5 (the vertical socket pair left of the
   DRAM), with pin 1 (square pad) toward the rear ports. J2 goes into CN4 (the
   horizontal socket above the keyboard connector), with pin 1 at the left end.
2. **DAT board (2 MB only):** the CPU must be socketed. Pull the 6809/6309, plug the
   DAT board into the CPU socket with pin 1 (square pad, marked "CPU pin 1")
   matching the socket's pin 1, then plug the CPU into the DAT board. The board is the
   CPU's width along its length; the CPLD end hangs about 28 mm past the CPU's pin-20
   end and is about 3 mm wider on the pin-21 side (22.6 × 78.7 mm overall). **Check
   there's room in your machine before ordering.**
3. Link DAT **J2** to memory **J3** with a 4-wire female–female cable, kept as short
   as practical. Both headers are **G, G, B, B** (marked on the silkscreen, pin 1 =
   square pad = G): match G to G and B to B. Which B goes to which doesn't matter -
   swapping the two bank lines only reorders memory. A 2-wire cable on the B pins
   alone also works (the grounds are extra).

## The CPLD (`boards/dat/cpld`)
* `dat2m.v` holds the logic and `dat2m_tb.v` is its testbench
  (`iverilog dat2m.v dat2m_tb.v && vvp a.out`).
* `dat2m_top.v` is the top level. It's generated from the PCB, so its `//PIN:` list
  matches the copper exactly.
* **`dat2m_top.jed` is ready to program** (`dat2m_top.fit` is the fitter report).
  It was built with [hoglet67/atf15xx_yosys](https://github.com/hoglet67/atf15xx_yosys)
  (Yosys plus Atmel's `fit1504` from ProChip 5.0.x, run under Wine). With every pin
  locked to the PCB it fits in 50 of 64 macrocells, with E on the global clock
  (pin 37), /RESET on global clear (pin 39) and the turbo LED on pin 14. The
  fitter's gate-level output passes the same 129-check testbench as the source.
* To rebuild: `ATF15XX=/path/to/atf15xx_yosys boards/dat/cpld/build.sh`. It
  synthesises, fits, and re-runs the testbench on the fitted netlist.
* In `dat2m_top.v` the E and Q inputs are called `ECLK`/`QCLK`: top-level ports named
  `E` or `Q` clash with cell pin names, and `fit1504` then rejects the netlist.
* Program `dat2m_top.jed` through J3 (10-pin, Atmel ATDH1150USB / USB-Blaster layout)
  with Microchip ATMISP (included with ProChip). Or convert it to SVF and play it
  with OpenOCD or UrJTAG from any compatible adapter. Power the CoCo while
  programming.

## Ordering (JLCPCB)
Each board has its own Gerbers, BOM and CPL file in `boards/<board>/fab/`. Upload the
gerbers zip (2 layers, 1.6 mm), then the BOM and CPL for assembly. Check part
rotations in JLC's placement preview: each chip's pin-1 dot should sit on its
silkscreen triangle. Ordering all boards together shares shipping.

**Parts (both memory boards):**
| Ref | Part | LCSC | Alternatives |
|---|---|---|---|
| U2 | TI SN74AHCT86PWR | C471866 | Nexperia 74AHCT86PW (C554719), or any 5 V TTL-input '86 in TSSOP-14 (AHCT, VHCT, ACT). Not HCT: too slow for the /RAS clock path. |
| U3, U4 | Toshiba 74VHCT574AFT(BE) | C7421311 | Nexperia 74AHCT574PW (C282328), Toshiba 74VHCT574AFT (C2677834), any ACT574 in TSSOP-20; HCT574 as a last resort (slower, less margin) |
| U1 (512K) | CY62146ESL-45ZSXI | C2953196 | CY62146ELL. Not the CY62146EV30 (3 V only). |
| U1 (2048K) | CY62167ELL-45ZXI | C2950509 | Not the CY62167EV30 (3 V only). |

**Never** use HC (CMOS-level inputs), LV or LVC (3.3 V) logic.

**DAT board:**
* **U1:** ATF1504AS-10AU44. LCSC (C219301) is usually out of stock and expensive;
  DigiKey, Mouser and RS stock it for about $5. Untick U1 in JLC's BOM, let JLC fit
  only the four 0402 caps, and hand-solder the CPLD (TQFP-44, 0.8 mm pitch).
* **R1, R2** 100 Ω (C25076) and **R3** 470 Ω (C25117), all JLC basic parts.
* **J1** is a 40-pin **wire-wrap** DIP socket (long square tails, e.g. Mill-Max
  123-43-640-41-001000), mounted on top with its tails pushed through the board and
  trimmed to about 6 mm, so they plug into the CoCo's CPU socket. The holes are
  1.0 mm for the 0.64 mm square tails.

**Hand-solder** all through-hole parts: memory board headers J1/J2 on the
**bottom** (J3, 1×4, on top, 2048K only), and the DAT board's J1, J2 (1×4),
J3 (2×5, JTAG) and J4 (1×2, turbo LED).

## First power-up
1. Check for shorts between +5V and GND on every board.
2. Fit the memory board alone and run a full 512K memory test (e.g. under NitrOS-9,
   or a RAM test program). On the 2048K board leave J3 open (bank 0).
3. If you have a scope, check /WE0 and /WE1 against /CAS at the end of a write. The
   design assumes /CAS rises before, or together with, the write line.
4. **2 MB:** program the CPLD, fit the DAT board, and check the machine boots as a
   512K CoCo 3. Then check BANK0/BANK1 at memory J3 settle **before** /RAS falls (it's
   latched there), in both fast and slow mode. The design expects /RAS to fall at
   least ~15 ns after the E/Q edge that starts the slot. Probe E and Q on the CPU's
   own pins, the bank lines on the DAT board's J2 B pins, and GND/+5V on its JTAG header.
5. Test 2 MB with NitrOS-9 configured for 2 MB, or a 2 MB memory test.

## Regenerating
Each board is defined in `scripts/<board>/design.py` (`512k`, `mem`, `dat`). Needs
KiCad 7's Python bindings (`pcbnew`), `shapely`, `scipy`, Java 21 and
[Freerouting](https://github.com/freerouting/freerouting) 2.x. For example, the
2048K memory board:
```sh
B=boards/2048k-mem/hardware/neo-mem-2048k-mem
python3 scripts/mem/make_sch.py && python3 scripts/mem/make_pcb.py      # unrouted board
FREEROUTING_JAR=/path/freerouting-2.1.0.jar FR_EXTRA=--router.optimizer.max_passes=40 \
  python3 scripts/common/route.py $B.kicad_pcb /tmp/r.kicad_pcb 60
python3 scripts/common/finish.py /tmp/r.kicad_pcb /tmp/drc.txt          # strip stubs, DRC
python3 scripts/common/schnets.py /tmp/r.kicad_pcb $B.kicad_pro
cp /tmp/r.kicad_pcb $B.kicad_pcb
python3 scripts/mem/verify.py $B.kicad_pcb $B.kicad_sch
python3 scripts/common/fab.py boards/2048k-mem/hardware neo-mem-2048k-mem \
  boards/2048k-mem/fab boards/2048k-mem/docs scripts/mem/bom.json
```
The 512K and DAT boards work the same way (the DAT checker also takes
`boards/dat/cpld/dat2m_top.v`, and `finish.py` takes `JP1` as a keepout). The fine
pitches need the 0.15 mm default clearance set in each `.kicad_pro`. Autorouting
isn't deterministic; the committed boards are the ones that were checked.

## License and credit
Derived from **cc3-512k** by Ciaran Anscomb (<https://gitlab.com/sixxie/cc3-512k>):
the traced CN4/CN5/CN6 pinout, connector positions, outline envelope and design
approach, with the XOR logic from Jim Brain (RETRO Innovations). The DAT approach
follows Tony Distefano's published description of the Disto 2-Meg kit. Released,
like the original, under the
[Creative Commons Attribution-ShareAlike 4.0 International](LICENSE) license.
