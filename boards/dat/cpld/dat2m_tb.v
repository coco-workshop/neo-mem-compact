`timescale 1ns/1ps
// Testbench: drives 6809-style E/Q bus cycles and checks BANK in every GIME slot.
module dat2m_tb;
    reg [15:0] A = 16'hFFFF; reg [7:0] D = 8'h00;
    reg RW = 1, E = 0, Q = 0, RESETn = 0, EN2M = 1;
    wire [1:0] BANK;
    dat2m dut(.A(A), .D0(D[0]), .D1(D[1]), .D3(D[3]), .D6(D[6]), .D7(D[7]),
              .RW(RW), .E(E), .Q(Q), .RESETn(RESETn), .EN2M(EN2M), .BANK(BANK));

    integer errors = 0, checks = 0;
    reg fast = 0;                      // what the CoCo is really running at
    localparam TICK = 34.92;           // 1/28.636 MHz

    task check(input [1:0] want, input [8*48-1:0] what);
        begin
            if (want !== 2'bxx) checks = checks + 1;
            if (want !== 2'bxx && BANK !== want) begin
                errors = errors + 1;
                $display("FAIL t=%0t %0s: BANK=%b want %b (A=%h fast=%0d E=%b Q=%b)", $time, what, BANK, want, A, fast, E, Q);
            end
        end
    endtask

    // One CPU cycle starting at E falling edge. Address/data set early in the cycle.
    // Samples BANK in the middle of each GIME slot (where /RAS would fall, ~2 ticks in)
    // and compares with the expected video and CPU bank.
    task cycle(input [15:0] addr, input rw, input [7:0] data, input [1:0] want_vid, input [1:0] want_cpu);
        integer half;
        begin
            half = fast ? 8 : 16;      // ticks per E half-period
            // E falls (previous cycle ends): new address appears shortly after
            E = 0; #(TICK*1); A = addr; RW = rw; D = data;
            if (fast) begin
                // slot 0: video (E low)
                #(TICK*1); check(want_vid, "fast video slot");
                #(TICK*2); Q = 1;                 // Q rises at tick 4
                #(TICK*4); E = 1;                 // E rises at tick 8 -> CPU slot
                #(TICK*2); check(want_cpu, "fast CPU slot (Q high)");
                #(TICK*2); Q = 0;                 // Q falls at tick 12
                #(TICK*2); check(want_cpu, "fast CPU slot (Q low)");
                #(TICK*2);
            end else begin
                #(TICK*1); check(want_vid, "slow video slot 1");
                #(TICK*6); Q = 1;                 // Q rises at tick 8 (idle slot)
                #(TICK*8); E = 1;                 // E rises at tick 16 -> video slot 2
                #(TICK*2); check(want_vid, "slow video slot 2");
                #(TICK*6); Q = 0;                 // Q falls at tick 24 -> CPU slot
                #(TICK*2); check(want_cpu, "slow CPU slot");
                #(TICK*6);
            end
        end
    endtask

    task wr(input [15:0] addr, input [7:0] data);
        begin cycle(addr, 0, data, 2'bxx, 2'bxx); end
    endtask

    initial begin
        // reset with clocks running
        repeat (3) begin #(TICK*16) E = ~E; end
        E = 0; RESETn = 1;

        // 1. after reset: everything is bank 0
        cycle(16'h4000, 1, 0, 2'b00, 2'b00);
        // 2. MMU still off: writing bank bits doesn't affect CPU accesses
        wr(16'hFFA2, 8'hC5);                       // block reg 2 (task 0, $4000) <- bank 3
        cycle(16'h4000, 1, 0, 2'b00, 2'b00);
        // 3. MMU on
        wr(16'hFF90, 8'h40);
        cycle(16'h4000, 1, 0, 2'b00, 2'b11);       // $4000-$5FFF -> bank 3
        cycle(16'h5FFF, 0, 8'hAA, 2'b00, 2'b11);   // writes too
        cycle(16'h2000, 1, 0, 2'b00, 2'b00);       // other block still 0
        // 4. video bank register
        wr(16'hFF9B, 8'hFE);                       // bits 1:0 = 2
        cycle(16'h4000, 1, 0, 2'b10, 2'b11);
        // 5. task 1
        wr(16'hFFAA, 8'h7F);                       // task1 reg 2 <- bank 1
        cycle(16'h4000, 1, 0, 2'b10, 2'b11);       // still task 0
        wr(16'hFF91, 8'h01);
        cycle(16'h4000, 1, 0, 2'b10, 2'b01);
        wr(16'hFF91, 8'h00);
        cycle(16'h4000, 1, 0, 2'b10, 2'b11);
        // 6. all 16 registers independent
        begin : allregs
            integer r;
            for (r = 0; r < 16; r = r + 1) wr(16'hFFA0 + r, {r[1:0], 6'h3F});
            for (r = 0; r < 8; r = r + 1) cycle({r[2:0], 13'h0123}, 1, 0, 2'b10, r[1:0]);
            wr(16'hFF91, 8'h01);
            for (r = 8; r < 16; r = r + 1) cycle({r[2:0], 13'h0123}, 1, 0, 2'b10, r[1:0]);
            wr(16'hFF91, 8'h00);
            wr(16'hFFA2, 8'hC5);                   // restore block reg 2 -> bank 3
        end
        // 7. constant page $FExx (MC3) forces bank 0 only when MC3 = 1
        wr(16'hFFA7, 8'hC0);                       // $E000-$FFFF task0 -> bank 3
        cycle(16'hFE10, 1, 0, 2'b10, 2'b11);       // MC3=0: follows MMU
        wr(16'hFF90, 8'h48);                       // MMU on + MC3
        cycle(16'hFE10, 1, 0, 2'b10, 2'b00);
        cycle(16'hE010, 1, 0, 2'b10, 2'b11);
        cycle(16'hFD10, 1, 0, 2'b10, 2'b11);
        // 8. reads of register addresses change nothing
        cycle(16'hFFA7, 1, 8'h00, 2'b10, 2'b11);
        cycle(16'hE010, 1, 0, 2'b10, 2'b11);
        // 9. fast mode: write $FFD9, real clock changes after this cycle
        wr(16'hFFD9, 8'h00); fast = 1;
        cycle(16'h4000, 1, 0, 2'b10, 2'b11);
        cycle(16'h7000, 1, 0, 2'b10, 2'b11);       // task0 reg 3 was set to bank 3 in step 6
        wr(16'hFFD8, 8'h00); fast = 0;
        cycle(16'h4000, 1, 0, 2'b10, 2'b11);
        // 10. MMU off again -> bank 0 for CPU, video bank unaffected
        wr(16'hFF90, 8'h00);
        cycle(16'h4000, 1, 0, 2'b10, 2'b00);
        // 11. 512K jumper
        wr(16'hFF90, 8'h40); EN2M = 0;
        cycle(16'h4000, 1, 0, 2'b00, 2'b00);
        EN2M = 1;
        cycle(16'h4000, 1, 0, 2'b10, 2'b11);
        // 12. reset clears everything
        RESETn = 0; #(TICK*4); RESETn = 1;
        cycle(16'h4000, 1, 0, 2'b00, 2'b00);

        $display("%0d checks, %0d errors", checks, errors);
        if (errors == 0) $display("ALL TESTS PASSED");
        $finish;
    end
endmodule
