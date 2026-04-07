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
    GeoLite2-ASN-IPv4.mmdb
    GeoLite2-ASN-IPv6.mmdb
    ip2asn-combined.tsv.gz
    health/
```

Что здесь важно:

- `.env` — секреты и токены
- `runtime/config.json` — основной редактируемый рантайм-конфиг
- `runtime/bans.db` — SQLite база
- `runtime/GeoLite2-ASN.mmdb` — одиночная ASN MMDB база
- `runtime/GeoLite2-ASN-IPv4.mmdb` + `runtime/GeoLite2-ASN-IPv6.mmdb` — split MMDB база
- `runtime/ip2asn-combined.tsv.gz` — ASN база IPtoASN в TSV формате
- `runtime/health/` — служебный каталог под health/runtime
- `Caddyfile.example` — пример конфигурации внешнего Caddy

---

## 2. Как устроен конфиг

### 2.1. Что хранится в `.env`

В `.env` должны лежать секреты, токены и опциональные install-time переключатели:

```env
TG_MAIN_BOT_TOKEN=
TG_ADMIN_BOT_TOKEN=
TG_ADMIN_BOT_USERNAME=
PANEL_TOKEN=
IPINFO_TOKEN=
# optional install-time switch: auto|oxl|dbip|maxmind|iptoasn|manual
ASN_DB_PROVIDER=auto
# optional: нужен только если выбран maxmind или auto дошёл до maxmind
MAXMIND_LICENSE_KEY=
```

Пояснения:

- `TG_MAIN_BOT_TOKEN` — основной Telegram-бот для сообщений пользователям
- `TG_ADMIN_BOT_TOKEN` — админ-бот
- `TG_ADMIN_BOT_USERNAME` — username админ-бота без `@`
- `PANEL_TOKEN` — токен доступа к Remnawave API
- `IPINFO_TOKEN` — обязательный токен IPInfo, без него score может деградировать к `0`
- `ASN_DB_PROVIDER` — необязательный install-time выбор ASN-источника; по умолчанию `auto`
- `MAXMIND_LICENSE_KEY` — необязательный ключ MaxMind, нужен только если выбран `maxmind` или `auto` дошёл до MaxMind

Обязательными для запуска `install.sh` с последующим `docker compose up -d --build` считаются только:

- `TG_MAIN_BOT_TOKEN`
- `TG_ADMIN_BOT_TOKEN`
- `TG_ADMIN_BOT_USERNAME`
- `PANEL_TOKEN`
- `IPINFO_TOKEN`

`MAXMIND_LICENSE_KEY` не блокирует установку, если ASN-источник уже лежит в `runtime/`, будет положен вручную позже или установка пока выполняется без него.

Большинство инфраструктурных путей пользователю вручную больше задавать не нужно:

- `db_file` считается константой: `/opt/mobguard/runtime/bans.db`
- `geoip_db` нормализуется к текущему runtime-dir автоматически
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

Обычно причины делятся на две группы.

### 3.1. Не заполнен `IPINFO_TOKEN`

Если `IPINFO_TOKEN` пустой:

- `IPInfo` не возвращает ASN, ISP и hostname
- `asn` часто становится `None`
- ISP определяется как `Unknown ISP`
- не срабатывают `pure_mobile_asns`, `pure_home_asns` и `mixed_asns`
- keyword-анализ сильно деградирует

Итог:

- score часто остаётся равным `0`
- кейсы массово улетают в ручную модерацию

### 3.2. Нет ASN-источника в `runtime/`

Если в `runtime/` отсутствует любой поддерживаемый ASN-источник:

- fallback по ASN работает неполно
- ASN-анализ и часть эвристик становятся менее точными
- `analysis_24h.asn_missing_ratio` может заметно расти
- score тоже может залипать ниже ожидаемого, особенно если данных от IPInfo недостаточно

Если одновременно нет и `IPINFO_TOKEN`, и ASN-источника, деградация качества анализа будет максимальной.

Теперь проект показывает это явно:

- предупреждение при старте
- статус в `/api/health`
- метрики:
  - `analysis_24h.score_zero_ratio`
  - `analysis_24h.asn_missing_ratio`

Если score снова стал массово равен `0`, в первую очередь проверяйте:

1. заполнен ли `IPINFO_TOKEN` в `.env`
2. показывает ли `/api/health` поле `ipinfo_token_present=true`
3. существует ли хотя бы один ASN-источник в `runtime/`:
   `GeoLite2-ASN.mmdb`, `GeoLite2-ASN-IPv4.mmdb` + `GeoLite2-ASN-IPv6.mmdb` или `ip2asn-combined.tsv.gz`
4. действительно ли прокси пишет лог в ожидаемое место

---

## 4. Самый простой сценарий установки

Идея установки такая:

- единственный официальный install entrypoint — корневой `install.sh`
- первый запуск может только подготовить проект: создать структуру, `.env`, `runtime/config.json` и `runtime/bans.db`
- после заполнения обязательных токенов тот же `install.sh` запускается повторно и продолжает установку
- отсутствие ASN-базы не должно выглядеть как полный блокер установки: проект можно подготовить и даже запустить без неё, но качество ASN-анализа будет ниже

Поддерживаются только два реальных сценария запуска:

- проект уже склонирован, запуск по месту: `./install.sh`
- в каталоге лежит только `install.sh`, и он сам клонирует приватный репозиторий: `./install.sh 'https://<TOKEN>@github.com/darkneeed/mobguard.git'`

### 4.1. Источники ASN-базы

`install.sh` поддерживает несколько бесплатных ASN-источников:

- `oxl` — open/free OXL, split MMDB (`GeoLite2-ASN-IPv4.mmdb` + `GeoLite2-ASN-IPv6.mmdb`)
- `dbip` — free DB-IP Lite, single MMDB (`GeoLite2-ASN.mmdb`)
- `maxmind` — free GeoLite2 ASN от MaxMind, single MMDB (`GeoLite2-ASN.mmdb`), нужен `MAXMIND_LICENSE_KEY`
- `iptoasn` — public-domain IPtoASN, combined TSV (`ip2asn-combined.tsv.gz`)
- `manual` — ничего не скачивать автоматически
- `auto` — пробовать источники по порядку `oxl -> dbip -> maxmind -> iptoasn`

Если ASN-файлы уже лежат в `runtime/`, `install.sh` использует их и ничего не перекачивает.

### 4.2. Сценарии ASN-базы

`install.sh` обрабатывает ASN-источник так:

1. если в `runtime/` уже найден поддерживаемый ASN-файл, установка продолжается без загрузки
2. если файла нет, `install.sh` пробует скачать его из выбранного `ASN_DB_PROVIDER`
3. если файла нет и загрузка не удалась или отключена, скрипт выводит предупреждение и продолжает установку без ASN-базы

В третьем сценарии можно в любой момент:

- положить вручную один из поддерживаемых файлов в `runtime/`
- выбрать `ASN_DB_PROVIDER` в `.env`
- при `maxmind` заполнить `MAXMIND_LICENSE_KEY`
- повторно запустить `./install.sh`

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
- gzip
- unzip

`curl`, `tar`, `gzip` и `unzip` нужны только для автоматической загрузки ASN-источников. Если ASN-файлы уже положены вручную, они не участвуют в анализе самого рантайма.

Проверьте:

```bash
docker --version
docker compose version
caddy version
git --version
curl --version
tar --version
gzip --version
unzip -v
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

