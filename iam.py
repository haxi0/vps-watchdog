import json
import time
import jwt
import requests
import os

IAM_URL = "https://iam.api.cloud.yandex.net/iam/v1/tokens"

# Cached IAM token and its expiration time (unix timestamp)
_cached_token = None
_cached_exp = 0

def get_iam_token(sa_key_path: str) -> str:
    """
    Get IAM token using service account key.
    Uses caching to avoid unnecessary token requests.
    """
    global _cached_token, _cached_exp

    if not os.path.exists(sa_key_path):
        raise FileNotFoundError(f"Service account key file not found: {sa_key_path}")

    now = int(time.time())
    # Return cached token if still valid (with 60 seconds buffer)
    if _cached_token and now < _cached_exp - 60:
        return _cached_token

    with open(sa_key_path, "r") as f:
        key = json.load(f)

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
    _cached_token = data["iamToken"]
    # Cache expiration time is set to 12 hours from now (unix timestamp)
    _cached_exp = now + 12 * 3600

    return _cached_token