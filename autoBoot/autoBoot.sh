#!/bin/bash
# ------------------------------------------------------------------
#                          SPEX ROVER 2025
# ------------------------------------------------------------------
# Purpose  : Autorun ROS on startup
# ------------------------------------------------------------------

source venv/bin/activate

dir=$(pwd)
#export PYTHONPATH="$dir/install/"

python3 autoBoot.py