### Шаг 3. Подготовьте `install.sh`

Есть только два поддерживаемых варианта.

#### Вариант А. Репозиторий уже склонирован

Если проект уже лежит в `/opt/mobguard`, используйте:

```bash
chmod +x /opt/mobguard/install.sh
```

#### Вариант Б. В каталоге пока только один `install.sh`

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

### Шаг 4. Запустите `install.sh` в первый раз

Если проект уже склонирован:

```bash
cd /opt/mobguard
./install.sh
```

Что делает скрипт:

1. найти исходники на месте или клонировать их из приватного git URL
2. создать `runtime/`
3. создать `runtime/health/`
4. создать `.env`, если файла нет
5. создать `runtime/config.json`, если файла нет
6. создать `runtime/bans.db`, если файла нет
7. проверить обязательные токены
8. обработать ASN-базу по мягкой логике
9. запустить `docker compose up -d --build`, только если обязательные токены уже заполнены

Что считается правильным результатом:

- появились:
  - `/opt/mobguard/.env`
  - `/opt/mobguard/runtime/config.json`
  - `/opt/mobguard/runtime/bans.db`
  - `/opt/mobguard/runtime/health/`
- скрипт не затирает уже существующие пользовательские файлы
- первый запуск может корректно закончиться только на этапе подготовки проекта

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

