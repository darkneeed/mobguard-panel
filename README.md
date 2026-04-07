# MobGuard

MobGuard — это система для выявления пользователей, которые некорректно используют мобильные конфиги прокси-сервиса.  
Проект состоит из трёх частей:

- `mobguard-core` — анализ логов, скоринг, предупреждения, блокировки, Telegram-уведомления
- `mobguard-api` — API админ-панели, Telegram-аутентификация, health-check, сохранение правил
- `mobguard-web` — веб-панель модерации, редактирования правил и просмотра метрик качества

Целевой production-сценарий:

- проект лежит в `/opt/mobguard`
- панель открывается по адресу `https://mobguard.example.com`
- внешний `Caddy` на сервере проксирует запросы на `127.0.0.1:8080`
- секреты лежат в `.env`
- все non-secret настройки лежат в `runtime/config.json`

Важно: проект сохраняет обратную совместимость.  
Если на старой установке используется legacy runtime path `/opt/ban_system`, код не должен ломаться.

---

## 1. Что лежит в проекте

В рабочем варианте структура должна быть такой:

```text
/opt/mobguard
  .env
  docker-compose.yml
  Caddyfile.example
  Dockerfile.core
  README.md
  behavioral_analyzers.py
  config.json
  ipinfo_api.py
  mobguard.py
  requirements-api.txt
  requirements-core.txt
  api/
  mobguard_platform/
  scripts/
  tests/
  web/
  runtime/
    config.json
    bans.db
    GeoLite2-ASN.mmdb
    health/
```

Где:

- `.env` — секреты и токены
- `runtime/config.json` — основной редактируемый конфиг
- `runtime/bans.db` — SQLite база
- `runtime/GeoLite2-ASN.mmdb` — GeoLite ASN база
- `Caddyfile.example` — пример конфигурации внешнего Caddy

---

## 2. Как работает конфигурация

### 2.1. Что хранится в `.env`

В `.env` хранятся только секреты и инфраструктурные параметры:

```env
TG_MAIN_BOT_TOKEN=
TG_ADMIN_BOT_TOKEN=
TG_ADMIN_BOT_USERNAME=
PANEL_TOKEN=
IPINFO_TOKEN=
BAN_SYSTEM_DIR=/opt/mobguard/runtime
MOBGUARD_ENV_FILE=/opt/mobguard/.env
REMNANODE_ACCESS_LOG=/var/log/remnanode/access.log
MOBGUARD_SESSION_COOKIE=mobguard_session
SESSION_COOKIE_SECURE=true
```

### 2.2. Что хранится в `runtime/config.json`

В `runtime/config.json` лежат все non-secret настройки:

- thresholds
- policy flags
- ASN списки
- keyword списки
- `admin_tg_ids`
- `review_ui_base_url`
- `shadow_mode`

Это основной источник правды для правил.  
Панель редактирует именно этот файл.

---

## 3. Почему раньше score мог быть равен 0

Самая частая причина:

- нет `IPINFO_TOKEN`
- `IPInfo` не возвращает ASN, ISP и hostname
- в результате:
  - `asn=None`
  - `Unknown ISP`
  - не срабатывают `pure_mobile_asns`
  - не срабатывают `pure_home_asns`
  - не срабатывают `mixed_asns`
  - keyword-анализ почти бесполезен

Итог: score часто остаётся около `0`, а кейсы уходят в ручную модерацию.

Теперь проект:

- предупреждает об отсутствии `IPINFO_TOKEN` при старте
- показывает это в `/api/health`
- считает:
  - `analysis_24h.score_zero_ratio`
  - `analysis_24h.asn_missing_ratio`

---

## 4. Пошаговое развёртывание на сервере

Ниже приведён максимально подробный сценарий.

### Шаг 1. Подготовьте сервер

На сервере должны быть установлены:

- Docker
- Docker Compose plugin
- Caddy

Проверьте:

