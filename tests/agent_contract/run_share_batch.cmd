@echo off
setlocal
cd /d "%~dp0..\.."
set "PYTHONPATH=src;."
set "PYTHON_EXE=%PYTHON_EXE%"
if "%PYTHON_EXE%"=="" set "PYTHON_EXE=python"
if not "%~1"=="" goto run
if not exist "tests\agent_contract\share_links.txt" (
  echo Missing tests\agent_contract\share_links.txt
  echo Copy tests\agent_contract\share_links.example.txt to that path and fill in your links.
  pause
  exit /b 2
)
%PYTHON_EXE% -m tests.agent_contract.evaluation.run_share_batch --links tests/agent_contract/share_links.txt --scenario-root tests/agent_contract/scenarios --evidence-root tests/agent_contract/evidence --output-dir tests/agent_contract/results/share-batch --user-data-dir tests/agent_contract/browser-profile --executable-path "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe" --workers 1
goto done
:run
%PYTHON_EXE% -m tests.agent_contract.evaluation.run_share_batch %*
:done
set "CODE=%ERRORLEVEL%"
echo.
if not "%CODE%"=="0" echo Batch failed. See the output directory for acquisition-summary.json and batch-summary.json.
pause
exit /b %CODE%