Заполните обязательные значения:

```env
TG_MAIN_BOT_TOKEN=...
TG_ADMIN_BOT_TOKEN=...
TG_ADMIN_BOT_USERNAME=...
PANEL_TOKEN=...
IPINFO_TOKEN=...
# optional install-time switch: auto|oxl|dbip|maxmind|iptoasn|manual
ASN_DB_PROVIDER=auto
# optional: только если выбран maxmind или auto дошёл до maxmind
MAXMIND_LICENSE_KEY=...
```

Что считается правильным результатом:

- обязательные строки не пустые
- `ASN_DB_PROVIDER=auto` подходит в большинстве случаев
- `MAXMIND_LICENSE_KEY` нужен только для MaxMind
- если ASN-источник уже лежит вручную, `MAXMIND_LICENSE_KEY` можно оставить пустым

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

### Шаг 7. Запустите `install.sh` повторно

После заполнения `.env` запустите тот же скрипт ещё раз.

Если проект уже склонирован:

```bash
cd /opt/mobguard
./install.sh
```

Теперь скрипт должен:

1. увидеть, что `.env` уже существует и не перетирать его
2. не трогать уже существующие `runtime/config.json` и `runtime/bans.db`
3. обработать ASN-источник по одному из сценариев:
   - использовать уже существующий ASN-файл из `runtime/`
   - скачать ASN-файл из выбранного `ASN_DB_PROVIDER`
   - вывести предупреждение и продолжить без ASN-базы
4. запустить `docker compose up -d --build`, если обязательные токены заполнены

Что считается правильным результатом:

- контейнеры стартовали, если обязательные токены были заполнены
- в `runtime/` появился один из поддерживаемых ASN-источников, либо его отсутствие явно объяснено предупреждением

Что проверить после шага:

```bash
ls -lh /opt/mobguard/runtime/GeoLite2-ASN.mmdb
ls -lh /opt/mobguard/runtime/GeoLite2-ASN-IPv4.mmdb
ls -lh /opt/mobguard/runtime/GeoLite2-ASN-IPv6.mmdb
ls -lh /opt/mobguard/runtime/ip2asn-combined.tsv.gz
docker compose ps
```

Если файла нет, но скрипт честно предупредил о снижении качества ASN-анализа и контейнеры поднялись, это не считается ошибкой установки.

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
3. существует ли ASN-источник в `runtime/`
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

# положить сюда уже склонированный проект или один install.sh

chmod +x install.sh
./install.sh

nano .env  # обязательные токены; ASN_DB_PROVIDER и MAXMIND_LICENSE_KEY опциональны
nano runtime/config.json

./install.sh  # продолжает установку; без ASN-базы только предупреждает

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
5. Если score снова падает к нулю — сначала проверяйте `IPINFO_TOKEN`, `/api/health` и наличие ASN-источника в `runtime/`
6. Первый безопасный запуск делайте с `shadow_mode=true`
