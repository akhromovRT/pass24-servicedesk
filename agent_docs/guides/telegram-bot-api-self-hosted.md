# Self-hosted telegram-bot-api — runbook

> Эксплуатация self-hosted Bot API сервера для `@PASS24bot` на Hetzner CX23 (`178.104.228.43`). Цель — обход лимита 20 МБ на скачивание файлов через `getFile`. См. ADR-015.

## Архитектура

```
client ──TG──> Telegram DC ──webhook──> support.pass24pro.ru/telegram/webhook/<secret>
                                          │
                                          ▼
                                    pass24-api (5.42.101.27)
                                          │
                                          │ для файлов >20 МБ
                                          ▼
                                    Caddy:80 (178.104.228.43)
                                          │
                                          ├─► localhost:8081 (telegram-bot-api --local, docker)
                                          │   └─► MTProto ──> Telegram DC
                                          │
                                          └─► file_server /tgfiles/* из /opt/telegram-bot-api/data/
```

**Гибридный режим:** webhook остаётся на `api.telegram.org` (нулевой downtime), pass24-api ходит на self-hosted только за `getFile` больших файлов. См. ADR-015 для обоснования.

## Инфра

| Параметр | Значение |
|---|---|
| Провайдер | Hetzner Cloud |
| Тариф | CX23 (2 vCPU / 4 ГБ RAM / 40 ГБ NVMe), €5.99/мес |
| Локация | Nuremberg (`eu-central`) |
| IP | `178.104.228.43` (IPv4) + `2a01:4f8:1c1a:ccd8::/64` (IPv6) |
| OS | Ubuntu 22.04 LTS |
| Hostname | `telegram-bot-api` |
| Backups | Hetzner snapshot раз в сутки, хранение 7 дней |
| SSH | Только по ключу (`~/.ssh/id_ed25519`), алиас `tg-api` в `~/.ssh/config` |

## Доступ

```bash
ssh tg-api                            # быстрый заход (алиас в ~/.ssh/config)
ssh root@178.104.228.43               # полный
```

Recovery пароль (только для Hetzner web-консоли, password auth по SSH отключён): хранится в `/tmp/tgapi_root_pass.txt` на ноуте разработчика + 1Password `pass24-servicedesk / telegram-bot-api / hetzner-root`.

## Креденшалы Telegram

`API_ID` / `API_HASH` получены на `my.telegram.org` под служебным Telegram-аккаунтом PASS24 (при увольнении владельца нужна ротация — см. секцию Rotation).

- Хранятся в `/opt/telegram-bot-api/.env` (chmod 600) на VPS
- **Не в git**, не в репо
- Дубль в 1Password `pass24-servicedesk / telegram-bot-api / my.telegram.org`

Bot-token `@PASS24bot` живёт в `.env` pass24-api на `support.pass24pro.ru`, self-hosted его не хранит — токен идёт в URL каждого запроса.

## Ключевые файлы на VPS

| Путь | Назначение |
|---|---|
| `/opt/telegram-bot-api/docker-compose.yml` | Compose-манифест контейнера |
| `/opt/telegram-bot-api/.env` | `TELEGRAM_API_ID`, `TELEGRAM_API_HASH` |
| `/opt/telegram-bot-api/data/` | Bind-mount TDLib хранилища — скачанные файлы и сессии |
| `/etc/caddy/Caddyfile` | Reverse proxy + file_server конфиг |
| `/var/log/caddy/tg-api.log` | Access log Caddy (JSON, rolled 20MB × 7) |

## Операции

### Проверить статус
```bash
ssh tg-api 'docker ps --filter name=telegram-bot-api --format "{{.Names}}: {{.Status}}"'
ssh tg-api 'systemctl is-active caddy fail2ban ufw'
curl -s http://178.104.228.43/bot<TOKEN>/getMe | jq   # с админ-IP в allowlist
```

### Посмотреть логи
```bash
ssh tg-api 'docker logs telegram-bot-api --tail 100 -f'
ssh tg-api 'tail -f /var/log/caddy/tg-api.log'
ssh tg-api 'journalctl -u caddy -n 50 --no-pager'
```

### Рестарт
```bash
ssh tg-api 'cd /opt/telegram-bot-api && docker compose restart'
ssh tg-api 'systemctl restart caddy'
```

### Обновление образа `aiogram/telegram-bot-api`
```bash
ssh tg-api 'cd /opt/telegram-bot-api && docker compose pull && docker compose up -d'
```
Образ обновляется редко (раз в квартал после выхода новых версий TDLib). Проверять `docker logs` после обновления.

### Добавить IP в allowlist
```bash
ssh tg-api 'vi /etc/caddy/Caddyfile'
# В строке @allowed remote_ip ... добавить новый IP через пробел
ssh tg-api 'systemctl restart caddy'   # reload не работает: admin off в конфиге
```

## Мониторинг

Минимум, что должно быть на глаз:

