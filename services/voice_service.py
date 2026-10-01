import os
import asyncio
import logging
from pathlib import Path
from typing import Optional
import edge_tts

logger = logging.getLogger(__name__)

AUDIO_DIR = Path(__file__).resolve().parent.parent / "media" / "voice_notes"
AUDIO_DIR.mkdir(parents=True, exist_ok=True)

class VoiceService:
    """
    15 yillik samimiy o'zbek sotuvchi ovozi (Neural Text-to-Speech).
    uz-UZ-SardorNeural (Erkak kishi, do'kondor samimiy ovozi)
    uz-UZ-MadinaNeural (Ayol kishi, xushmuomala ovoz)
    """

    VOICE_FEMALE = "uz-UZ-MadinaNeural"
    VOICE_MALE = "uz-UZ-SardorNeural"

    @staticmethod
    def _clean_for_speech(text: str) -> str:
        """Ovozli xabar uchun matnni toza, jonli va ravon inson nutqi holatiga keltirish"""
        import re
        t = text
        # Texnik belgilar va qavslar ichidagi so'zlarni moslash
        t = t.replace("(Waterproof)", "suv o'tkazmaydigan")
        t = t.replace("(Kapushonka)", "kapushonli")
        t = re.sub(r"[*_`#~\[\]\(\)>]", " ", t)
        t = re.sub(r"https?://\S+", "", t)
        t = re.sub(r"#\d+", "", t)
        # Emojilarni tozalash
        t = re.sub(r"[\U00010000-\U0010ffff]", "", t)
        # Qisqartmalarni to'liq so'z qilish
        t = re.sub(r"\bsm\b", " santimetr", t)
        t = re.sub(r"\bming\b", " ming so'm", t)
        # Ortiqcha bo'shliqlarni yo'qotish
        t = re.sub(r"\s+", " ", t).strip()

        # Agar matn juda uzun bo'lsa, eng ma'noli 320-380 belgida jumlani tugallash
        if len(t) > 380:
            slice_t = t[:380]
            last_punct = max(slice_t.rfind("."), slice_t.rfind("!"), slice_t.rfind("?"))
            if last_punct > 150:
                t = slice_t[:last_punct + 1]
            else:
                t = slice_t + "!"
        return t

    @classmethod
    async def text_to_speech(cls, text: str, filename_prefix: str = "voice", voice: str = VOICE_FEMALE) -> Optional[str]:
        """Matnni o'zbekcha real yoqimli, chaqqon qiz bola ovoziga (Madina) aylantirish"""
        try:
            clean_text = cls._clean_for_speech(text)
            if not clean_text:
                clean_text = "Voy, assalomu alaykum! Xush kelibsiz! Sizga qanday yordam bera olaman?"

            out_path = AUDIO_DIR / f"{filename_prefix}_{os.getpid()}_{asyncio.get_event_loop().time():.0f}.mp3"
            
            # rate=+18% va pitch=+2Hz: real inson kabi chaqqon, mehmondo'st, quvnoq va jonli qiz ovozi!
            communicate = edge_tts.Communicate(clean_text, voice=voice, rate="+18%", pitch="+2Hz")
            await communicate.save(str(out_path))
            return str(out_path)
        except Exception as e:
            logger.error(f"TTS ovoz yaratishda xatolik: {e}")
            return None
