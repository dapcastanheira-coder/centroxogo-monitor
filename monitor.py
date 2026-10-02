import os
import json
import re
from datetime import datetime, timezone
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from curl_cffi import requests as curl_requests


# ============================================================
# PRODUCTS
# ============================================================

PRODUCTS = {
    "Centroxogo Booster Bundle": {
        "url": "https://www.centroxogo.pt/pokemon-tcg-30th-celebration-booster-bundle-003pc10451101.html",
        "out_of_stock_words": [
            "esgotado",
        ],
    },

    "El Corte Inglés 30th Anniversary ETB": {
        "url": "https://www.elcorteingles.pt/brinquedos/A202042813-30-caixa-elite-trainer-comemoracao-do-30-aniversario-do-tcg-ingles-pokemon-bandai",
        "out_of_stock_words": [
            "esgotado",
            "temporariamente esgotado",
            "sem stock",
            "fora de stock",
            "indisponível",
            "não disponível",
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


# ============================================================
# ALZA SEARCH
# ============================================================

ALZA_SEARCH_URL = (
    "https://www.alza.cz/search.htm?exps=booster+bundle"
)


# ============================================================
# STATE / TELEGRAM
# ============================================================

STATE_FILE = "state.json"

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]


# ============================================================
# HEADERS
# ============================================================

HEADERS_PT = {
    "Accept": (
        "text/html,application/xhtml+xml,"
        "application/xml;q=0.9,image/avif,image/webp,"
        "image/apng,*/*;q=0.8"
    ),
    "Accept-Language": (
        "pt-PT,pt;q=0.9,en-US;q=0.8,en;q=0.7"
    ),
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
    "Upgrade-Insecure-Requests": "1",
}


HEADERS_CZ = {
    "Accept": (
        "text/html,application/xhtml+xml,"
        "application/xml;q=0.9,image/avif,image/webp,"
        "image/apng,*/*;q=0.8"
    ),
    "Accept-Language": (
        "cs-CZ,cs;q=0.9,en-US;q=0.8,en;q=0.7"
    ),
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
    "Upgrade-Insecure-Requests": "1",
}


# ============================================================
# TELEGRAM
# ============================================================

def send_telegram(message):

    response = curl_requests.post(
        f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
        data={
            "chat_id": CHAT_ID,
            "text": message,
            "disable_web_page_preview": False,
        },
        timeout=30,
        impersonate="chrome",
    )

    response.raise_for_status()


# ============================================================
# STATE
# ============================================================

def load_state():

    if not os.path.exists(STATE_FILE):
        return {
            "products": {},
            "alza_products": {},
            "last_heartbeat": None,
        }

    try:

        with open(STATE_FILE, "r", encoding="utf-8") as f:
            state = json.load(f)

        state.setdefault("products", {})
        state.setdefault("alza_products", {})
        state.setdefault("last_heartbeat", None)

        return state

    except Exception:

        return {
            "products": {},
            "alza_products": {},
            "last_heartbeat": None,
        }


def save_state(state):

    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(
            state,
            f,
            indent=2,
            ensure_ascii=False,
        )


# ============================================================
# EL CORTE INGLES PORTUGUESE STOCK DETECTION
# ============================================================

def check_el_corte_ingles(soup, text):

    # --------------------------------------------------------
    # Portuguese OUT OF STOCK indicators
    # --------------------------------------------------------

    out_of_stock_words = [
        "esgotado",
        "temporariamente esgotado",
        "sem stock",
        "fora de stock",
        "indisponível",
        "não disponível",
        "produto esgotado",
        "artigo esgotado",
    ]

    for word in out_of_stock_words:

        if word in text:

            print(
                "El Corte Inglés: "
                f"Portuguese out-of-stock indicator found: "
                f"'{word}'"
            )

            return False

    # --------------------------------------------------------
    # Portuguese PURCHASE indicators
    # --------------------------------------------------------

    purchase_words = [
        "adicionar ao carrinho",
        "adicionar",
        "comprar",
        "comprar agora",
    ]

    for word in purchase_words:

        if word in text:

            print(
                "El Corte Inglés: "
                f"Portuguese purchase indicator found: "
                f"'{word}'"
            )

            return True

    # --------------------------------------------------------
    # Check buttons and links
    # --------------------------------------------------------

    elements = soup.find_all(
        ["button", "a", "input"]
    )

    for element in elements:

        element_text = (
            element.get_text(
                " ",
                strip=True
            ).lower()
        )

        value = (
            element.get(
                "value",
                ""
            ).lower()
        )

        aria_label = (
            element.get(
                "aria-label",
                ""
            ).lower()
        )

        title = (
            element.get(
                "title",
                ""
            ).lower()
        )

        element_classes = " ".join(
            element.get(
                "class",
                []
            )
        ).lower()

        combined = (
            element_text
            + " "
            + value
            + " "
            + aria_label
            + " "
            + title
            + " "
            + element_classes
        )

        for word in purchase_words:

            if word in combined:

                print(
                    "El Corte Inglés: "
                    f"Purchase element found: "
                    f"'{word}'"
                )

                return True

    # --------------------------------------------------------
    # Portuguese availability indicators
    # --------------------------------------------------------

    availability_words = [
        "em stock",
        "disponível",
        "disponível online",
        "disponível para entrega",
        "disponível para envio",
    ]

    for word in availability_words:

        if word in text:

            print(
                "El Corte Inglés: "
                f"Portuguese availability indicator found: "
                f"'{word}'"
            )

            if word != "disponível":
                return True

    # --------------------------------------------------------
    # Structured data
    # --------------------------------------------------------

    html = str(soup).lower()

    structured_stock_indicators = [
        '"availability":"https://schema.org/instock"',
        '"availability": "https://schema.org/instock"',
        "schema.org/instock",
        '"availability":"instock"',
        '"availability": "instock"',
    ]

    for indicator in structured_stock_indicators:

        if indicator in html:

            print(
                "El Corte Inglés: "
                f"Structured IN STOCK indicator found: "
                f"'{indicator}'"
            )

            return True

    # --------------------------------------------------------
    # Product availability attributes
    # --------------------------------------------------------

    availability_elements = soup.find_all(
        attrs={
            "itemprop": "availability"
        }
    )

    for element in availability_elements:

        value = (
            element.get(
                "content",
                ""
            )
            + " "
            + element.get_text(
                " ",
                strip=True
            )
        ).lower()

        print(
            "El Corte Inglés: "
            f"Availability attribute found: '{value}'"
        )

        if (
            "instock" in value
            or "in stock" in value
            or "disponível" in value
        ):
            return True

        if (
            "outofstock" in value
            or "out of stock" in value
            or "esgotado" in value
        ):
            return False

    # --------------------------------------------------------
    # Nothing conclusive
    # --------------------------------------------------------

    print(
        "El Corte Inglés: "
        "stock status could not be determined"
    )

    return None


# ============================================================
# GENERAL STOCK CHECK
# ============================================================

def check_stock(product_name, product):

    print()
    print("=" * 60)
    print(f"Checking: {product_name}")
    print(f"URL: {product['url']}")

    response = curl_requests.get(
        product["url"],
        headers=HEADERS_PT,
        timeout=60,
        impersonate="chrome",
        allow_redirects=True,
    )

    print(
        f"{product_name}: "
        f"HTTP {response.status_code}"
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

    # ========================================================
    # EL CORTE INGLES
    # ========================================================

    if product_name == "El Corte Inglés 30th Anniversary ETB":

        return check_el_corte_ingles(
            soup,
            text,
        )

    # ========================================================
    # GENERAL STORES
    # ========================================================

    out_of_stock = any(
        word.lower() in text
        for word in product["out_of_stock_words"]
    )

    purchase_words = [
        "adicionar ao carrinho",
        "adicionar",
        "comprar",
        "comprar agora",
        "add to cart",
        "add to basket",
        "buy now",
    ]

    has_purchase_option = any(
        word in text
        for word in purchase_words
    )

    if out_of_stock:

        print(
            f"{product_name}: "
            "OUT OF STOCK detected"
        )

        return False

    if has_purchase_option:

        print(
            f"{product_name}: "
            "PURCHASE OPTION detected"
        )

        return True

    print(
        f"{product_name}: "
        "stock status could not be determined"
    )

    return None


# ============================================================
# ALZA HELPERS
# ============================================================

def normalize_text(value):

    if not value:
        return ""

    return " ".join(
        value.lower().split()
    )


def is_pokemon_product(name):

    name_normalized = normalize_text(name)

    pokemon_keywords = [
        "pokemon",
        "pokémon",
    ]

    return any(
        keyword in name_normalized
        for keyword in pokemon_keywords
    )


def is_booster_bundle_product(name):

    name_normalized = normalize_text(name)

    return (
        "booster bundle" in name_normalized
        and is_pokemon_product(name)
    )


def extract_price(text):

    if not text:
        return None

    # Czech price formats such as:
    # 1 499 Kč
    # 1 499,00 Kč
    # 1499 Kč

    patterns = [
        r"([\d\s]+[,.]?\d*)\s*Kč",
        r"([\d\s]+[,.]?\d*)\s*CZK",
    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            text,
            re.IGNORECASE,
        )

        if match:

            price = match.group(1).strip()

            price = re.sub(
                r"\s+",
                " ",
                price,
            )

            return price + " Kč"

    return None


def get_product_name(element):

    # Try common Alza title structures

    selectors = [
        ".name",
        ".name.browsinglink",
        "h2",
        "h3",
        "a",
    ]

    for selector in selectors:

        found = element.select_one(selector)

        if found:

            name = found.get_text(
                " ",
                strip=True,
            )

            if (
                name
                and len(name) > 5
                and (
                    "pokemon" in name.lower()
                    or "pokémon" in name.lower()
                )
            ):
                return name

    # Fallback: inspect all links

    for link in element.find_all("a"):

        name = link.get_text(
            " ",
            strip=True,
        )

        if (
            name
            and len(name) > 5
            and (
                "pokemon" in name.lower()
                or "pokémon" in name.lower()
            )
        ):
            return name

    return None


def get_product_url(element):

    for link in element.find_all("a"):

        href = link.get("href")

        if not href:
            continue

        href_lower = href.lower()

        if (
            "alza.cz" in href_lower
            or href.startswith("/")
        ):

            return urljoin(
                "https://www.alza.cz",
                href,
            )

    return None


def has_czech_add_to_cart(element):

    # --------------------------------------------------------
    # Czech purchase indicators
    # --------------------------------------------------------

    purchase_words = [
        "do košíku",
        "přidat do košíku",
    ]

    text = normalize_text(
        element.get_text(
            " ",
            strip=True,
        )
    )

    for word in purchase_words:

        if word in text:

            print(
                f"Alza: purchase indicator found: "
                f"'{word}'"
            )

            return True

    # --------------------------------------------------------
    # Check button attributes
    # --------------------------------------------------------

    for child in element.find_all(
        ["button", "a", "input"]
    ):

        combined = " ".join([
            normalize_text(
                child.get_text(
                    " ",
                    strip=True,
                )
            ),
            normalize_text(
                child.get(
                    "value",
                    "",
                )
            ),
            normalize_text(
                child.get(
                    "aria-label",
                    "",
                )
            ),
            normalize_text(
                child.get(
                    "title",
                    "",
                )
            ),
            normalize_text(
                " ".join(
                    child.get(
                        "class",
                        [],
                    )
                )
            ),
        ])

        for word in purchase_words:

            if word in combined:

                print(
                    f"Alza: purchase element found: "
                    f"'{word}'"
                )

                return True

    return False


def has_czech_out_of_stock(element):

    text = normalize_text(
        element.get_text(
            " ",
            strip=True,
        )
    )

    out_of_stock_words = [
        "hlídat",
        "momentálně nedostupné",
        "momentálně nedostupný",
        "není skladem",
        "nedostupné",
        "nedostupný",
        "vyprodáno",
        "prodej skončil",
        "nelze objednat",
    ]

    for word in out_of_stock_words:

        if word in text:

            print(
                f"Alza: out-of-stock indicator found: "
                f"'{word}'"
            )

            return True

    return False


def find_alza_product_cards(soup):

    cards = []

    # --------------------------------------------------------
    # Common Alza product containers
    # --------------------------------------------------------

    selectors = [
        "div.browsingitem",
        "div[class*='browsingitem']",
        "article",
        "div.product",
        "div[class*='product']",
    ]

    seen = set()

    for selector in selectors:

        for element in soup.select(selector):

            identifier = id(element)

            if identifier in seen:
                continue

            seen.add(identifier)

            text = normalize_text(
                element.get_text(
                    " ",
                    strip=True,
                )
            )

            if (
                "booster bundle" in text
                and (
                    "pokemon" in text
                    or "pokémon" in text
                )
            ):

                cards.append(element)

    return cards


def check_alza_search():

    print()
    print("=" * 60)
    print("Checking ALZA Booster Bundle search")
    print(f"URL: {ALZA_SEARCH_URL}")

    response = curl_requests.get(
        ALZA_SEARCH_URL,
        headers=HEADERS_CZ,
        timeout=60,
        impersonate="chrome",
        allow_redirects=True,
    )

    print(
        f"Alza search: HTTP {response.status_code}"
    )

    response.raise_for_status()

    soup = BeautifulSoup(
        response.text,
        "html.parser",
    )

    cards = find_alza_product_cards(soup)

    print(
        f"Alza: found {len(cards)} possible product cards"
    )

    products = {}

    for card in cards:

        name = get_product_name(card)

        if not name:
            continue

        if not is_booster_bundle_product(name):
            continue

        url = get_product_url(card)

        if not url:
            continue

        price = extract_price(
            card.get_text(
                " ",
                strip=True,
            )
        )

        in_stock = has_czech_add_to_cart(card)

        if has_czech_out_of_stock(card):
            in_stock = False

        product_key = url

        products[product_key] = {
            "name": name,
            "url": url,
            "price": price,
            "in_stock": in_stock,
        }

        print()
        print("ALZA PRODUCT:")
        print(f"Name: {name}")
        print(f"Price: {price}")
        print(f"Stock: {in_stock}")
        print(f"URL: {url}")

    return products


# ============================================================
# ALZA PRODUCT MONITOR
# ============================================================

def monitor_alza(state):

    try:

        current_products = check_alza_search()

    except Exception as e:

        print(
            f"ERROR checking Alza search: {e}"
        )

        return [
            "Alza: ⚠️ CHECK ERROR"
        ]

    old_products = state.get(
        "alza_products",
        {}
    )

    # First run?
    first_run = len(old_products) == 0

    heartbeat_status = []

    for url, product in current_products.items():

        name = product["name"]
        price = product["price"]
        in_stock = product["in_stock"]

        old_product = old_products.get(url)

        # ====================================================
        # NEW PRODUCT
        # ====================================================

        if old_product is None:

            print(
                f"Alza NEW PRODUCT: {name}"
            )

            # Do not spam on first initialization.
            if not first_run:

                if in_stock:

                    message = (
                        "🆕 ALZA NEW PRODUCT + IN STOCK!\n\n"
                        f"{name}\n"
                    )

                    if price:
                        message += f"\n💰 {price}\n"

                    message += (
                        f"\n🛒 Do košíku\n"
                        f"\n{url}"
                    )

                    send_telegram(message)

                else:

                    message = (
                        "🆕 ALZA NEW PRODUCT!\n\n"
                        f"{name}\n"
                    )

                    if price:
                        message += f"\n💰 {price}\n"

                    message += (
                        "\n⚪ Currently not available\n"
                        f"\n{url}"
                    )

                    send_telegram(message)

        # ====================================================
        # BACK IN STOCK
        # ====================================================

        else:

            old_stock = old_product.get(
                "in_stock"
            )

            if (
                in_stock is True
                and old_stock is not True
            ):

                print(
                    f"Alza BACK IN STOCK: {name}"
                )

                message = (
                    "🚨 ALZA BACK IN STOCK!\n\n"
                    f"{name}\n"
                )

                if price:
                    message += f"\n💰 {price}\n"

                message += (
                    "\n🛒 Do košíku\n"
                    f"\n{url}"
                )

                send_telegram(message)

        # ====================================================
        # HEARTBEAT STATUS
        # ====================================================

        if in_stock:

            status = "🟢 IN STOCK"

        else:

            status = "🔴 OUT OF STOCK"

        heartbeat_status.append(
            f"Alza: {name} — {status}"
        )

    # ========================================================
    # SAVE CURRENT PRODUCTS
    # ========================================================

    state["alza_products"] = current_products

    if not current_products:

        heartbeat_status.append(
            "Alza: ⚠️ No Pokémon Booster Bundles found"
        )

    return heartbeat_status


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
    # CHECK EXISTING PORTUGUESE PRODUCTS
    # ========================================================

    for product_name, product in PRODUCTS.items():

        try:

            new_stock = check_stock(
                product_name,
                product,
            )

            old_stock = state["products"].get(
                product_name
            )

            print(
                f"{product_name}: "
                f"Current={new_stock}, "
                f"Previous={old_stock}"
            )

            # =================================================
            # BACK IN STOCK ALERT
            # =================================================

            if (
                new_stock is True
                and old_stock is not True
            ):

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
            # ONLY SAVE CONFIRMED RESULTS
            # =================================================

            if new_stock is not None:

                state["products"][product_name] = (
                    new_stock
                )

            # =================================================
            # HEARTBEAT STATUS
            # =================================================

            if new_stock is True:

                status = "🟢 IN STOCK"

            elif new_stock is False:

                status = "🔴 OUT OF STOCK"

            else:

                status = "⚠️ UNKNOWN"

            heartbeat_status.append(
                f"{product_name}: {status}"
            )

        except Exception as e:

            print(
                f"ERROR checking "
                f"{product_name}: {e}"
            )

            heartbeat_status.append(
                f"{product_name}: ⚠️ CHECK ERROR"
            )

    # ========================================================
    # CHECK ALZA
    # ========================================================

    alza_status = monitor_alza(
        state
    )

    heartbeat_status.extend(
        alza_status
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

            print(
                "Heartbeat sent."
            )

        except Exception as e:

            print(
                f"ERROR sending heartbeat: {e}"
            )

    # ========================================================
    # SAVE STATE
    # ========================================================

    save_state(state)

    print()
    print(
        "State saved successfully."
    )


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":
    main()
