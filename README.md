# 🏪 Ingichka Baraka Savdo Markazi: AI Sotuvchi va Biznes Menejeri

Telegram kanal va guruhlari, shuningdek shaxsiy profillar uchun mo'ljallangan **15 yillik tajribali sotuvchi psixologiyasiga ega avtonom AI tizimi**.

---

## 🌟 Tizimning Asosiy Imkoniyatlari

1. **15 Yillik Ekspert Sotuvchi Psixologiyasi:**
   * Odamlar uni bot deb o'ylamaydi — xuddi tirik, mehmondo'st o'zbek do'kondoridek gaplashadi.
   * E'tirozlar bilan ishlaydi ("Qimmat ekan" degan mijozga sifat va tekin yetkazishni tushuntirib, savdoni yopadi).
   * Cross-sell (O'rtacha chekni oshirish) qiladi.

2. **Nol Gallutsinatsiya (Zero Hallucination):**
   * Yo'q tovar yoki to'qima narxni aslo aytmaydi.
   * Ombor bilan doimiy real vaqt sinxronizatsiyasi mavjud.

3. **Ingichka bo'ylab Mahalliy Ustunlik:**
   * Ingichka shaharchasi bo'ylab 30-60 daqiqada bepul yetkazib berish va eshik oldida kiyib ko'rib to'lash imkoniyati.

4. **Kassa Hisoboti va AI Maslahatchi:**
   * 1 kunlik, 1 haftalik, 1 oylik va 1 yillik tushum, xarajat, sof foyda va rentabellik hisoboti.
   * Inqiroz signallari (Savdo tushib ketsa, darhol ogohlantiradi).
   * Do'kon egasi uchun savdoni oshirish bo'yicha amaliy maslahatlar.

5. **Ombor Tahlili va Yangi Tovar Tavsiyalari:**
   * Kam qolgan va tugagan tovarlar ro'yxati.
   * Zakaz uchun kerakli sarmoyani oldindan hisoblab berish.
   * Mavsumiy va trend tovarlar bo'yicha tavsiyalar.

6. **Ovoz va Matn orqali yangi tovar qo'shish:**
   * Tovar rasmini tashlab, ovozli qilib aytishingiz bilan AI avtomatik omborga kiritadi.

---

## 🚀 Ishga Tushirish Qo'llanmasi

### 1. Bot Tokenini o'rnatish
`config.py` faylini oching va Telegram [@BotFather](https://t.me/BotFather) dan olgan bot tokeningizni hamda admin ID raqamingizni yozing:
```python
BOT_TOKEN = "SIZNING_BOT_TOKENINGIZ"
ADMIN_TELEGRAM_IDS = [SIZNING_TELEGRAM_ID]
```

### 2. Tizimni Test Qilish (Simulyatsiya)
Barcha sotuv va hisobot jarayonini sinab ko'rish uchun:
```bash
python test_system.py
```

### 3. Telegram Botni Ishga Tushirish
```bash
python bot/bot_app.py
```

---

## 📂 Loyiha Strukturasi
```
ingichka_smart_store/
├── config.py                 # Asosiy sozlamalar va do'kon parametrlari
├── ingichka_store.db         # SQLite ma'lumotlar bazasi
├── database/
│   └── db_manager.py         # Kassa, ombor va mijozlar bazasi operatsiyalari
├── ai_engine/
│   ├── sales_persona.py      # 15 yillik sotuvchi prompti va xulq-atvori
│   └── sales_agent.py        # Sotuv dialogi va intent tahlili
├── services/
│   ├── analytics_advisor.py  # Moliya, foyda, inqiroz va biznes maslahatchi
│   └── inventory_manager.py  # Ombor qoldig'i, zakaz budjeti va trendlar
├── bot/
│   ├── bot_app.py            # Aiogram 3 Telegram bot
│   └── keyboards.py          # Menyular va interaktiv tugmalar
├── data/
│   └── seed_data.py          # Boshlang'ich kiyim va tovarlar bazasi
└── test_system.py            # 100% to'liq tizimli test skripti
```
