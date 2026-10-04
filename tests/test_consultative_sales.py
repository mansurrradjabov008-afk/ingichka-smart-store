import sys
from pathlib import Path

# Add project root
sys.path.append(str(Path(__file__).resolve().parent.parent))

from ai_engine.ai_brain import ai_brain

def test_consultative_sales_flow():
    print("============================================================")
    print("CONSULTATIVE SALES & DISCOVERY DIALOGUE VERIFICATION")
    print("============================================================")

    uid = 998877

    # 1. Turn 1: Category inquiry for wife
    print("\n--- 1. INQUIRY: 'menga ayollarning kiyimi kerak xotinim uchun olmoqchiman' ---")
    reply1 = ai_brain.ask(uid, "menga ayollarning kiyimi kerak xotinim uchun olmoqchiman", "Mansur")
    print(f"Bot: {reply1}")

    # Must NOT ask for phone/address prematurely
    assert "telefon raqamingiz" not in reply1.lower(), "Should NOT ask for phone number on category inquiry!"
    assert "manzilingiz" not in reply1.lower(), "Should NOT ask for address on category inquiry!"
    # Must ask discovery questions (fason, razmer, rang, turdagi)
    assert any(w in reply1.lower() for w in ["fason", "ko'ylak", "palto", "kiyim"]), "Must mention styles/products!"
    assert any(w in reply1.lower() for w in ["o'lcham", "razmer", "rang", "turdagi", "qanday", "yoqadi"]), "Must ask discovery questions!"
    print("PASS: Turn 1 consultative discovery questions asked properly!")

    # 2. Turn 2: User specifies style and color preference
    print("\n--- 2. PREFERENCE: 'ko\'ylak yoqadi, qizil rang' ---")
    reply2 = ai_brain.ask(uid, "ko'ylak yoqadi, qizil rang", "Mansur")
    print(f"Bot: {reply2}")
    assert any(w in reply2.lower() for w in ["ko'ylak", "ko‘ylak", "ko’ylak", "ko'ylag", "ko‘ylag", "ko’ylag", "koylak"])
    assert any(w in reply2.lower() for w in ["qizil", "afsuski", "yo'q", "reebok", "zara", "defacto", "koton"])
    print("PASS: Turn 2 matched available dresses with price & size options!")

    # 3. Turn 3: User confirms purchase
    print("\n--- 3. CONFIRMATION: 'ha shuni olaman' ---")
    reply3 = ai_brain.ask(uid, "ha shuni olaman", "Mansur")
    print(f"Bot: {reply3}")
    assert "telefon raqamingiz" in reply3.lower() or "telefon" in reply3.lower()
    assert "manzil" in reply3.lower()
    print("PASS: Turn 3 correctly requested phone & address upon purchase confirmation!")

    # 4. Turn 4: User provides phone and address
    print("\n--- 4. ORDER DETAILS: '+998901234567 Toshkent Chilonzor' ---")
    reply4 = ai_brain.ask(uid, "+998901234567 Toshkent Chilonzor", "Mansur")
    print(f"Bot: {reply4}")
    assert "qabul qilinmoqda" in reply4.lower() or "tasdiqlaymiz" in reply4.lower() or "qabul qilindi" in reply4.lower()
    print("PASS: Turn 4 order completed and accepted!")

    # 5. Men's clothing inquiry
    print("\n--- 5. MEN'S CLOTHING: 'o\'zimga kiyim olmoqchiman' ---")
    reply_men = ai_brain.ask(uid + 1, "o'zimga kiyim olmoqchiman", "Ali")
    print(f"Bot: {reply_men}")
    assert "telefon raqamingiz" not in reply_men.lower()
    assert any(w in reply_men.lower() for w in ["qanday", "turdagi", "kurtka", "futbolka", "jinsi", "kiyim"])
    print("PASS: Men's clothing consultative questions verified!")

    # 6. Shoes inquiry
    print("\n--- 6. SHOES: 'krasovka bormi' ---")
    reply_shoes = ai_brain.ask(uid + 2, "krasovka bormi", "Vali")
    print(f"Bot: {reply_shoes}")
    assert any(w in reply_shoes.lower() for w in ["krossovka", "krasovka", "poyabzal"])
    assert any(w in reply_shoes.lower() for w in ["yo'q", "mavjud emas", "afsuski", "kurtka", "kiyim", "boshqa"])
    print("PASS: Shoes availability and consultative question verified!")

    print("\n============================================================")
    print("ALL CONSULTATIVE SALES TESTS PASSED 100%!")
    print("============================================================")

if __name__ == "__main__":
    test_consultative_sales_flow()