```bash
docker --version
docker compose version
caddy version
```

Если `docker compose` не работает, сначала установите Docker Compose plugin.

### Шаг 2. Подготовьте каталог проекта

Создайте каталог:

```bash
sudo mkdir -p /opt/mobguard
sudo chown -R $USER:$USER /opt/mobguard
cd /opt/mobguard
```

Скопируйте в него файлы проекта.

После копирования проверьте содержимое:

```bash
ls -la /opt/mobguard
```

### Шаг 3. Создайте runtime-структуру

Выполните bootstrap-скрипт:

```bash
cd /opt/mobguard
chmod +x scripts/bootstrap-runtime.sh
./scripts/bootstrap-runtime.sh
```

Что он делает:

1. создаёт `runtime/`
2. создаёт `runtime/health/`
3. копирует `config.json` в `runtime/config.json`, если файла ещё нет
4. создаёт `.env` из `.env.example`, если файла ещё нет
5. создаёт пустой `runtime/bans.db`, если файла ещё нет

Проверьте:

```bash
ls -la /opt/mobguard
ls -la /opt/mobguard/runtime
```

### Шаг 4. Заполните `.env`

Откройте файл:

```bash
nano /opt/mobguard/.env
```

Заполните значения:

```env
TG_MAIN_BOT_TOKEN=...
TG_ADMIN_BOT_TOKEN=...
TG_ADMIN_BOT_USERNAME=...
PANEL_TOKEN=...
IPINFO_TOKEN=...
BAN_SYSTEM_DIR=/opt/mobguard/runtime
MOBGUARD_ENV_FILE=/opt/mobguard/.env
REMNANODE_ACCESS_LOG=/var/log/remnanode/access.log
MOBGUARD_SESSION_COOKIE=mobguard_session
SESSION_COOKIE_SECURE=true
```

Пояснения:

- `TG_MAIN_BOT_TOKEN` — основной Telegram-бот для сообщений пользователям
- `TG_ADMIN_BOT_TOKEN` — админ-бот
- `TG_ADMIN_BOT_USERNAME` — username админ-бота без `@`
- `PANEL_TOKEN` — токен Remnawave API
- `IPINFO_TOKEN` — токен IPInfo, без него score может часто быть `0`
- `REMNANODE_ACCESS_LOG` — путь к access log прокси

Если пока тестируете без HTTPS и хотите временно ослабить cookie-флаг:

```env
SESSION_COOKIE_SECURE=false
```

Но в production за Caddy лучше держать:

```env
SESSION_COOKIE_SECURE=true
```

### Шаг 5. Положите GeoLite ASN базу

Файл должен лежать здесь:

```text
/opt/mobguard/runtime/GeoLite2-ASN.mmdb
```

Проверьте:

```bash
ls -lh /opt/mobguard/runtime/GeoLite2-ASN.mmdb
```

Если файла нет, анализ подсетей и ASN будет работать неполноценно.

### Шаг 6. Проверьте runtime-config

Откройте:

```bash
nano /opt/mobguard/runtime/config.json
```

Обязательно проверьте эти поля:

- `settings.review_ui_base_url`
- `settings.panel_url`
- `settings.log_file`
- `settings.db_file`
- `settings.geoip_db`
- `settings.shadow_mode`
- `admin_tg_ids`

Минимально важные значения:

```json
{
  "settings": {
    "review_ui_base_url": "https://mobguard.example.com",
    "db_file": "/opt/mobguard/runtime/bans.db",
    "geoip_db": "/opt/mobguard/runtime/GeoLite2-ASN.mmdb",
    "shadow_mode": true
  },
  "admin_tg_ids": [123456789]
}
```

Пояснения:

- `review_ui_base_url` должен быть именно `https://mobguard.example.com`
- `shadow_mode=true` рекомендован для первого запуска
- `admin_tg_ids` — список Telegram ID администраторов панели

### Шаг 7. Проверьте docker-compose

Откройте:

