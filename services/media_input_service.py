"""
services/media_input_service.py
TASK 6: Voice and photo input. Strictly follows RULES.md.

1. Voice/audio message:
   - Check duration limit: <= 60 seconds, otherwise ask for shorter one.
   - Download, transcribe (Gemini or Whisper, Uzbek supported).
   - Show nothing extra, then process the text exactly like a normal message.
   - If transcription is empty/unclear, ask the customer to repeat or type.
2. Photo:
   - Send to the vision model with a strict prompt:
     describe type, color, style as JSON {is_product, type, color, style, keywords}.
   - Call search_products with those keywords and show closest in-stock matches with photos.
   - Say "o'xshash mahsulotlar" (similar), never claim it is the same item.
3. If photo is unrelated or unreadable, say so politely.
4. Delete temp media files after processing.
5. Handle API failure with a fallback message.
"""

import os
import re
import json
import base64
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple, Callable
import requests

from config import GEMINI_API_KEY, _FALLBACK_GEMINI_KEY
from database.db_manager import DatabaseManager
from services.catalog_service import load_products

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TEMP_MEDIA_DIR = PROJECT_ROOT / "media" / "temp_media"
TEMP_MEDIA_DIR.mkdir(parents=True, exist_ok=True)

# Max voice duration in seconds
MAX_VOICE_DURATION_SECONDS = 60

# Standart xabarlar
VOICE_TOO_LONG_MSG = "Ovozli xabar davomiyligi 60 soniyadan oshmasligi kerak. Iltimos, qisqaroq qilib qayta yuboring yoki matn ko'rinishida yozing."
VOICE_EMPTY_TRANSCRIPT_MSG = "Ovozli xabarni aniqlab bo'lmadi. Iltimos, qaytadan aniqroq gapiring yoki xabarni matn ko'rinishida yozing."
VOICE_API_FALLBACK_MSG = "Ovozli xabarni qayta ishlashda vaqtinchalik xatolik yuz berdi. Iltimos, birozdan so'ng qayta urinib ko'ring yoki xabarni matn ko'rinishida yozing."

PHOTO_UNRELATED_MSG = "Kechirasiz, yuborilgan rasmda do'konimizga oid kiyim yoki poyabzal aniqlanmadi (yoki rasm noaniq). Iltimos, aniqroq kiyim yoki poyabzal rasmini yuboring."
PHOTO_NO_STOCK_MSG = "Kechirasiz, ushbu modelga o'xshash mahsulotlarimiz ayni paytda omborda qolmagan. Boshqa sara modellarimizni katalogdan ko'rishingiz mumkin."
PHOTO_API_FALLBACK_MSG = "Rasmni tahlil qilishda vaqtinchalik xatolik yuz berdi. Iltimos, birozdan so'ng qayta urinib ko'ring yoki tovar nomini matn ko'rinishida yozing."
PHOTO_SIMILAR_INTRO = "Siz yuborgan rasmga o'xshash do'konimizdagi mahsulotlar:"


