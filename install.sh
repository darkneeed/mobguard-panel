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
ROOT_DIR="$SCRIPT_DIR"
RUNTIME_DIR="$ROOT_DIR/runtime"
ENV_FILE="$ROOT_DIR/.env"
CONFIG_FILE="$RUNTIME_DIR/config.json"
DB_FILE="$RUNTIME_DIR/bans.db"
GEOIP_DB="$RUNTIME_DIR/GeoLite2-ASN.mmdb"
GEOIP_DB_IPV4="$RUNTIME_DIR/GeoLite2-ASN-IPv4.mmdb"
GEOIP_DB_IPV6="$RUNTIME_DIR/GeoLite2-ASN-IPv6.mmdb"
IPTOASN_TSV="$RUNTIME_DIR/ip2asn-combined.tsv.gz"
HEALTH_DIR="$RUNTIME_DIR/health"
DEFAULT_REPO_URL="${1:-${MOBGUARD_REPO_URL:-}}"
OXL_ASN_IPV4_URL_DEFAULT="https://geoip.oxl.app/file/asn_ipv4_small.mmdb.zip"
OXL_ASN_IPV6_URL_DEFAULT="https://geoip.oxl.app/file/asn_ipv6_small.mmdb.zip"
IPTOASN_URL_DEFAULT="https://iptoasn.com/data/ip2asn-combined.tsv.gz"

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
  require_cmd caddy
}

get_missing_required_env() {
  missing=""

  for key in TG_MAIN_BOT_TOKEN TG_ADMIN_BOT_TOKEN TG_ADMIN_BOT_USERNAME PANEL_TOKEN IPINFO_TOKEN; do
    eval "value=\${$key:-}"
    if [ -z "$value" ]; then
      if [ -n "$missing" ]; then
        missing="$missing "
      fi
      missing="${missing}${key}"
    fi
  done

  printf '%s' "$missing"
}

download_geolite_asn() {
  require_cmd curl
  require_cmd tar
  require_cmd mktemp

  TMP_DIR="$(mktemp -d)"
  ARCHIVE_PATH="$TMP_DIR/geolite-asn.tar.gz"
  DOWNLOAD_URL="https://download.maxmind.com/app/geoip_download?edition_id=GeoLite2-ASN&license_key=${MAXMIND_LICENSE_KEY}&suffix=tar.gz"

  info "Скачиваю GeoLite2-ASN.mmdb с MaxMind"
  if ! curl -fsSL "$DOWNLOAD_URL" -o "$ARCHIVE_PATH"; then
    rm -rf "$TMP_DIR"
    return 1
  fi

  if ! tar -xzf "$ARCHIVE_PATH" -C "$TMP_DIR"; then
    rm -rf "$TMP_DIR"
    return 1
  fi

  MMDB_PATH="$(find "$TMP_DIR" -name 'GeoLite2-ASN.mmdb' | head -n 1)"
  if [ -z "$MMDB_PATH" ]; then
    rm -rf "$TMP_DIR"
    return 1
  fi

  cp "$MMDB_PATH" "$GEOIP_DB"
  rm -rf "$TMP_DIR"
  info "GeoLite2-ASN.mmdb сохранён в $GEOIP_DB"
}

