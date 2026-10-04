import os
import sys
import json
import sqlite3
from pathlib import Path

# Add project root to sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT_DIR))

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

PRODUCTS_RAW = [
    {
        "id": 1,
        "sku": "KK-1002",
        "name": "Adidas Printli futbolka Ko'k",
        "category": "Futbolka",
        "brand": "Adidas",
        "size": "XXL",
        "color": "Ko'k",
        "gender": "Bolalar",
        "material": "Paxta 100%",
        "stock": 43,
        "min_stock": 3,
        "cost_price": 121853,
        "sale_price": 200000,
        "supplier": "Guangzhou Trade",
        "incoming_date": "20.07.2026",
        "status": "Mavjud",
        "aliases": ["adidas futbolka", "printli futbolka", "ko'k futbolka", "adidas", "futbolka", "синяя футболка", "футболка адидас", "adidas printli futbolka"]
    },
    {
        "id": 2,
        "sku": "KK-1001",
        "name": "Local Brand UZ Oddiy futbolka Ko'k",
        "category": "Futbolka",
        "brand": "Local Brand UZ",
        "size": "L",
        "color": "Ko'k",
        "gender": "Ayol",
        "material": "Paxta 100%",
        "stock": 23,
        "min_stock": 3,
        "cost_price": 87811,
        "sale_price": 118000,
        "supplier": "Istanbul Import",
        "incoming_date": "23.05.2026",
        "status": "Mavjud",
        "aliases": ["oddiy futbolka", "ayollar futbolkasi", "local brand futbolka", "ko'k futbolka ayollar", "футболка"]
    },
    {
        "id": 3,
        "sku": "KK-1004",
        "name": "Nike Polo futbolka Qizil",
        "category": "Futbolka",
        "brand": "Nike",
        "size": "XXL",
        "color": "Qizil",
        "gender": "Uniseks",
        "material": "Polyester",
        "stock": 28,
        "min_stock": 7,
        "cost_price": 100916,
        "sale_price": 174000,
        "supplier": "Istanbul Textile Co",
        "incoming_date": "04.09.2026",
        "status": "Mavjud",
        "aliases": ["nike polo", "polo futbolka", "qizil futbolka", "nike futbolka", "nike", "polo", "найк поло", "красная футболка"]
    },
    {
        "id": 4,
        "sku": "KK-1003",
        "name": "Reebok Sport futbolka Oq",
        "category": "Futbolka",
        "brand": "Reebok",
        "size": "L",
        "color": "Oq",
        "gender": "Erkak",
        "material": "Paxta 95% + Elastan",
        "stock": 17,
        "min_stock": 7,
        "cost_price": 91390,
        "sale_price": 152000,
        "supplier": "Dubai Fashion Hub",
        "incoming_date": "29.08.2026",
        "status": "Mavjud",
        "aliases": ["reebok futbolka", "oq futbolka", "sport futbolka", "reebok", "белая футболка", "рибок"]
    },
    {
        "id": 5,
        "sku": "KK-1061",
        "name": "Adidas Sport ichki Ko'k",
        "category": "Ichki kiyim",
        "brand": "Adidas",
        "size": "S",
        "color": "Ko'k",
        "gender": "Erkak",
        "material": "Polyester",
        "stock": 28,
        "min_stock": 5,
        "cost_price": 106669,
        "sale_price": 166000,
        "supplier": "Local Factory UZ",
        "incoming_date": "20.07.2026",
        "status": "Mavjud",
        "aliases": ["adidas ichki kiyim", "sport ichki kiyim", "ichki kiyim", "erkaklar ichki kiyimi"]
    },
    {
        "id": 6,
        "sku": "KK-1058",
        "name": "Adidas Sport ichki Qizil",
        "category": "Ichki kiyim",
        "brand": "Adidas",
        "size": "M",
        "color": "Qizil",
        "gender": "Ayol",
        "material": "Polyester",
        "stock": 8,
        "min_stock": 7,
        "cost_price": 148262,
        "sale_price": 251000,
        "supplier": "Dubai Fashion Hub",
        "incoming_date": "13.04.2026",
        "status": "Mavjud",
        "aliases": ["ayollar ichki kiyimi", "adidas ayollar ichki", "qizil ichki kiyim"]
    },
    {
        "id": 7,
        "sku": "KK-1063",
        "name": "Bershka Sport ichki Jigarrang",
        "category": "Ichki kiyim",
        "brand": "Bershka",
        "size": "XL",
        "color": "Jigarrang",
        "gender": "Erkak",
        "material": "Modal",
        "stock": 16,
        "min_stock": 9,
        "cost_price": 112449,
        "sale_price": 192000,
        "supplier": "Toshkent Optom",
        "incoming_date": "14.04.2026",
        "status": "Mavjud",
        "aliases": ["bershka ichki kiyim", "jigarrang ichki kiyim", "bershka"]
    },
    {
        "id": 8,
        "sku": "KK-1060",
        "name": "Defacto Sport ichki Bej",
        "category": "Ichki kiyim",
        "brand": "Defacto",
        "size": "S",
        "color": "Bej",
        "gender": "Ayol",
        "material": "Polyester",
        "stock": 14,
        "min_stock": 10,
        "cost_price": 55543,
        "sale_price": 88000,
        "supplier": "Local Factory UZ",
        "incoming_date": "09.07.2026",
        "status": "Mavjud",
        "aliases": ["defacto ichki kiyim", "bej ichki kiyim", "defacto"]
    },
    {
        "id": 9,
        "sku": "KK-1059",
        "name": "LC Waikiki Briefs Jigarrang",
        "category": "Ichki kiyim",
        "brand": "LC Waikiki",
        "size": "S",
        "color": "Jigarrang",
        "gender": "Erkak",
        "material": "Polyester",
        "stock": 2,
        "min_stock": 3,
        "cost_price": 66747,
        "sale_price": 113000,
        "supplier": "Dubai Fashion Hub",
        "incoming_date": "07.05.2026",
        "status": "Kam qolgan",
        "aliases": ["lc waikiki briefs", "briefs", "trusilar", "waikiki ichki kiyim"]
    },
    {
        "id": 10,
        "sku": "KK-1064",
        "name": "LC Waikiki Termo ichki Ko'k",
        "category": "Ichki kiyim",
        "brand": "LC Waikiki",
        "size": "S",
        "color": "Ko'k",
        "gender": "Ayol",
        "material": "Polyester",
        "stock": 0,
        "min_stock": 7,
        "cost_price": 116987,
        "sale_price": 159000,
        "supplier": "Guangzhou Trade",
        "incoming_date": "09.06.2026",
        "status": "Tugagan",
        "aliases": ["termo ichki kiyim", "lc waikiki termo", "issiq ichki kiyim", "termo"]
    },
    {
        "id": 11,
        "sku": "KK-1062",
        "name": "Pull&Bear Briefs Pushti",
        "category": "Ichki kiyim",
        "brand": "Pull&Bear",
        "size": "XL",
        "color": "Pushti",
        "gender": "Ayol",
        "material": "Paxta",
        "stock": 17,
        "min_stock": 4,
        "cost_price": 66079,
        "sale_price": 96000,
        "supplier": "Moscow Textile",
        "incoming_date": "26.05.2026",
        "status": "Mavjud",
        "aliases": ["pull&bear briefs", "pushti ichki kiyim", "pull and bear"]
    },
    {
        "id": 12,
        "sku": "KK-1022",
        "name": "Adidas Slim fit jinsi Moviy",
        "category": "Jinsi",
        "brand": "Adidas",
        "size": "34",
        "color": "Moviy",
        "gender": "Erkak",
        "material": "Denim 98% + Elastan",
        "stock": 12,
        "min_stock": 8,
        "cost_price": 256066,
        "sale_price": 445000,
        "supplier": "Guangzhou Trade",
        "incoming_date": "19.07.2026",
        "status": "Mavjud",
        "aliases": ["adidas jinsi", "slim fit jinsi", "moviy jinsi", "jinsi", "shim", "джинсы адидас"]
    },
    {
        "id": 13,
        "sku": "KK-1021",
        "name": "Bershka Relaxed jinsi Moviy",
        "category": "Jinsi",
        "brand": "Bershka",
        "size": "36",
        "color": "Moviy",
        "gender": "Uniseks",
        "material": "Denim",
        "stock": 16,
        "min_stock": 5,
        "cost_price": 572159,
        "sale_price": 928000,
        "supplier": "Local Factory UZ",
        "incoming_date": "11.07.2026",
        "status": "Mavjud",
        "aliases": ["bershka jinsi", "relaxed jinsi", "keng jinsi", "bershka jeans"]
    },
    {
        "id": 14,
        "sku": "KK-1023",
        "name": "Defacto Straight jinsi Bordo",
        "category": "Jinsi",
        "brand": "Defacto",
        "size": "36",
        "color": "Bordo",
        "gender": "Uniseks",
        "material": "Denim 98% + Elastan",
        "stock": 5,
        "min_stock": 5,
        "cost_price": 358656,
        "sale_price": 486000,
        "supplier": "Toshkent Optom",
        "incoming_date": "11.05.2026",
        "status": "Kam qolgan",
        "aliases": ["defacto jinsi", "straight jinsi", "bordo jinsi", "to'g'ri jinsi"]
    },
    {
        "id": 15,
        "sku": "KK-1020",
        "name": "Koton Slim fit jinsi Kulrang",
        "category": "Jinsi",
        "brand": "Koton",
        "size": "28",
        "color": "Kulrang",
        "gender": "Erkak",
        "material": "Denim 98% + Elastan",
        "stock": 33,
        "min_stock": 6,
        "cost_price": 523520,
        "sale_price": 836000,
        "supplier": "Dubai Fashion Hub",
        "incoming_date": "09.09.2026",
        "status": "Mavjud",
        "aliases": ["koton jinsi", "kulrang jinsi", "koton slim fit", "koton"]
    },
    {
        "id": 16,
        "sku": "KK-1024",
        "name": "Zara Straight jinsi Moviy",
        "category": "Jinsi",
        "brand": "Zara",
        "size": "32",
        "color": "Moviy",
        "gender": "Ayol",
        "material": "Denim",
        "stock": 14,
        "min_stock": 3,
        "cost_price": 268390,
        "sale_price": 434000,
        "supplier": "Istanbul Textile Co",
        "incoming_date": "21.07.2026",
        "status": "Mavjud",
        "aliases": ["zara jinsi", "ayollar jinsisi", "moviy jinsi ayollar", "zara jeans"]
    },
    {
        "id": 17,
        "sku": "KK-1075",
        "name": "LC Waikiki Snapback Oq",
        "category": "Kepka",
        "brand": "LC Waikiki",
        "size": "One size",
        "color": "Oq",
        "gender": "Ayol",
        "material": "Polyester",
        "stock": 17,
        "min_stock": 7,
        "cost_price": 65751,
        "sale_price": 117000,
        "supplier": "Moscow Textile",
        "incoming_date": "20.06.2026",
        "status": "Mavjud",
        "aliases": ["lc waikiki snapback", "oq kepka", "snapback", "kepka", "baskir", "кепка"]
    },
    {
        "id": 18,
        "sku": "KK-1072",
        "name": "Nike Yozgi kepka Bej",
        "category": "Kepka",
        "brand": "Nike",
        "size": "One size",
        "color": "Bej",
        "gender": "Ayol",
        "material": "Polyester",
        "stock": 46,
        "min_stock": 7,
        "cost_price": 153969,
        "sale_price": 229000,
        "supplier": "Istanbul Import",
        "incoming_date": "29.07.2026",
        "status": "Mavjud",
        "aliases": ["nike kepka", "yozgi kepka", "bej kepka", "nike", "найк кепка"]
    },
    {
        "id": 19,
        "sku": "KK-1073",
        "name": "Pull&Bear Yozgi kepka Kulrang",
        "category": "Kepka",
        "brand": "Pull&Bear",
        "size": "One size",
        "color": "Kulrang",
        "gender": "Ayol",
        "material": "Paxta",
        "stock": 65,
        "min_stock": 10,
        "cost_price": 97517,
        "sale_price": 138000,
        "supplier": "Moscow Textile",
        "incoming_date": "26.07.2026",
        "status": "Mavjud",
        "aliases": ["pull&bear kepka", "kulrang kepka", "pull and bear kepka"]
    },
    {
        "id": 20,
        "sku": "KK-1074",
        "name": "Zara Yozgi kepka Bej",
        "category": "Kepka",
        "brand": "Zara",
        "size": "One size",
        "color": "Bej",
        "gender": "Uniseks",
        "material": "Paxta",
        "stock": 48,
        "min_stock": 7,
        "cost_price": 171230,
        "sale_price": 281000,
        "supplier": "Local Factory UZ",
        "incoming_date": "14.07.2026",
        "status": "Mavjud",
        "aliases": ["zara kepka", "zara yozgi kepka", "bej kepka zara"]
    },
    {
        "id": 21,
        "sku": "KK-1005",
        "name": "Defacto Yozgi ko'ylak Kulrang",
        "category": "Ko'ylak",
        "brand": "Defacto",
        "size": "L",
        "color": "Kulrang",
        "gender": "Uniseks",
        "material": "Linen",
        "stock": 70,
        "min_stock": 4,
        "cost_price": 239725,
        "sale_price": 375000,
        "supplier": "Istanbul Import",
        "incoming_date": "19.08.2026",
        "status": "Mavjud",
        "aliases": ["defacto ko'ylak", "yozgi ko'ylak", "kulrang ko'ylak", "ko'ylak", "koylak", "рубашка", "платье"]
    },
    {
        "id": 22,
        "sku": "KK-1010",
        "name": "Koton Yozgi ko'ylak Jigarrang",
        "category": "Ko'ylak",
        "brand": "Koton",
        "size": "M",
        "color": "Jigarrang",
        "gender": "Erkak",
        "material": "Polyester + Paxta",
        "stock": 3,
        "min_stock": 8,
        "cost_price": 234698,
        "sale_price": 368000,
        "supplier": "Istanbul Textile Co",
        "incoming_date": "17.05.2026",
        "status": "Kam qolgan",
        "aliases": ["koton ko'ylak", "erkaklar ko'ylagi", "jigarrang ko'ylak"]
    },
    {
        "id": 23,
        "sku": "KK-1006",
        "name": "LC Waikiki Katta tugmali ko'ylak Pushti",
        "category": "Ko'ylak",
        "brand": "LC Waikiki",
        "size": "L",
        "color": "Pushti",
        "gender": "Ayol",
        "material": "Polyester + Paxta",
        "stock": 40,
        "min_stock": 8,
        "cost_price": 360325,
        "sale_price": 516000,
        "supplier": "Istanbul Import",
        "incoming_date": "07.05.2026",
        "status": "Mavjud",
        "aliases": ["lc waikiki ko'ylak", "katta tugmali ko'ylak", "pushti ko'ylak", "ayollar ko'ylagi"]
    },
    {
        "id": 24,
        "sku": "KK-1011",
        "name": "Pull&Bear Klassik ko'ylak Bej",
        "category": "Ko'ylak",
        "brand": "Pull&Bear",
        "size": "L",
        "color": "Bej",
        "gender": "Erkak",
        "material": "Paxta",
        "stock": 0,
        "min_stock": 4,
        "cost_price": 194907,
        "sale_price": 324000,
        "supplier": "Istanbul Textile Co",
        "incoming_date": "12.09.2026",
        "status": "Tugagan",
        "aliases": ["pull&bear ko'ylak", "klassik ko'ylak", "bej ko'ylak", "oqshom ko'ylagi"]
    },
    {
        "id": 25,
        "sku": "KK-1008",
        "name": "Puma Ofis ko'ylagi Bej",
        "category": "Ko'ylak",
        "brand": "Puma",
        "size": "XXL",
        "color": "Bej",
        "gender": "Erkak",
        "material": "Paxta",
        "stock": 1,
        "min_stock": 9,
        "cost_price": 183306,
        "sale_price": 273000,
        "supplier": "Dubai Fashion Hub",
        "incoming_date": "02.06.2026",
        "status": "Kam qolgan",
        "aliases": ["puma ko'ylak", "ofis ko'ylagi", "bej ofis ko'ylak", "puma"]
    },
    {
        "id": 26,
        "sku": "KK-1007",
        "name": "Reebok Yozgi ko'ylak Sariq",
        "category": "Ko'ylak",
        "brand": "Reebok",
        "size": "XL",
        "color": "Sariq",
        "gender": "Bolalar",
        "material": "Paxta",
        "stock": 41,
        "min_stock": 7,
        "cost_price": 374622,
        "sale_price": 655000,
        "supplier": "Local Factory UZ",
        "incoming_date": "29.06.2026",
        "status": "Mavjud",
        "aliases": ["reebok ko'ylak", "bolalar ko'ylagi", "sariq ko'ylak", "reebok yozgi"]
    },
    {
        "id": 27,
        "sku": "KK-1009",
        "name": "Zara Denim ko'ylak Qora",
        "category": "Ko'ylak",
        "brand": "Zara",
        "size": "XXL",
        "color": "Qora",
        "gender": "Erkak",
        "material": "Polyester + Paxta",
        "stock": 75,
        "min_stock": 4,
        "cost_price": 303878,
        "sale_price": 461000,
        "supplier": "Local Factory UZ",
        "incoming_date": "29.09.2026",
        "status": "Mavjud",
        "aliases": ["zara ko'ylak", "denim ko'ylak", "qora ko'ylak", "jinsi ko'ylak", "zara black shirt"]
    },
    {
        "id": 28,
        "sku": "KK-1026",
        "name": "Adidas Parka Moviy",
        "category": "Kurtka",
        "brand": "Adidas",
        "size": "L",
        "color": "Moviy",
        "gender": "Ayol",
        "material": "Paxta + Polyester",
        "stock": 7,
        "min_stock": 3,
        "cost_price": 725190,
        "sale_price": 1018000,
        "supplier": "Istanbul Import",
        "incoming_date": "12.04.2026",
        "status": "Mavjud",
        "aliases": ["adidas parka", "parka", "moviy kurtka", "adidas kurtka", "kurtka", "куртка адидас"]
    },
    {
        "id": 29,
        "sku": "KK-1025",
        "name": "H&M Qishki kurtka Pushti",
        "category": "Kurtka",
        "brand": "H&M",
        "size": "M",
        "color": "Pushti",
        "gender": "Uniseks",
        "material": "Polyester",
        "stock": 23,
        "min_stock": 3,
        "cost_price": 467308,
        "sale_price": 625000,
        "supplier": "Moscow Textile",
        "incoming_date": "22.08.2026",
        "status": "Mavjud",
        "aliases": ["h&m kurtka", "qishki kurtka", "pushti kurtka", "h&m", "зимняя куртка"]
    },
    {
        "id": 30,
        "sku": "KK-1027",
        "name": "H&M Qishki kurtka Sariq",
        "category": "Kurtka",
        "brand": "H&M",
        "size": "XXL",
        "color": "Sariq",
        "gender": "Ayol",
        "material": "Polyester",
        "stock": 0,
        "min_stock": 8,
        "cost_price": 1170391,
        "sale_price": 2066000,
        "supplier": "Istanbul Textile Co",
        "incoming_date": "11.04.2026",
        "status": "Tugagan",
        "aliases": ["h&m sariq kurtka", "sariq kurtka", "ayollar qishki kurtkasi"]
    },
    {
        "id": 31,
        "sku": "KK-1028",
        "name": "Zara Yengil kurtka Bordo",
        "category": "Kurtka",
        "brand": "Zara",
        "size": "M",
        "color": "Bordo",
        "gender": "Erkak",
        "material": "Paxta + Polyester",
        "stock": 1,
        "min_stock": 10,
        "cost_price": 716643,
        "sale_price": 1040000,
        "supplier": "Local Factory UZ",
        "incoming_date": "02.08.2026",
        "status": "Kam qolgan",
        "aliases": ["zara kurtka", "yengil kurtka", "bordo kurtka", "zara jacket"]
    },
    {
        "id": 32,
        "sku": "KK-1042",
        "name": "Adidas Yengil palto Moviy",
        "category": "Palto",
        "brand": "Adidas",
        "size": "XL",
        "color": "Moviy",
        "gender": "Erkak",
        "material": "Jun",
        "stock": 4,
        "min_stock": 7,
        "cost_price": 1395038,
        "sale_price": 2041000,
        "supplier": "Local Factory UZ",
        "incoming_date": "08.07.2026",
        "status": "Kam qolgan",
        "aliases": ["adidas palto", "yengil palto", "moviy palto", "palto", "пальто адидас"]
    },
    {
        "id": 33,
        "sku": "KK-1044",
        "name": "Artel Style Klassik palto Ko'k",
        "category": "Palto",
        "brand": "Artel Style",
        "size": "S",
        "color": "Ko'k",
        "gender": "Ayol",
        "material": "Jun",
        "stock": 5,
        "min_stock": 4,
        "cost_price": 1782729,
        "sale_price": 3162000,
        "supplier": "Local Factory UZ",
        "incoming_date": "26.07.2026",
        "status": "Mavjud",
        "aliases": ["artel palto", "klassik palto", "ayollar paltosi", "ko'k palto"]
    },
    {
        "id": 34,
        "sku": "KK-1043",
        "name": "Artel Style Uzun palto Qizil",
        "category": "Palto",
        "brand": "Artel Style",
        "size": "XL",
        "color": "Qizil",
        "gender": "Bolalar",
        "material": "Polyester",
        "stock": 27,
        "min_stock": 3,
        "cost_price": 1333920,
        "sale_price": 1883000,
        "supplier": "Toshkent Optom",
        "incoming_date": "16.04.2026",
        "status": "Mavjud",
        "aliases": ["artel style uzun palto", "uzun palto", "qizil palto", "bolalar paltosi"]
    },
    {
        "id": 35,
        "sku": "KK-1047",
        "name": "Koton Klassik palto Qora",
        "category": "Palto",
        "brand": "Koton",
        "size": "L",
        "color": "Qora",
        "gender": "Bolalar",
        "material": "Polyester",
        "stock": 49,
        "min_stock": 10,
        "cost_price": 920845,
        "sale_price": 1397000,
        "supplier": "Moscow Textile",
        "incoming_date": "19.05.2026",
        "status": "Mavjud",
        "aliases": ["koton palto", "qora palto", "klassik palto qora", "пальто котон"]
    },
    {
        "id": 36,
        "sku": "KK-1046",
        "name": "Local Brand UZ Yengil palto Oq",
        "category": "Palto",
        "brand": "Local Brand UZ",
        "size": "M",
        "color": "Oq",
        "gender": "Uniseks",
        "material": "Cashmere blend",
        "stock": 76,
        "min_stock": 3,
        "cost_price": 1328139,
        "sale_price": 2080000,
        "supplier": "Moscow Textile",
        "incoming_date": "27.06.2026",
        "status": "Mavjud",
        "aliases": ["oq palto", "kashmir palto", "yengil palto oq", "cashmere palto"]
    },
    {
        "id": 37,
        "sku": "KK-1049",
        "name": "Pull&Bear Yengil palto Yashil",
        "category": "Palto",
        "brand": "Pull&Bear",
        "size": "XL",
        "color": "Yashil",
        "gender": "Erkak",
        "material": "Polyester",
        "stock": 3,
        "min_stock": 7,
        "cost_price": 1313742,
        "sale_price": 1891000,
        "supplier": "Dubai Fashion Hub",
        "incoming_date": "21.07.2026",
        "status": "Kam qolgan",
        "aliases": ["pull&bear palto", "yashil palto", "erkaklar paltosi"]
    },
    {
        "id": 38,
        "sku": "KK-1045",
        "name": "Puma Uzun palto Kulrang",
        "category": "Palto",
        "brand": "Puma",
        "size": "S",
        "color": "Kulrang",
        "gender": "Uniseks",
        "material": "Jun",
        "stock": 6,
        "min_stock": 9,
        "cost_price": 1431844,
        "sale_price": 2535000,
        "supplier": "Istanbul Import",
        "incoming_date": "10.09.2026",
        "status": "Kam qolgan",
        "aliases": ["puma palto", "uzun palto kulrang", "puma coat"]
    },
    {
        "id": 39,
        "sku": "KK-1048",
        "name": "Zara Yengil palto Bej",
        "category": "Palto",
        "brand": "Zara",
        "size": "XL",
        "color": "Bej",
        "gender": "Bolalar",
        "material": "Cashmere blend",
        "stock": 46,
        "min_stock": 4,
        "cost_price": 1184954,
        "sale_price": 2062000,
        "supplier": "Istanbul Import",
        "incoming_date": "03.06.2026",
        "status": "Mavjud",
        "aliases": ["zara palto", "bej palto", "zara yengil palto", "пальто зара"]
    },
    {
        "id": 40,
        "sku": "KK-1069",
        "name": "Adidas Ko'rinmas paypoq Bordo",
        "category": "Paypoq",
        "brand": "Adidas",
        "size": "43-46",
        "color": "Bordo",
        "gender": "Bolalar",
        "material": "Synthetics",
        "stock": 68,
        "min_stock": 5,
        "cost_price": 57461,
        "sale_price": 102000,
        "supplier": "Istanbul Import",
        "incoming_date": "24.05.2026",
        "status": "Mavjud",
        "aliases": ["adidas paypoq", "ko'rinmas paypoq", "bordo paypoq", "paypoq", "носки"]
    },
    {
        "id": 41,
        "sku": "KK-1065",
        "name": "Adidas Oddiy paypoq Bordo",
        "category": "Paypoq",
        "brand": "Adidas",
        "size": "39-42",
        "color": "Bordo",
        "gender": "Ayol",
        "material": "Jun",
        "stock": 6,
        "min_stock": 6,
        "cost_price": 32435,
        "sale_price": 49000,
        "supplier": "Toshkent Optom",
        "incoming_date": "17.04.2026",
        "status": "Kam qolgan",
        "aliases": ["oddiy paypoq", "ayollar paypog'i", "adidas paypoq ayollar"]
    },
    {
        "id": 42,
        "sku": "KK-1071",
        "name": "Bershka Ko'rinmas paypoq Yashil",
        "category": "Paypoq",
        "brand": "Bershka",
        "size": "39-42",
        "color": "Yashil",
        "gender": "Bolalar",
        "material": "Jun",
        "stock": 23,
        "min_stock": 6,
        "cost_price": 66363,
        "sale_price": 108000,
        "supplier": "Guangzhou Trade",
        "incoming_date": "02.08.2026",
        "status": "Mavjud",
        "aliases": ["bershka paypoq", "yashil paypoq", "bershka socks"]
    },
    {
        "id": 43,
        "sku": "KK-1066",
        "name": "Defacto Sport paypoq Jigarrang",
        "category": "Paypoq",
        "brand": "Defacto",
        "size": "43-46",
        "color": "Jigarrang",
        "gender": "Uniseks",
        "material": "Jun",
        "stock": 21,
        "min_stock": 5,
        "cost_price": 50138,
        "sale_price": 69000,
        "supplier": "Dubai Fashion Hub",
        "incoming_date": "22.05.2026",
        "status": "Mavjud",
        "aliases": ["defacto paypoq", "sport paypoq", "jigarrang paypoq"]
    },
    {
        "id": 44,
        "sku": "KK-1068",
        "name": "Defacto Sport paypoq Yashil",
        "category": "Paypoq",
        "brand": "Defacto",
        "size": "43-46",
        "color": "Yashil",
        "gender": "Uniseks",
        "material": "Synthetics",
        "stock": 55,
        "min_stock": 6,
        "cost_price": 70711,
        "sale_price": 100000,
        "supplier": "Local Factory UZ",
        "incoming_date": "01.08.2026",
        "status": "Mavjud",
        "aliases": ["yashil sport paypoq", "defacto yashil paypoq"]
    },
    {
        "id": 45,
        "sku": "KK-1070",
        "name": "UzTex Qishki paypoq Bej",
        "category": "Paypoq",
        "brand": "UzTex",
        "size": "39-42",
        "color": "Bej",
        "gender": "Erkak",
        "material": "Synthetics",
        "stock": 4,
        "min_stock": 5,
        "cost_price": 29903,
        "sale_price": 45000,
        "supplier": "Guangzhou Trade",
        "incoming_date": "05.07.2026",
        "status": "Kam qolgan",
        "aliases": ["uztex paypoq", "qishki paypoq", "issiq paypoq", "uztex"]
    },
    {
        "id": 46,
        "sku": "KK-1067",
        "name": "UzTex Sport paypoq Qizil",
        "category": "Paypoq",
        "brand": "UzTex",
        "size": "39-42",
        "color": "Qizil",
        "gender": "Bolalar",
        "material": "Jun",
        "stock": 0,
        "min_stock": 7,
        "cost_price": 79884,
        "sale_price": 127000,
        "supplier": "Moscow Textile",
        "incoming_date": "27.05.2026",
        "status": "Tugagan",
        "aliases": ["uztex sport paypoq", "qizil paypoq"]
    },
    {
        "id": 47,
        "sku": "KK-1017",
        "name": "Artel Style Cargo shim Oq",
        "category": "Shim",
        "brand": "Artel Style",
        "size": "36",
        "color": "Oq",
        "gender": "Erkak",
        "material": "Polyester",
        "stock": 31,
        "min_stock": 6,
        "cost_price": 267194,
        "sale_price": 401000,
        "supplier": "Local Factory UZ",
        "incoming_date": "06.08.2026",
        "status": "Mavjud",
        "aliases": ["cargo shim", "oq cargo shim", "artel shim", "shim", "bryuk", "брюки"]
    },
    {
        "id": 48,
        "sku": "KK-1013",
        "name": "Defacto Chino shim Bej",
        "category": "Shim",
        "brand": "Defacto",
        "size": "36",
        "color": "Bej",
        "gender": "Erkak",
        "material": "Denim",
        "stock": 0,
        "min_stock": 6,
        "cost_price": 488512,
        "sale_price": 688000,
        "supplier": "Toshkent Optom",
        "incoming_date": "21.04.2026",
        "status": "Tugagan",
        "aliases": ["chino shim", "defacto chino shim", "bej shim", "chino"]
    },
    {
        "id": 49,
        "sku": "KK-1016",
        "name": "LC Waikiki Klassik shim Yashil",
        "category": "Shim",
        "brand": "LC Waikiki",
        "size": "38",
        "color": "Yashil",
        "gender": "Erkak",
        "material": "Denim",
        "stock": 12,
        "min_stock": 9,
        "cost_price": 276200,
        "sale_price": 397000,
        "supplier": "Istanbul Import",
        "incoming_date": "10.09.2026",
        "status": "Mavjud",
        "aliases": ["lc waikiki shim", "klassik shim", "yashil shim", "lc waikiki klassik"]
    }
]

