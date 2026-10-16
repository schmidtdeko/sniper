import os
import json
import time
import random
from curl_cffi import requests as c_requests

DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")
SEEN_FILE = "seen_items.json"

# Cidades permitidas no raio geográfico (Vale do Itajaí)
ALLOWED_CITIES = ["blumenau", "gaspar", "indaial", "pomerode", "timbó", "timbo"]

# Tabela de referência de preços justos de mercado
PRICE_REFERENCES = {
    "pioneer ddj-400": 2200,
    "pioneer ddj-flx4": 2500,
    "controladora traktor": 1500,
    "monitor krk": 1800,
    "macbook air m1": 4200
}

def load_seen_items():
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE, "r") as f:
            return json.load(f)
    return []

def save_seen_items(seen):
    with open(SEEN_FILE, "w") as f:
        json.dump(seen[-500:], f)

def is_valid_location(location_str):
    if not location_str:
        return False
    loc_lower = location_str.lower()
    return any(city in loc_lower for city in ALLOWED_CITIES)

def calculate_discount(title, price):
    title_lower = title.lower()
    for key, market_price in PRICE_REFERENCES.items():
        if key in title_lower:
            discount = ((market_price - price) / market_price) * 100
            return discount, market_price
    return 0, 0

def send_discord_alert(item, discount, market_price):
    if not DISCORD_WEBHOOK_URL:
        print(f"[MODO SILENCIOSO] Oportunidade achada, mas Discord desativado:")
        print(f"-> {item['title']} | R$ {item['price']:.2f} ({discount:.1f}% off) | {item['url']}")
        return

    payload = {
        "embeds": [{
            "title": f"🎯 Oportunidade: {item['title']}",
            "description": (
                f"**Preço Anunciado:** R$ {item['price']:.2f}\n"
                f"**Preço de Mercado:** R$ {market_price:.2f}\n"
                f"🔥 **Deságio:** `{discount:.1f}% abaixo do valor`\n"
                f"📍 **Local:** {item['location']}"
            ),
            "url": item['url'],
            "color": 65280
        }]
    }
    try:
        c_requests.post(DISCORD_WEBHOOK_URL, json=payload, impersonate="chrome")
    except Exception as e:
        print(f"Erro ao enviar alerta para o Discord: {e}")

def search_mercadolibre_api():
    items_to_process = []
    search_queries = list(PRICE_REFERENCES.keys())
    
    for query in search_queries:
        url = "https://api.mercadolibre.com/sites/MLB/search"
        params = {
            "q": query,
            "state": "MLB3810", # Código de Santa Catarina
            "sort": "date_desc"
        }
        headers = {
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        try:
            response = c_requests.get(url, params=params, headers=headers, impersonate="chrome")
            if response.status_code == 200:
                data = response.json()
                for result in data.get("results", []):
                    address = result.get("address", {})
                    city_name = address.get("city", {}).get("name", "")
                    state_name = address.get("state", {}).get("name", "")
                    location_str = f"{city_name} - {state_name}"
                    
                    items_to_process.append({
                        "id": result.get("id"),
                        "title": result.get("title"),
                        "price": float(result.get("price", 0)),
                        "location": location_str,
                        "url": result.get("permalink")
                    })
            time.sleep(random.uniform(1.5, 3.0))
        except Exception as e:
            print(f"Erro na busca do termo '{query}': {e}")
            
    return items_to_process

def run_sniper():
    seen_items = load_seen_items()
    fetched_ads = search_mercadolibre_api()
    
    print(f"Total de anúncios encontrados na API: {len(fetched_ads)}")

    for item in fetched_ads:
        if item["id"] in seen_items:
            continue

        if not is_valid_location(item["location"]):
            seen_items.append(item["id"])
            continue

        discount, market_price = calculate_discount(item["title"], item["price"])
        MIN_DISCOUNT_PERCENT = 15.0
        
        if discount >= MIN_DISCOUNT_PERCENT:
            send_discord_alert(item, discount, market_price)
        
        seen_items.append(item["id"])

    save_seen_items(seen_items)

if __name__ == "__main__":
    run_sniper()
