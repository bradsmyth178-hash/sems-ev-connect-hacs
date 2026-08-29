#!/usr/bin/env sh
# One command to run the integration's tests. Home Assistant is needed because
# half the point is proving the integration still loads against a real one.
#
# pip resolves the newest Home Assistant the interpreter supports, so a newer
# Python tests against a newer Home Assistant. The suite prints which version it
# actually ran against - read that line, do not assume.
set -e
if [ ! -d .venv ]; then
  PY=
  for v in 3.14 3.13 3.12 3.11; do
    if [ -z "$PY" ] && command -v "python$v" >/dev/null 2>&1; then PY="python$v"; fi
  done
  [ -n "$PY" ] || PY=python3
  echo "Creating .venv with $PY and installing Home Assistant (a few minutes, once)..."
  "$PY" -m venv .venv || { rm -rf .venv; echo "Could not build the test environment. Is Python 3.11 or newer installed?"; exit 1; }
  .venv/bin/pip install --quiet --disable-pip-version-check homeassistant || { rm -rf .venv; echo "Could not install Home Assistant."; exit 1; }
fi
.venv/bin/python -m tests.test_integration
