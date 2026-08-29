@echo off
REM One command to run the integration's tests. Home Assistant is needed because
REM half the point is proving the integration still loads against a real one.
REM
REM `py -3` picks the newest Python installed, and pip then resolves the newest
REM Home Assistant that Python supports - so a newer Python tests against a newer
REM Home Assistant. The suite prints which version it actually ran against; read
REM that line rather than assuming.
setlocal
if not exist .venv (
  set "PY=py -3"
  py -3 -c "" >nul 2>&1 || set "PY=python"
  echo Creating .venv and installing Home Assistant ^(a few minutes, once^)...
  call :make || exit /b 1
)
.venv\Scripts\python -m tests.test_integration
exit /b %errorlevel%

REM A half-built .venv is worse than none: the next run would skip creation and
REM fail somewhere less obvious. Remove it and report instead.
:make
%PY% -m venv .venv || goto :broken
.venv\Scripts\pip install --quiet --disable-pip-version-check homeassistant || goto :broken
exit /b 0
:broken
rmdir /s /q .venv 2>nul
echo Could not build the test environment. Is Python 3.11 or newer installed and on PATH?
exit /b 1
