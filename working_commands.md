Initialize: IN;

Command Echo Mode ON/OFF: !CT0; --> Disable Echo Mode // !CT1; --> Enable Echo Mode (Get "C\cr") after each command execution.

Move Relative: PRx,y;

    z.B. PR1500,0; moves 1,5cm in x and 0 in y axis

Draw Circle: CIr;

    z.B. CL1500; draws a circle with 1.5cm radius around the current pos.

Enable Motor: !EM1;

Disable Motor; !EM0;

Pen Up: PU;

Pen Down: PD;

Get Current Pos: !ON0; --> returns Pos of all 3 Axes: z.B.: P19100,9000,0C --> X: 19100 Y: 9000 Z:0

!ON1; --> get X Pos

!ON2; --> get Y Pos

!ON3; --> get Z Pos

Draw Rectangle with 5cm length:

!TS500;PD;PR5000,0;PR0,5000;PR-5000,0;PR0,-5000;PU;!TS0;
