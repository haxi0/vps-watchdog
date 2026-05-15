import json
import os
import subprocess
import sys
import threading
import time
from datetime import datetime

import requests

from iam import get_iam_token

# Path to an optional JSON config file describing multiple watchdog targets.
# When set, the config takes precedence over the single-VM environment variables.
WATCHDOG_CONFIG = os.getenv("WATCHDOG_CONFIG")

# Defaults used when a value is not provided by config or environment.
DEFAULT_CHECK_INTERVAL = 60
DEFAULT_PING_ATTEMPTS = 3
DEFAULT_PING_TIMEOUT = 3
DEFAULT_SA_KEY_PATH = "/app/sa-key.json"


def log(msg: str) -> None:
    """Log a message with an ISO timestamp."""
    print(f"[{datetime.now().isoformat(sep=' ', timespec='seconds')}] {msg}", flush=True)


def ping_host(host: str, attempts: int, timeout: int) -> bool:
    """Ping a host up to `attempts` times. Returns True on first success."""
    for _ in range(attempts):
        if subprocess.call(
            ["ping", "-c", "1", "-W", str(timeout), host],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        ) == 0:
            return True
        time.sleep(timeout)
    return False


def start_instance(instance_id: str, sa_key_path: str) -> tuple:
    """Send a request to start the given cloud instance.

    Returns a tuple of (success: bool, detail: str) for the caller to log.
    """
    token = get_iam_token(sa_key_path)
    url = f"https://compute.api.cloud.yandex.net/compute/v1/instances/{instance_id}:start"

    r = requests.post(
        url,
        headers={"Authorization": f"Bearer {token}"},
        timeout=10,
    )

    if r.status_code == 200:
        return True, "VM start request sent"
    return False, f"Start failed: {r.status_code} {r.text}"


def watch_target(target: dict, defaults: dict, stop_event: threading.Event) -> None:
    """Continuously monitor a single target until `stop_event` is set."""
    name = target["name"]
    host = target["host"]
    instance_id = target["instance_id"]
    sa_key_path = target.get("sa_key_path", defaults["sa_key_path"])
    check_interval = int(target.get("check_interval", defaults["check_interval"]))
    ping_attempts = int(target.get("ping_attempts", defaults["ping_attempts"]))
    ping_timeout = int(target.get("ping_timeout", defaults["ping_timeout"]))

    prefix = f"[{name}]"
    log(f"{prefix} Watchdog started (host={host}, instance={instance_id}, key={sa_key_path})")

    while not stop_event.is_set():
        try:
            if ping_host(host, ping_attempts, ping_timeout):
                log(f"{prefix} Server is alive")
            else:
                log(f"{prefix} Server is DOWN -> starting VM")
                try:
                    ok, detail = start_instance(instance_id, sa_key_path)
                    log(f"{prefix} {detail}")
                except Exception as e:
                    log(f"{prefix} Exception while starting VM: {e}")
        except Exception as e:
            log(f"{prefix} Unexpected error in watch loop: {e}")

        # Use the stop event for an interruptible sleep so Ctrl+C exits promptly.
        if stop_event.wait(check_interval):
            break

    log(f"{prefix} Watchdog stopped")


def _validate_target(target: dict, idx: int) -> None:
    """Raise ValueError if a target dict is missing required fields."""
    for field in ("name", "host", "instance_id"):
        if not target.get(field):
            raise ValueError(f"Target #{idx} is missing required field '{field}'")


def load_targets() -> tuple:
    """Load watchdog targets and default settings.

    Returns (targets: list[dict], defaults: dict).

    Two configuration sources are supported:
      1. JSON config file pointed to by the WATCHDOG_CONFIG env var.
      2. Single-target legacy mode using VM_HOST / INSTANCE_ID / SA_KEY_PATH.
    """
    defaults = {
        "check_interval": int(os.getenv("CHECK_INTERVAL", DEFAULT_CHECK_INTERVAL)),
        "ping_attempts": int(os.getenv("PING_ATTEMPTS", DEFAULT_PING_ATTEMPTS)),
        "ping_timeout": int(os.getenv("PING_TIMEOUT", DEFAULT_PING_TIMEOUT)),
        "sa_key_path": os.getenv("SA_KEY_PATH", DEFAULT_SA_KEY_PATH),
    }

    if WATCHDOG_CONFIG:
        if not os.path.exists(WATCHDOG_CONFIG):
            raise FileNotFoundError(f"Config file not found: {WATCHDOG_CONFIG}")
        with open(WATCHDOG_CONFIG, "r") as f:
            cfg = json.load(f)

        # Config-level defaults override env defaults.
        for key in ("check_interval", "ping_attempts", "ping_timeout", "sa_key_path"):
            if key in cfg:
                defaults[key] = cfg[key]

        targets = cfg.get("targets") or []
        if not targets:
            raise ValueError("Config file must define a non-empty 'targets' list")

        for i, t in enumerate(targets):
            _validate_target(t, i)
        return targets, defaults

    # Legacy single-target mode.
    vm_host = os.getenv("VM_HOST")
    instance_id = os.getenv("INSTANCE_ID")
    if not vm_host or not instance_id:
        raise ValueError(
            "No configuration found. Set WATCHDOG_CONFIG to a JSON config file, "
            "or define VM_HOST and INSTANCE_ID environment variables."
        )

    target = {
        "name": os.getenv("VM_NAME", vm_host),
        "host": vm_host,
        "instance_id": instance_id,
        "sa_key_path": defaults["sa_key_path"],
    }
    return [target], defaults


def main() -> int:
    try:
        targets, defaults = load_targets()
    except (ValueError, FileNotFoundError) as e:
        log(f"ERROR: {e}")
        return 1

    log(f"Loaded {len(targets)} target(s)")

    stop_event = threading.Event()
    threads = []
    for target in targets:
        t = threading.Thread(
            target=watch_target,
            args=(target, defaults, stop_event),
            name=f"watchdog-{target['name']}",
            daemon=True,
        )
        t.start()
        threads.append(t)

    try:
        # Keep the main thread alive so daemon workers keep running.
        while any(t.is_alive() for t in threads):
            for t in threads:
                t.join(timeout=1.0)
    except KeyboardInterrupt:
        log("Shutdown requested, stopping watchdogs...")
        stop_event.set()
        for t in threads:
            t.join(timeout=5.0)

    return 0


if __name__ == "__main__":
    sys.exit(main())