```bash
nano /opt/mobguard/docker-compose.yml
```

Убедитесь, что:

- `mobguard-web` публикуется только на `127.0.0.1:8080`
- `BAN_SYSTEM_DIR=/opt/mobguard/runtime`
- `MOBGUARD_ENV_FILE=/opt/mobguard/.env`

Наружу должен быть открыт только web через localhost bind:

```yaml
ports:
  - "127.0.0.1:8080:80"
```

### Шаг 8. Запустите контейнеры

```bash
cd /opt/mobguard
docker compose up -d --build
```

Проверьте статус:

```bash
docker compose ps
```

Ожидается:

- `mobguard-core` — up
- `mobguard-api` — up (healthy)
- `mobguard-web` — up (healthy)

### Шаг 9. Проверьте локальную доступность панели

На самом сервере:

```bash
curl -I http://127.0.0.1:8080
```

И health:

```bash
curl http://127.0.0.1:8080/api/health
```

Что проверить в ответе:

- `status`
- `core.healthy`
- `ipinfo_token_present`
- `analysis_24h.score_zero_ratio`
- `analysis_24h.asn_missing_ratio`

Нормально, если сразу после первого запуска `analysis_24h.total = 0`, потому что ещё нет событий.

Если `ipinfo_token_present=false`, сначала исправьте `.env`, иначе скоринг будет деградировать.

### Шаг 10. Настройте DNS

У домена `mobguard.example.com` должна быть A-запись на IP сервера.

Проверьте:

```bash
dig mobguard.example.com +short
```

или:

```bash
nslookup mobguard.example.com
```

### Шаг 11. Настройте Caddy

Откройте ваш основной конфиг Caddy и добавьте туда содержимое из `Caddyfile.example`.

Итоговый блок должен выглядеть так:

```caddy
mobguard.example.com {
    encode zstd gzip

    header {
        Strict-Transport-Security "max-age=31536000; includeSubDomains; preload"
        X-Content-Type-Options "nosniff"
        X-Frame-Options "SAMEORIGIN"
        Referrer-Policy "strict-origin-when-cross-origin"
        Permissions-Policy "geolocation=(), microphone=(), camera=()"
    }

    log {
        output file /var/log/caddy/mobguard-access.log
        format console
    }

    reverse_proxy 127.0.0.1:8080 {
        header_up X-Forwarded-Host {host}
        header_up X-Forwarded-Proto {scheme}
        header_up X-Forwarded-For {remote_host}
    }
}
```

После этого перезагрузите Caddy:

```bash
sudo systemctl reload caddy
```

Проверьте статус:

```bash
sudo systemctl status caddy
```

### Шаг 12. Откройте панель в браузере

Откройте:

```text
https://mobguard.example.com
```

Ожидаемое поведение:

1. открывается страница логина
2. виден Telegram login widget
3. вход проходит только для `admin_tg_ids`
4. после входа доступны:
   - `Queue`
   - `Rules`
   - `Quality`

### Шаг 13. Проверьте тёмную тему

В боковой панели выберите:

- `System`
- `Light`
- `Dark`

Проверьте, что:

- тема реально переключается
- queue и detail остаются читаемыми
- severity badges видны и в тёмной теме

### Шаг 14. Проверьте редактирование правил

Откройте раздел `Rules`.

Измените, например:

- `shadow_mode`
- `threshold_mobile`
- один из ASN/keyword списков

Сохраните.

Затем проверьте:

1. нет ошибки revision conflict
2. изменения видны в UI
3. изменения реально записались в:

```text
/opt/mobguard/runtime/config.json
```

Проверка:

```bash
cat /opt/mobguard/runtime/config.json
```

---

## 5. Что делать после первого запуска

Рекомендуемый rollout:

1. оставить `shadow_mode=true`
2. подождать, пока система соберёт реальные события
3. открыть `Quality`
4. посмотреть:
   - backlog
   - `score_zero_ratio`
   - `asn_missing_ratio`
   - top noisy ASN
