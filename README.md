# MobGuard

MobGuard — это система, которая отслеживает некорректное использование мобильных конфигов прокси-сервиса, считает score, создаёт кейсы для ручной модерации и, при необходимости, применяет ограничения к пользователям.

Проект состоит из трёх внутренних частей, но остаётся **одним репозиторием и одним продуктом**:

- `mobguard-core` — читает лог, анализирует подключения, считает score, создаёт предупреждения и блокировки, отправляет Telegram-уведомления
- `mobguard-api` — обслуживает админ-панель, Telegram-аутентификацию, редактирование правил, проверку состояния и очередь модерации
- `mobguard-web` — веб-панель для модерации, просмотра метрик и редактирования правил

Целевой сценарий для боевого развёртывания:

- проект разворачивается в `/opt/mobguard`
- панель открывается по адресу `https://mobguard.example.com`
- внешний `Caddy` на сервере проксирует запросы на `127.0.0.1:8080`
- секреты лежат в `.env`
- несекретный конфиг лежит в `runtime/config.json`

Важно:

- проект сохраняет обратную совместимость
- если у старой установки используется legacy path `/opt/ban_system`, код не должен ломаться
- правила из панели сохраняются обратно в `runtime/config.json`
- БД не является основным источником истины для правил, она используется для аудита, ревизий, очереди, меток и кэша

---

## 1. Что находится в проекте

Рабочая структура проекта должна выглядеть так:

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

Что здесь важно:

- `.env` — секреты и токены
- `runtime/config.json` — основной редактируемый рантайм-конфиг
- `runtime/bans.db` — SQLite база
- `runtime/GeoLite2-ASN.mmdb` — ASN база MaxMind
- `runtime/health/` — служебный каталог под health/runtime
- `Caddyfile.example` — пример конфигурации внешнего Caddy

---

## 2. Как устроен конфиг

### 2.1. Что хранится в `.env`

В `.env` должны лежать только секреты и обязательные токены:

```env
TG_MAIN_BOT_TOKEN=
TG_ADMIN_BOT_TOKEN=
TG_ADMIN_BOT_USERNAME=
PANEL_TOKEN=
IPINFO_TOKEN=
MAXMIND_LICENSE_KEY=
```

Пояснения:

- `TG_MAIN_BOT_TOKEN` — основной Telegram-бот для сообщений пользователям
- `TG_ADMIN_BOT_TOKEN` — админ-бот
- `TG_ADMIN_BOT_USERNAME` — username админ-бота без `@`
- `PANEL_TOKEN` — токен доступа к Remnawave API
- `IPINFO_TOKEN` — токен IPInfo, без него score может деградировать к `0`
- `MAXMIND_LICENSE_KEY` — ключ MaxMind, нужен для автоматической загрузки `GeoLite2-ASN.mmdb`

Большинство инфраструктурных путей пользователю вручную больше задавать не нужно:

- `db_file` считается константой: `/opt/mobguard/runtime/bans.db`
- `geoip_db` считается константой: `/opt/mobguard/runtime/GeoLite2-ASN.mmdb`
- runtime-dir считается `/opt/mobguard/runtime`
- health-dir считается `/opt/mobguard/runtime/health`

### 2.2. Что хранится в `runtime/config.json`

В `runtime/config.json` лежат все несекретные настройки:

- thresholds
- policy flags
- ASN списки
- keyword списки
- `admin_tg_ids`
- `review_ui_base_url`
- `shadow_mode`
- другие runtime-правила

Это основной источник правды для правил.  
Панель редактирует именно этот файл.  
БД хранит ревизии и аудит, но не заменяет этот файл как основной конфиг.

---

## 3. Почему score может быть равен 0

Самая частая причина:

- не заполнен `IPINFO_TOKEN`
- `IPInfo` не возвращает ASN, ISP и hostname
- из-за этого:
  - `asn=None`
  - `Unknown ISP`
  - не срабатывают `pure_mobile_asns`
  - не срабатывают `pure_home_asns`
  - не срабатывают `mixed_asns`
  - keyword-анализ сильно деградирует

Итог:

- score часто остаётся равным `0`
- кейсы массово улетают в ручную модерацию

Теперь проект показывает это явно:

- предупреждение при старте
- статус в `/api/health`
- метрики:
  - `analysis_24h.score_zero_ratio`
  - `analysis_24h.asn_missing_ratio`

