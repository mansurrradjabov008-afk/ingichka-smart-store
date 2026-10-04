"""
utils/logger.py
Rule 5: Log errors to bot.log with chat_id and a short reason.
"""

import os
import logging
from pathlib import Path
from datetime import datetime
from typing import Any, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BOT_LOG_FILE = PROJECT_ROOT / "bot.log"

def log_bot_error(chat_id: Any, reason: str, exc: Optional[Exception] = None) -> str:
    """
    Log an error with chat_id and short reason to bot.log and root logger.
    Format: YYYY-MM-DD HH:MM:SS - [Chat <chat_id>] - ERROR - <reason>
    """
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cid_str = str(chat_id) if chat_id is not None else "SYSTEM"
    clean_reason = reason.strip().replace("\n", " ")
    
    log_line = f"{now_str} - [Chat {cid_str}] - ERROR - {clean_reason}"
    if exc:
        log_line += f" | Exception: {type(exc).__name__}: {str(exc)}"

    # 1. Write to standard logger
    logging.getLogger("bot").error(log_line)

    # 2. Append directly to bot.log in project root
    try:
        with open(BOT_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(log_line + "\n")
    except Exception as e:
        logging.getLogger("bot").error(f"Failed to write to bot.log: {e}")

    return log_line
