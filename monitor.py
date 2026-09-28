import os
import json
import requests
from bs4 import BeautifulSoup

URL = "https://www.centroxogo.pt/pokemon-tcg-30th-celebration-booster-bundle-003pc10451101.html"

STATE_FILE = "state.json"

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) "
        "Version/18.0 Mobile/15E148 Safari/604.1"
    )
}


def send_telegram(message):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    requests.post(
        url,
        data={
            "chat_id": CHAT_ID,
            "text": message,
        },
        timeout=30,
    )


def load_state():
    if not os.path.exists(STATE_FILE):
        return {"in_stock": False}

    try:
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {"in_stock": False}


def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)


def check_stock():
    response = requests.get(
        URL,
        headers=HEADERS,
        timeout=30,
    )

    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    text = soup.get_text(" ", strip=True).lower()

    # Centroxogo currently uses "Esgotado" for out of stock.
    out_of_stock = "esgotado" in text

    # Look for typical purchase indicators.
    purchase_words = [
        "adicionar ao carrinho",
        "comprar",
        "add to cart",
        "adicionar",
    ]

    has_purchase_option = any(
        word in text for word in purchase_words
    )

    in_stock = not out_of_stock and has_purchase_option

    return in_stock


def main():
    old_state = load_state()
    old_stock = old_state.get("in_stock", False)

    try:
        new_stock = check_stock()

        print(f"Current stock: {new_stock}")
        print(f"Previous stock: {old_stock}")

        # Only notify when it changes from OUT -> IN.
        if new_stock and not old_stock:
            send_telegram(
                "🚨 CENTROXOGO BACK IN STOCK!\n\n"
                "Pokémon TCG 30th Celebration Booster Bundle\n\n"
                f"{URL}"
            )

        save_state({"in_stock": new_stock})

    except Exception as e:
        print(f"ERROR: {e}")
        raise


if __name__ == "__main__":
    main()
