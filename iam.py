import json
import time
import jwt
import requests

IAM_URL = "https://iam.api.cloud.yandex.net/iam/v1/tokens"

_cached_token = None
_cached_exp = 0

def get_iam_token(sa_key_path: str) -> str:
    global _cached_token, _cached_exp

    now = int(time.time())
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
    _cached_exp = now + 12 * 3600

    return _cached_token