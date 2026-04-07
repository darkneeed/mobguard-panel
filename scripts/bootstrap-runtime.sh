#!/usr/bin/env sh
set -eu

info() {
  printf '%s\n' "[INFO] $*"
}

warn() {
  printf '%s\n' "[WARN] $*" >&2
}

fail() {
  printf '%s\n' "[ERROR] $*" >&2
  exit 1
}

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || fail "Не найдена команда: $1"
}

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"

if [ -f "$SCRIPT_DIR/../docker-compose.yml" ] && [ -f "$SCRIPT_DIR/../mobguard.py" ]; then
  ROOT_DIR="$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)"
else
  ROOT_DIR="$SCRIPT_DIR"
fi

RUNTIME_DIR="$ROOT_DIR/runtime"
ENV_FILE="$ROOT_DIR/.env"
CONFIG_FILE="$RUNTIME_DIR/config.json"
DB_FILE="$RUNTIME_DIR/bans.db"
GEOIP_DB="$RUNTIME_DIR/GeoLite2-ASN.mmdb"
HEALTH_DIR="$RUNTIME_DIR/health"
DEFAULT_REPO_URL="${1:-${MOBGUARD_REPO_URL:-}}"

clone_repo_if_needed() {
  if [ -f "$ROOT_DIR/docker-compose.yml" ] && [ -f "$ROOT_DIR/mobguard.py" ]; then
    info "Исходники проекта уже найдены в $ROOT_DIR"
    return
  fi

  [ -n "$DEFAULT_REPO_URL" ] || fail "Исходники не найдены. Передайте URL приватного репозитория первым аргументом или через MOBGUARD_REPO_URL."

  require_cmd git
  require_cmd mktemp

  TMP_DIR="$(mktemp -d)"
  info "Клонирую репозиторий во временную директорию"
  git clone "$DEFAULT_REPO_URL" "$TMP_DIR/repo"

  [ -f "$TMP_DIR/repo/docker-compose.yml" ] || fail "После клонирования не найден docker-compose.yml"
  [ -f "$TMP_DIR/repo/mobguard.py" ] || fail "После клонирования не найден mobguard.py"

  rm -rf "$TMP_DIR/repo/.git"
  cp -R "$TMP_DIR/repo/." "$ROOT_DIR/"
  rm -rf "$TMP_DIR"
  info "Исходники проекта скопированы в $ROOT_DIR"
}

ensure_structure() {
  mkdir -p "$RUNTIME_DIR" "$HEALTH_DIR"

  if [ ! -f "$CONFIG_FILE" ]; then
    cp "$ROOT_DIR/config.json" "$CONFIG_FILE"
    info "Создан runtime/config.json из шаблона"
  else
    info "Найден существующий runtime/config.json"
  fi

  if [ ! -f "$ENV_FILE" ]; then
    cp "$ROOT_DIR/.env.example" "$ENV_FILE"
    info "Создан .env из шаблона .env.example"
  else
    info "Найден существующий .env"
  fi

  if [ ! -f "$DB_FILE" ]; then
    : > "$DB_FILE"
    info "Создан пустой runtime/bans.db"
  else
    info "Найдена существующая база runtime/bans.db"
  fi
}

load_env_if_exists() {
  if [ -f "$ENV_FILE" ]; then
    set -a
    # shellcheck disable=SC1090
    . "$ENV_FILE"
    set +a
  fi
}

require_base_dependencies() {
  require_cmd docker
  docker compose version >/dev/null 2>&1 || fail "Не найден docker compose plugin"
  require_cmd curl
  require_cmd tar
  require_cmd caddy
}

check_required_env() {
  missing=""

  for key in TG_MAIN_BOT_TOKEN TG_ADMIN_BOT_TOKEN TG_ADMIN_BOT_USERNAME PANEL_TOKEN IPINFO_TOKEN; do
    eval "value=\${$key:-}"
    if [ -z "$value" ]; then
      missing="$missing $key"
    fi
  done

  if [ ! -f "$GEOIP_DB" ]; then
    if [ -z "${MAXMIND_LICENSE_KEY:-}" ]; then
      missing="$missing MAXMIND_LICENSE_KEY"
    fi
  fi

  if [ -n "$missing" ]; then
    warn "Не заполнены обязательные переменные в .env:$missing"
    warn "Откройте $ENV_FILE, заполните значения и запустите скрипт повторно."
    exit 1
  fi
}

download_geolite_asn() {
  if [ -f "$GEOIP_DB" ]; then
    info "GeoLite2-ASN.mmdb уже существует"
    return
  fi

  [ -n "${MAXMIND_LICENSE_KEY:-}" ] || fail "MAXMIND_LICENSE_KEY не задан, GeoLite2-ASN.mmdb не может быть загружен"

  TMP_DIR="$(mktemp -d)"
  ARCHIVE_PATH="$TMP_DIR/geolite-asn.tar.gz"
  DOWNLOAD_URL="https://download.maxmind.com/app/geoip_download?edition_id=GeoLite2-ASN&license_key=${MAXMIND_LICENSE_KEY}&suffix=tar.gz"

  info "Скачиваю GeoLite2-ASN.mmdb с MaxMind"
  curl -fsSL "$DOWNLOAD_URL" -o "$ARCHIVE_PATH"
  tar -xzf "$ARCHIVE_PATH" -C "$TMP_DIR"

  MMDB_PATH="$(find "$TMP_DIR" -name 'GeoLite2-ASN.mmdb' | head -n 1)"
  [ -n "$MMDB_PATH" ] || fail "После распаковки не найден файл GeoLite2-ASN.mmdb"

  cp "$MMDB_PATH" "$GEOIP_DB"
  rm -rf "$TMP_DIR"
  info "GeoLite2-ASN.mmdb сохранён в $GEOIP_DB"
}

print_next_steps() {
  printf '%s\n' ""
  printf '%s\n' "Следующие шаги:"
  printf '%s\n' "1. Проверьте .env: $ENV_FILE"
  printf '%s\n' "2. Проверьте runtime/config.json: $CONFIG_FILE"
  printf '%s\n' "3. Откройте README.md и выполните дальнейшие шаги по настройке DNS и Caddy"
}

start_stack() {
  info "Запускаю docker compose"
  (
    cd "$ROOT_DIR"
    docker compose up -d --build
  )
  info "Контейнеры запущены"
  (
    cd "$ROOT_DIR"
    docker compose ps
  )
}

main() {
  info "Рабочий каталог: $ROOT_DIR"

  clone_repo_if_needed
  ensure_structure
  load_env_if_exists
  require_base_dependencies
  check_required_env
  download_geolite_asn
  start_stack
  print_next_steps
}

main "$@"
