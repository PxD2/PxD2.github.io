# Run this on the machine that has the 5080. Do not open the pipeline.
Set-Location $PSScriptRoot
python -m pip install -q -r requirements.txt
python floor.py
