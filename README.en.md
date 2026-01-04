# VPS Watchdog for Preemptible VMs

Automatic watchdog for preemptible virtual machines in Yandex Cloud.

This service periodically checks the availability of a VPS via ICMP (ping) and automatically starts the virtual machine if it is stopped or unreachable. It runs in Docker and does not require manual IAM token updates.

---

## Overview

- 🔄 Automatic VM start on failure  
- 📡 Availability check via ping  
- 🔐 Authentication via service account  
- ♻️ Automatic IAM token refresh  
- 🐳 Runs in Docker / docker-compose  
- ⚙️ All parameters configurable via `.env`  
- 🧠 Minimal dependencies, no cron or systemd required  

---

## How It Works

1. The container periodically pings the specified IP or hostname.  
2. If all ping attempts fail, the server is considered unreachable.  
3. The watchdog obtains an IAM token using the service account.  
4. It sends a request to the Compute API:  
   
   ```
   POST /compute/v1/instances/{instance_id}:start
   ```
   
5. The virtual machine is started.

---

## Requirements

- Docker 20+  
- Docker Compose v2  
- Yandex Cloud account  
- Preemptible or regular VM  
- Service account with permissions to manage the VM  

---

## Setup

### 1. Prepare in Yandex Cloud

1. Create a service account:

   ```bash
   yc iam service-account create --name vps-watchdog
   ```

2. Grant permissions:

   Minimum required role:

   ```bash
   yc resource-manager folder add-access-binding <FOLDER_ID> \
     --role compute.admin \
     --subject serviceAccount:<SERVICE_ACCOUNT_ID>
   ```

3. Create a service account key:

   ```bash
   yc iam key create \
     --service-account-id <SERVICE_ACCOUNT_ID> \
     --output sa-key.json
   ```

> The `sa-key.json` file is permanent and does not require updates.

---

### 2. Project Setup

1. Clone the repository:

   ```bash
   git clone https://github.com/your-org/vps-watchdog.git
   cd vps-watchdog
   ```

2. Prepare the `.env` file:

   ```bash
   cp .env.example .env
   ```

3. Edit `.env` with your VPS and VM details. Example `.env`:

   ```
   # IP or DNS of your VPS
   VM_HOST=1.2.3.4

   # Yandex Cloud virtual machine ID
   INSTANCE_ID=xxxxxxxxxxxxxxxx

   # Intervals
   CHECK_INTERVAL=60
   PING_ATTEMPTS=5
   PING_TIMEOUT=5
   ```

4. Place `sa-key.json` next to `docker-compose.yml`:

   ```
   vps-watchdog/
   ├── sa-key.json
   ├── docker-compose.yml
   └── ...
   ```

---

## Usage

### Docker Compose

`docker-compose.yml` snippet:

```yaml
services:
  vps-watchdog:
    build: .
    container_name: vps-watchdog
    restart: unless-stopped
    env_file:
      - .env
    volumes:
      - ./sa-key.json:/app/sa-key.json:ro
```

> The key is mounted as read-only and is not copied inside the container.

### Dockerfile

Recommended current version:

```dockerfile
FROM python:3.12-slim

WORKDIR /app

RUN apt-get update \
    && apt-get install -y iputils-ping \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY monitor.py .
COPY iam.py .

CMD ["python", "monitor.py"]
```

### Running with Logs

```bash
docker compose up -d --build && docker compose logs -f
```

### Example Logs

Server is available:

```
[2026-01-04 20:01:01] Watchdog started
[2026-01-04 20:01:01] Server is alive
```

Server went down:

```
[2026-01-04 20:05:42] Server is DOWN → starting VM
[2026-01-04 20:05:43] VM start request sent
```

---

## Security

- `sa-key.json` is not included in the Docker image.  
- The service account key is mounted as a volume (read-only).  

---

## Limitations and Notes

- The check is performed via ICMP (ping). The VM might respond to ping but be unreachable via SSH/HTTP.  
- The watchdog sends start requests even if the VM is already starting (the Compute API handles this gracefully).  
- There is no cooldown timer (can be added if needed).  

---

## Possible Improvements

- TCP port checks (e.g., 22 / 443)  
- HTTP health checks  
- Notifications via Telegram / Slack  
- Rate limiting restarts  
- Checking VM status via API before starting  

---

## Contributing

Pull requests and issues are welcome.  
This project is intentionally kept simple and reliable without overengineering.