class MediaInputService:
    """Ovoz va rasm orqali qidiruv va muloqot xizmati"""

    # ---------------------------------------------------------
    # 1. Voice Duration Validation & Transcription
    # ---------------------------------------------------------
    @classmethod
    def validate_voice_duration(cls, duration_seconds: float) -> Tuple[bool, Optional[str]]:
        """
        Ovozli xabar davomiyligini tekshirish (Limit: 60 sekund).
        """
        if duration_seconds > MAX_VOICE_DURATION_SECONDS:
            return False, VOICE_TOO_LONG_MSG
        return True, None

    @classmethod
    def transcribe_audio(
        cls,
        audio_bytes: bytes,
        mime_type: str = "audio/ogg",
        transcriber_fn: Optional[Callable[[bytes, str], str]] = None
    ) -> Dict[str, Any]:
        """
        Ovozli xabarni transkripsiya qilish (Gemini yoki Whisper, o'zbek tili qo'llab-quvvatlanadi).
        """
        # Maxsus / Mock qilingan funksiya bo'lsa (Unit testlar uchun)
        if transcriber_fn is not None:
            try:
                transcript = transcriber_fn(audio_bytes, mime_type)
                if not transcript or not transcript.strip():
                    return {
                        "success": False,
                        "error_type": "empty_transcript",
                        "message": VOICE_EMPTY_TRANSCRIPT_MSG
                    }
                return {
                    "success": True,
                    "transcript": transcript.strip()
                }
            except Exception as e:
                logger.error(f"Mock transcriber error: {e}")
                return {
                    "success": False,
                    "error_type": "api_timeout",
                    "message": VOICE_API_FALLBACK_MSG
                }

        # Haqiqiy Gemini Multimodal Audio Transcription API
        if not GEMINI_API_KEY:
            return {
                "success": False,
                "error_type": "api_timeout",
                "message": VOICE_API_FALLBACK_MSG
            }

        # MIME turini tozalash (Gemini faqat standart toza formatlarni qabul qiladi)
        clean_mime = "audio/ogg"
        if mime_type:
            clean_mime = mime_type.split(";")[0].strip().lower()
        if clean_mime not in ["audio/ogg", "audio/mp3", "audio/wav", "audio/m4a", "audio/aac", "audio/flac"]:
            clean_mime = "audio/ogg"

        audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")
        prompt = (
            "Ushbu ovozli xabarni toza, aniq o'zbek tilida so'zma-so'z matnga aylantir (transcribe). "
            "Faqat aytilgan gapni yoz, hech qanday qo'shimcha so'z, izoh yoki kirish qo'shma."
        )
        payload = {
            "contents": [{
                "parts": [
                    {"text": prompt},
                    {
                        "inlineData": {
                            "mimeType": clean_mime,
                            "data": audio_b64
                        }
                    }
                ]
            }],
            "generationConfig": {"temperature": 0.1, "maxOutputTokens": 300}
        }

        # Eng chaqqon va barqaror modellarni ketma-ket sinash (gemini-3.5-flash-lite eng birinchi!)
        active_models = ["gemini-3.5-flash-lite", "gemini-3.6-flash"]
        keys_to_try = [GEMINI_API_KEY]
        if _FALLBACK_GEMINI_KEY and _FALLBACK_GEMINI_KEY not in keys_to_try:
            keys_to_try.append(_FALLBACK_GEMINI_KEY)

        for api_k in keys_to_try:
            if not api_k:
                continue
            for model in active_models:
                try:
                    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_k}"
                    resp = requests.post(url, json=payload, timeout=7.5)
                    if resp.status_code == 200:
                        data = resp.json()
                        candidates = data.get("candidates", [])
                        if candidates and "content" in candidates[0]:
                            parts = candidates[0]["content"].get("parts", [])
                            if parts and "text" in parts[0]:
                                text = parts[0]["text"].strip()
                                if text:
                                    logger.info(f"Ovoz transkripsiyasi muvaffaqiyatli ({model}): {text[:50]}...")
                                    return {"success": True, "transcript": text}
                    elif resp.status_code == 401:
                        logger.warning(f"Voice transcribe 401 unauthorized on key ...{api_k[-4:]} with {model}")
                        break
                    else:
                        logger.warning(f"Voice transcribe status {resp.status_code} with {model}: {resp.text[:120]}")
                except Exception as e:
                    logger.warning(f"Voice transcribe timeout/error with {model}: {e}")

        # Agar transkripsiya bo'sh yoki xato bo'lsa
        return {
            "success": False,
            "error_type": "empty_transcript",
            "message": VOICE_EMPTY_TRANSCRIPT_MSG
        }

    # ---------------------------------------------------------
    # 2. Photo Vision Analysis & Similar Products Search
    # ---------------------------------------------------------
    @classmethod
    def analyze_photo_with_vision(
        cls,
        image_bytes: bytes,
        mime_type: str = "image/jpeg",
        vision_fn: Optional[Callable[[bytes, str], Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Rasmni Vision model orqali tahlil qilish va qat'iy JSON formatida
        {is_product, type, color, style, keywords} olish.
        """
        # Maxsus / Mock qilingan funksiya bo'lsa (Unit testlar uchun)
        if vision_fn is not None:
            try:
                analysis = vision_fn(image_bytes, mime_type)
                return cls._evaluate_vision_analysis(analysis)
            except Exception as e:
                logger.error(f"Mock vision error: {e}")
                return {
                    "success": False,
                    "error_type": "api_timeout",
                    "message": PHOTO_API_FALLBACK_MSG
                }

        if not GEMINI_API_KEY:
            return {
                "success": False,
                "error_type": "api_timeout",
                "message": PHOTO_API_FALLBACK_MSG
            }

        image_b64 = base64.b64encode(image_bytes).decode("utf-8")
        prompt = (
            "Siz kiyim va poyabzal do'konining professional vision tahlilchisisiz.\n"
            "Ushbu rasmni sinchiklab tahlil qiling va FAQAT quyidagi JSON formatida javob bering:\n"
            "{\n"
            '  "is_product": true,\n'
            '  "type": "krossovka / kurtka / futbolka / shim / poyabzal / ko\'ylak / xudi",\n'
            '  "color": "oq / qora / ko\'k / qizil / kulrang / etc.",\n'
            '  "style": "sport / klassik / casual / etc.",\n'
            '  "keywords": ["krossovka", "oq", "sport"]\n'
            "}\n\n"
            "QAT'IY QOIDALAR:\n"
            "- Agar rasmda kiyim-kechak, poyabzal yoki aksessuar bo'lmasa, yoki rasm noaniq/tushunarsiz bo'lsa:\n"
            '  {"is_product": false, "type": null, "color": null, "style": null, "keywords": []}\n'
            "- Hech qanday markdown (```json) yoki qo'shimcha so'z yozmang, faqat toza JSON."
        )

        payload = {
            "contents": [{
                "parts": [
                    {"text": prompt},
                    {
                        "inlineData": {
                            "mimeType": mime_type,
                            "data": image_b64
                        }
                    }
                ]
            }],
            "generationConfig": {"temperature": 0.1, "maxOutputTokens": 300}
        }

        for model in ["gemini-flash-lite-latest", "gemini-3.5-flash-lite", "gemini-3.5-flash", "gemini-3.6-flash", "gemini-2.0-flash", "gemini-1.5-flash"]:
            try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GEMINI_API_KEY}"
                resp = requests.post(url, json=payload, timeout=12)
                if resp.status_code == 200:
                    data = resp.json()
                    candidates = data.get("candidates", [])
                    if candidates and "content" in candidates[0]:
                        parts = candidates[0]["content"].get("parts", [])
                        if parts and "text" in parts[0]:
                            text = parts[0]["text"].strip()
                            clean_json = re.sub(r"^```(?:json)?|```$", "", text, flags=re.MULTILINE).strip()
                            parsed = json.loads(clean_json)
                            return cls._evaluate_vision_analysis(parsed)
            except Exception as e:
                logger.error(f"Vision analyze error with {model}: {e}")

        return {
            "success": False,
            "error_type": "api_timeout",
            "message": PHOTO_API_FALLBACK_MSG
        }

    @classmethod
    def _evaluate_vision_analysis(cls, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Vision natijasini tekshirish va do'kondan o'xshash tovarlarni qidirish"""
        if not isinstance(analysis, dict):
            return {
                "success": False,
                "error_type": "non_product",
                "message": PHOTO_UNRELATED_MSG
            }

        is_product = analysis.get("is_product", False)
        prod_type = analysis.get("type")

        # 3. Agar rasm kiyimga aloqasiz yoki noaniq bo'lsa
        if not is_product or not prod_type:
            return {
                "success": False,
                "error_type": "non_product",
                "message": PHOTO_UNRELATED_MSG
            }

        # Do'kon omboridan eng yaqin o'xshash tovarlarni qidirish (Faqat in-stock)
        matches = cls.find_similar_in_stock_products(analysis)
        if not matches:
            return {
                "success": True,
                "is_product": True,
                "analysis": analysis,
                "products": [],
                "message": PHOTO_NO_STOCK_MSG
            }

        # 2. Qoida: "o'xshash mahsulotlar" deb ko'rsatish (Never claim it is the same item)
        return {
            "success": True,
            "is_product": True,
            "analysis": analysis,
            "products": matches[:3],
            "intro_message": PHOTO_SIMILAR_INTRO
        }

    # ---------------------------------------------------------
    # 3. Ombor ichidan o'xshash tovarlarni saralash (Stock > 0)
    # ---------------------------------------------------------
    @classmethod
    def find_similar_in_stock_products(cls, analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Vision tahlilidan kelgan type, color, style, keywords bo'yicha
        faqat omborda bor (stock > 0) eng o'xshash tovarlarni topish.
        """
        all_prods = DatabaseManager.get_products(in_stock_only=True)
        if not all_prods:
            all_prods = [p for p in load_products() if p.get("stock", 0) > 0]

        prod_type = (analysis.get("type") or "").lower()
        color = (analysis.get("color") or "").lower()
        style = (analysis.get("style") or "").lower()
        keywords = [k.lower() for k in analysis.get("keywords", []) if k]

        # Sinov / qidiruv kalit so'zlari
        search_terms = set(keywords)
        if prod_type:
            search_terms.add(prod_type)
        if color:
            search_terms.add(color)
        if style:
            search_terms.add(style)

        scored_candidates = []
        for p in all_prods:
            name = p.get("name", "").lower()
            cat = p.get("category", "").lower()
            p_color = p.get("color", "").lower() if isinstance(p.get("color"), str) else " ".join(p.get("colors", [])).lower()
            desc = p.get("description", "").lower()

            target_blob = f"{name} {cat} {p_color} {desc}"

            score = 0
            # Mahsulot turi mosligi (eng muhim)
            if prod_type and (prod_type in target_blob or (prod_type.rstrip("lar") in target_blob)):
                score += 10
            # Rangi mosligi
            if color and color in target_blob:
                score += 5
            # Kalit so'zlar mosligi
            for kw in search_terms:
                if kw in target_blob:
                    score += 2

            if score > 0:
                scored_candidates.append((score, p))

        # Ballar bo'yicha yuqoridan pastga saralash
        scored_candidates.sort(key=lambda x: x[0], reverse=True)
        return [c[1] for c in scored_candidates]

    # ---------------------------------------------------------
    # 4. Vaqtinchalik fayllarni xavfsiz tozalash (Cleanup)
    # ---------------------------------------------------------
    @classmethod
    def cleanup_temp_file(cls, file_path: Optional[str]) -> None:
        """Vaqtinchalik media faylni o'chirish"""
        if not file_path:
            return
        try:
            p = Path(file_path)
            if p.exists() and p.is_file():
                p.unlink(missing_ok=True)
        except Exception as e:
            logger.warning(f"Temp file cleanup failed: {e}")
