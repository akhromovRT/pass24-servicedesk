# tg-proxy — reverse-proxy для Telegram Bot API

Nginx-контейнер, который форвардит `*/telegram/bot<token>/<method>` (и
`/telegram/file/bot<token>/<path>`) на `https://api.telegram.org/`.

## Зачем

Российский хостер, где крутится `site-pass24-servicedesk`, блокирует исходящий
трафик до подсетей Telegram (149.154.160.0/20). Входящие апдейты через webhook
приходят нормально, но `sendMessage` / push-уведомления из контейнера падают
с `TelegramNetworkError: Request timeout`.

Решение — развернуть этот контейнер **на VPS вне блокировки** и направить бэкенд
через него, выставив `TELEGRAM_API_BASE=http://<proxy-host>:8080/telegram`.
Контракт aiogram: библиотека сама дописывает `/bot<token>/<method>` и
`/file/bot<token>/<path>` к базе, nginx снимает префикс `/telegram` и
пробрасывает запрос 1:1.

Подхватывают базу:
- `backend/telegram/bot.py` — aiogram session через `TelegramAPIServer.from_base()`
- `backend/telegram/services/notify.py` — прямые httpx-вызовы из push-нотификаций

## Разворачивание

На хосте вне RU-блокировки (проверить: `curl -v https://api.telegram.org/` с хоста):

```bash
# Склонировать только ops/tg-proxy или scp'нуть директорию
scp -r ops/tg-proxy user@<proxy-host>:/opt/

ssh user@<proxy-host>
cd /opt/tg-proxy
docker compose up -d

# Проверка
curl -s http://127.0.0.1:8080/healthz                    # → ok
curl -s http://127.0.0.1:8080/telegram/bot0:0/getMe | head -c 200
#   Ждём 401 от Telegram (фейковый токен), это означает, что прокси достучался:
#   {"ok":false,"error_code":401,"description":"Unauthorized"}
```

Открыть порт 8080 только для IP основного приложения:

```bash
# ufw-пример (подставить реальный IP site-pass24-servicedesk)
ufw allow from <APP_HOST_IP> to any port 8080 proto tcp
ufw deny  8080/tcp
```

## Подключение со стороны бэкенда

На VPS с `site-pass24-servicedesk` в `.env` / docker-compose добавить:

```env
TELEGRAM_API_BASE=http://<proxy-host>:8080/telegram
```

Рестартовать контейнер. В логах должно исчезнуть
`TelegramNetworkError: Request timeout error`. Smoke-тест:

```bash
docker exec site-pass24-servicedesk python - <<'PY'
import asyncio, httpx, os
base = os.environ["TELEGRAM_API_BASE"].rstrip("/")
tok  = os.environ["TELEGRAM_BOT_TOKEN"]
async def main():
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.get(f"{base}/bot{tok}/getMe")
        print(r.status_code, r.json())
asyncio.run(main())
PY
```

Ожидаем `200` и тело с `"ok": true`.

## Безопасность

- Токен бота передаётся в URL — любой, кто видит трафик между бэкендом и
  прокси, видит и токен. Держать прокси в доверенной сети (VPN / внутренний
  IP) либо подкрутить HTTPS с Let's Encrypt (см. «Как включить HTTPS»).
- Прокси принимает только `/telegram/*` и `/healthz`, всё остальное —
  404 (нормальная защита от случайных сканеров, не от целевых атак).
- Логи пишутся без токена: `map $request_uri → $scrubbed_uri` маскирует
  `/bot<digits>:<alnum>/` в `/bot***/`.

## Как включить HTTPS (опционально)

1. Направить A-запись домена (например `tgproxy.example.com`) на VPS.
2. Выпустить сертификат на хосте:
   ```bash
   apt install certbot
   certbot certonly --standalone -d tgproxy.example.com
   ```
3. Смонтировать сертификаты в контейнер (`/etc/letsencrypt` → `/etc/letsencrypt:ro`)
   и добавить в `nginx.conf` второй `server`-блок со `listen 443 ssl;` +
   `ssl_certificate /etc/letsencrypt/live/tgproxy.example.com/fullchain.pem;`.
4. На бэкенде выставить `TELEGRAM_API_BASE=https://tgproxy.example.com/telegram`.
5. Плановый перевыпуск — `0 3 * * * certbot renew --post-hook "docker compose -f /opt/tg-proxy/docker-compose.yml kill -s HUP tg-proxy"`.

## Как проверить блокировку на основном хосте

```bash
docker exec site-pass24-servicedesk python -c \
  "import httpx; print(httpx.get('https://api.telegram.org/', timeout=5).status_code)"
# Network is unreachable → блокировка активна, прокси нужен.
# 200/301 → блокировки нет, можно выставить TELEGRAM_API_BASE="".
```
