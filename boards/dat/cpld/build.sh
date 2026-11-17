#!/bin/bash -e
# Build dat2m_top.jed and check the fitted netlist against the testbench.
# Needs: yosys, wine, iverilog, a clone of https://github.com/hoglet67/atf15xx_yosys
# with its vendor/ folder populated from ProChip 5.0.x (see that repo's README),
# pointed to by ATF15XX (default ~/atf15xx_yosys).
cd "$(dirname "$0")"
ATF15XX=${ATF15XX:-$HOME/atf15xx_yosys}
export WINEDEBUG=-all
"$ATF15XX/run_yosys.sh" dat2m_top > yosys.log
"$ATF15XX/run_fitter.sh" -d ATF1504AS -p TQFP44 -s 10 dat2m_top \
    -preassign keep -tdi_pullup on -tms_pullup on -output_fast off -xor_synthesis on \
    -strategy Verilog_sim Verilog > fitter.log
grep -q "^\$Device TQFP44 fits" dat2m_top.fit || { echo "FIT FAILED - see dat2m_top.fit"; exit 1; }
# post-fit simulation: the fitter's gate-level netlist must pass the same testbench
sed 's/^\tPRIM_DFFE (/\tPRIM_DFFE p0 (/' dat2m_top.vo > postfit.v
iverilog -g2012 -o postfit.vvp dat2m_tb.v postfit_wrap.v postfit.v postfit_prims.v
vvp postfit.vvp | tail -2
# the CPLD must never drive the CPU bus: only BANK0/BANK1/LED_FASTn may be outputs
python3 ../../../scripts/dat/check_pins.py ../hardware/neo-mem-2048k-dat.kicad_pcb . \
    | tee ../docs/pin-check.txt | tail -1
grep -q "CHECK PASSED" ../docs/pin-check.txt || { echo "PIN CHECK FAILED"; exit 1; }
echo "dat2m_top.jed ready"
