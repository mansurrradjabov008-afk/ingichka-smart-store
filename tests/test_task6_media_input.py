"""
tests/test_task6_media_input.py
Comprehensive test suite for TASK 6: Voice and photo input.
Strictly follows RULES.md.

Tests (Mocking the APIs):
1. empty transcript:
   Transcription is empty or whitespace -> asks customer to repeat or type.
2. long voice:
   Voice duration > 60 seconds -> rejects with polite limit message.
   Voice duration <= 60 seconds -> passes validation.
3. sneaker photo -> sneaker results:
   Photo of sneakers analyzed by vision model -> returns closest in-stock sneaker matches
   with caption "o'xshash mahsulotlar" (never claims it is the exact same product).
4. non-product photo:
   Unrelated/unreadable photo -> politely informs customer that clothing/shoes were not detected.
5. API timeout:
   Voice API timeout / Vision API timeout -> safe fallback messages without crashing.
6. Temp media cleanup:
   Ensures temporary media files are safely cleaned up from disk.
7. Out of stock photo:
   If matching items have 0 stock -> informs customer politely.
"""

import sys
import os
import unittest
from pathlib import Path
import tempfile

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(PROJECT_ROOT))

from database.db_manager import DatabaseManager, init_db
from services.media_input_service import (
    MediaInputService,
    MAX_VOICE_DURATION_SECONDS,
    VOICE_TOO_LONG_MSG,
    VOICE_EMPTY_TRANSCRIPT_MSG,
    VOICE_API_FALLBACK_MSG,
    PHOTO_UNRELATED_MSG,
    PHOTO_NO_STOCK_MSG,
    PHOTO_API_FALLBACK_MSG,
    PHOTO_SIMILAR_INTRO,
    TEMP_MEDIA_DIR
)


