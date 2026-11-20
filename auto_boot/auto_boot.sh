#!/bin/bash
# ------------------------------------------------------------------
#                          SPEX ROVER 2026
# ------------------------------------------------------------------
# file name     : auto_boot.sh
# purpose       : run the boot helper from the venv: wait until the
#                 rover XBee answers a ping, then start the
#                 basestation headless. Called by the systemd
#                 service or desktop entry.
# created on    : 7/12/2026 - Ryan
# last modified : 11/20/2026 - fixed to use auto_boot.py + venv
# ------------------------------------------------------------------
set -e

cd "$(dirname "${BASH_SOURCE[0]}")/.."

# Keep a ROS-sourced shell's PYTHONPATH from shadowing the local
# basestation package; the venv is self-contained.
unset PYTHONPATH

if [ ! -x .venv/bin/python3 ]; then
    echo "error: .venv not found - run ./auto_boot/setup.sh first" >&2
    exit 1
fi

exec .venv/bin/python3 auto_boot/auto_boot.py "$@"
