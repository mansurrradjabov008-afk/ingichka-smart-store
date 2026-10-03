import subprocess
import sys
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
supervisor_py = BASE_DIR / "bot_supervisor.py"
pythonw_exe = Path(r"C:\Users\BRand\AppData\Local\Programs\Python\Python311\pythonw.exe")
if not pythonw_exe.exists():
    pythonw_exe = sys.executable

DETACHED_PROCESS = 0x00000008
CREATE_NEW_PROCESS_GROUP = 0x00000200

proc = subprocess.Popen(
    [str(pythonw_exe), str(supervisor_py)],
    cwd=str(BASE_DIR),
    creationflags=DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP,
    close_fds=True
)

print(f"Bot supervisori mustaqil fon rejimida ishga tushirildi! PID: {proc.pid}")