5. убедиться, что `core.healthy=true`
6. только после этого решать, отключать ли `shadow_mode`

Если у вас снова много кейсов со `score=0`, в первую очередь проверяйте:

1. есть ли `IPINFO_TOKEN` в `.env`
2. что `/api/health` показывает `ipinfo_token_present=true`
3. что `settings.log_file` указывает на реальный лог
4. что `runtime/GeoLite2-ASN.mmdb` существует

---

## 6. Как обновлять проект

Если вы обновили код:

```bash
cd /opt/mobguard
docker compose up -d --build
```

Потом проверьте:

```bash
docker compose ps
curl http://127.0.0.1:8080/api/health
```

---

## 7. Как смотреть логи

### Логи core

```bash
docker compose logs -f mobguard-core
```

### Логи API

```bash
docker compose logs -f mobguard-api
```

### Логи web

```bash
docker compose logs -f mobguard-web
```

### Логи Caddy

Если вы оставили логирование в файл:

```bash
sudo tail -f /var/log/caddy/mobguard-access.log
```

---

## 8. Как проверить health после запуска

Команда:

```bash
curl http://127.0.0.1:8080/api/health
```

Смотрите на:

- `status`
- `db.healthy`
- `core.healthy`
- `core.age_seconds`
- `ipinfo_token_present`
- `analysis_24h.total`
- `analysis_24h.score_zero_ratio`
- `analysis_24h.asn_missing_ratio`

### Нормальный сценарий

- `status = ok`
- `core.healthy = true`
- `ipinfo_token_present = true`
- `score_zero_ratio` не застрял на `1.0`

### Плохой сценарий

- `status = degraded`
- `core.healthy = false`
- `ipinfo_token_present = false`
- `asn_missing_ratio` очень высокий

---

## 9. Резервное копирование

Перед backup желательно остановить core:

```bash
cd /opt/mobguard
docker compose stop mobguard-core
```

Сохраните:

- `/opt/mobguard/runtime/bans.db`
- `/opt/mobguard/runtime/bans.db-wal`
- `/opt/mobguard/runtime/bans.db-shm`
- `/opt/mobguard/runtime/config.json`
- `/opt/mobguard/.env`

После этого верните core:

```bash
docker compose start mobguard-core
```

---

## 10. Откат

Если после изменения правил что-то пошло не так:

1. верните старый `/opt/mobguard/runtime/config.json`
2. включите `shadow_mode=true`
3. при необходимости перезапустите контейнеры:

```bash
cd /opt/mobguard
docker compose up -d --build
```

Если проблема не в правилах, а в коде:

1. откатите файлы проекта
2. пересоберите:

```bash
docker compose up -d --build
```

---

## 11. Проверки для разработки

### Python-тесты

```bash
python -m unittest discover -s tests
```

### Сборка фронтенда

```bash
cd web
npm install
npm run build
```

---

## 12. Короткий чек-лист без пояснений

```bash
sudo mkdir -p /opt/mobguard
sudo chown -R $USER:$USER /opt/mobguard
cd /opt/mobguard

# скопировать сюда проект

chmod +x scripts/bootstrap-runtime.sh
./scripts/bootstrap-runtime.sh

nano .env
nano runtime/config.json

ls -lh runtime/GeoLite2-ASN.mmdb

docker compose up -d --build
docker compose ps

curl http://127.0.0.1:8080/api/health

sudo systemctl reload caddy
sudo systemctl status caddy
```

---

## 13. Главное, что нужно запомнить

1. Домен панели: `https://mobguard.example.com`
2. Каталог проекта: `/opt/mobguard`
3. Секреты: `/opt/mobguard/.env`
4. Правила и runtime-конфиг: `/opt/mobguard/runtime/config.json`
5. Если score снова падает к нулю — сначала проверяйте `IPINFO_TOKEN` и `/api/health`
