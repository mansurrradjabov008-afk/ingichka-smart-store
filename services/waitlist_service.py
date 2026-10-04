"""
services/waitlist_service.py
Task 2 & Rule 4: Waitlist management for sold-out products.
Saves {chat_id, product_id, created_at} to data/waitlist.json (no duplicates).
Uses atomic writes with concurrency lock.
"""

import os
import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional

from utils.file_utils import atomic_write_json

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
WAITLIST_FILE = DATA_DIR / "waitlist.json"

class WaitlistService:
    """Kutilayotgan tovarlar (Waitlist) xizmati"""

    @classmethod
    def _load_waitlist(cls) -> List[Dict[str, Any]]:
        """data/waitlist.json faylidan o'qish"""
        if not WAITLIST_FILE.exists():
            return []
        try:
            with open(WAITLIST_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    return data
        except Exception:
            pass
        return []

    @classmethod
    def add_to_waitlist(cls, chat_id: int, product_id: int) -> bool:
        """
        Xaridorni tovar bo'yicha kutilayotganlar ro'yxatiga qo'shish.
        No duplicates: Agar chat_id va product_id juftligi allaqachon mavjud bo'lsa, qayta qo'shilmaydi.
        """
        waitlist = cls._load_waitlist()
        
        # Dublikat tekshiruvi
        for item in waitlist:
            if item.get("chat_id") == chat_id and item.get("product_id") == product_id:
                return False  # Already in waitlist

        new_entry = {
            "chat_id": chat_id,
            "product_id": product_id,
            "created_at": datetime.now().isoformat()
        }
        waitlist.append(new_entry)
        
        # Atomik yozish (Rule 4)
        atomic_write_json(str(WAITLIST_FILE), waitlist, indent=2)
        return True

    @classmethod
    def get_waitlist_for_product(cls, product_id: int) -> List[Dict[str, Any]]:
        """Muayyan tovar bo'yicha kutayotgan xaridorlar ro'yxatini olish"""
        waitlist = cls._load_waitlist()
        return [item for item in waitlist if item.get("product_id") == product_id]

    @classmethod
    def clear_product_waitlist(cls, product_id: int) -> List[Dict[str, Any]]:
        """
        Tovar omborga kelganda (restock), unga navbatda turgan barcha xaridorlarni
        qaytarib, fayldan o'chirish (atomik).
        """
        waitlist = cls._load_waitlist()
        notified = []
        remaining = []

        for item in waitlist:
            if item.get("product_id") == product_id:
                notified.append(item)
            else:
                remaining.append(item)

        if notified:
            atomic_write_json(str(WAITLIST_FILE), remaining, indent=2)

        return notified

    @classmethod
    def is_user_waiting(cls, chat_id: int, product_id: int) -> bool:
        """Foydalanuvchi ushbu tovar uchun ro'yxatda bormi?"""
        waitlist = cls._load_waitlist()
        return any(i.get("chat_id") == chat_id and i.get("product_id") == product_id for i in waitlist)
