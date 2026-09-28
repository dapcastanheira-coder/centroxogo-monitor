import os
import json
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


PRODUCTS = {
    "Centroxogo Booster Bundle": {
        "url": "https://www.centroxogo.pt/pokemon-tcg-30th-celebration-booster-bundle-003pc10451101.html",
        "out_of_stock_words": ["esgotado"],
    },

    "El Corte Inglés 30th Anniversary ETB": {
        "url": "https://www.elcorteingles.pt/brinquedos/A202042813-30-caixa-elite-trainer-comemoracao-do-30-aniversario-do-tcg-ingles-pokemon-bandai",
        "out_of_stock_words": [
            "esgotado",
            "temporariamente esgotado",
        ],
    },

    "Toysrus 30th Anniversary Booster Bundle": {
        "url": "https://www.toysrus.pt/Pok%C3%A9mon-30%C2%BA-Anivers%C3%A1rio-Booster-Bundle-%28Ingl%C3%AAs%29/p/K1108953",
        "out_of_stock_words": [
            "esgotado",
            "temporariamente esgotado",
        ],
    },
}


STATE_FILE = "state.json"

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 Mobile/15E148 "
        "Safari/604.1"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;"
        "q=0.9,*/*;q=0.8"
    ),
    "Accept-Language": "pt-PT,pt;q=0.9,en-US;q=0.8,en;q=0.7",
    "Connection": "keep-alive",
}


# ============================================================
# HTTP SESSION WITH RETRIES
# ============================================================

session = requests.Session()

retry_strategy = Retry(
    total=3,
    connect=3,
    read=3,
    backoff_factor=2,
    status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=["GET"],
)

adapter = HTTPAdapter(
    max_retries=retry_strategy
)

session.mount("https://", adapter)
session.mount("http://", adapter)


# ============================================================
# TELEGRAM
# ============================================================

def send_telegram(message):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    response = requests.post(
        url,
        data={
            "chat_id": CHAT_ID,
            "text": message,
        },
        timeout=30,
    )

    response.raise_for_status()


# ============================================================
# STATE
# ============================================================

def load_state():
    if not os.path.exists(STATE_FILE):
        return {
            "products": {},
            "last_heartbeat": None,
        }

    try:
        with open(STATE_FILE, "r") as f:
            state = json.load(f)

        state.setdefault("products", {})
        state.setdefault("last_heartbeat", None)

        return state

    except Exception:
        return {
            "products": {},
            "last_heartbeat": None,
        }


def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(
            state,
            f,
            indent=2,
        )


# ============================================================
# STOCK CHECK
# ============================================================

def check_stock(product):
    print(f"Checking: {product['url']}")

    response = session.get(
        product["url"],
        headers=HEADERS,

        # 15 seconds to connect / TLS handshake
        # 60 seconds to receive the response
        timeout=(15, 60),
    )

    response.raise_for_status()

    soup = BeautifulSoup(
        response.text,
        "html.parser",
    )

    text = soup.get_text(
        " ",
        strip=True,
    ).lower()

    # --------------------------------------------------------
    # OUT OF STOCK
    # --------------------------------------------------------

    out_of_stock = any(
        word.lower() in text
        for word in product["out_of_stock_words"]
    )

    # --------------------------------------------------------
    # PURCHASE OPTIONS
    # --------------------------------------------------------

    purchase_words = [
        "adicionar ao carrinho",
        "adicionar",
        "comprar",
        "add to cart",
        "add to basket",
    ]

    has_purchase_option = any(
        word in text
        for word in purchase_words
    )

    # --------------------------------------------------------
    # FINAL STOCK RESULT
    # --------------------------------------------------------

    in_stock = (
        not out_of_stock
        and has_purchase_option
    )

    return in_stock


# ============================================================
# HEARTBEAT
# ============================================================

def should_send_heartbeat(last_heartbeat):
    if not last_heartbeat:
        return True

    try:
        last_time = datetime.fromisoformat(
            last_heartbeat
        )

        now = datetime.now(timezone.utc)

        hours_since = (
            now - last_time
        ).total_seconds() / 3600

        return hours_since >= 4

    except Exception:
        return True


# ============================================================
# MAIN
# ============================================================

def main():

    state = load_state()

    now = datetime.now(timezone.utc)

    heartbeat_status = []


    # ========================================================
    # CHECK ALL PRODUCTS
    # ========================================================

    for product_name, product in PRODUCTS.items():

        try:

            new_stock = check_stock(product)

            old_stock = state["products"].get(
                product_name,
                False,
            )

            print(
                f"{product_name}: "
                f"Current={new_stock}, "
                f"Previous={old_stock}"
            )


            # =================================================
            # BACK IN STOCK ALERT
            # =================================================

            if new_stock and not old_stock:

                print(
                    f"🚨 BACK IN STOCK: "
                    f"{product_name}"
                )

                send_telegram(
                    "🚨 BACK IN STOCK!\n\n"
                    f"{product_name}\n\n"
                    f"{product['url']}"
                )


            # =================================================
            # SAVE CURRENT STATUS
            # =================================================

            state["products"][product_name] = new_stock


            status = (
                "🟢 IN STOCK"
                if new_stock
                else "🔴 OUT OF STOCK"
            )

            heartbeat_status.append(
                f"{product_name}: {status}"
            )


        except Exception as e:

            # -------------------------------------------------
            # IMPORTANT:
            # A failed website check DOES NOT CRASH THE SCRIPT
            # -------------------------------------------------

            print(
                f"ERROR checking "
                f"{product_name}: {e}"
            )

            heartbeat_status.append(
                f"{product_name}: ⚠️ CHECK ERROR"
            )


    # ========================================================
    # HEARTBEAT EVERY 4 HOURS
    # ========================================================

    last_heartbeat = state.get(
        "last_heartbeat"
    )

    if should_send_heartbeat(
        last_heartbeat
    ):

        message = (
            "💓 Pokémon stock monitor heartbeat\n\n"
            + "\n".join(heartbeat_status)
            + "\n\n"
            f"Checked: "
            f"{now.strftime('%Y-%m-%d %H:%M UTC')}\n"
            "Monitor is running normally."
        )

        try:

            send_telegram(message)

            state["last_heartbeat"] = (
                now.isoformat()
            )

        except Exception as e:

            print(
                f"ERROR sending heartbeat: {e}"
            )


    # ========================================================
    # SAVE STATE
    # ========================================================

    save_state(state)

    print("State saved successfully.")


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":
    main()