Если score снова стал массово равен `0`, в первую очередь проверяйте:

1. заполнен ли `IPINFO_TOKEN` в `.env`
2. показывает ли `/api/health` поле `ipinfo_token_present=true`
3. существует ли `runtime/GeoLite2-ASN.mmdb`
4. действительно ли прокси пишет лог в ожидаемое место

---

## 4. Самый простой сценарий установки

Идея установки такая:

- пользователь создаёт каталог `/opt/mobguard`
- кладёт туда один install/bootstrap script
- запускает его
- при первом запуске скрипт создаёт структуру, `.env`, `runtime/config.json`, базу и останавливается, если обязательные секреты не заполнены
- после заполнения `.env` пользователь запускает тот же скрипт повторно
- при повторном запуске скрипт скачивает `GeoLite2-ASN.mmdb`, поднимает контейнеры и завершает установку

Если репозиторий уже склонирован — скрипт работает по месту.  
Если репозиторий ещё не склонирован — скрипт может сам его клонировать по `MOBGUARD_REPO_URL` или по первому аргументу.

---

## 5. Пошаговое развёртывание на сервере

Ниже приведён максимально подробный сценарий для боевого развёртывания.

### Шаг 1. Подготовьте сервер

На сервере должны быть доступны:

- Docker
- Docker Compose plugin
- Caddy
- git
- curl
- tar

Проверьте:

```bash
docker --version
docker compose version
caddy version
git --version
curl --version
tar --version
```

Если какой-то команды нет, сначала установите её.

Что считается правильным результатом:

- каждая команда выводит версию
- ошибок `command not found` нет

Что проверить после шага:

- `docker compose version` реально отрабатывает
- `caddy version` реально отрабатывает

### Шаг 2. Создайте каталог проекта

Выполните:

```bash
sudo mkdir -p /opt/mobguard
sudo chown -R $USER:$USER /opt/mobguard
cd /opt/mobguard
```

Что считается правильным результатом:

- каталог `/opt/mobguard` существует
- у вас есть права на запись в него

Что проверить после шага:

```bash
pwd
ls -la /opt/mobguard
```

Текущий каталог должен быть `/opt/mobguard`.

### Шаг 3. Подготовьте install script

Есть два варианта.

#### Вариант А. Репозиторий уже склонирован

Если проект уже лежит в `/opt/mobguard`, используйте:

```bash
chmod +x /opt/mobguard/install.sh
```

#### Вариант Б. В каталоге пока только один скрипт

Если вы загрузили только один `install.sh` в пустую папку `/opt/mobguard`, то он должен быть исполняемым:

```bash
chmod +x /opt/mobguard/install.sh
```

И запускаться с URL репозитория:

```bash
MOBGUARD_REPO_URL='https://<TOKEN>@github.com/darkneeed/mobguard.git' /opt/mobguard/install.sh
```

или:

```bash
/opt/mobguard/install.sh 'https://<TOKEN>@github.com/darkneeed/mobguard.git'
```

Что считается правильным результатом:

- если проект не был склонирован, скрипт сам подтягивает исходники
- если проект уже был склонирован, скрипт не ломает существующие файлы

Что проверить после шага:

```bash
ls -la /opt/mobguard
```

Должны появиться основные файлы проекта:

- `docker-compose.yml`
- `mobguard.py`
- `README.md`
- `install.sh`

### Шаг 4. Запустите install/bootstrap script в первый раз

Если проект уже склонирован:

```bash
cd /opt/mobguard
./install.sh
```

Что должен сделать скрипт:

1. создать `runtime/`
2. создать `runtime/health/`
3. создать `.env`, если файла нет
4. создать `runtime/config.json`, если файла нет
5. создать `runtime/bans.db`, если файла нет
6. проверить обязательные зависимости
7. остановиться с понятной инструкцией, если обязательные секреты ещё не заполнены

Что считается правильным результатом:

- появились:
  - `/opt/mobguard/.env`
  - `/opt/mobguard/runtime/config.json`
  - `/opt/mobguard/runtime/bans.db`
  - `/opt/mobguard/runtime/health/`
- скрипт не затирает уже существующие пользовательские файлы

Что проверить после шага:

```bash
ls -la /opt/mobguard
ls -la /opt/mobguard/runtime
```

### Шаг 5. Заполните `.env`

