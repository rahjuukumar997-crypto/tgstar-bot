"""
Validates Telegram WebApp `initData` per the official algorithm:
https://core.telegram.org/bots/webapps#validating-data-received-via-the-web-app

Never trust a telegram_id sent plainly in a request body — always re-derive
the user from a validated initData string, or a forged request could drain
someone else's wallet.
"""
import hashlib
import hmac
import json
import time
from urllib.parse import parse_qsl

from config import BOT_TOKEN

MAX_AGE_SECONDS = 24 * 60 * 60  # reject stale initData older than this


def validate_init_data(init_data: str, max_age: int = MAX_AGE_SECONDS):
    """Returns the parsed user dict if valid, otherwise None."""
    try:
        pairs = dict(parse_qsl(init_data, strict_parsing=True))
    except ValueError:
        return None

    received_hash = pairs.pop("hash", None)
    if not received_hash:
        return None

    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(pairs.items()))
    secret_key = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
    computed_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(computed_hash, received_hash):
        return None

    auth_date = int(pairs.get("auth_date", "0"))
    if max_age and (time.time() - auth_date) > max_age:
        return None

    user_json = pairs.get("user")
    if not user_json:
        return None
    return json.loads(user_json)
