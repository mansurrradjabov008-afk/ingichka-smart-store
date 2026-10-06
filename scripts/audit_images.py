import json
import requests

def audit():
    with open('products.json', 'r', encoding='utf-8') as f:
        products = json.load(f)

    print(f"Total products: {len(products)}")
    bad_count = 0
    for p in products:
        pid = p.get('id')
        name = p.get('name')
        url = p.get('image_url')
        try:
            r = requests.get(url, timeout=5, stream=True, headers={'User-Agent': 'Mozilla/5.0'})
            if r.status_code != 200:
                print(f"FAILED [{r.status_code}] -> ID {pid:2d} | {name} | {url}")
                bad_count += 1
            else:
                print(f"OK [200] -> ID {pid:2d} | {name}")
        except Exception as e:
            print(f"ERROR [{e}] -> ID {pid:2d} | {name} | {url}")
            bad_count += 1

    print(f"\nAudit completed: {len(products) - bad_count} OK, {bad_count} FAILED.")

if __name__ == '__main__':
    audit()