download_oxl_asn() {
  require_cmd curl
  require_cmd unzip
  require_cmd mktemp

  TMP_DIR="$(mktemp -d)"
  ARCHIVE_IPV4="$TMP_DIR/asn-ipv4.zip"
  ARCHIVE_IPV6="$TMP_DIR/asn-ipv6.zip"
  URL_IPV4="${OXL_ASN_IPV4_URL:-$OXL_ASN_IPV4_URL_DEFAULT}"
  URL_IPV6="${OXL_ASN_IPV6_URL:-$OXL_ASN_IPV6_URL_DEFAULT}"

  info "Скачиваю ASN-базы OXL (IPv4 + IPv6)"
  if ! curl -fsSL "$URL_IPV4" -o "$ARCHIVE_IPV4"; then
    rm -rf "$TMP_DIR"
    return 1
  fi
  if ! curl -fsSL "$URL_IPV6" -o "$ARCHIVE_IPV6"; then
    rm -rf "$TMP_DIR"
    return 1
  fi

  mkdir -p "$TMP_DIR/ipv4" "$TMP_DIR/ipv6"
  if ! unzip -jo "$ARCHIVE_IPV4" '*.mmdb' -d "$TMP_DIR/ipv4" >/dev/null 2>&1; then
    rm -rf "$TMP_DIR"
    return 1
  fi
  if ! unzip -jo "$ARCHIVE_IPV6" '*.mmdb' -d "$TMP_DIR/ipv6" >/dev/null 2>&1; then
    rm -rf "$TMP_DIR"
    return 1
  fi

  MMDB_IPV4_PATH="$(find "$TMP_DIR/ipv4" -name '*.mmdb' | head -n 1)"
  MMDB_IPV6_PATH="$(find "$TMP_DIR/ipv6" -name '*.mmdb' | head -n 1)"
  if [ -z "$MMDB_IPV4_PATH" ] || [ -z "$MMDB_IPV6_PATH" ]; then
    rm -rf "$TMP_DIR"
    return 1
  fi

  cp "$MMDB_IPV4_PATH" "$GEOIP_DB_IPV4"
  cp "$MMDB_IPV6_PATH" "$GEOIP_DB_IPV6"
  rm -rf "$TMP_DIR"
  info "ASN-базы OXL сохранены в $GEOIP_DB_IPV4 и $GEOIP_DB_IPV6"
}

download_dbip_asn() {
  require_cmd curl
  require_cmd gzip
  require_cmd mktemp
  require_cmd date

  TMP_DIR="$(mktemp -d)"
  ARCHIVE_PATH="$TMP_DIR/dbip-asn.mmdb.gz"
  CURRENT_MONTH="$(date -u +%Y-%m)"
  CURRENT_URL="${DBIP_ASN_URL:-https://download.db-ip.com/free/dbip-asn-lite-${CURRENT_MONTH}.mmdb.gz}"
  PREVIOUS_URL=""

  if PREVIOUS_MONTH="$(date -u -d "$(date -u +%Y-%m-01) -1 month" +%Y-%m 2>/dev/null)"; then
    if [ "$PREVIOUS_MONTH" != "$CURRENT_MONTH" ]; then
      PREVIOUS_URL="https://download.db-ip.com/free/dbip-asn-lite-${PREVIOUS_MONTH}.mmdb.gz"
    fi
  fi

  info "Скачиваю ASN-базу DB-IP Lite"
  if ! curl -fsSL "$CURRENT_URL" -o "$ARCHIVE_PATH"; then
    if [ -n "$PREVIOUS_URL" ] && ! curl -fsSL "$PREVIOUS_URL" -o "$ARCHIVE_PATH"; then
      rm -rf "$TMP_DIR"
      return 1
    elif [ -z "$PREVIOUS_URL" ]; then
      rm -rf "$TMP_DIR"
      return 1
    fi
  fi

  if ! gzip -dc "$ARCHIVE_PATH" > "$TMP_DIR/GeoLite2-ASN.mmdb"; then
    rm -rf "$TMP_DIR"
    return 1
  fi

  cp "$TMP_DIR/GeoLite2-ASN.mmdb" "$GEOIP_DB"
  rm -rf "$TMP_DIR"
  info "ASN-база DB-IP Lite сохранена в $GEOIP_DB"
}

download_iptoasn() {
  require_cmd curl
  require_cmd gzip
  require_cmd mktemp

  TMP_DIR="$(mktemp -d)"
  ARCHIVE_PATH="$TMP_DIR/ip2asn-combined.tsv.gz"
  DOWNLOAD_URL="${IPTOASN_URL:-$IPTOASN_URL_DEFAULT}"

  info "Скачиваю ASN-базу IPtoASN (combined TSV)"
  if ! curl -fsSL "$DOWNLOAD_URL" -o "$ARCHIVE_PATH"; then
    rm -rf "$TMP_DIR"
    return 1
  fi

  if ! gzip -t "$ARCHIVE_PATH" >/dev/null 2>&1; then
    rm -rf "$TMP_DIR"
    return 1
  fi

  cp "$ARCHIVE_PATH" "$IPTOASN_TSV"
  rm -rf "$TMP_DIR"
  info "ASN-база IPtoASN сохранена в $IPTOASN_TSV"
}

