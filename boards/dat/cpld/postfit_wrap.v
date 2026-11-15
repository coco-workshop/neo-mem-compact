// Maps the testbench's dat2m ports onto the fitted dat2m_top (post-fit simulation only).
module dat2m(input [15:0] A, input D0,D1,D3,D6,D7, input RW, input E, input Q, input RESETn, input EN2M, output [1:0] BANK);
  dat2m_top u(.A0(A[0]),.A1(A[1]),.A2(A[2]),.A3(A[3]),.A4(A[4]),.A5(A[5]),.A6(A[6]),.A7(A[7]),.A8(A[8]),.A9(A[9]),.A10(A[10]),.A11(A[11]),.A12(A[12]),.A13(A[13]),.A14(A[14]),.A15(A[15]),
    .D0(D0),.D1(D1),.D3(D3),.D6(D6),.D7(D7),.RW(RW),.ECLK(E),.QCLK(Q),.RESETn(RESETn),.EN2M(EN2M),.BANK0(BANK[0]),.BANK1(BANK[1]));
endmodule