def build_inventory():
    print(f"Jami {len(PRODUCTS_RAW)} ta tovar qayta ishlanmoqda...")

    # 1. products.json faylini yaratish
    json_path = ROOT_DIR / "products.json"
    json_data = []
    for p in PRODUCTS_RAW:
        json_data.append({
            "id": p["id"],
            "sku": p["sku"],
            "name": p["name"],
            "category": p["category"],
            "brand": p["brand"],
            "price": p["sale_price"],
            "cost_price": p["cost_price"],
            "sizes": [p["size"]],
            "colors": [p["color"].lower()],
            "gender": p["gender"],
            "material": p["material"],
            "stock": p["stock"],
            "min_stock": p["min_stock"],
            "supplier": p["supplier"],
            "status": p["status"],
            "aliases": p["aliases"]
        })

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(json_data, f, ensure_ascii=False, indent=2)
    print(f"✅ products.json muvaffaqiyatli saqlandi ({len(json_data)} tovar)!")

    # 2. SQLite bazasini to'ldirish
    db_path = ROOT_DIR / "ingichka_store.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Bazada qo'shimcha ustunlar mavjudligini tekshirish
    cursor.execute("PRAGMA table_info(products)")
    existing_cols = [c[1] for c in cursor.fetchall()]
    new_cols = [
        ("sku", "TEXT"),
        ("brand", "TEXT"),
        ("gender", "TEXT"),
        ("material", "TEXT"),
        ("min_stock", "INTEGER DEFAULT 0"),
        ("supplier", "TEXT")
    ]
    for col_name, col_type in new_cols:
        if col_name not in existing_cols:
            cursor.execute(f"ALTER TABLE products ADD COLUMN {col_name} {col_type};")

    # Mavjud tovarlarni tozalash va yangi 49 ta tovar bilan to'ldirish
    cursor.execute("DELETE FROM products;")
    for p in PRODUCTS_RAW:
        desc = f"Brend: {p['brand']}, Jinsi: {p['gender']}, Material: {p['material']}, SKU: {p['sku']}. " + ", ".join(p["aliases"])
        cursor.execute("""
            INSERT INTO products (
                id, name, category, size, color, cost_price, sale_price, stock_quantity,
                description, is_active, sku, brand, gender, material, min_stock, supplier
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?, ?, ?, ?)
        """, (
            p["id"], p["name"], p["category"], p["size"], p["color"].lower(),
            p["cost_price"], p["sale_price"], p["stock"],
            desc, p["sku"], p["brand"], p["gender"], p["material"], p["min_stock"], p["supplier"]
        ))
    conn.commit()
    conn.close()
    print(f"✅ SQLite bazasi (ingichka_store.db) 49 ta real tovar bilan 100% to'ldirildi!")

    # 3. Professional Excel hisobotini yaratish (openpyxl)
    try:
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
        from openpyxl.utils import get_column_letter

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Ombor Hisoboti"

        # Sarlavha
        ws.merge_cells("A1:P1")
        title_cell = ws["A1"]
        title_cell.value = "KIYIM-KECHAK DO'KONI — OMBOR HISOBOTI (REAL OMBOR BAZASI)"
        title_cell.font = Font(name="Calibri", size=14, bold=True, color="1F4E79")
        title_cell.alignment = Alignment(horizontal="center", vertical="center")

        ws.merge_cells("A2:P2")
        sub_cell = ws["A2"]
        sub_cell.value = "Yaratilgan sana: 04.10.2026 | Maqsad: MarkazSavdo AI sotuv boti mahsulotlar ombori"
        sub_cell.font = Font(name="Calibri", size=10, italic=True, color="595959")
        sub_cell.alignment = Alignment(horizontal="center", vertical="center")

        headers = [
            "№", "SKU", "Mahsulot nomi", "Kategoriya", "Brend", "O'lcham", "Rang",
            "Jins", "Material", "Miqdor", "Min. qoldiq", "Sotib olish narxi (so'm)",
            "Sotish narxi (so'm)", "Yetkazib beruvchi", "Kirim sanasi", "Holat"
        ]

        header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
        header_fill = PatternFill(start_color="1F4E79", end_color="1F4E79", fill_type="solid")
        border_thin = Border(
            left=Side(style='thin', color='D9D9D9'),
            right=Side(style='thin', color='D9D9D9'),
            top=Side(style='thin', color='D9D9D9'),
            bottom=Side(style='thin', color='D9D9D9')
        )

        for col_idx, h in enumerate(headers, 1):
            cell = ws.cell(row=4, column=col_idx, value=h)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

        status_fill_kam = PatternFill(start_color="FFF2CC", end_color="FFF2CC", fill_type="solid") # Sariq
        status_fill_tug = PatternFill(start_color="FCE4D6", end_color="FCE4D6", fill_type="solid") # Qizilroq
        status_fill_mav = PatternFill(start_color="E2EFDA", end_color="E2EFDA", fill_type="solid") # Yashil

        for row_idx, p in enumerate(PRODUCTS_RAW, 5):
            ws.cell(row=row_idx, column=1, value=p["id"]).alignment = Alignment(horizontal="center")
            ws.cell(row=row_idx, column=2, value=p["sku"]).alignment = Alignment(horizontal="center")
            ws.cell(row=row_idx, column=3, value=p["name"]).alignment = Alignment(horizontal="left")
            ws.cell(row=row_idx, column=4, value=p["category"]).alignment = Alignment(horizontal="center")
            ws.cell(row=row_idx, column=5, value=p["brand"]).alignment = Alignment(horizontal="center")
            ws.cell(row=row_idx, column=6, value=p["size"]).alignment = Alignment(horizontal="center")
            ws.cell(row=row_idx, column=7, value=p["color"]).alignment = Alignment(horizontal="center")
            ws.cell(row=row_idx, column=8, value=p["gender"]).alignment = Alignment(horizontal="center")
            ws.cell(row=row_idx, column=9, value=p["material"]).alignment = Alignment(horizontal="center")

            # Miqdor va narxlar
            c_stock = ws.cell(row=row_idx, column=10, value=p["stock"])
            c_stock.alignment = Alignment(horizontal="right")
            c_stock.number_format = "#,##0"

            c_min = ws.cell(row=row_idx, column=11, value=p["min_stock"])
            c_min.alignment = Alignment(horizontal="right")
            c_min.number_format = "#,##0"

            c_cost = ws.cell(row=row_idx, column=12, value=p["cost_price"])
            c_cost.alignment = Alignment(horizontal="right")
            c_cost.number_format = "#,##0"

            c_sale = ws.cell(row=row_idx, column=13, value=p["sale_price"])
            c_sale.alignment = Alignment(horizontal="right")
            c_sale.number_format = "#,##0"

            ws.cell(row=row_idx, column=14, value=p["supplier"]).alignment = Alignment(horizontal="left")
            ws.cell(row=row_idx, column=15, value=p["incoming_date"]).alignment = Alignment(horizontal="center")

            c_stat = ws.cell(row=row_idx, column=16, value=p["status"])
            c_stat.alignment = Alignment(horizontal="center")

            # Rang berish
            if p["status"] == "Kam qolgan":
                c_stat.fill = status_fill_kam
            elif p["status"] == "Tugagan":
                c_stat.fill = status_fill_tug
            else:
                c_stat.fill = status_fill_mav

            for col_i in range(1, 17):
                ws.cell(row=row_idx, column=col_i).border = border_thin

        # Ustun kengliklari
        for col in ws.columns:
            max_len = max(len(str(cell.value or '')) for cell in col)
            col_letter = get_column_letter(col[0].column)
            ws.column_dimensions[col_letter].width = max(max_len + 3, 11)

        excel_path = ROOT_DIR / "reports" / "KIYIM_KECHAK_DOKONI_OMBOR_HISOBOTI.xlsx"
        excel_path.parent.mkdir(parents=True, exist_ok=True)
        wb.save(str(excel_path))
        print(f"✅ Professional Excel fayli saqlandi: {excel_path}!")
    except Exception as e:
        print(f"Excel faylini yaratishda xato: {e}")

if __name__ == "__main__":
    build_inventory()
