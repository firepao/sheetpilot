@echo off
setlocal
cd /d "%~dp0..\.."
set "PYTHON_EXE=%PYTHON_EXE%"
if "%PYTHON_EXE%"=="" set "PYTHON_EXE=python"
%PYTHON_EXE% -m pip install playwright tzdata
if errorlevel 1 exit /b %ERRORLEVEL%
echo Share batch dependencies installed.
pause
