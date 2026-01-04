VPS Watchdog for Preemptible VMs

Автоматический watchdog для прерываемых виртуальных машин в Yandex Cloud.

Сервис периодически проверяет доступность VPS по ICMP (ping) и автоматически запускает виртуальную машину, если она была остановлена или недоступна.

Работает в Docker, не требует ручного обновления IAM-токенов.

⸻

✨ Возможности
	•	🔄 Автоматический запуск VM при падении
	•	📡 Проверка доступности по ping
	•	🔐 Аутентификация через сервисный аккаунт
	•	♻️ Автоматическое обновление IAM-токена
	•	🐳 Запуск в Docker / docker-compose
	•	⚙️ Все параметры настраиваются через .env
	•	🧠 Минимум зависимостей, без cron и systemd

⸻

🧠 Как это работает
	1.	Контейнер периодически пингует указанный IP / hostname.
	2.	Если все попытки ping неудачны — сервер считается недоступным.
	3.	Watchdog получает IAM-токен через сервисный аккаунт.
	4.	Отправляется запрос к Compute API:
    5.	Виртуальная машина запускается.

    POST /compute/v1/instances/{instance_id}:start
    
⸻

📁 Структура проекта
```
vps-watchdog/
├── docker-compose.yml
├── Dockerfile
├── monitor.py          # основной цикл мониторинга
├── iam.py              # получение IAM-токена через JWT
├── requirements.txt
├── .env.example
├── sa-key.json         # ключ сервисного аккаунта (НЕ коммитится)
└── README.md
```

⸻

⚠️ Требования
	•	Docker 20+
	•	Docker Compose v2
	•	Аккаунт в Yandex Cloud
	•	Прерываемая или обычная VM
	•	Сервисный аккаунт с правами на управление VM

⸻

1️⃣ Подготовка в Yandex Cloud

1. Создайте сервисный аккаунт
```
yc iam service-account create --name vps-watchdog
```
2. Выдайте права

Минимально необходимая роль:
```
yc resource-manager folder add-access-binding <FOLDER_ID> \
  --role compute.admin \
  --subject serviceAccount:<SERVICE_ACCOUNT_ID>
```
3. Создайте ключ сервисного аккаунта
```
yc iam key create \
  --service-account-id <SERVICE_ACCOUNT_ID> \
  --output sa-key.json
```
📌 Файл sa-key.json бессрочный, обновлять его не нужно.

⸻

2️⃣ Настройка проекта

1. Клонируйте репозиторий
```
git clone https://github.com/your-org/vps-watchdog.git
cd vps-watchdog
```
2. Подготовьте .env
```
cp .env.example .env
```
Пример .env:
```
# IP или DNS вашего VPS
VM_HOST=1.2.3.4

# ID виртуальной машины в Yandex Cloud
INSTANCE_ID=xxxxxxxxxxxxxxxx

# Интервалы
CHECK_INTERVAL=60
PING_ATTEMPTS=5
PING_TIMEOUT=5
```
3. Положите sa-key.json

Файл должен лежать рядом с docker-compose.yml:
```
vps-watchdog/
├── sa-key.json
├── docker-compose.yml
└── ...
```

⸻

3️⃣ Docker Compose

docker-compose.yml
```
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
🔒 Ключ монтируется read-only, внутрь контейнера он не копируется.

⸻

4️⃣ Dockerfile

Текущая версия (рекомендованная):
```
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

⸻

5️⃣ Запуск с логами
```
docker compose up -d --build && docker compose logs -f
```

⸻

✅ Пример логов

Сервер доступен
```
[2026-01-04 20:01:01] Watchdog started
[2026-01-04 20:01:01] Server is alive
```
Сервер упал
```
[2026-01-04 20:05:42] Server is DOWN → starting VM
[2026-01-04 20:05:43] VM start request sent
```

⸻

🔐 Безопасность
	•	sa-key.json не попадает в Docker image
	•	Файл монтируется как volume

⸻

⚠️ Ограничения и замечания
	•	Проверка осуществляется по ICMP (ping)
VM может отвечать на ping, но быть недоступной по SSH / HTTP.
	•	Watchdog отправляет start, даже если VM уже запускается
(Compute API это нормально обрабатывает).
	•	Нет cooldown-таймера (можно добавить при необходимости).

⸻

🧩 Возможные улучшения
	•	Проверка TCP-порта (22 / 443)
	•	HTTP health-check
	•	Уведомления в Telegram / Slack
	•	Ограничение частоты рестартов
	•	Проверка статуса VM через API перед start

⸻

🤝 Contributing

PR и issue приветствуются.
Проект сознательно остаётся простым и надёжным, без оверинжиниринга.