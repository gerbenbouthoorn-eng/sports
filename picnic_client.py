"""
Picnic (online supermarket) API client for groceries, cart, and deliveries.

Picnic has no official public API. This uses the community-maintained
python-picnic-api2 library (the same one Home Assistant uses), so things
may break if Picnic changes its app.

Requires: python-picnic-api2
    pip install python-picnic-api2
"""

import json
import os
from python_picnic_api2 import PicnicAPI, Picnic2FARequired

# After the first login the auth token is saved here, so you don't have to
# send your password every time. Delete this file to force a fresh login.
TOKEN_FILE = os.path.expanduser("~/.picnic_token")


def get_client(
    email: str = None,
    password: str = None,
    country_code: str = None,
) -> PicnicAPI:
    """
    Create and authenticate a Picnic client.

    Credentials are read from arguments or environment variables:
        PICNIC_EMAIL, PICNIC_PASSWORD, PICNIC_COUNTRY (default "NL", or "DE")

    A saved auth token (see TOKEN_FILE) is reused when present. If Picnic asks
    for two-factor authentication, a code is sent by SMS and you are prompted
    to type it in.

    On machines without a saved token file (e.g. a cloud session), the token
    can instead be provided in the PICNIC_AUTH_TOKEN environment variable.
    Returns an authenticated PicnicAPI instance.
    """
    country_code = country_code or os.environ.get("PICNIC_COUNTRY", "NL")

    token = os.environ.get("PICNIC_AUTH_TOKEN")
    if not token and os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE) as f:
            token = f.read().strip()
    if token:
        client = PicnicAPI(country_code=country_code, auth_token=token)
        if _token_works(client):
            return client

    email = email or os.environ["PICNIC_EMAIL"]
    password = password or os.environ["PICNIC_PASSWORD"]
    client = PicnicAPI(country_code=country_code)
    try:
        client.login(email, password)
    except Picnic2FARequired:
        client.generate_2fa_code("SMS")
        client.verify_2fa_code(input("Picnic sent you an SMS. Enter the code: ").strip())
    if not client.logged_in():
        raise RuntimeError("Picnic login failed: check your email and password")

    with open(TOKEN_FILE, "w") as f:
        f.write(client.session.auth_token)
    os.chmod(TOKEN_FILE, 0o600)
    return client


def _token_works(client: PicnicAPI) -> bool:
    try:
        client.get_user()
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# User
# ---------------------------------------------------------------------------

def get_user(client: PicnicAPI):
    """Fetch the authenticated user's account details."""
    return client.get_user()


# ---------------------------------------------------------------------------
# Products
# ---------------------------------------------------------------------------

def search(client: PicnicAPI, term: str):
    """Search the product catalogue, e.g. search(client, "havermout")."""
    return client.search(term)


def get_article(client: PicnicAPI, article_id: str):
    """Fetch details for a single product."""
    return client.get_article(article_id)


# ---------------------------------------------------------------------------
# Cart
# ---------------------------------------------------------------------------

def get_cart(client: PicnicAPI):
    """Fetch the current shopping cart."""
    return client.get_cart()


def add_product(client: PicnicAPI, product_id: str, count: int = 1):
    """Add a product to the cart."""
    return client.add_product(product_id, count)


def remove_product(client: PicnicAPI, product_id: str, count: int = 1):
    """Remove a product from the cart."""
    return client.remove_product(product_id, count)


# ---------------------------------------------------------------------------
# Deliveries
# ---------------------------------------------------------------------------

def get_delivery_slots(client: PicnicAPI):
    """List available delivery time slots."""
    return client.get_delivery_slots()


def get_deliveries(client: PicnicAPI):
    """List past and upcoming deliveries (summary)."""
    return client.get_deliveries()


def get_delivery(client: PicnicAPI, delivery_id: str):
    """Fetch full details (including ordered items) for one delivery."""
    return client.get_delivery(delivery_id)


# ---------------------------------------------------------------------------
# CLI convenience
# ---------------------------------------------------------------------------

def to_plain(obj):
    """Convert the library's result objects into plain dicts/lists."""
    if hasattr(obj, "model_dump"):
        return obj.model_dump(mode="json")
    if isinstance(obj, list):
        return [to_plain(item) for item in obj]
    return obj


def print_json(obj) -> None:
    print(json.dumps(to_plain(obj), indent=2, default=str))


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Picnic CLI")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("user", help="Print account details")
    sub.add_parser("cart", help="Print current cart")
    sub.add_parser("slots", help="List delivery slots")
    sub.add_parser("deliveries", help="List deliveries")

    search_p = sub.add_parser("search", help="Search for products")
    search_p.add_argument("term")

    delivery_p = sub.add_parser("delivery", help="Show one delivery")
    delivery_p.add_argument("delivery_id")

    add_p = sub.add_parser("add", help="Add a product to the cart")
    add_p.add_argument("product_id")
    add_p.add_argument("--count", type=int, default=1)

    args = parser.parse_args()
    if args.command is None:
        parser.print_help()
        raise SystemExit

    client = get_client()

    if args.command == "user":
        print_json(get_user(client))
    elif args.command == "cart":
        print_json(get_cart(client))
    elif args.command == "slots":
        print_json(get_delivery_slots(client))
    elif args.command == "deliveries":
        print_json(get_deliveries(client))
    elif args.command == "search":
        print_json(search(client, args.term))
    elif args.command == "delivery":
        print_json(get_delivery(client, args.delivery_id))
    elif args.command == "add":
        print_json(add_product(client, args.product_id, args.count))
