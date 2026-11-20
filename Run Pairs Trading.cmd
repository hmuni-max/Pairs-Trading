@echo off
setlocal
pushd "%~dp0"
set "PAIR_PY=python"
if exist ".venv\Scripts\python.exe" set "PAIR_PY=.venv\Scripts\python.exe"
"%PAIR_PY%" -B pairs_trading.py %*
set "PAIR_EXIT=%errorlevel%"
if "%~1"=="" pause
popd
exit /b %PAIR_EXIT%
