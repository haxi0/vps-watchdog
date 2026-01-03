import os
import subprocess
import time
import requests
from datetime import datetime

VM_HOST = os.getenv("VM_HOST")
INSTANCE_ID = os.getenv("INSTANCE_ID")
IAM_TOKEN = os.getenv("IAM_TOKEN")

CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", 60))
PING_ATTEMPTS = int(os.getenv("PING_ATTEMPTS", 5))
PING_TIMEOUT = int(os.getenv("PING_TIMEOUT", 5))

if not all([VM_HOST, INSTANCE_ID, IAM_TOKEN]):
    raise RuntimeError("VM_HOST, INSTANCE_ID и IAM_TOKEN должны быть заданы")

def log(msg: str):
    print(f"[{datetime.now().isoformat(sep=' ', timespec='seconds')}] {msg}", flush=True)

def ping_host() -> bool:
    for attempt in range(1, PING_ATTEMPTS + 1):
        result = subprocess.call(
            ["ping", "-c", "1", "-W", "3", VM_HOST],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if result == 0:
            return True
        log(f"Ping {attempt}/{PING_ATTEMPTS} failed, retry in {PING_TIMEOUT}s")
        time.sleep(PING_TIMEOUT)
    return False

def start_instance():
    url = f"https://compute.api.cloud.yandex.net/compute/v1/instances/{INSTANCE_ID}:start"
    headers = {
        "Authorization": f"Bearer {IAM_TOKEN}",
        "Content-Type": "application/json",
    }

    try:
        r = requests.post(url, headers=headers, timeout=10)
        if r.status_code == 200:
            log("Start request sent successfully")
        else:
            log(f"Start failed: {r.status_code} {r.text}")
    except Exception as e:
        log(f"API request error: {e}")

log("Watchdog started")

while True:
    if ping_host():
        log("Server is alive")
    else:
        log("Server is DOWN → sending start request")
        start_instance()

    time.sleep(CHECK_INTERVAL)