// neo-mem-2048k-compact - DAT (dynamic address translation) extension for the CoCo 3
// Target: Microchip ATF1504AS-10AU44 (5 V, 64 macrocells), sitting under the 6809/6309.
//
// The GIME's MMU only stores 6 bits per block register (512K). This CPLD shadows the
// CPU's writes to the GIME registers and supplies the two missing physical block bits
// (A20:A19, called BANK[1:0]) for every memory slot. The memory board latches BANK on
// the falling edge of /RAS together with the row address.
//
//   $FFA0-$FFAF  MMU block registers   - D7:D6 are kept here (GIME keeps D5:D0)
//   $FF90        INIT0                  - bit 6 MMU enable, bit 3 MC3 ($FExx constant page)
//   $FF91        INIT1                  - bit 0 task select
//   $FF9B        video bank (Disto)     - bits 1:0 = A20:A19 for video fetches
//   $FFD8/$FFD9  CPU rate (SAM R1)      - slow/fast, needed to find the CPU slot
//
// GIME memory slots run at a fixed ~3.58 MHz. Counting from the falling edge of E:
//   fast (1.79 MHz): video, CPU                 -> CPU slot = E high
//   slow (0.89 MHz): video, idle, video, CPU    -> CPU slot = E high and Q low
// i.e. the CPU slot is always the one that ends at E's falling edge.
//
// All shadow registers are write-only (reads come from the GIME as normal) and are
// cleared by /RESET, so the machine starts as a plain 512K CoCo 3 (bank 0).
// Tie EN2M low (solder jumper JP1) to force bank 0 permanently = 512K mode.

module dat2m (
    input  wire [15:0] A,       // CPU address bus
    input  wire D0, D1, D3, D6, D7,   // CPU data bits we need
    input  wire RW,             // 1 = read, 0 = write
    input  wire E,              // 6809 E clock (GCLK1)
    input  wire Q,              // 6809 Q clock
    input  wire RESETn,         // CPU /RESET (GCLR)
    input  wire EN2M,           // 1 = 2 MB mode, 0 = force bank 0
    output wire [1:0] BANK      // A20:A19 to the memory board
);
    reg [1:0] mmu [0:15];       // {task, A15:A13} -> D7:D6
    reg       mmuen, mc3, tsk, fast;
    reg [1:0] vbank;

    wire wr    = ~RW;
    wire is_ffa = (A[15:4] == 12'hFFA);

    integer i;
    always @(negedge E or negedge RESETn) begin
        if (!RESETn) begin
            for (i = 0; i < 16; i = i + 1) mmu[i] <= 2'b00;
            mmuen <= 1'b0; mc3 <= 1'b0; tsk <= 1'b0; fast <= 1'b0; vbank <= 2'b00;
        end else if (wr) begin
            if (is_ffa)             mmu[A[3:0]] <= {D7, D6};
            if (A == 16'hFF90)      begin mmuen <= D6; mc3 <= D3; end
            if (A == 16'hFF91)      tsk   <= D0;
            if (A == 16'hFF9B)      vbank <= {D1, D0};
            if (A == 16'hFFD8)      fast  <= 1'b0;
            if (A == 16'hFFD9)      fast  <= 1'b1;
        end
    end

    wire cpu_slot = fast ? E : (E & ~Q);
    wire fexx     = (A[15:8] == 8'hFE);
    wire [1:0] cpu_bank = (~mmuen | (mc3 & fexx)) ? 2'b00 : mmu[{tsk, A[15:13]}];

    assign BANK = EN2M ? (cpu_slot ? cpu_bank : vbank) : 2'b00;
endmodule
