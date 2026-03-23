$env:PYTHONPATH = "$PWD"
& .venv\Scripts\Activate.ps1
python scripts\seed_demo_user.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }