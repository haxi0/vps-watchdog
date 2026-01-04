import os
import subprocess
import time
import requests
from datetime import datetime
from iam import get_iam_token

VM_HOST = os.getenv("VM_HOST")
INSTANCE_ID = os.getenv("INSTANCE_ID")
SA_KEY_PATH = os.getenv("SA_KEY_PATH", "/app/sa-key.json")

CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", 60))
PING_ATTEMPTS = int(os.getenv("PING_ATTEMPTS", 5))
PING_TIMEOUT = int(os.getenv("PING_TIMEOUT", 5))

def log(msg):
    print(f"[{datetime.now().isoformat(sep=' ', timespec='seconds')}] {msg}", flush=True)

def ping_host():
    for i in range(PING_ATTEMPTS):
        if subprocess.call(
            ["ping", "-c", "1", "-W", "3", VM_HOST],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        ) == 0:
            return True
        time.sleep(PING_TIMEOUT)
    return False

def start_instance():
    token = get_iam_token(SA_KEY_PATH)
    url = f"https://compute.api.cloud.yandex.net/compute/v1/instances/{INSTANCE_ID}:start"

    r = requests.post(
        url,
        headers={"Authorization": f"Bearer {token}"},
        timeout=10,
    )

    if r.status_code == 200:
        log("VM start request sent")
    else:
        log(f"Start failed: {r.status_code} {r.text}")

log("Watchdog started")

while True:
    if ping_host():
        log("Server is alive")
    else:
        log("Server is DOWN → starting VM")
        start_instance()

    time.sleep(CHECK_INTERVAL)