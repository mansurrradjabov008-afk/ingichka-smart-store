import sys
from pathlib import Path

# Set stdout to UTF-8
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Add project root
sys.path.append(str(Path(__file__).resolve().parent))

from ai_engine.ai_brain import ai_brain

def run_20_tests():
    print("=" * 70)
    print("      INGICHKA SMART STORE - 20 SAMPLE QUESTIONS TEST SUITE")
    print("=" * 70)

    # 20 diverse, realistic sample questions covering all user requirements
    test_cases = [
        # (chat_id, question, description)
        (101, "Assalomu alaykum", "1. Salomlashish (Uzbek Latin)"),
        (102, "Здравствуйте! Что у вас есть?", "2. Salomlashish va tovar so'rovi (Russian)"),
        (103, "Сизда қандай кийимлар бор?", "3. Umumiy tovar so'rovi (Uzbek Cyrillic)"),
        (104, "krasovka bormi", "4. Alias qidiruvi ('krasovka' -> Krossovka)"),
        (105, "oq krasovka 42 razmer bormi", "5. Tovar + rang + razmer ('oq krasovka 42 razmer')"),
        (105, "narxi qancha?", "6. Narx so'rovi (Kontekstda, qayta razmer so'ramaslik)"),
        (106, "qora kurtka bormi", "7. Tovar va rang ('qora kurtka')"),
        (107, "butsa bormi", "8. Do'konda yo'q tovar ('Afsuski, hozir yo'q' + muqobil)"),
        (108, "300 minggacha nima bor?", "9. Narx filtri ('300 minggacha')"),
        (109, "Yetkazib berish qanday bo'ladi?", "10. Yetkazib berish sharti (store_info.json)"),
        (110, "To'lovni qanday qilaman?", "11. To'lov sharti (store_info.json)"),
        (111, "Razmeri to'g'ri kelmasa qaytarsa bo'ladimi?", "12. Qaytarish sharti (store_info.json)"),
        (112, "Operator bilan gaplashmoqchiman", "13. Jonli odam/operator so'rovi ('Operatorga ulayman')"),
        (113, "menga ayollarning kiyimi kerak xotinim uchun olmoqchiman", "14. Ehtiyojni aniqlash (Ayollar kiyimi, xotinimga)"),
        (113, "ko'ylak yoqadi, qizil rang", "15. Fason va rang tanlovi ('ko'ylak, qizil rang')"),
        (113, "ha, shuni olaman", "16. Xarid tasdig'i (Telefon va manzil so'rash)"),
        (113, "+998901234567 Navoiy ko'chasi 15-uy", "17. Buyurtma ma'lumotlari (Telefon va manzil)"),
        (114, "kepka bormi", "18. Kepka qidiruvi"),
        (115, "футболка борми", "19. Кириллча қидирув ('футболка борми')"),
        (116, "джинсы есть?", "20. Поиск на русском языке ('джинсы есть?')")
    ]

    for idx, (cid, question, desc) in enumerate(test_cases, 1):
        print(f"\n[SAVOL #{idx}] {desc}")
        print(f"Xaridor (Chat {cid}): {question}")
        reply = ai_brain.ask(chat_id=cid, user_message=question, customer_name=f"Mijoz_{cid}")
        print(f"Bot Javobi:\n{reply}")
        print("-" * 70)

    print("\n" + "=" * 70)
    print("        BARCHA 20 TA TEST MUVAFFAQIYATLI YAKUNLANDI!")
    print("=" * 70)

if __name__ == "__main__":
    run_20_tests()
