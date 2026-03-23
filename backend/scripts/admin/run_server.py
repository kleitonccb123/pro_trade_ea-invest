#!/usr/bin/env python
import sys
import os
import subprocess

# Add backend to path
backend_path = os.path.join(os.path.dirname(__file__), 'backend')
os.chdir(backend_path)
sys.path.insert(0, backend_path)

# Run uvicorn
subprocess.run([sys.executable, '-m', 'uvicorn', 'app.main:app', '--reload', '--host', '0.0.0.0', '--port', '8000'])
