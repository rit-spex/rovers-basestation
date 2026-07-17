#!/bin/bash
# ------------------------------------------------------------------
#                          SPEX ROVER 2026
# ------------------------------------------------------------------
# file name     : auto_boot.sh
# purpose       : activate the venv and run the basestation; called
#                 by the systemd service or desktop entry
# created on    : 7/12/2026 - Ryan
# last modified : 7/12/2026 - Ryan
# ------------------------------------------------------------------
set -e
cd "$(dirname "${BASH_SOURCE[0]}")/.."
source .venv/bin/activate
exec python3 -m basestation
