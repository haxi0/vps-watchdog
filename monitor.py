import os
import subprocess
import time
import requests
from datetime import datetime
from iam import get_iam_token
import sys

# Hostname or IP of the VM to ping
VM_HOST = os.getenv("VM_HOST")
# ID of the cloud instance to start if VM is down
INSTANCE_ID = os.getenv("INSTANCE_ID")
# Path to the service account key file for IAM token generation
SA_KEY_PATH = os.getenv("SA_KEY_PATH", "/app/sa-key.json")

CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", 60))  # Interval between checks in seconds
PING_ATTEMPTS = int(os.getenv("PING_ATTEMPTS", 3))    # Number of ping attempts before declaring down
PING_TIMEOUT = int(os.getenv("PING_TIMEOUT", 3))      # Seconds to wait between ping attempts
# Timeout for each ping packet in seconds (passed to ping command via -W)
PING_PACKET_TIMEOUT = PING_TIMEOUT

def log(msg):
    """Log message with timestamp."""
    print(f"[{datetime.now().isoformat(sep=' ', timespec='seconds')}] {msg}", flush=True)

# Check required environment variables are set
if not VM_HOST:
    log("ERROR: VM_HOST environment variable is not set.")
    sys.exit(1)
if not INSTANCE_ID:
    log("ERROR: INSTANCE_ID environment variable is not set.")
    sys.exit(1)

def ping_host():
    """Ping the VM host multiple times to check if it is alive."""
    for i in range(PING_ATTEMPTS):
        if subprocess.call(
            ["ping", "-c", "1", "-W", str(PING_PACKET_TIMEOUT), VM_HOST],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        ) == 0:
            return True
        time.sleep(PING_TIMEOUT)
    return False

def start_instance():
    """Send a request to start the cloud instance."""
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
        try:
            start_instance()
        except Exception as e:
            log(f"Exception while starting VM: {e}")

    time.sleep(CHECK_INTERVAL)