find_existing_asn_source() {
  found=""

  if [ -f "$GEOIP_DB" ]; then
    found="$GEOIP_DB"
  fi
  if [ -f "$GEOIP_DB_IPV4" ]; then
    found="${found}${found:+, }$GEOIP_DB_IPV4"
  fi
  if [ -f "$GEOIP_DB_IPV6" ]; then
    found="${found}${found:+, }$GEOIP_DB_IPV6"
  fi
  if [ -f "$IPTOASN_TSV" ]; then
    found="${found}${found:+, }$IPTOASN_TSV"
  fi

  printf '%s' "$found"
}

print_asn_missing_warning() {
  provider="$1"

  warn "ASN-база не найдена в runtime."
  warn "Поддерживаемые файлы: $GEOIP_DB, $GEOIP_DB_IPV4 + $GEOIP_DB_IPV6, $IPTOASN_TSV."
  warn "Установка продолжится без ASN-базы, но ASN-анализ и качество score будут ниже."
  if [ "$provider" = "maxmind" ] || [ "$provider" = "auto" ]; then
    warn "Можно заполнить MAXMIND_LICENSE_KEY в $ENV_FILE и повторно запустить install.sh."
  fi
  warn "Также можно выбрать ASN_DB_PROVIDER=oxl|dbip|maxmind|iptoasn|manual или положить один из файлов вручную и повторно запустить install.sh."
}

try_auto_download_asn() {
  if download_oxl_asn; then
    info "Использую ASN-провайдер OXL"
    return 0
  fi
  warn "Не удалось скачать ASN-базу OXL, пробую следующий источник."

  if download_dbip_asn; then
    info "Использую ASN-провайдер DB-IP Lite"
    return 0
  fi
  warn "Не удалось скачать ASN-базу DB-IP Lite, пробую следующий источник."

  if [ -n "${MAXMIND_LICENSE_KEY:-}" ]; then
    if download_geolite_asn; then
      info "Использую ASN-провайдер MaxMind GeoLite2 ASN"
      return 0
    fi
    warn "Не удалось скачать ASN-базу MaxMind, пробую следующий источник."
  fi

  if download_iptoasn; then
    info "Использую ASN-провайдер IPtoASN"
    return 0
  fi

  return 1
}

handle_asn_database() {
  existing_asn_source="$(find_existing_asn_source)"
  if [ -n "$existing_asn_source" ]; then
    info "Найден существующий ASN-источник: $existing_asn_source"
    return
  fi

  provider="${ASN_DB_PROVIDER:-auto}"

  case "$provider" in
    auto)
      if ! try_auto_download_asn; then
        print_asn_missing_warning "$provider"
      fi
      ;;
    oxl)
      if ! download_oxl_asn; then
        print_asn_missing_warning "$provider"
      fi
      ;;
    dbip)
      if ! download_dbip_asn; then
        print_asn_missing_warning "$provider"
      fi
      ;;
    maxmind)
      if [ -z "${MAXMIND_LICENSE_KEY:-}" ] || ! download_geolite_asn; then
        print_asn_missing_warning "$provider"
      fi
      ;;
    iptoasn)
      if ! download_iptoasn; then
        print_asn_missing_warning "$provider"
      fi
      ;;
    manual)
      print_asn_missing_warning "$provider"
      ;;
    *)
      warn "Неизвестный ASN_DB_PROVIDER=$provider. Поддерживаются: auto, oxl, dbip, maxmind, iptoasn, manual."
      print_asn_missing_warning "$provider"
      ;;
  esac
}

print_missing_env_warning() {
  missing="$1"

  [ -n "$missing" ] || return

  warn "Не заполнены обязательные переменные в $ENV_FILE: $missing"
  warn "Подготовительный этап завершён. Заполните .env и повторно запустите install.sh для запуска docker compose."
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
  missing_required="$(get_missing_required_env)"
  handle_asn_database
  if [ -n "$missing_required" ]; then
    print_missing_env_warning "$missing_required"
    print_next_steps
    exit 0
  fi
  start_stack
  print_next_steps
}

main "$@"
