#!/bin/sh
# Run this on the machine that has the 5080. Do not open the pipeline.
cd "$(dirname "$0")"
python3 -m pip install -q -r requirements.txt
exec python3 floor.py