Откройте:

```bash
nano /opt/mobguard/.env
```

Заполните:

```env
TG_MAIN_BOT_TOKEN=...
TG_ADMIN_BOT_TOKEN=...
TG_ADMIN_BOT_USERNAME=...
PANEL_TOKEN=...
IPINFO_TOKEN=...
MAXMIND_LICENSE_KEY=...
```

Что считается правильным результатом:

- значения заполнены
- пустых обязательных строк не осталось

Что проверить после шага:

```bash
cat /opt/mobguard/.env
```

Проверьте, что нужные переменные реально присутствуют.

### Шаг 6. Проверьте `runtime/config.json`

Откройте:

```bash
nano /opt/mobguard/runtime/config.json
```

Обязательно проверьте:

- `settings.review_ui_base_url`
- `settings.panel_url`
- `settings.log_file`
- `settings.shadow_mode`
- `admin_tg_ids`

Минимально важные значения:

```json
{
  "settings": {
    "review_ui_base_url": "https://mobguard.example.com",
    "shadow_mode": true
  },
  "admin_tg_ids": [123456789]
}
```

Что считается правильным результатом:

- `review_ui_base_url` равен `https://mobguard.example.com`
- `shadow_mode=true` на первом запуске
- `admin_tg_ids` заполнен

Что проверить после шага:

```bash
cat /opt/mobguard/runtime/config.json
```

### Шаг 7. Запустите install/bootstrap script повторно

После заполнения `.env` запустите тот же скрипт ещё раз.

Если проект уже склонирован:

```bash
cd /opt/mobguard
./install.sh
```

Теперь скрипт должен:

1. увидеть, что `.env` уже заполнен
2. скачать `GeoLite2-ASN.mmdb` через `MAXMIND_LICENSE_KEY`, если файла ещё нет
3. не трогать уже существующие `runtime/config.json` и `.env`
4. запустить `docker compose up -d --build`

Что считается правильным результатом:

- `runtime/GeoLite2-ASN.mmdb` появился
- контейнеры стартовали

Что проверить после шага:

```bash
ls -lh /opt/mobguard/runtime/GeoLite2-ASN.mmdb
docker compose ps
```

### Шаг 8. Проверьте состояние контейнеров

Команда:

```bash
cd /opt/mobguard
docker compose ps
```

Ожидается:

- `mobguard-core` — `Up`
- `mobguard-api` — `Up (healthy)` или `healthy`
- `mobguard-web` — `Up (healthy)` или `healthy`

Если контейнер не поднялся:

```bash
docker compose logs -f mobguard-core
docker compose logs -f mobguard-api
docker compose logs -f mobguard-web
```

### Шаг 9. Проверьте локальную доступность панели

На самом сервере:

```bash
curl -I http://127.0.0.1:8080
```

И отдельно проверьте health:

```bash
curl http://127.0.0.1:8080/api/health
```

Что считается правильным результатом:

- web отвечает на `127.0.0.1:8080`
- `/api/health` возвращает JSON

Что проверить после шага:

- `status`
- `core.healthy`
- `ipinfo_token_present`
- `analysis_24h.score_zero_ratio`
- `analysis_24h.asn_missing_ratio`

Если `ipinfo_token_present=false`, сначала исправьте `.env`, иначе скоринг будет деградировать.

### Шаг 10. Настройте DNS

Убедитесь, что домен `mobguard.example.com` указывает на IP вашего сервера.

Проверка:

```bash
dig mobguard.example.com +short
```

или:

```bash
nslookup mobguard.example.com
```

Что считается правильным результатом:

- возвращается IP вашего сервера

### Шаг 11. Настройте внешний Caddy

Откройте конфиг Caddy и добавьте туда блок из `Caddyfile.example`.

Итоговый блок:

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

После редактирования:

```bash
sudo systemctl reload caddy
sudo systemctl status caddy
```

Что считается правильным результатом:

- `caddy` успешно перезагрузился
- в статусе нет ошибки конфигурации

### Шаг 12. Откройте панель в браузере

Откройте:

```text
https://mobguard.example.com
```

Что должно произойти:

1. открывается страница логина
2. виден Telegram login widget
3. вход разрешён только Telegram ID из `admin_tg_ids`
4. после входа доступны разделы:
   - `Queue`
   - `Rules`
   - `Quality`

