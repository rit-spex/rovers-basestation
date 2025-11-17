#!/bin/bash
# ------------------------------------------------------------------
#                          SPEX ROVER 2025
# ------------------------------------------------------------------
# Purpose  : Autorun ROS on startup
# ------------------------------------------------------------------

source .venv/bin/activate

dir=$(pwd)
#export PYTHONPATH="$dir/install/"

cd xbee

#python3 autoBoot.py
cd ~/rovers-basestation/xbee
python3 Xbee.py