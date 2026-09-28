import os
import json
from datetime import datetime, timezone
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
        return {
            "in_stock": False,
            "last_heartbeat": None
        }

    try:
        with open(STATE_FILE, "r") as f:
            state = json.load(f)

        state.setdefault("in_stock", False)
        state.setdefault("last_heartbeat", None)

        return state

    except Exception:
        return {
            "in_stock": False,
            "last_heartbeat": None
        }


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

    # Centroxogo uses "Esgotado" when the product is out of stock.
    out_of_stock = "esgotado" in text

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


def should_send_heartbeat(last_heartbeat):
    if not last_heartbeat:
        return True

    try:
        last_time = datetime.fromisoformat(last_heartbeat)
        now = datetime.now(timezone.utc)

        hours_since = (
            now - last_time
        ).total_seconds() / 3600

        return hours_since >= 4

    except Exception:
        return True


def main():
    state = load_state()

    old_stock = state.get("in_stock", False)

    try:
        new_stock = check_stock()

        now = datetime.now(timezone.utc)

        print(f"Current stock: {new_stock}")
        print(f"Previous stock: {old_stock}")

        # ==========================================
        # BACK IN STOCK ALERT
        # ==========================================

        if new_stock and not old_stock:
            send_telegram(
                "🚨 CENTROXOGO BACK IN STOCK!\n\n"
                "Pokémon TCG 30th Celebration Booster Bundle\n\n"
                f"{URL}"
            )

        # ==========================================
        # HEARTBEAT - EVERY 4 HOURS
        # ==========================================

        last_heartbeat = state.get("last_heartbeat")

        if should_send_heartbeat(last_heartbeat):

            status = "🟢 IN STOCK" if new_stock else "🔴 OUT OF STOCK"

            send_telegram(
                "💓 Centroxogo monitor heartbeat\n\n"
                f"Status: {status}\n"
                f"Checked: {now.strftime('%Y-%m-%d %H:%M UTC')}\n\n"
                "Monitor is running normally."
            )

            state["last_heartbeat"] = now.isoformat()

        # ==========================================
        # SAVE CURRENT STATE
        # ==========================================

        state["in_stock"] = new_stock

        save_state(state)

    except Exception as e:
        print(f"ERROR: {e}")
        raise


if __name__ == "__main__":
    main()