### Шаг 13. Проверьте переключение темы

В боковой панели выберите:

- `System`
- `Light`
- `Dark`

Что считается правильным результатом:

- тема реально переключается
- интерфейс остаётся читаемым
- severity badges видны в обеих темах

### Шаг 14. Проверьте редактирование правил

Откройте раздел `Rules`.

Попробуйте изменить, например:

- `shadow_mode`
- `threshold_mobile`
- один ASN
- одно keyword-значение

Сохраните.

Что считается правильным результатом:

1. нет ошибки `revision conflict`
2. изменения видны в интерфейсе
3. изменения реально записались в `/opt/mobguard/runtime/config.json`

Проверка:

```bash
cat /opt/mobguard/runtime/config.json
```

---

## 6. Что делать после первого запуска

Рекомендуемый порядок rollout:

1. оставить `shadow_mode=true`
2. подождать появления реальных событий
3. открыть раздел `Quality`
4. посмотреть:
   - backlog
   - `score_zero_ratio`
   - `asn_missing_ratio`
   - noisy ASN
5. убедиться, что `core.healthy=true`
6. только после этого решать, отключать ли `shadow_mode`

Если score снова часто равен `0`, сначала проверяйте:

1. заполнен ли `IPINFO_TOKEN`
2. доступен ли `IPINFO` по `/api/health`
3. существует ли `runtime/GeoLite2-ASN.mmdb`
4. пишет ли прокси лог в нужное место

---

## 7. Как проверить health

Команда:

```bash
curl http://127.0.0.1:8080/api/health
```

На что смотреть:

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
- `score_zero_ratio` не залип на `1.0`

### Плохой сценарий

- `status = degraded`
- `core.healthy = false`
- `ipinfo_token_present = false`
- `asn_missing_ratio` слишком высокий

---

## 8. Как смотреть логи

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

## 9. Как обновлять проект

Если вы обновили код:

```bash
cd /opt/mobguard
docker compose up -d --build
```

После этого проверьте:

```bash
docker compose ps
curl http://127.0.0.1:8080/api/health
```

---

## 10. Как делать резервную копию

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

После завершения backup:

```bash
docker compose start mobguard-core
```

---

## 11. Как откатиться

Если проблема в правилах:

1. верните предыдущий `/opt/mobguard/runtime/config.json`
2. убедитесь, что `shadow_mode=true`
3. при необходимости перезапустите контейнеры:

```bash
cd /opt/mobguard
docker compose up -d --build
```

Если проблема в коде:

1. откатите файлы проекта
2. пересоберите контейнеры:

```bash
cd /opt/mobguard
docker compose up -d --build
```

---

## 12. Как пользоваться панелью

### Queue

Здесь находятся спорные кейсы, требующие модерации.

Что можно делать:

- фильтровать по статусу
- фильтровать по confidence
- фильтровать по severity
- быстро проставлять `Mobile`, `Home`, `Skip`

### Rules

Здесь редактируются:

- `Thresholds`
- `Policy`
- `ASN Lists`
- `Keywords`
- `Admin`

Все изменения сохраняются без рестарта и пишутся в `runtime/config.json`.

### Quality

Здесь смотрят:

- размер очереди модерации
- resolution ratios
- noisy ASN
- active promoted patterns
- revision правил

### Переключение темы

Поддерживаются:

- `System`
- `Light`
- `Dark`

Тема хранится локально в браузере.

---

## 13. Проверки для разработки

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

## 14. Короткий чек-лист без пояснений

```bash
sudo mkdir -p /opt/mobguard
sudo chown -R $USER:$USER /opt/mobguard
cd /opt/mobguard

# поместить сюда проект или один install-скрипт

chmod +x install.sh
./install.sh

nano .env
nano runtime/config.json

./install.sh

docker compose ps
curl http://127.0.0.1:8080/api/health

sudo systemctl reload caddy
sudo systemctl status caddy
```

---

## 15. Главное, что нужно запомнить

1. Домен панели: `https://mobguard.example.com`
2. Каталог проекта: `/opt/mobguard`
3. Секреты: `/opt/mobguard/.env`
4. Основной runtime-конфиг: `/opt/mobguard/runtime/config.json`
5. Если score снова падает к нулю — сначала проверяйте `IPINFO_TOKEN` и `/api/health`
6. Первый безопасный запуск делайте с `shadow_mode=true`
