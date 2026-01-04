# Watchdog для прерываемых ВМ

Автоматический watchdog для прерываемых виртуальных машин в Яндекс Облаке.

Сервис периодически проверяет доступность VPS через ICMP (ping) и автоматически запускает виртуальную машину, если она остановлена или недоступна. Работает в Docker и не требует ручного обновления IAM токена.

---

## Обзор

- 🔄 Автоматический запуск ВМ при сбое  
- 📡 Проверка доступности через ping  
- 🔐 Аутентификация через сервисный аккаунт  
- ♻️ Автоматическое обновление IAM токена  
- 🐳 Запуск в Docker / docker-compose  
- ⚙️ Все параметры настраиваются через `.env`  
- 🧠 Минимум зависимостей, без cron и systemd  

---

## Как это работает

1. Контейнер периодически пингует указанный IP или хост.  
2. Если все попытки пинга неудачны, сервер считается недоступным.  
3. Watchdog получает IAM токен с помощью сервисного аккаунта.  
4. Отправляет запрос к Compute API:  
   
   ```
   POST /compute/v1/instances/{instance_id}:start
   ```
   
5. Виртуальная машина запускается.

---

## Требования

- Docker 20+  
- Docker Compose v2  
- Аккаунт в Яндекс Облаке  
- Прерываемая или обычная ВМ  
- Сервисный аккаунт с правами управления ВМ  

---

## Настройка

### 1. Подготовка в Яндекс Облаке

1. Создайте сервисный аккаунт:

   ```bash
   yc iam service-account create --name vps-watchdog
   ```

2. Назначьте права:

   Минимальная необходимая роль:

   ```bash
   yc resource-manager folder add-access-binding <FOLDER_ID> \
     --role compute.admin \
     --subject serviceAccount:<SERVICE_ACCOUNT_ID>
   ```

3. Создайте ключ сервисного аккаунта:

   ```bash
   yc iam key create \
     --service-account-id <SERVICE_ACCOUNT_ID> \
     --output sa-key.json
   ```

> Файл `sa-key.json` постоянный и не требует обновлений.

---

### 2. Настройка проекта

1. Клонируйте репозиторий:

   ```bash
   git clone https://github.com/your-org/vps-watchdog.git
   cd vps-watchdog
   ```

2. Создайте файл `.env`:

   ```bash
   cp .env.example .env
   ```

3. Отредактируйте `.env`, указав данные VPS и ВМ. Пример `.env`:

   ```
   # IP или DNS вашего VPS
   VM_HOST=1.2.3.4

   # ID виртуальной машины в Яндекс Облаке
   INSTANCE_ID=xxxxxxxxxxxxxxxx

   # Интервалы
   CHECK_INTERVAL=60
   PING_ATTEMPTS=5
   PING_TIMEOUT=5
   ```

4. Поместите `sa-key.json` рядом с `docker-compose.yml`:

   ```
   vps-watchdog/
   ├── sa-key.json
   ├── docker-compose.yml
   └── ...
   ```

---

## Использование

### Docker Compose

Фрагмент `docker-compose.yml`:

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

> Ключ монтируется в контейнер только для чтения и не копируется внутрь.

### Dockerfile

Рекомендуемая версия:

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

### Запуск с выводом логов

```bash
docker compose up -d --build && docker compose logs -f
```

### Пример логов

Сервер доступен:

```
[2026-01-04 20:01:01] Watchdog started
[2026-01-04 20:01:01] Server is alive
```

Сервер упал:

```
[2026-01-04 20:05:42] Server is DOWN → starting VM
[2026-01-04 20:05:43] VM start request sent
```

---

## Безопасность

- `sa-key.json` не входит в Docker-образ.  
- Ключ сервисного аккаунта монтируется как volume (только для чтения).  

---

## Ограничения и особенности

- Проверка происходит через ICMP (ping). ВМ может отвечать на ping, но быть недоступной по SSH/HTTP.  
- Watchdog отправляет запросы на запуск даже если ВМ уже запускается (Compute API обрабатывает это корректно).  
- Отсутствует таймер ожидания между попытками (можно добавить при необходимости).  

---

## Возможные улучшения

- Проверка TCP портов (например, 22 / 443)  
- HTTP health check  
- Уведомления через Telegram / Slack  
- Ограничение частоты перезапусков  
- Проверка статуса ВМ через API перед запуском  

---

## Участие в проекте

Pull request и issues приветствуются.  
Проект сознательно простой и надежный без излишней сложности.