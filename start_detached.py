import subprocess
import sys
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
supervisor_py = BASE_DIR / "bot_supervisor.py"

# CREATE_NO_WINDOW creates a hidden console process that runs in background
CREATE_NO_WINDOW = 0x08000000

proc = subprocess.Popen(
    [sys.executable, str(supervisor_py)],
    cwd=str(BASE_DIR),
    creationflags=CREATE_NO_WINDOW
)

print(f"Bot supervisori mustaqil fon rejimida ishga tushirildi! PID: {proc.pid}")
