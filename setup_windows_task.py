import subprocess
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
RUNNER_BAT = BASE_DIR / "run_bot_silent.bat"

# Create a clean runner bat
pythonw_exe = Path(r"C:\Users\BRand\AppData\Local\Programs\Python\Python311\pythonw.exe")
supervisor_py = BASE_DIR / "bot_supervisor.py"

bat_content = f"""@echo off
cd /d "{BASE_DIR}"
start "" "{pythonw_exe}" "{supervisor_py}"
"""
RUNNER_BAT.write_text(bat_content, encoding="utf-8")
print(f"Created: {RUNNER_BAT}")

# Register with schtasks
cmd = [
    "schtasks", "/create",
    "/tn", "IngichkaBot24_7",
    "/tr", f'"{str(RUNNER_BAT)}"',
    "/sc", "onlogon",
    "/f"
]

res = subprocess.run(cmd, capture_output=True, text=True)
print("Schtasks output:", res.stdout)
if res.stderr:
    print("Schtasks error:", res.stderr)

# Now immediately run the task via schtasks
run_cmd = ["schtasks", "/run", "/tn", "IngichkaBot24_7"]
res_run = subprocess.run(run_cmd, capture_output=True, text=True)
print("Schtasks run output:", res_run.stdout)