class TestTask6MediaInput(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()

    # -------------------------------------------------------------
    # 1. Voice Duration Tests (Limit: 60 seconds)
    # -------------------------------------------------------------
    def test_voice_duration_under_or_equal_60s(self):
        """Voice <= 60s is valid"""
        ok, msg = MediaInputService.validate_voice_duration(15.5)
        self.assertTrue(ok)
        self.assertIsNone(msg)

        ok, msg = MediaInputService.validate_voice_duration(60.0)
        self.assertTrue(ok)
        self.assertIsNone(msg)

    def test_long_voice_over_60s_rejected(self):
        """Voice > 60s is rejected with polite limit message"""
        ok, msg = MediaInputService.validate_voice_duration(61.0)
        self.assertFalse(ok)
        self.assertEqual(msg, VOICE_TOO_LONG_MSG)

        ok, msg = MediaInputService.validate_voice_duration(120.5)
        self.assertFalse(ok)
        self.assertEqual(msg, VOICE_TOO_LONG_MSG)

    # -------------------------------------------------------------
    # 2. Voice Transcription: Empty Transcript
    # -------------------------------------------------------------
    def test_empty_transcript_handling(self):
        """Empty transcript returns polite message asking to repeat or type"""
        dummy_audio = b"\x00" * 100

        # Mock transcriber returning empty string
        mock_empty = lambda b, m: ""
        res = MediaInputService.transcribe_audio(dummy_audio, transcriber_fn=mock_empty)
        self.assertFalse(res["success"])
        self.assertEqual(res["error_type"], "empty_transcript")
        self.assertEqual(res["message"], VOICE_EMPTY_TRANSCRIPT_MSG)

        # Mock transcriber returning only whitespace
        mock_whitespace = lambda b, m: "   \n\t  "
        res2 = MediaInputService.transcribe_audio(dummy_audio, transcriber_fn=mock_whitespace)
        self.assertFalse(res2["success"])
        self.assertEqual(res2["error_type"], "empty_transcript")
        self.assertEqual(res2["message"], VOICE_EMPTY_TRANSCRIPT_MSG)

    def test_valid_voice_transcript(self):
        """Valid voice returns transcribed text cleanly"""
        dummy_audio = b"\x00" * 100
        mock_valid = lambda b, m: "Oq krossovka bormi?"
        res = MediaInputService.transcribe_audio(dummy_audio, transcriber_fn=mock_valid)
        self.assertTrue(res["success"])
        self.assertEqual(res["transcript"], "Oq krossovka bormi?")

    # -------------------------------------------------------------
    # 3. Photo Input: Sneaker Photo -> Sneaker Results
    # -------------------------------------------------------------
    def test_sneaker_photo_to_sneaker_results(self):
        """
        Sneaker photo analyzed by vision model returns in-stock sneaker matches
        with intro 'o'xshash mahsulotlar' and never claims identical match.
        """
        dummy_img = b"\xFF\xD8\xFF\xE0" + b"\x00" * 50

        # Mock vision model returning sneaker JSON analysis
        mock_sneaker_vision = lambda b, m: {
            "is_product": True,
            "type": "krossovka",
            "color": "oq",
            "style": "sport",
            "keywords": ["krossovka", "oq", "sport"]
        }

        res = MediaInputService.analyze_photo_with_vision(dummy_img, vision_fn=mock_sneaker_vision)
        self.assertTrue(res["success"])
        self.assertTrue(res["is_product"])
        self.assertIn("products", res)
        self.assertGreater(len(res["products"]), 0)

        # Max 3 products
        self.assertLessEqual(len(res["products"]), 3)

        # Verify all returned products are in-stock
        for p in res["products"]:
            stock_qty = p.get("stock_quantity") or p.get("stock") or 0
            self.assertGreater(stock_qty, 0)

        # Verify intro phrase adheres strictly to 'o'xshash mahsulotlar' (similar items)
        self.assertEqual(res.get("intro_message"), PHOTO_SIMILAR_INTRO)
        self.assertIn("o'xshash", res.get("intro_message").lower())

    # -------------------------------------------------------------
    # 4. Photo Input: Non-Product / Unrelated Photo
    # -------------------------------------------------------------
    def test_non_product_photo_handling(self):
        """
        Non-product or unreadable photo returns polite unrelated message.
        """
        dummy_img = b"\xFF\xD8\xFF\xE0" + b"\x00" * 50

        mock_non_product = lambda b, m: {
            "is_product": False,
            "type": None,
            "color": None,
            "style": None,
            "keywords": []
        }

        res = MediaInputService.analyze_photo_with_vision(dummy_img, vision_fn=mock_non_product)
        self.assertFalse(res["success"])
        self.assertEqual(res["error_type"], "non_product")
        self.assertEqual(res["message"], PHOTO_UNRELATED_MSG)

    def test_invalid_structure_from_vision(self):
        """If vision returns non-dict or malformed object, handles gracefully"""
        dummy_img = b"\xFF\xD8\xFF\xE0" + b"\x00" * 50
        mock_malformed = lambda b, m: "not a dict"

        res = MediaInputService.analyze_photo_with_vision(dummy_img, vision_fn=mock_malformed)
        self.assertFalse(res["success"])
        self.assertEqual(res["error_type"], "non_product")
        self.assertEqual(res["message"], PHOTO_UNRELATED_MSG)

    # -------------------------------------------------------------
    # 5. API Timeout & Failure Fallbacks
    # -------------------------------------------------------------
    def test_voice_api_timeout(self):
        """Voice API timeout returns safe fallback without crash"""
        dummy_audio = b"\x00" * 100

        def mock_timeout(b, m):
            raise TimeoutError("Connection to voice recognition timed out")

        res = MediaInputService.transcribe_audio(dummy_audio, transcriber_fn=mock_timeout)
        self.assertFalse(res["success"])
        self.assertEqual(res["error_type"], "api_timeout")
        self.assertEqual(res["message"], VOICE_API_FALLBACK_MSG)

    def test_photo_api_timeout(self):
        """Photo Vision API timeout returns safe fallback without crash"""
        dummy_img = b"\xFF\xD8\xFF\xE0" + b"\x00" * 50

        def mock_timeout(b, m):
            raise TimeoutError("Connection to vision model timed out")

        res = MediaInputService.analyze_photo_with_vision(dummy_img, vision_fn=mock_timeout)
        self.assertFalse(res["success"])
        self.assertEqual(res["error_type"], "api_timeout")
        self.assertEqual(res["message"], PHOTO_API_FALLBACK_MSG)

    # -------------------------------------------------------------
    # 6. Temp Media File Cleanup
    # -------------------------------------------------------------
    def test_temp_media_cleanup(self):
        """Temporary media files on disk are safely deleted"""
        temp_file = TEMP_MEDIA_DIR / "test_temp_audio_123.ogg"
        with open(temp_file, "wb") as f:
            f.write(b"TEMP_AUDIO_DATA_FOR_CLEANUP_TEST")

        self.assertTrue(temp_file.exists())
        MediaInputService.cleanup_temp_file(str(temp_file))
        self.assertFalse(temp_file.exists())

        # Calling cleanup on non-existent file must not crash
        try:
            MediaInputService.cleanup_temp_file(str(TEMP_MEDIA_DIR / "non_existent.ogg"))
            MediaInputService.cleanup_temp_file(None)
        except Exception as e:
            self.fail(f"cleanup_temp_file crashed on missing file: {e}")

    # -------------------------------------------------------------
    # 7. Photo In-Stock vs Out-Of-Stock Handling
    # -------------------------------------------------------------
    def test_photo_when_item_not_in_stock(self):
        """When visual search yields 0 matches in stock, informs customer politely"""
        dummy_img = b"\xFF\xD8\xFF\xE0" + b"\x00" * 50

        mock_rare_item = lambda b, m: {
            "is_product": True,
            "type": "noyob_kosmik_kastyum",
            "color": "kumush",
            "style": "fantastik",
            "keywords": ["noyob_kosmik_kastyum", "kumush"]
        }

        res = MediaInputService.analyze_photo_with_vision(dummy_img, vision_fn=mock_rare_item)
        self.assertTrue(res["success"])
        self.assertEqual(len(res["products"]), 0)
        self.assertEqual(res["message"], PHOTO_NO_STOCK_MSG)


if __name__ == "__main__":
    unittest.main()
