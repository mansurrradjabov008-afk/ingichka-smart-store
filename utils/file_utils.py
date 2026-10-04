"""
utils/file_utils.py
Rule 4: Write data files atomically (write temp file, then rename). Use a lock for concurrent access.
"""

import os
import json
import tempfile
import threading
from typing import Any, Optional

_FILE_LOCK = threading.RLock()

def atomic_write_text(filepath: str, content: str, encoding: str = "utf-8") -> str:
    """
    Atomically write text content to a file:
    1. Acquire thread lock.
    2. Write to a temporary file in the same directory.
    3. Flush and sync to disk.
    4. Atomically replace the destination file.
    """
    with _FILE_LOCK:
        target_path = os.path.abspath(filepath)
        dir_name = os.path.dirname(target_path)
        os.makedirs(dir_name, exist_ok=True)

        temp_fd, temp_path = tempfile.mkstemp(dir=dir_name, prefix=".tmp_atom_", text=True)
        try:
            with open(temp_fd, "w", encoding=encoding) as f:
                f.write(content)
                f.flush()
                os.fsync(f.fileno())
            os.replace(temp_path, target_path)
            return target_path
        except Exception:
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except Exception:
                    pass
            raise

def atomic_write_json(filepath: str, data: Any, indent: int = 2, encoding: str = "utf-8") -> str:
    """Atomically serialize and write JSON data to file."""
    content = json.dumps(data, indent=indent, ensure_ascii=False)
    return atomic_write_text(filepath, content, encoding=encoding)

def atomic_write_binary(filepath: str, save_func) -> str:
    """
    Atomically save binary data using a custom save callback (e.g. openpyxl Workbook.save).
    save_func(temp_path) is called, then temp_path is atomically moved to filepath.
    """
    with _FILE_LOCK:
        target_path = os.path.abspath(filepath)
        dir_name = os.path.dirname(target_path)
        os.makedirs(dir_name, exist_ok=True)

        temp_fd, temp_path = tempfile.mkstemp(dir=dir_name, prefix=".tmp_bin_")
        os.close(temp_fd)
        try:
            save_func(temp_path)
            os.replace(temp_path, target_path)
            return target_path
        except Exception:
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except Exception:
                    pass
            raise
