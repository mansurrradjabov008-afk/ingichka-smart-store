import sys
import os
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from ai_engine.ai_brain import AIBrain
from ai_engine.sales_agent import sales_agent

def run_tests():
    print("=" * 60)
    print("TESTING CONVERSATIONAL INTELLIGENCE & 0-REPETITION")
    print("=" * 60)

    # 1. Test offline tool agent fallback
    b = AIBrain()
    b.gemini_api_key = None
    b.groq_api_key = ''
    b.openai_api_key = ''

    cid = 1001
    print("\n--- Test 1: Offline Tool Agent Fallback ---")
    
    r1 = b.ask(cid, "men uglimga krasovka olmoqchi edim,menga krasovkalarizni kursata olasizmi")
    print("User: men uglimga krasovka olmoqchi edim,menga krasovkalarizni kursata olasizmi")
    print(f"Bot: {r1}")
    assert "krossovka" in r1.lower() or "380" in r1, "Should present krossovka"
    assert "barcha turdagi" not in r1, "Must not contain repetitive fallback"

    r2 = b.ask(cid, "menga krasovka kerak")
    print("\nUser: menga krasovka kerak")
    print(f"Bot: {r2}")
    assert "krossovka" in r2.lower() or "380" in r2 or "katalogimiz" in r2.lower(), "Should acknowledge krasovka or deduplicate"
    assert "barcha turdagi" not in r2, "Must not contain repetitive fallback"

    r3 = b.ask(cid, "kitob bormi")
    print("\nUser: kitob bormi")
    print(f"Bot: {r3}")
    assert "kitob" in r3.lower() and ("mavjud emas" in r3.lower() or "yo'q" in r3.lower()), "Must state kitob is out of stock"
    assert "barcha turdagi" not in r3, "Must not contain repetitive fallback"

    r4 = b.ask(cid, "45-razmer bormi")
    print("\nUser: 45-razmer bormi")
    print(f"Bot: {r4}")
    assert ("45" in r4 and "faqat" in r4.lower()) or "krossovka" in r4.lower(), "Must acknowledge krossovka or size"
    assert "barcha turdagi" not in r4, "Must not contain repetitive fallback"

    # 2. Test SalesAgent process_message fallback
    print("\n--- Test 2: SalesAgent process_message Fallback ---")
    sa_r1 = sales_agent.process_message("men uglimga krasovka olmoqchi edim,menga krasovkalarizni kursata olasizmi", 2001)
    print(f"SA 1: {sa_r1}")
    assert "krossovka" in sa_r1.lower() or "380" in sa_r1, "Should match krossovka"
    assert "barcha turdagi" not in sa_r1, "Must not contain repetitive fallback"

    sa_r2 = sales_agent.process_message("menga krasovka kerak", 2002)
    print(f"SA 2: {sa_r2}")
    assert "krossovka" in sa_r2.lower() or "380" in sa_r2, "Should match krossovka"
    assert "barcha turdagi" not in sa_r2, "Must not contain repetitive fallback"

    sa_r3 = sales_agent.process_message("kitob bormi", 2003)
    print(f"SA 3: {sa_r3}")
    assert "kitob" in sa_r3.lower() and ("mavjud emas" in sa_r3.lower() or "yo'q" in sa_r3.lower()), "Must state kitob is out of stock"
    assert "barcha turdagi" not in sa_r3, "Must not contain repetitive fallback"

    print("\n" + "=" * 60)
    print("ALL CONVERSATIONAL INTELLIGENCE TESTS PASSED 100%!")
    print("=" * 60)

if __name__ == "__main__":
    run_tests()