1. **Диск**: `df -h /opt/telegram-bot-api/data/` — TDLib сам файлы не чистит
2. **Контейнер**: `docker ps --filter name=telegram-bot-api` должен быть `Up`
3. **MTProto connection**: `docker logs telegram-bot-api | tail -50` — не должно быть `failed to connect`
4. **pass24-api getFile latency**: в логах `backend/telegram/services/ticket_service.py` смотреть `download failed for file_id=...` — не должны появляться

Рекомендуется настроить healthchecks.io cron каждые 5 минут:
```bash
curl -s http://178.104.228.43/bot<TOKEN>/getMe | jq -e '.ok == true' && curl https://hc-ping.com/<UUID>
```

## Disk cleanup cron

TDLib в `--local` режиме **не удаляет** скачанные файлы. Раз в неделю надо чистить:
```bash
# на VPS
find /opt/telegram-bot-api/data -type f -atime +7 -delete
find /opt/telegram-bot-api/data -type d -empty -delete
```

Crontab (добавить руками после первых проблем с диском):
```
0 3 * * 0  find /opt/telegram-bot-api/data -type f -atime +7 -delete && find /opt/telegram-bot-api/data -type d -empty -delete
```

## Troubleshooting

### `getMe` возвращает 401 Unauthorized
Токен бота неверный или отозван. Проверить `.env` на `support.pass24pro.ru`, совпадает ли `TELEGRAM_BOT_TOKEN`. Сверить с `@BotFather /mybots`.

### `forbidden` (403) от Caddy
IP звонящего не в allowlist. См. «Добавить IP в allowlist».

### `502 Bad Gateway`
Docker-контейнер упал или не поднялся. `ssh tg-api 'docker ps -a --filter name=telegram-bot-api'` — если `Exited`, смотреть логи. Типичные причины: неверные `API_ID`/`API_HASH`, проблема с сетью к Telegram DC.

### `getFile` возвращает `file not found` для больших файлов
Self-hosted скачал файл, но pass24-api не может его получить через `/tgfiles/*`. Проверить:
- Путь в file_path (должен начинаться на `/var/lib/telegram-bot-api/`)
- Caddy логи для этого пути
- Файл реально существует: `ls /opt/telegram-bot-api/data/<api_id>/documents/`

### pass24-api не видит self-hosted
Проверить env на `support.pass24pro.ru`:
```bash
ssh root@5.42.101.27 'grep -E "TELEGRAM_(API|FILE)_BASE" /opt/sites/pass24-servicedesk/.env'
```
Должны быть непустые значения. После правки — `docker compose up -d --force-recreate --no-deps site-pass24-servicedesk`.

### DNS `tg-api.pass24pro.ru` не резолвится
Известная проблема Timeweb: зона не применяется для sub-доменов ресурсов вне Timeweb-инфраструктуры (VPS-то Hetzner). Пока используется IP напрямую. Для восстановления домена — переезд DNS зоны `pass24pro.ru` на Cloudflare или reg.ru (как `pass24.online`).

## Rollback

Полный откат на cloud `api.telegram.org`:
```bash
ssh root@5.42.101.27 'cd /opt/sites/pass24-servicedesk && \
  sed -i "/^TELEGRAM_API_BASE=/d; /^TELEGRAM_FILE_API_BASE=/d" .env && \
  docker compose up -d --force-recreate --no-deps site-pass24-servicedesk'
```
Поведение моментально вернётся к cloud Bot API. Большие файлы снова будут skipped (лог `exceeds ... bytes`), маленькие — работают как обычно. VPS можно оставить включённым для debug.

## Rotation (ротация API_ID/HASH)

Если увольняется владелец служебного Telegram-аккаунта:
1. На `my.telegram.org` под тем же аккаунтом → delete application.
2. Создать новое приложение (с другого служебного аккаунта).
3. `ssh tg-api 'vi /opt/telegram-bot-api/.env'` — поменять `TELEGRAM_API_ID`/`TELEGRAM_API_HASH`.
4. `ssh tg-api 'cd /opt/telegram-bot-api && docker compose up -d --force-recreate'`.
5. Первый `getMe` через self-hosted — убедиться что работает.
6. Обновить 1Password.

Bot-token `@PASS24bot` при этом не меняется — он привязан к самому боту у BotFather.

## Что НЕ делать

- **Не делать `setWebhook` через self-hosted**. Пока webhook на `api.telegram.org` — это конфликт, Telegram заблокирует бот за session collision. Если всё-таки надо — сначала `logOut` на cloud + 10 мин FLOOD_WAIT.
- **Не делать `getUpdates` через self-hosted**. Webhook активен, Telegram вернёт `Conflict: can't use getUpdates method while a webhook is active`.
- **Не коммитить `.env` с VPS в git**. `API_ID` / `API_HASH` чувствительны.
- **Не открывать 8081 наружу**. Docker bind: `127.0.0.1:8081`, только Caddy имеет к нему доступ. Если docker-compose изменён — проверить.
