import json
import os
import threading
import time

import jwt
import requests

IAM_URL = "https://iam.api.cloud.yandex.net/iam/v1/tokens"

# Per-key cache: maps absolute sa_key_path -> {"token": str, "exp": int}.
# A lock guards the cache against concurrent access from multiple watchdog threads.
_token_cache: dict = {}
_cache_lock = threading.Lock()


def _request_token(sa_key_path: str) -> tuple:
    """Request a fresh IAM token for the given service account key.

    Returns a tuple of (token, exp_unix_timestamp).
    """
    with open(sa_key_path, "r") as f:
        key = json.load(f)

    now = int(time.time())
    payload = {
        "aud": IAM_URL,
        "iss": key["service_account_id"],
        "iat": now,
        "exp": now + 360,
    }

    jwt_token = jwt.encode(
        payload,
        key["private_key"],
        algorithm="PS256",
        headers={"kid": key["id"]},
    )

    r = requests.post(IAM_URL, json={"jwt": jwt_token}, timeout=10)
    r.raise_for_status()

    data = r.json()
    # Yandex Cloud IAM tokens are valid for up to 12 hours.
    return data["iamToken"], now + 12 * 3600


def get_iam_token(sa_key_path: str) -> str:
    """Get an IAM token for the given service account key.

    Caches the token per key path to avoid unnecessary token requests when
    multiple watchdog targets share the same service account.
    """
    if not os.path.exists(sa_key_path):
        raise FileNotFoundError(f"Service account key file not found: {sa_key_path}")

    cache_key = os.path.abspath(sa_key_path)
    now = int(time.time())

    with _cache_lock:
        entry = _token_cache.get(cache_key)
        # Return cached token if still valid (with 60 seconds buffer).
        if entry and now < entry["exp"] - 60:
            return entry["token"]

        token, exp = _request_token(sa_key_path)
        _token_cache[cache_key] = {"token": token, "exp": exp}
        return token