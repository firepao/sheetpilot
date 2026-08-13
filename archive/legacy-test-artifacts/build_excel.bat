@echo off
setlocal enabledelayedexpansion
set FILE=D:\bitexcel\SheetPilot\tests\data\result\UV_DEMO_I3_dirty_orders_result.xlsx

echo Step 1: Set headers for CleaningDetail sheet
officecli set "%FILE%" "/CleaningDetail/A1" --prop value="OriginalRow" --prop bold=true
officecli set "%FILE%" "/CleaningDetail/B1" --prop value="OrderID" --prop bold=true
officecli set "%FILE%" "/CleaningDetail/C1" --prop value="Date" --prop bold=true
officecli set "%FILE%" "/CleaningDetail/D1" --prop value="City" --prop bold=true
officecli set "%FILE%" "/CleaningDetail/E1" --prop value="Channel" --prop bold=true
officecli set "%FILE%" "/CleaningDetail/F1" --prop value="Category" --prop bold=true
officecli set "%FILE%" "/CleaningDetail/G1" --prop value="Sales" --prop bold=true
officecli set "%FILE%" "/CleaningDetail/H1" --prop value="Cost" --prop bold=true
officecli set "%FILE%" "/CleaningDetail/I1" --prop value="DeliveryTime" --prop bold=true
officecli set "%FILE%" "/CleaningDetail/J1" --prop value="IsReturn" --prop bold=true
officecli set "%FILE%" "/CleaningDetail/K1" --prop value="Rating" --prop bold=true
officecli set "%FILE%" "/CleaningDetail/L1" --prop value="Status" --prop bold=true
officecli set "%FILE%" "/CleaningDetail/M1" --prop value="Issue" --prop bold=true
officecli set "%FILE%" "/CleaningDetail/N1" --prop value="StdCity" --prop bold=true
officecli set "%FILE%" "/CleaningDetail/O1" --prop value="StdChannel" --prop bold=true
officecli set "%FILE%" "/CleaningDetail/P1" --prop value="StdCategory" --prop bold=true
officecli set "%FILE%" "/CleaningDetail/Q1" --prop value="ProfitMargin" --prop bold=true
officecli set "%FILE%" "/CleaningDetail/R1" --prop value="Profit" --prop bold=true

echo Step 2: Set column widths
officecli set "%FILE%" "/CleaningDetail/col[A]" --prop width=10
officecli set "%FILE%" "/CleaningDetail/col[B]" --prop width=12
officecli set "%FILE%" "/CleaningDetail/col[C]" --prop width=12
officecli set "%FILE%" "/CleaningDetail/col[D]" --prop width=10
officecli set "%FILE%" "/CleaningDetail/col[E]" --prop width=12
officecli set "%FILE%" "/CleaningDetail/col[F]" --prop width=10
officecli set "%FILE%" "/CleaningDetail/col[G]" --prop width=12
officecli set "%FILE%" "/CleaningDetail/col[H]" --prop width=12
officecli set "%FILE%" "/CleaningDetail/col[I]" --prop width=12
officecli set "%FILE%" "/CleaningDetail/col[J]" --prop width=10
officecli set "%FILE%" "/CleaningDetail/col[K]" --prop width=8
officecli set "%FILE%" "/CleaningDetail/col[L]" --prop width=10
officecli set "%FILE%" "/CleaningDetail/col[M]" --prop width=20
officecli set "%FILE%" "/CleaningDetail/col[N]" --prop width=12
officecli set "%FILE%" "/CleaningDetail/col[O]" --prop width=12
officecli set "%FILE%" "/CleaningDetail/col[P]" --prop width=12
officecli set "%FILE%" "/CleaningDetail/col[Q]" --prop width=10
officecli set "%FILE%" "/CleaningDetail/col[R]" --prop width=12

echo Step 3: Set BusinessOverview headers
officecli set "%FILE%" "/BusinessOverview/A1" --prop value="KPI" --prop bold=true
officecli set "%FILE%" "/BusinessOverview/B1" --prop value="Value" --prop bold=true
officecli set "%FILE%" "/BusinessOverview/D1" --prop value="Monthly Summary" --prop bold=true
officecli set "%FILE%" "/BusinessOverview/E1" --prop value="Month" --prop bold=true
officecli set "%FILE%" "/BusinessOverview/F1" --prop value="Sales" --prop bold=true
officecli set "%FILE%" "/BusinessOverview/G1" --prop value="Orders" --prop bold=true
officecli set "%FILE%" "/BusinessOverview/J1" --prop value="City Summary" --prop bold=true
officecli set "%FILE%" "/BusinessOverview/K1" --prop value="City" --prop bold=true
officecli set "%FILE%" "/BusinessOverview/L1" --prop value="Sales" --prop bold=true
officecli set "%FILE%" "/BusinessOverview/M1" --prop value="Orders" --prop bold=true
officecli set "%FILE%" "/BusinessOverview/N1" --prop value="AvgProfit" --prop bold=true

echo Step 4: Set Validation headers
officecli set "%FILE%" "/Validation/A1" --prop value="Check Item" --prop bold=true
officecli set "%FILE%" "/Validation/B1" --prop value="Expected" --prop bold=true
officecli set "%FILE%" "/Validation/C1" --prop value="Actual" --prop bold=true
officecli set "%FILE%" "/Validation/D1" --prop value="Pass" --prop bold=true

echo Done with headers
pause
