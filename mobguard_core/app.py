import asyncio
import json
import logging
import os
import re
import sqlite3
import aiohttp
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Tuple, Dict, Any, List, Set

# Compatibility-only runtime:
# panel/shared logic is the canonical implementation. Keep this module working,
# but avoid introducing new primary business logic here.

from aiogram import Bot, Dispatcher
from aiogram.filters import Command, CommandObject
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from behavioral_analyzers import BehavioralEngine
from ipinfo_api import ipinfo_api
from mobguard_platform import (
    apply_remote_restriction_state_async,
    apply_remote_access_state_async,
    apply_remote_traffic_cap_async,
    build_auto_restriction_state,
    DecisionBundle,
    DEFAULT_TRAFFIC_LIMIT_STRATEGY,
    PlatformStore,
    load_runtime_context,
    normalize_restriction_mode,
    remote_access_squad_name,
    review_reason_for_bundle,
    restore_remote_restriction_state_async,
    resolve_asn_source,
    SQUAD_RESTRICTION_MODE,
    should_warning_only,
    TRAFFIC_CAP_RESTRICTION_MODE,
)
from mobguard_platform.template_utils import render_optional_template
from mobguard_platform.runtime_admin_defaults import (
    ENFORCEMENT_SETTINGS_DEFAULTS,
    ENFORCEMENT_TEMPLATE_DEFAULTS,
    normalize_telegram_runtime_settings,
    telegram_event_notifications_enabled,
    telegram_notification_setting,
)
from mobguard_core.scoring import ScoringContext, ScoringDependencies, evaluate_mobile_network

# ================= CONFIGURATION & SETUP =================

ROOT_DIR = Path(__file__).resolve().parents[1]
try:
    RUNTIME_CONTEXT = load_runtime_context(ROOT_DIR, os.getenv("BAN_SYSTEM_DIR"))
except FileNotFoundError as exc:
    print(f"CRITICAL: {exc}")
    raise SystemExit(1) from exc

BAN_SYSTEM_DIR = str(RUNTIME_CONTEXT.runtime_dir)
ENV_PATH = str(RUNTIME_CONTEXT.env_path)
CONFIG_PATH = str(RUNTIME_CONTEXT.config_path)
CONFIG = RUNTIME_CONTEXT.config

# Env variables
TG_MAIN_BOT_TOKEN = os.getenv("TG_MAIN_BOT_TOKEN")
TG_ADMIN_BOT_TOKEN = os.getenv("TG_ADMIN_BOT_TOKEN")
TG_ADMIN_CHAT_ID = CONFIG['settings'].get('tg_admin_chat_id', "-1003304969829")
TG_TOPIC_ID = CONFIG['settings'].get('tg_topic_id', 58)
PANEL_TOKEN = os.getenv("PANEL_TOKEN")

# Global State
DEBUG_LEVEL = CONFIG['settings'].get('debug_level', 'OFF').upper()
DEBUG_MODE = DEBUG_LEVEL != 'OFF'
DRY_RUN = CONFIG['settings'].get('dry_run', True)
EXEMPT_UUIDS: Set[str] = set(str(x) for x in CONFIG.get('exempt_uuids', []))

# Режимы модерации
MANUAL_REVIEW_UNSURE = False  # Mixed ASN HOME → ручная проверка
MANUAL_REVIEW_ALL_BANS = False  # Все баны → утверждение

# IP-API Rate Limiting
IP_API_RATE_LIMITED = False
IP_API_RATE_LIMIT_UNTIL = None
IP_API_PENDING_POOL: Set[str] = set()

_STATS_BUFFER: Dict[str, Any] = {
    'asn': {},          # {asn_int: {'mobile': N, 'home': N, 'unsure': N}}
    'keyword': {},      # {keyword_str: {'mobile': N, 'home': N}}
    'potential_kw': {}, # {word_str: count}
}

UNSURE_NOTIFIED: Set[str] = set()
PROCESSING_LOCK: Set[str] = set()

# Telegram flood control - FIX БАГ #2
TG_MESSAGE_QUEUE: asyncio.Queue = None
TG_LAST_MESSAGE_TIME = datetime.now()
TG_MIN_INTERVAL = float(CONFIG['settings'].get('telegram_message_min_interval_seconds', 1.0))

# Regex Compilation
REGEX_UUID = re.compile(r'email: (\S+)')
REGEX_IP = re.compile(r'from (?:tcp:|udp:)?(\d+\.\d+\.\d+\.\d+)')

# Logging
logging.basicConfig(
    level=logging.INFO if not DEBUG_MODE else logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("MobGuard")

def _dbg(level: str, msg: str):
    if not DEBUG_MODE: return
    if DEBUG_LEVEL == 'FULL':
        logger.debug(msg)
    elif DEBUG_LEVEL == 'ANALYSIS' and level in ('ANALYSIS', 'IMPORTANT'):
        logger.debug(msg)
    elif DEBUG_LEVEL == 'IMPORTANT' and level == 'IMPORTANT':
        logger.debug(msg)

# ================= DATABASE MANAGER (ASYNC WRAPPER) =================

class DatabaseManager:
    def __init__(self, db_path: str):
        self.db_path = db_path

    def init_db(self):
        with sqlite3.connect(self.db_path, check_same_thread=False) as conn:
            c = conn.cursor()
            c.execute("PRAGMA journal_mode=WAL")
            c.execute("PRAGMA busy_timeout = 5000")
            
            # Core tables
            c.execute('''CREATE TABLE IF NOT EXISTS violations
                         (uuid text primary key, strikes int, unban_time timestamp, 
                          last_forgiven timestamp, last_strike_time timestamp,
                          warning_time timestamp, warning_count int DEFAULT 0,
                          restriction_mode text DEFAULT 'SQUAD',
                          saved_traffic_limit_bytes int,
                          saved_traffic_limit_strategy text,
                          applied_traffic_limit_bytes int)''')
            c.execute('''CREATE TABLE IF NOT EXISTS violation_history
                         (id integer primary key autoincrement, uuid text, ip text, 
                          isp text, asn int, tag text, strike_number int, 
                          punishment_duration int, timestamp timestamp,
                          FOREIGN KEY (uuid) REFERENCES violations(uuid))''')
            c.execute('''CREATE TABLE IF NOT EXISTS manual_traffic_cap_overrides
                         (uuid text primary key, saved_traffic_limit_bytes int,
                          saved_traffic_limit_strategy text, applied_traffic_limit_bytes int,
                          updated_at timestamp)''')
            c.execute('''CREATE TABLE IF NOT EXISTS active_trackers
                         (key text primary key, start_time timestamp, last_seen timestamp)''')
            c.execute('''CREATE TABLE IF NOT EXISTS ip_decisions
                         (ip text primary key, status text, 
                          confidence text, details text, asn int, expires timestamp, log_json text)''')
            c.execute('''CREATE TABLE IF NOT EXISTS unsure_patterns
                         (ip_pattern text primary key, decision text, timestamp timestamp)''')
            
            c.execute('''CREATE TABLE IF NOT EXISTS unsure_learning
                         (id integer primary key autoincrement,
                          pattern_type text,
                          pattern_value text,
                          decision text,
                          confidence int,
                          timestamp timestamp,
                          UNIQUE(pattern_type, pattern_value, decision))''')

            c.execute('''CREATE TABLE IF NOT EXISTS subnet_evidence
                         (subnet text primary key, mobile_count int default 0, 
                          home_count int default 0, last_updated timestamp)''')
            c.execute('''CREATE TABLE IF NOT EXISTS ip_history
                         (id integer primary key autoincrement, uuid text, ip text, 
                          timestamp timestamp)''')
            
            c.execute('''CREATE TABLE IF NOT EXISTS daily_stats
                         (id integer primary key autoincrement,
                          stat_type text NOT NULL,
                          stat_key text NOT NULL,
                          sub_key text NOT NULL DEFAULT '',
                          value integer NOT NULL DEFAULT 0,
                          date text NOT NULL,
                          UNIQUE(stat_type, stat_key, sub_key, date))''')
            
            # Indexes
            c.execute("CREATE INDEX IF NOT EXISTS idx_trackers_last_seen ON active_trackers(last_seen)")
            c.execute("CREATE INDEX IF NOT EXISTS idx_decisions_expires ON ip_decisions(expires)")
            c.execute("CREATE INDEX IF NOT EXISTS idx_unsure_timestamp ON unsure_patterns(timestamp)")
            c.execute("CREATE INDEX IF NOT EXISTS idx_learning_pattern ON unsure_learning(pattern_type, pattern_value)")
            c.execute("CREATE INDEX IF NOT EXISTS idx_ip_history_uuid ON ip_history(uuid)")
            
            # Migrations - idempotent
            c.execute("PRAGMA table_info(violations)")
            cols = [col[1] for col in c.fetchall()]
            if 'warning_time' not in cols:
                c.execute("ALTER TABLE violations ADD COLUMN warning_time timestamp")
            if 'restriction_mode' not in cols:
                c.execute("ALTER TABLE violations ADD COLUMN restriction_mode text DEFAULT 'SQUAD'")
            if 'saved_traffic_limit_bytes' not in cols:
                c.execute("ALTER TABLE violations ADD COLUMN saved_traffic_limit_bytes int")
            if 'saved_traffic_limit_strategy' not in cols:
                c.execute("ALTER TABLE violations ADD COLUMN saved_traffic_limit_strategy text")
            if 'applied_traffic_limit_bytes' not in cols:
                c.execute("ALTER TABLE violations ADD COLUMN applied_traffic_limit_bytes int")
            
            c.execute("PRAGMA table_info(ip_decisions)")
            cols = [col[1] for col in c.fetchall()]
            if 'log_json' not in cols:
                c.execute("ALTER TABLE ip_decisions ADD COLUMN log_json text")
            if 'bundle_json' not in cols:
                c.execute("ALTER TABLE ip_decisions ADD COLUMN bundle_json text")
            
            # Migration: is_mobile → status
            if 'is_mobile' in cols and 'status' not in cols:
                c.execute("ALTER TABLE ip_decisions RENAME COLUMN is_mobile TO status")
            elif 'status' not in cols:
                c.execute("ALTER TABLE ip_decisions ADD COLUMN status text")
                
            conn.commit()

    def _execute(self, query: str, args: tuple):
        with sqlite3.connect(self.db_path, check_same_thread=False) as conn:
            conn.execute("PRAGMA busy_timeout = 5000")
            c = conn.cursor()
            c.execute(query, args)
            conn.commit()
            return c.fetchall()

    def _fetch_one(self, query: str, args: tuple):
        with sqlite3.connect(self.db_path, check_same_thread=False) as conn:
            conn.execute("PRAGMA busy_timeout = 5000")
            c = conn.cursor()
            c.execute(query, args)
            return c.fetchone()
            
    def _fetch_all(self, query: str, args: tuple):
        with sqlite3.connect(self.db_path, check_same_thread=False) as conn:
            conn.execute("PRAGMA busy_timeout = 5000")
            c = conn.cursor()
            c.execute(query, args)
            return c.fetchall()

    async def execute(self, query: str, args: tuple = ()):
        return await asyncio.get_running_loop().run_in_executor(None, self._execute, query, args)

    async def fetch_one(self, query: str, args: tuple = ()):
        return await asyncio.get_running_loop().run_in_executor(None, self._fetch_one, query, args)

    async def fetch_all(self, query: str, args: tuple = ()):
        return await asyncio.get_running_loop().run_in_executor(None, self._fetch_all, query, args)

    # --- Persistence Methods ---
    
    async def get_tracker_start(self, key: str) -> Optional[datetime]:
        row = await self.fetch_one("SELECT start_time FROM active_trackers WHERE key=?", (key,))
        return datetime.fromisoformat(row[0]) if row else None

    async def update_tracker(self, key: str, start_time: datetime):
        now = datetime.now().isoformat()
        await self.execute("""INSERT INTO active_trackers (key, start_time, last_seen) 
                              VALUES (?, ?, ?)
                              ON CONFLICT(key) DO UPDATE SET last_seen=?""", 
                           (key, start_time.isoformat(), now, now))

    async def delete_tracker(self, key: str):
        await self.execute("DELETE FROM active_trackers WHERE key=?", (key,))
        
    async def clear_trackers_for_uuid(self, uuid: str) -> int:
        rows = await self.fetch_all("SELECT key FROM active_trackers WHERE key LIKE ?", (f"{uuid}:%",))
        count = len(rows) if rows else 0
        if count > 0:
            await self.execute("DELETE FROM active_trackers WHERE key LIKE ?", (f"{uuid}:%",))
        return count

    async def get_cached_decision(self, ip: str) -> Optional[Dict]:
        row = await self.fetch_one(
            "SELECT status, confidence, details, asn, expires, log_json, bundle_json FROM ip_decisions WHERE ip=?",
            (ip,),
        )
        if row:
            if datetime.fromisoformat(row[4]) > datetime.now():
                log = json.loads(row[5]) if row[5] else []
                bundle = json.loads(row[6]) if len(row) > 6 and row[6] else None
                return {
                    'status': row[0],
                    'confidence': row[1],
                    'isp': row[2],
                    'asn': row[3],
                    'log': log,
                    'bundle': bundle,
                }
        return None

    async def cache_decision(self, ip: str, data: Dict):
        expires = datetime.now() + timedelta(days=3)
        log_json = json.dumps(data.get('log', []), ensure_ascii=False)
        bundle_json = json.dumps(data.get('bundle'), ensure_ascii=False) if data.get('bundle') else None
        await self.execute(
            """INSERT OR REPLACE INTO ip_decisions (ip, status, confidence, details, asn, expires, log_json, bundle_json)
                              VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                ip,
                data['status'],
                data['confidence'],
                data['details'],
                data.get('asn'),
                expires.isoformat(),
                log_json,
                bundle_json,
            ),
        )

    async def get_unsure_pattern(self, ip: str) -> Optional[str]:
        """Check if this IP has a cached manual decision"""
        row = await self.fetch_one("SELECT decision FROM unsure_patterns WHERE ip_pattern=?", (ip,))
        return row[0] if row else None

    async def set_unsure_pattern(self, ip: str, decision: str):
        """Save manual decision for UNSURE IP"""
        now = datetime.now().isoformat()
        await self.execute("""INSERT OR REPLACE INTO unsure_patterns (ip_pattern, decision, timestamp) 
                              VALUES (?, ?, ?)""", (ip, decision, now))

    async def cleanup_old_unsure_patterns(self, days: int = 7):
        """Remove unsure patterns older than X days"""
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        await self.execute("DELETE FROM unsure_patterns WHERE timestamp < ?", (cutoff,))

    async def invalidate_ip_cache(self, ip: str):
        await self.execute("DELETE FROM ip_decisions WHERE ip=?", (ip,))
    
    async def add_learning_pattern(self, pattern_type: str, pattern_value: str, decision: str):
        """Добавляет паттерн в базу обучения"""
        now = datetime.now().isoformat()
        await self.execute("""
            INSERT INTO unsure_learning (pattern_type, pattern_value, decision, confidence, timestamp)
            VALUES (?, ?, ?, 1, ?)
            ON CONFLICT(pattern_type, pattern_value, decision) 
            DO UPDATE SET confidence = confidence + 1, timestamp = ?
        """, (pattern_type, pattern_value, decision, now, now))
    
    async def get_learning_confidence(self, pattern_type: str, pattern_value: str, decision: str) -> int:
        """Получает уверенность для паттерна"""
        row = await self.fetch_one("""
            SELECT confidence FROM unsure_learning 
            WHERE pattern_type = ? AND pattern_value = ? AND decision = ?
        """, (pattern_type, pattern_value, decision))
        return row[0] if row else 0
    
    async def get_learning_stats(self):
        """Статистика обучения"""
        rows = await self.fetch_all("""
            SELECT pattern_type, COUNT(*) as cnt, SUM(confidence) as total_conf
            FROM unsure_learning
            GROUP BY pattern_type
        """, ())
        return {row[0]: {'count': row[1], 'confidence': row[2]} for row in rows}

        # --- Behavioral Analysis Support Methods ---
    
    def get_subnet(self, ip: str) -> str:
        return ip.rsplit('.', 1)[0]

    async def count_concurrent_users(self, ip: str, minutes: int = 15) -> int:
        cutoff = (datetime.now() - timedelta(minutes=minutes)).isoformat()
        query = "SELECT COUNT(DISTINCT SUBSTR(key, 1, INSTR(key, ':')-1)) FROM active_trackers WHERE key LIKE ? AND last_seen > ?"
        row = await self.fetch_one(query, (f"%:{ip}", cutoff))
        return row[0] if row else 0

    async def get_churn_rate(self, uuid: str, hours: int) -> int:
        cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()
        row = await self.fetch_one("SELECT COUNT(DISTINCT ip) FROM ip_history WHERE uuid=? AND timestamp > ?", (uuid, cutoff))
        return row[0] if row else 0

    async def get_session_lifetime(self, uuid: str, ip: str) -> float:
        key = f"{uuid}:{ip}"
        row = await self.fetch_one("SELECT start_time, last_seen FROM active_trackers WHERE key=?", (key,))
        if row:
            start = datetime.fromisoformat(row[0])
            last = datetime.fromisoformat(row[1])
            return (last - start).total_seconds() / 3600.0
        return 0.0

    async def record_subnet_signal(self, ip: str, uuid: str, signal: str):
        subnet = self.get_subnet(ip)
        col = "mobile_count" if signal == "MOBILE" else "home_count"
        now = datetime.now().isoformat()
        await self.execute(f"""INSERT INTO subnet_evidence (subnet, mobile_count, home_count, last_updated)
                               VALUES (?, {'1' if signal=='MOBILE' else '0'}, {'1' if signal=='HOME' else '0'}, ?)
                               ON CONFLICT(subnet) DO UPDATE SET {col} = {col} + 1, last_updated=?""",
                           (subnet, now, now))

    async def get_subnet_evidence(self, ip: str) -> Dict[str, int]:
        subnet = self.get_subnet(ip)
        row = await self.fetch_one("SELECT mobile_count, home_count FROM subnet_evidence WHERE subnet=?", (subnet,))
        if row:
            return {'MOBILE': row[0], 'HOME': row[1]}
        return {'MOBILE': 0, 'HOME': 0}

    async def update_ip_history(self, uuid: str, ip: str):
        now = datetime.now().isoformat()
        await self.execute("INSERT INTO ip_history (uuid, ip, timestamp) VALUES (?, ?, ?)", (uuid, ip, now))
    
    async def update_session(self, uuid: str, ip: str, tag: str):
        key = f"{uuid}:{ip}"
        now = datetime.now()
        await self.update_tracker(key, now)

    # --- Методы для ежедневной статистики (daily_stats) ---

    async def increment_daily_stat(self, stat_type: str, stat_key: str, sub_key: str = '', amount: int = 1):
        """Увеличивает счётчик в таблице daily_stats для текущей даты."""
        today = datetime.now().strftime('%Y-%m-%d')
        await self.execute("""
            INSERT INTO daily_stats (stat_type, stat_key, sub_key, value, date)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(stat_type, stat_key, sub_key, date)
            DO UPDATE SET value = value + ?
        """, (stat_type, stat_key, sub_key, amount, today, amount))

    async def get_daily_stats(self, stat_type: str, date: Optional[str] = None) -> list:
        """Возвращает все записи для указанного типа статистики за дату (по умолчанию — сегодня)."""
        if date is None:
            date = datetime.now().strftime('%Y-%m-%d')
        return await self.fetch_all(
            "SELECT stat_key, sub_key, value FROM daily_stats WHERE stat_type=? AND date=?",
            (stat_type, date)
        )

    async def clear_daily_stats(self, date: Optional[str] = None):
        """Очищает статистику за указанную дату (по умолчанию — сегодня)."""
        if date is None:
            date = datetime.now().strftime('%Y-%m-%d')
        await self.execute("DELETE FROM daily_stats WHERE date=?", (date,))

    async def cleanup_old_daily_stats(self, days: int = 7):
        """Удаляет записи статистики старше N дней."""
        cutoff = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
        await self.execute("DELETE FROM daily_stats WHERE date < ?", (cutoff,))

db = DatabaseManager(CONFIG['settings']['db_file'])
behavioral_engine = BehavioralEngine(db, CONFIG)
platform_store = PlatformStore(CONFIG['settings']['db_file'], CONFIG, CONFIG_PATH)

# Передаём конфиг в ipinfo_api, чтобы is_datacenter использовал exclude_isp_keywords из конфига
ipinfo_api.set_config(CONFIG)

# ================= API & UTILS LAYER =================

class PanelAPI:
    def __init__(self, base_url: str, token: str):
        self.base_url = base_url
        self.headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        self.last_error: Optional[str] = None
        self._uuid_cache: Dict[str, Dict] = {}
        self._tg_cache: Dict[int, str] = {}
        self._internal_squad_uuid_cache: Dict[str, str] = {}
        # Общая сессия — устанавливается извне через set_session()
        self._session: Optional[aiohttp.ClientSession] = None

    def set_session(self, session: aiohttp.ClientSession):
        """Принимает общую aiohttp-сессию для повторного использования соединений (Keep-Alive)."""
        self._session = session

    async def get_user_data(self, identifier: str | int) -> Optional[Dict]:
        str_id = str(identifier).strip()
        self.last_error = None
        
        if len(str_id) > 20 and '-' in str_id:
            if str_id in self._uuid_cache: return self._uuid_cache[str_id]
            endpoint = f"/api/users/{str_id}"
        elif str_id.isdigit():
            tg_id = int(str_id)
            if tg_id in self._tg_cache: return self._uuid_cache.get(self._tg_cache[tg_id])
            endpoint = f"/api/users/by-id/{str_id}"
        else:
             endpoint = f"/api/users/by-id/{str_id}"

        _own_session = None
        if self._session and not self._session.closed:
            session = self._session
        else:
            _own_session = aiohttp.ClientSession()
            session = _own_session
        
        try:
            try:
                async with session.get(f"{self.base_url}{endpoint}", headers=self.headers, timeout=5) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        user = data.get('response', data)
                        if isinstance(user, list): user = user[0] if user else None
                        
                        if user and user.get('uuid'):
                            self._cache_user(user)
                            return user
                    
                    if str_id.isdigit() and "by-id" in endpoint:
                        endpoint_tg = f"/api/users/by-telegram-id/{str_id}"
                        async with session.get(f"{self.base_url}{endpoint_tg}", headers=self.headers, timeout=5) as resp2:
                            if resp2.status == 200:
                                data = await resp2.json()
                                user = data.get('response', data)
                                if isinstance(user, list): user = user[0] if user else None
                                if user:
                                    self._cache_user(user)
                                    return user
            except Exception as e:
                self.last_error = f"Panel lookup failed for '{str_id}': {e}"
                logger.error(f"PanelAPI Error for user '{str_id}': {type(e).__name__}: {e}")
        finally:
            if _own_session:
                await _own_session.close()
        return None

    def _cache_user(self, user: Dict):
        uuid = user.get('uuid')
        if uuid:
            self._uuid_cache[uuid] = user
            if user.get('telegramId'):
                self._tg_cache[int(user['telegramId'])] = uuid
            for squad in user.get('activeInternalSquads', []):
                if isinstance(squad, dict):
                    name = str(squad.get('name', '')).strip()
                    squad_uuid = str(squad.get('uuid', '')).strip()
                    if name and squad_uuid:
                        self._internal_squad_uuid_cache[name] = squad_uuid

    async def list_internal_squads(self) -> List[Dict[str, Any]]:
        url = f"{self.base_url}/api/internal-squads"
        _own_session = None
        if self._session and not self._session.closed:
            session = self._session
        else:
            _own_session = aiohttp.ClientSession()
            session = _own_session
        try:
            try:
                async with session.get(url, headers=self.headers, timeout=5) as resp:
                    if resp.status != 200:
                        self.last_error = f"Internal squads request failed with HTTP {resp.status}"
                        return []
                    payload = await resp.json()
                    response = payload.get('response', payload)
                    if isinstance(response, dict):
                        squads = response.get('internalSquads', [])
                    elif isinstance(response, list):
                        squads = response
                    else:
                        squads = []
                    result = [item for item in squads if isinstance(item, dict)]
                    self._internal_squad_uuid_cache.update(
                        {
                            str(item.get('name', '')).strip(): str(item.get('uuid', '')).strip()
                            for item in result
                            if str(item.get('name', '')).strip() and str(item.get('uuid', '')).strip()
                        }
                    )
                    self.last_error = None
                    return result
            except Exception as e:
                self.last_error = f"Internal squads request failed: {e}"
                logger.error(f"Internal squads request error: {e}")
                return []
        finally:
            if _own_session:
                await _own_session.close()

    async def resolve_internal_squad_uuid(self, squad_name: str) -> Optional[str]:
        normalized_name = str(squad_name or "").strip()
        if not normalized_name:
            self.last_error = "Internal squad name is empty"
            return None

        cached = self._internal_squad_uuid_cache.get(normalized_name)
        if cached:
            self.last_error = None
            return cached

        squads = await self.list_internal_squads()
        for squad in squads:
            if str(squad.get('name', '')).strip() == normalized_name:
                squad_uuid = str(squad.get('uuid', '')).strip()
                if squad_uuid:
                    self._internal_squad_uuid_cache[normalized_name] = squad_uuid
                    self.last_error = None
                    return squad_uuid

        self.last_error = f"Internal squad '{normalized_name}' was not found"
        return None

    async def update_user_active_internal_squads(self, uuid: str, squad_uuids: List[str]) -> bool:
        return await self.update_user_fields(uuid=uuid, activeInternalSquads=squad_uuids)

    async def apply_access_squad(self, uuid: str, squad_name: str) -> bool:
        squad_uuid = await self.resolve_internal_squad_uuid(squad_name)
        if not squad_uuid:
            return False
        return await self.update_user_active_internal_squads(uuid, [squad_uuid])

    async def update_user_fields(self, **fields: Any) -> bool:
        url = f"{self.base_url}/api/users"
        _own_session = None
        if self._session and not self._session.closed:
            session = self._session
        else:
            _own_session = aiohttp.ClientSession()
            session = _own_session
        try:
            try:
                async with session.patch(
                    url,
                    headers=self.headers,
                    json=fields,
                    timeout=5,
                ) as resp:
                    if resp.status not in [200, 201]:
                        self.last_error = f"User update failed with HTTP {resp.status}"
                        return False
                    try:
                        payload = await resp.json()
                    except Exception:
                        payload = None
                    if isinstance(payload, dict):
                        user = payload.get('response', payload)
                        if isinstance(user, dict):
                            self._cache_user(user)
                    self.last_error = None
                    return True
            except Exception as e:
                self.last_error = f"User update failed: {e}"
                logger.error(f"User update error: {e}")
                return False
        finally:
            if _own_session:
                await _own_session.close()

    async def update_user_traffic_limit(
        self,
        uuid: str,
        traffic_limit_bytes: int,
        traffic_limit_strategy: str,
    ) -> bool:
        return await self.update_user_fields(
            uuid=uuid,
            trafficLimitBytes=int(traffic_limit_bytes),
            trafficLimitStrategy=str(traffic_limit_strategy or DEFAULT_TRAFFIC_LIMIT_STRATEGY),
        )

panel = PanelAPI(CONFIG['settings']['panel_url'], PANEL_TOKEN)

# ================= NETWORK ANALYSIS =================

class NetworkAnalyzer:
    def __init__(self):
        self.db_path = CONFIG['settings']['geoip_db']
        self.asn_source = resolve_asn_source(BAN_SYSTEM_DIR, self.db_path)
        self.ip_api_cache = {} 
        self.whois_cache = {}
        # Общая сессия — устанавливается извне через set_session()
        self._shared_session: Optional[aiohttp.ClientSession] = None

    def set_session(self, session: aiohttp.ClientSession):
        """Принимает общую aiohttp-сессию для повторного использования соединений (Keep-Alive)."""
        self._shared_session = session

    def get_asn_info(self, ip: str) -> Tuple[Optional[int], str]:
        return self.asn_source.lookup(ip)

    async def _check_ip_api(self, ip: str) -> Optional[bool]:
        global IP_API_RATE_LIMITED, IP_API_RATE_LIMIT_UNTIL, IP_API_PENDING_POOL
        now = datetime.now()
        
        if ip in self.ip_api_cache:
            if self.ip_api_cache[ip]['expires'] > now:
                _dbg('CACHE', f"   > IP-API (Cache): {self.ip_api_cache[ip]['val']}")
                return self.ip_api_cache[ip]['val']
        
        if IP_API_RATE_LIMITED:
            if IP_API_RATE_LIMIT_UNTIL and now < IP_API_RATE_LIMIT_UNTIL:
                if ip not in IP_API_PENDING_POOL: IP_API_PENDING_POOL.add(ip)
                return None
            else:
                IP_API_RATE_LIMITED = False
                IP_API_RATE_LIMIT_UNTIL = None
                logger.info("IP-API rate limit recovered.")

        try:
            url = f"http://ip-api.com/json/{ip}?fields=mobile,message"
            if self._shared_session and not self._shared_session.closed:
                resp_ctx = self._shared_session.get(url, timeout=aiohttp.ClientTimeout(total=3))
                own_session = None
            else:
                own_session = aiohttp.ClientSession()
                resp_ctx = own_session.get(url, timeout=aiohttp.ClientTimeout(total=3))
            
            try:
                async with resp_ctx as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        is_mobile = data.get("mobile", False)
                        self.ip_api_cache[ip] = {'val': is_mobile, 'expires': now + timedelta(minutes=15)}
                        _dbg('ANALYSIS', f"   > IP-API (Live): {is_mobile}")
                        return is_mobile
                    elif resp.status == 429:
                        IP_API_RATE_LIMITED = True
                        IP_API_RATE_LIMIT_UNTIL = now + timedelta(minutes=60)
                        IP_API_PENDING_POOL.add(ip)
                        logger.warning("IP-API RATE LIMIT HIT!")
                        return None
            finally:
                if own_session:
                    await own_session.close()
        except Exception as e: 
            _dbg('ANALYSIS', f"   > IP-API Error: {e}")
            return None
        return None

    async def _get_whois_data(self, ip: str) -> str:
        now = datetime.now()
        if ip in self.whois_cache and self.whois_cache[ip]['exp'] > now:
            return self.whois_cache[ip]['data']
        try:
            proc = await asyncio.create_subprocess_exec('whois', ip, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=5)
            if stdout:
                data = stdout.decode('utf-8', errors='ignore').lower()
                self.whois_cache[ip] = {'data': data, 'exp': now + timedelta(hours=24)}
                _dbg('ANALYSIS', f"   > WHOIS fetched")
                return data
        except: pass
        return ""

    def _find_keywords(self, text: str, keyword_list: List[str]) -> List[str]:
        """Find all matching keywords in text"""
        return [kw for kw in keyword_list if kw in text]

    def _record_stats(self, asn: Optional[int], status: str, matched_kw: Optional[str], org: str):
        """
        Записывает статистику в оперативный буфер (in-memory).
        Данные периодически сбрасываются в БД фоновой задачей stats_flush_task().
        Такой подход исключает шквал мелких транзакций к SQLite при высокой нагрузке.
        """
        sub_key = 'mobile' if status == 'MOBILE' else ('home' if status == 'HOME' else 'unsure')

        if asn:
            if asn not in _STATS_BUFFER['asn']:
                _STATS_BUFFER['asn'][asn] = {'mobile': 0, 'home': 0, 'unsure': 0}
            _STATS_BUFFER['asn'][asn][sub_key] += 1

        if matched_kw:
            kw_sub = 'mobile' if status == 'MOBILE' else 'home'
            if matched_kw not in _STATS_BUFFER['keyword']:
                _STATS_BUFFER['keyword'][matched_kw] = {'mobile': 0, 'home': 0}
            _STATS_BUFFER['keyword'][matched_kw][kw_sub] += 1

        known_words = (
            set(CONFIG['allowed_isp_keywords'])
            | set(CONFIG.get('home_isp_keywords', []))
            | set(CONFIG['exclude_isp_keywords'])
        )
        org_words = (
            set(re.split(r'[\s\-_/.,()]+', org))
            - {'', 'the', 'of', 'and', 'in', 'to', 'for', 'jsc', 'ooo', 'ojsc', 'zao', 'ao'}
        )
        for w in org_words:
            if len(w) >= 3 and w not in known_words:
                _STATS_BUFFER['potential_kw'][w] = _STATS_BUFFER['potential_kw'].get(w, 0) + 1

    async def check_is_mobile(self, ip: str, uuid: str = None, tag: str = None) -> DecisionBundle:
        async def get_manual_override(target_ip: str) -> Optional[str]:
            manual_decision = await platform_store.async_get_ip_override(target_ip)
            if manual_decision:
                return manual_decision
            return await db.get_unsure_pattern(target_ip)

        async def analyze_behavior(current_uuid: str, target_ip: str, current_tag: str) -> dict[str, Any]:
            behavior = await behavioral_engine.analyze(current_uuid, target_ip, current_tag)
            behavior["subnet"] = db.get_subnet(target_ip)
            return behavior

        return await evaluate_mobile_network(
            context=ScoringContext(ip=ip, uuid=uuid, tag=tag),
            config=CONFIG,
            deps=ScoringDependencies(
                get_manual_override=get_manual_override,
                get_ip_info=ipinfo_api.get_ip_info,
                parse_asn=ipinfo_api.parse_asn,
                normalize_isp_name=ipinfo_api.normalize_isp_name,
                is_datacenter=ipinfo_api.is_datacenter,
                analyze_behavior=analyze_behavior,
                get_promoted_pattern=platform_store.async_get_promoted_pattern,
                get_legacy_confidence=db.get_learning_confidence,
                check_ip_api_mobile=self._check_ip_api,
                record_decision=behavioral_engine.record_decision,
                record_stats=self._record_stats,
            ),
        )

network_analyzer = NetworkAnalyzer()

# ================= TELEGRAM HANDLERS =================

bot = Bot(token=TG_ADMIN_BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML)) if TG_ADMIN_BOT_TOKEN else None
main_bot = Bot(token=TG_MAIN_BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML)) if TG_MAIN_BOT_TOKEN else None
dp = Dispatcher()


def settings() -> Dict[str, Any]:
    return CONFIG.setdefault("settings", {})


def config_flag(key: str, default: bool) -> bool:
    return bool(settings().get(key, default))


def config_value(key: str, default: Any) -> Any:
    return settings().get(key, default)


def enforcement_value(key: str) -> Any:
    defaults = dict(ENFORCEMENT_SETTINGS_DEFAULTS)
    if key == "warning_timeout_seconds":
        if key in settings():
            return settings()[key]
        return settings().get("warning_timeout", defaults[key])
    return settings().get(key, defaults[key])


def enforcement_template(key: str) -> str:
    return str(settings().get(key, ENFORCEMENT_TEMPLATE_DEFAULTS[key]))


def telegram_setting(key: str) -> Any:
    return normalize_telegram_runtime_settings(settings())[key]


def _violation_state_from_row(row: Any) -> Dict[str, Any]:
    if not row:
        return {
            "restriction_mode": SQUAD_RESTRICTION_MODE,
            "saved_traffic_limit_bytes": None,
            "saved_traffic_limit_strategy": None,
            "applied_traffic_limit_bytes": None,
        }
    return {
        "restriction_mode": normalize_restriction_mode(row[4] if len(row) > 4 else None),
        "saved_traffic_limit_bytes": row[5] if len(row) > 5 else None,
        "saved_traffic_limit_strategy": row[6] if len(row) > 6 else None,
        "applied_traffic_limit_bytes": row[7] if len(row) > 7 else None,
    }


def admin_bot_available() -> bool:
    return bot is not None


def main_bot_available() -> bool:
    return main_bot is not None


def admin_notifications_enabled() -> bool:
    return admin_bot_available() and telegram_notification_setting(
        settings(),
        "telegram_admin_notifications_enabled",
    )


def user_notifications_enabled() -> bool:
    return main_bot_available() and telegram_notification_setting(
        settings(),
        "telegram_user_notifications_enabled",
    )


def admin_event_notifications_enabled(event: str) -> bool:
    return admin_bot_available() and telegram_event_notifications_enabled(
        settings(),
        "admin",
        event,
    )


def user_event_notifications_enabled(event: str) -> bool:
    return main_bot_available() and telegram_event_notifications_enabled(
        settings(),
        "user",
        event,
    )


def admin_commands_enabled() -> bool:
    return admin_bot_available() and config_flag("telegram_admin_commands_enabled", True)


def format_duration_text(minutes: int) -> str:
    if minutes % 10080 == 0:
        weeks = minutes // 10080
        return f"{weeks} нед." if weeks > 1 else "1 неделя"
    if minutes % 1440 == 0:
        days = minutes // 1440
        return f"{days} дн." if days > 1 else "24 часа"
    if minutes % 60 == 0:
        hours = minutes // 60
        return f"{hours} ч." if hours > 1 else "1 час"
    return f"{minutes} мин."


def render_runtime_template(template_key: str, context: Dict[str, Any]) -> str:
    return render_optional_template(enforcement_template(template_key), context, escape_html)


def refresh_runtime_state_from_config() -> None:
    global CONFIG, TG_ADMIN_CHAT_ID, TG_TOPIC_ID, DEBUG_LEVEL, DEBUG_MODE, DRY_RUN, EXEMPT_UUIDS, TG_MIN_INTERVAL

    file_config = RUNTIME_CONTEXT.reload_config()

    platform_store.sync_runtime_config(file_config)
    CONFIG.clear()
    CONFIG.update(file_config)
    ipinfo_api.set_config(CONFIG)
    panel.base_url = settings().get('panel_url', panel.base_url)
    network_analyzer.db_path = CONFIG['settings']['geoip_db']
    TG_ADMIN_CHAT_ID = str(settings().get('tg_admin_chat_id', "-1003304969829"))
    TG_TOPIC_ID = int(settings().get('tg_topic_id', 58) or 0)
    DEBUG_LEVEL = str(settings().get('debug_level', 'OFF')).upper()
    DEBUG_MODE = DEBUG_LEVEL != 'OFF'
    DRY_RUN = config_flag('dry_run', True)
    EXEMPT_UUIDS = set(str(x) for x in CONFIG.get('exempt_uuids', []))
    TG_MIN_INTERVAL = float(telegram_setting('telegram_message_min_interval_seconds'))

def is_admin(user_id: int) -> bool: 
    return user_id in CONFIG.get('admin_tg_ids', [])

async def resolve_target(target: str): 
    return await panel.get_user_data(target)

async def notify_admin(text: str, reply_markup=None):
    global TG_MESSAGE_QUEUE
    if not admin_notifications_enabled():
        return
    if TG_MESSAGE_QUEUE:
        await TG_MESSAGE_QUEUE.put(('admin', text, reply_markup))
    else:
        try: 
            if bot and TG_ADMIN_CHAT_ID:
                await bot.send_message(TG_ADMIN_CHAT_ID, text, message_thread_id=TG_TOPIC_ID or None, reply_markup=reply_markup)
        except Exception as e:
            logger.error(f"TG Error: {e}")
            await notify_error(f"Ошибка отправки в админ-чат: {e}")

async def notify_user(tg_id: int, text: str):
    global TG_MESSAGE_QUEUE
    if DRY_RUN or not user_notifications_enabled():
        return
    if TG_MESSAGE_QUEUE:
        await TG_MESSAGE_QUEUE.put(('user', tg_id, text))
    else:
        try: 
            if main_bot:
                await main_bot.send_message(tg_id, text)
        except Exception as e:
            logger.error(f"TG User notify error: {e}")

async def notify_error(error_msg: str):
    if not admin_notifications_enabled():
        return
    try:
        msg = (
            f"📶 <b>#mobguard</b>\n"
            f"➖➖➖➖➖➖➖➖➖\n"
            f"❌ <b>ОШИБКА СИСТЕМЫ</b>\n\n"
            f"<code>{escape_html(error_msg)}</code>\n\n"
            f"Время: {datetime.now().strftime('%d.%m %H:%M:%S')}"
        )
        if bot and TG_ADMIN_CHAT_ID:
            await bot.send_message(TG_ADMIN_CHAT_ID, msg, message_thread_id=TG_TOPIC_ID or None)
    except:
        pass  # Не можем отправить сообщение об ошибке

def escape_html(text: str) -> str:
    return str(text).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

async def send_unsure_notify(user: Dict, bundle: DecisionBundle, tag: str, review_reason: str):
    global UNSURE_NOTIFIED
    if not admin_event_notifications_enabled("review"):
        return

    uuid = user.get('uuid')
    notify_key = f"{uuid}:{bundle.ip}:{review_reason}"

    if notify_key in UNSURE_NOTIFIED:
        _dbg('IMPORTANT', f"[UNSURE] Already notified for {notify_key}, skipping")
        return

    UNSURE_NOTIFIED.add(notify_key)

    tg_id = user.get('telegramId') or ""
    review_url = platform_store.build_review_url(bundle.case_id) if bundle.case_id else ""
    title = {
        "unsure": "ТРЕБУЕТСЯ РУЧНАЯ ПРОВЕРКА",
        "probable_home": "ПОГРАНИЧНЫЙ HOME КЕЙС",
        "home_requires_review": "HOME КЕЙС ТРЕБУЕТ ПОДТВЕРЖДЕНИЯ",
        "manual_review_mixed_home": "MIXED ASN HOME КЕЙС",
    }.get(review_reason, "ТРЕБУЕТСЯ РУЧНАЯ ПРОВЕРКА")

    msg = render_runtime_template(
        "admin_review_template",
        {
            "username": user.get('username', 'N/A'),
            "uuid": uuid or "N/A",
            "system_id": user.get('id') or "",
            "telegram_id": tg_id,
            "ip": bundle.ip,
            "isp": bundle.isp,
            "tag": tag,
            "confidence_band": f"{title} / {bundle.verdict} / {bundle.confidence_band}",
            "review_url": review_url,
        },
    )
    if bundle.case_id:
        msg += f"\n<b>Case ID:</b> <code>{bundle.case_id}</code>\n"
    msg += "\n<b>Основания:</b>\n"
    for entry in bundle.log:
        msg += f"  • {escape_html(entry)}\n"

    await notify_admin(msg)

@dp.callback_query(lambda c: c.data and c.data.startswith('unsure:'))
async def handle_unsure_callback(callback: CallbackQuery):
    global UNSURE_NOTIFIED
    
    if not is_admin(callback.from_user.id):
        await callback.answer("Access denied", show_alert=True)
        return
    
    try:
        _, ip_pattern, decision = callback.data.split(':')
        
        if decision in ('MOBILE', 'HOME'):
            cached = await db.get_cached_decision(ip_pattern)
            if cached:
                asn = cached.get('asn')
                isp = cached.get('isp', '')
                log = cached.get('log', [])
                
                # Обучение по ASN
                if asn:
                    await db.add_learning_pattern('asn', str(asn), decision)
                    _dbg('IMPORTANT', f"[LEARNING] ASN {asn} -> {decision}")
                
                if asn:
                    found_keywords = []
                    isp_lower = isp.lower()
                    
                    # Собираем все найденные keywords
                    for keyword in ['broadband', 'dsl', 'fiber', 'ftth', 'fttb', 'cable', 
                                   'mobile', 'cellular', 'lte', '4g', '5g', 'gprs', 'gpon']:
                        if keyword in isp_lower:
                            found_keywords.append(keyword)
                            await db.add_learning_pattern('keyword', keyword, decision)
                            _dbg('IMPORTANT', f"[LEARNING] Keyword '{keyword}' -> {decision}")
                    
                    # Сохраняем комбо-паттерн ASN+keywords
                    if found_keywords:
                        combo_key = f"{asn}+{','.join(sorted(found_keywords))}"
                        await db.add_learning_pattern('combo', combo_key, decision)
                        _dbg('IMPORTANT', f"[LEARNING] Combo '{combo_key}' -> {decision}")
                
                # Обучение по PTR паттернам
                for entry in log:
                    if 'PTR:' in entry and 'PTR: None' not in entry:
                        ptr_value = entry.split('PTR:')[1].strip()
                        parts = ptr_value.split('.')
                        if len(parts) >= 2:
                            domain = '.'.join(parts[-2:])
                            await db.add_learning_pattern('ptr_domain', domain, decision)
                            _dbg('IMPORTANT', f"[LEARNING] PTR domain '{domain}' -> {decision}")
        
        # Сохраняем решение
        await db.set_unsure_pattern(ip_pattern, decision)
        await platform_store.async_set_ip_override(
            ip_pattern,
            decision,
            "telegram_callback",
            callback.from_user.first_name or "Admin",
            callback.from_user.id,
        )
        
        await db.invalidate_ip_cache(ip_pattern)
        
        if decision == 'MOBILE':
            response = f"✅ IP {ip_pattern} помечен как МОБИЛЬНЫЙ"
        elif decision == 'HOME':
            response = f"⛔ IP {ip_pattern} помечен как ДОМАШНИЙ"
        else:  # SKIP
            response = f"⏭️ IP {ip_pattern} пропущен"
        
        await callback.answer(response)
        
        # Update message to show decision was made
        if callback.message:
            try:
                original_text = callback.message.text
                safe_text = escape_html(original_text)
                
                new_text = f"{safe_text}\n\n<b>✓ Решение:</b> {decision} (by {callback.from_user.first_name})"
                
                await callback.message.edit_text(
                    text=new_text,
                    reply_markup=None,
                    parse_mode="HTML"
                )
            except Exception as e:
                logger.error(f"Error editing message: {e}")
    except Exception as e:
        logger.error(f"Callback error: {e}")
        await callback.answer("Error processing decision", show_alert=True)
        await notify_error(f"Callback error: {e}")

@dp.callback_query(lambda c: c.data and c.data.startswith('ban_approve:'))
async def handle_ban_approve(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Access denied", show_alert=True)
        return
    
    try:
        parts = callback.data.split(':')
        uuid, ip, strikes, ban_min = parts[1], parts[2], int(parts[3]), int(parts[4])
        row = await db.fetch_one(
            """
            SELECT strikes, unban_time, warning_time, warning_count,
                   restriction_mode, saved_traffic_limit_bytes,
                   saved_traffic_limit_strategy, applied_traffic_limit_bytes
            FROM violations WHERE uuid=?
            """,
            (uuid,),
        )
        restriction_state = _violation_state_from_row(row)
        
        if not DRY_RUN:
            restricted = await apply_remote_restriction_state_async(
                panel,
                uuid,
                settings(),
                restriction_state,
            )
            if not restricted:
                logger.error(
                    "Access restriction approval failed for %s (%s): %s",
                    uuid,
                    restriction_state["restriction_mode"],
                    panel.last_error or "unknown error",
                )
                await callback.answer("Не удалось применить ограничение", show_alert=True)
                return
        
        admin_name = callback.from_user.first_name or "Admin"
        await callback.answer(f"✅ Ограничение применено ({ban_min} мин)")
        
        if callback.message:
            try:
                safe_text = escape_html(callback.message.text)
                await callback.message.edit_text(
                    text=f"{safe_text}\n\n✅ <b>Ограничение доступа одобрено</b> (by {admin_name})",
                    reply_markup=None,
                    parse_mode="HTML"
                )
            except Exception as e:
                logger.error(f"Error editing message: {e}")
        
        _dbg('IMPORTANT', f"[MANUAL_REVIEW] Access restriction approved for {uuid} by {admin_name}")
        
    except Exception as e:
        logger.error(f"Ban approve error: {e}")
        await callback.answer("Error approving access restriction", show_alert=True)

@dp.callback_query(lambda c: c.data and c.data.startswith('ban_reject:'))
async def handle_ban_reject(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Access denied", show_alert=True)
        return
    
    try:
        parts = callback.data.split(':')
        uuid, ip = parts[1], parts[2]
        
        await db.execute("DELETE FROM violations WHERE uuid=?", (uuid,))
        await db.execute("DELETE FROM active_trackers WHERE uuid=?", (uuid,))
        
        admin_name = callback.from_user.first_name or "Admin"
        await callback.answer("❌ Ограничение отменено")
        
        if callback.message:
            try:
                safe_text = escape_html(callback.message.text)
                await callback.message.edit_text(
                    text=f"{safe_text}\n\n❌ <b>Ограничение доступа отменено</b> (by {admin_name})",
                    reply_markup=None,
                    parse_mode="HTML"
                )
            except Exception as e:
                logger.error(f"Error editing message: {e}")
        
        _dbg('IMPORTANT', f"[MANUAL_REVIEW] Access restriction rejected for {uuid} by {admin_name}")
        
    except Exception as e:
        logger.error(f"Ban reject error: {e}")
        await callback.answer("Error rejecting access restriction", show_alert=True)

@dp.message(Command("status"))
async def cmd_status(message: Message):
    if not is_admin(message.from_user.id): return
    active = await db.fetch_one("SELECT COUNT(*) FROM violations WHERE unban_time > ?", (datetime.now().isoformat(),))
    total = await db.fetch_one("SELECT COUNT(*) FROM violations", ())
    trackers = await db.fetch_one("SELECT COUNT(*) FROM active_trackers", ())
    unsure_patterns = await db.fetch_one("SELECT COUNT(*) FROM unsure_patterns", ())
    quality = platform_store.get_quality_metrics()
    await message.reply(
        f"📊 <b>Статус Mobguard</b>\n"
        f"• Активных ограничений: {active[0]}\n"
        f"• Всего нарушений: {total[0]}\n"
        f"• Активных трекеров: {trackers[0]}\n"
        f"• UNSURE patterns: {unsure_patterns[0]}\n"
        f"• Review queue: {quality['open_cases']}\n"
        f"• Active learning patterns: {quality['active_learning_patterns']}\n"
        f"• UNSURE notified (session): {len(UNSURE_NOTIFIED)}\n"
        f"• Пользователей с иммунитетом: {len(EXEMPT_UUIDS)}\n"
        f"• Режим: {'⚠️ DRY RUN' if DRY_RUN else '✅ ОГРАНИЧЕНИЯ'}\n"
        f"• Shadow mode: {'ON' if CONFIG['settings'].get('shadow_mode', True) else 'OFF'}\n"
        f"• DEBUG: {DEBUG_LEVEL}"
    )

@dp.message(Command("dry"))
async def cmd_dry(message: Message):
    if not is_admin(message.from_user.id): return
    global DRY_RUN
    DRY_RUN = not DRY_RUN
    await message.reply(f"🔄 DRY RUN: {'✅ ВКЛЮЧЕН' if DRY_RUN else '⛔ ВЫКЛЮЧЕН'}")
    logger.info(f"DRY_RUN toggled to {DRY_RUN}")

@dp.message(Command("review_mode"))
async def cmd_review_mode(message: Message, command: CommandObject):
    """Режимы модерации: /review_mode unsure/bans/auto"""
    global MANUAL_REVIEW_UNSURE, MANUAL_REVIEW_ALL_BANS

    if not is_admin(message.from_user.id): return
    
    if not command.args:
        await message.reply(
            f"🔍 <b>Режимы модерации:</b>\n\n"
            f"Mixed ASN: {'✅' if MANUAL_REVIEW_UNSURE else '⛔'}\n"
            f"Restriction approval: {'✅' if MANUAL_REVIEW_ALL_BANS else '⛔'}\n\n"
            f"/review_mode unsure|bans|auto"
        )
        return
    
    mode = command.args.strip().lower()
    
    if mode == 'unsure':
        MANUAL_REVIEW_UNSURE = not MANUAL_REVIEW_UNSURE
        await message.reply(f"🔍 Mixed ASN: {'✅' if MANUAL_REVIEW_UNSURE else '⛔'}")
    elif mode == 'bans':
        MANUAL_REVIEW_ALL_BANS = not MANUAL_REVIEW_ALL_BANS
        await message.reply(f"👮 Ограничения: {'✅' if MANUAL_REVIEW_ALL_BANS else '⛔'}")
    elif mode == 'auto':
        MANUAL_REVIEW_UNSURE = False
        MANUAL_REVIEW_ALL_BANS = False
        await message.reply("⚡ Auto mode")
    else:
        await message.reply("❌ unsure|bans|auto")

@dp.message(Command("exempt"))
async def cmd_exempt(message: Message, command: CommandObject):
    if not is_admin(message.from_user.id): return
    if not command.args:
        await message.reply("Usage: /exempt <uuid or telegram_id>")
        return
    
    target = await resolve_target(command.args)
    if not target:
        await message.reply("❌ Пользователь не найден")
        return
    
    uuid = target['uuid']
    if uuid in EXEMPT_UUIDS:
        EXEMPT_UUIDS.remove(uuid)
        status = "снят"
    else:
        EXEMPT_UUIDS.add(uuid)
        status = "установлен"
    
    await message.reply(f"✅ Иммунитет {status} для {target.get('username', uuid)}")

@dp.message(Command("unban"))
async def cmd_unban(message: Message, command: CommandObject):
    if not is_admin(message.from_user.id): return
    if not command.args:
        await message.reply("Usage: /unban <uuid or telegram_id>")
        return
    
    target = await resolve_target(command.args)
    if not target:
        await message.reply("❌ Пользователь не найден")
        return
    
    uuid = target['uuid']
    row = await db.fetch_one(
        """
        SELECT strikes, unban_time, warning_time, warning_count,
               restriction_mode, saved_traffic_limit_bytes,
               saved_traffic_limit_strategy, applied_traffic_limit_bytes
        FROM violations WHERE uuid=?
        """,
        (uuid,),
    )
    restriction_state = _violation_state_from_row(row)
    if not DRY_RUN:
        restore_result = await restore_remote_restriction_state_async(
            panel,
            uuid,
            settings(),
            restriction_state,
        )
        if not restore_result["remote_updated"]:
            await message.reply(
                f"❌ Не удалось восстановить полный доступ для {target.get('username', uuid)}: "
                f"{panel.last_error or 'unknown error'}"
            )
            return
    await db.execute("DELETE FROM violations WHERE uuid=?", (uuid,))

    await message.reply(f"✅ Полный доступ восстановлен для {target.get('username', uuid)}")
    await notify_admin(
        f"📶 <b>#mobguard</b>\n"
        f"➖➖➖➖➖➖➖➖➖\n"
        f"🔓 <b>Восстановление полного доступа</b>\n"
        f"Админ: {message.from_user.first_name}\n"
        f"User: {escape_html(target.get('username', uuid))}"
    )

@dp.message(Command("forgive"))
async def cmd_forgive(message: Message, command: CommandObject):
    if not is_admin(message.from_user.id): return
    if not command.args:
        await message.reply("Usage: /forgive <uuid or telegram_id>")
        return
    
    target = await resolve_target(command.args)
    if not target:
        await message.reply("❌ Пользователь не найден")
        return
    
    uuid = target['uuid']
    row = await db.fetch_one("SELECT strikes FROM violations WHERE uuid=?", (uuid,))
    
    if not row or row[0] == 0:
        await message.reply("❌ У пользователя нет страйков")
        return
    
    strikes = row[0]
    new_strikes = max(0, strikes - 1)
    now = datetime.now()
    
    await db.execute("""UPDATE violations SET strikes=?, last_forgiven=? WHERE uuid=?""",
                     (new_strikes, now.isoformat(), uuid))
    
    name = target.get('username', uuid)
    await message.reply(f"✅ Прощён страйк для {name}\nСтрайки: {strikes} → {new_strikes}")
    
    admin_msg = (
        f"📶 <b>#mobguard</b>\n"
        f"➖➖➖➖➖➖➖➖➖\n"
        f"🎁 <b>Милостыня</b>\n\n"
        f"Username: {name}\n"
        f"Страйки: {strikes} -> {new_strikes}"
    )
    await notify_admin(admin_msg)

@dp.message(Command("stats"))
async def cmd_stats(message: Message):
    if not is_admin(message.from_user.id): return
    
    total_violators = await db.fetch_one("SELECT COUNT(DISTINCT uuid) FROM violation_history", ())
    total_incidents = await db.fetch_one("SELECT COUNT(*) FROM violation_history", ())
    top_violators = await db.fetch_all("SELECT uuid, COUNT(*) as cnt FROM violation_history GROUP BY uuid ORDER BY cnt DESC LIMIT 5", ())
    top_isps = await db.fetch_all("SELECT isp, COUNT(*) as cnt FROM violation_history GROUP BY isp ORDER BY cnt DESC LIMIT 5", ())
    
    msg = (f"📊 <b>MobGuard • Статистика</b>\n\n"
           f"👥 Всего нарушителей: {total_violators[0]}\n"
           f"⚠️ Всего инцидентов: {total_incidents[0]}\n\n"
           f"🔝 <b>Топ нарушителей:</b>\n")
    
    for uuid, cnt in top_violators:
        u = await panel.get_user_data(uuid)
        name = u.get('username', 'Unknown') if u else uuid[:8]
        msg += f"   {name}: {cnt}\n"
        
    msg += "\n🌐 <b>Проблемные ISP:</b>\n"
    for isp, cnt in top_isps:
        msg += f"   {isp}: {cnt}\n"
        
    await message.reply(msg)

@dp.message(Command("learning"))
async def cmd_learning(message: Message, command: CommandObject):
    """ML управление: /learning stats|view|edit|reset"""
    if not is_admin(message.from_user.id): return
    
    args = command.args.strip().split() if command.args else []
    
    if not args or args[0] == 'stats':
        stats = await db.get_learning_stats()
        msg = "🧠 <b>ML Stats</b>\n\n"
        if stats:
            for pt, st in stats.items():
                msg += f"• {pt}: {st['count']} ({st['confidence']})\n"
        else:
            msg += "No data"
        await message.reply(msg)
    
    elif args[0] == 'view' and len(args) >= 3:
        ptype, value = args[1], args[2]
        rows = await db.fetch_all(
            "SELECT decision, confidence FROM unsure_learning WHERE pattern_type=? AND pattern_value=?",
            (ptype, value)
        )
        if rows:
            msg = f"<b>{ptype} {value}</b>\n\n"
            for dec, conf in rows:
                msg += f"{'✅' if dec=='MOBILE' else '⛔'} {dec}: {conf}\n"
            await message.reply(msg)
        else:
            await message.reply("No data")
    
    elif args[0] == 'edit' and len(args) >= 4:
        ptype, value, decision = args[1], args[2], args[3].upper()
        if decision == 'DELETE':
            await db.execute("DELETE FROM unsure_learning WHERE pattern_type=? AND pattern_value=?", (ptype, value))
            await message.reply(f"✅ Deleted")
        elif decision in ['MOBILE', 'HOME']:
            now = datetime.now().isoformat()
            await db.execute(
                "INSERT OR REPLACE INTO unsure_learning (pattern_type, pattern_value, decision, confidence, timestamp) VALUES (?,?,?,10,?)",
                (ptype, value, decision, now)
            )
            await message.reply(f"✅ {ptype} {value} → {decision}")
    
    elif args[0] == 'reset':
        if len(args) < 2:
            await message.reply("❌ /learning reset all|asn|subnet")
            return
        if args[1] == 'all':
            await db.execute("DELETE FROM unsure_learning", ())
            await message.reply("✅ Reset")
        elif args[1] == 'asn' and len(args) >= 3:
            await db.execute("DELETE FROM unsure_learning WHERE pattern_type='asn' AND pattern_value=?", (args[2],))
            await message.reply(f"✅ ASN {args[2]} reset")
    else:
        await message.reply("/learning stats|view|edit|reset")

@dp.message(Command("clear"))
async def cmd_clear(message: Message, command: CommandObject):
    if not is_admin(message.from_user.id): return
    
    if not command.args:
        await message.reply(
            "📋 <b>Использование команды /clear:</b>\n\n"
            "• <code>/clear all</code> - полная очистка всех данных\n"
            "• <code>/clear violations</code> - очистка violations + history\n"
            "• <code>/clear trackers</code> - очистка активных трекеров\n"
            "• <code>/clear ip_cache</code> - очистка IP кеша\n"
            "• <code>/clear unsure_patterns</code> - очистка UNSURE решений\n"
        )
        return
    
    flag = command.args.strip().lower()
    
    if flag == 'all':
        await db.execute("DELETE FROM violations", ())
        await db.execute("DELETE FROM violation_history", ())
        await db.execute("DELETE FROM active_trackers", ())
        await db.execute("DELETE FROM ip_decisions", ())
        await db.execute("DELETE FROM unsure_patterns", ())
        await message.reply("✅ База данных полностью очищена")
        await notify_admin(f"🗑️ <b>БД очищена полностью</b>\nАдмин: {message.from_user.first_name}")
        
    elif flag == 'violations':
        await db.execute("DELETE FROM violations", ())
        await db.execute("DELETE FROM violation_history", ())
        await message.reply("✅ Violations и история очищены")
        await notify_admin(f"🗑️ <b>Violations очищены</b>\nАдмин: {message.from_user.first_name}")
        
    elif flag == 'trackers':
        await db.execute("DELETE FROM active_trackers", ())
        await message.reply("✅ Активные трекеры очищены")
        
    elif flag == 'ip_cache':
        await db.execute("DELETE FROM ip_decisions", ())
        await message.reply("✅ IP кеш очищен")
        
    elif flag == 'unsure':
        global UNSURE_NOTIFIED
        count = len(UNSURE_NOTIFIED)
        UNSURE_NOTIFIED.clear()
        await message.reply(f"✅ UNSURE cleared ({count})")
        
    else:
        await message.reply("❌ Неизвестный флаг. Используйте: all, violations, trackers, ip_cache, unsure_patterns")

@dp.message(Command("check"))
async def cmd_check(message: Message, command: CommandObject):
    """Информация о пользователе с историей нарушений"""
    if not is_admin(message.from_user.id): return
    
    if not command.args:
        await message.reply("Usage: /check <uuid или telegram_id>")
        return
    
    target = await resolve_target(command.args)
    if not target:
        await message.reply("❌ Пользователь не найден")
        return
    
    uuid = target['uuid']
    username = target.get('username', 'N/A')
    tg_id = target.get('telegramId', 'N/A')
    
    # Информация о нарушениях
    violation_row = await db.fetch_one("SELECT strikes, unban_time, last_forgiven, last_strike_time, warning_time FROM violations WHERE uuid=?", (uuid,))
    
    msg = (
        f"👤 <b>Информация о пользователе</b>\n\n"
        f"<b>Username:</b> {escape_html(username)}\n"
        f"<b>UUID:</b> <code>{uuid}</code>\n"
        f"<b>Telegram ID:</b> {tg_id}\n"
        f"<b>Иммунитет:</b> {'✅ Да' if uuid in EXEMPT_UUIDS else '❌ Нет'}\n\n"
    )
    
    if violation_row:
        strikes, unban_time_str, last_forgiven_str, last_strike_str, warning_time_str = violation_row
        msg += f"⚠️ <b>Статус нарушений:</b>\n"
        msg += f"• Страйки: {strikes}\n"
        
        if unban_time_str:
            unban_time = datetime.fromisoformat(unban_time_str)
            if unban_time > datetime.now():
                remaining = unban_time - datetime.now()
                hours = int(remaining.total_seconds() // 3600)
                minutes = int((remaining.total_seconds() % 3600) // 60)
                msg += f"• Статус: 🔒 Доступ ограничен (осталось {hours}ч {minutes}м)\n"
            else:
                msg += f"• Статус: ✅ Активен\n"
        elif warning_time_str:
            msg += f"• Статус: ⚠️ Предупреждён\n"
        else:
            msg += f"• Статус: ✅ Активен\n"
        
        if last_strike_str:
            last_strike = datetime.fromisoformat(last_strike_str)
            msg += f"• Последний страйк: {last_strike.strftime('%d.%m.%Y %H:%M')}\n"
        
        if last_forgiven_str:
            last_forgiven = datetime.fromisoformat(last_forgiven_str)
            days_since = (datetime.now() - last_forgiven).days
            msg += f"• Последнее прощение: {last_forgiven.strftime('%d.%m.%Y')} ({days_since} дней назад)\n"
    else:
        msg += "✅ <b>Нарушений нет</b>\n"
    
    # История нарушений
    history = await db.fetch_all(
        "SELECT ip, isp, tag, strike_number, punishment_duration, timestamp FROM violation_history WHERE uuid=? ORDER BY timestamp DESC LIMIT 10",
        (uuid,)
    )
    
    if history:
        msg += f"\n📜 <b>История нарушений (последние 10):</b>\n"
        for ip, isp, tag, strike_num, duration, timestamp_str in history:
            dt = datetime.fromisoformat(timestamp_str)
            msg += f"\n• {dt.strftime('%d.%m %H:%M')} | Страйк #{strike_num}\n"
            msg += f"  IP: <code>{ip}</code>\n"
            msg += f"  ISP: {escape_html(isp)}\n"
            msg += f"  Config: {escape_html(tag)}\n"
            msg += f"  Ограничение: {duration} мин\n"
    
    # Активные трекеры
    trackers = await db.fetch_all("SELECT key, start_time FROM active_trackers WHERE key LIKE ?", (f"{uuid}:%",))
    if trackers:
        msg += f"\n🎯 <b>Активные трекеры:</b>\n"
        for key, start_str in trackers:
            start = datetime.fromisoformat(start_str)
            duration = int((datetime.now() - start).total_seconds())
            msg += f"• {key.split(':')[1]} - {duration}s\n"
    
    await message.reply(msg)

@dp.message(Command("ipinfo"))
async def cmd_ipinfo(message: Message, command: CommandObject):
    """Ручная проверка IP по системе"""
    if not is_admin(message.from_user.id): return
    
    if not command.args:
        await message.reply("Usage: /ipinfo <IP адрес>")
        return
    
    ip = command.args.strip()
    
    # Проверка формата IP
    if not re.match(r'^\d+\.\d+\.\d+\.\d+$', ip):
        await message.reply("❌ Неверный формат IP адреса")
        return
    
    await message.reply(f"🔍 Анализирую IP <code>{ip}</code>...")
    
    try:
        # Проверяем кеш
        cached = await db.get_cached_decision(ip)
        
        if cached:
            bundle = DecisionBundle.from_cache_record(ip, cached)
            msg = (
                f"📊 <b>IP Анализ (из кеша)</b>\n\n"
                f"<b>IP:</b> <code>{ip}</code>\n"
                f"<b>Статус:</b> {bundle.verdict}\n"
                f"<b>Уверенность:</b> {bundle.confidence_band}\n"
                f"<b>ISP:</b> {escape_html(bundle.isp)}\n"
                f"<b>ASN:</b> {bundle.asn if bundle.asn else 'N/A'}\n\n"
            )
            
            if bundle.log:
                msg += "<b>Детали анализа:</b>\n"
                for entry in bundle.log:
                    msg += f"• {escape_html(entry)}\n"
        else:
            # Проводим полный анализ
            bundle = await network_analyzer.check_is_mobile(ip)
            
            msg = (
                f"📊 <b>IP Анализ (новая проверка)</b>\n\n"
                f"<b>IP:</b> <code>{ip}</code>\n"
                f"<b>Статус:</b> {bundle.verdict}\n"
                f"<b>Уверенность:</b> {bundle.confidence_band}\n"
                f"<b>ISP:</b> {escape_html(bundle.isp)}\n"
                f"<b>ASN:</b> {bundle.asn if bundle.asn else 'N/A'}\n\n"
            )
            
            if bundle.log:
                msg += "<b>Детали анализа:</b>\n"
                for entry in bundle.log:
                    msg += f"• {escape_html(entry)}\n"
            
            # Кешируем результат
            await db.cache_decision(ip, bundle.to_cache_payload())
        
        await message.reply(msg)
        
    except Exception as e:
        await message.reply(f"❌ Ошибка при анализе IP: {e}")
        logger.error(f"IP analysis error for {ip}: {e}")

@dp.message(Command("strike"))
async def cmd_strike(message: Message, command: CommandObject):
    """Управление страйками пользователя"""
    if not is_admin(message.from_user.id): return
    
    if not command.args:
        await message.reply(
            "📋 <b>Использование:</b>\n"
            "<code>/strike add &lt;user&gt;</code> - добавить страйк\n"
            "<code>/strike remove &lt;user&gt;</code> - убрать страйк\n"
            "<code>/strike set &lt;user&gt; &lt;число&gt;</code> - установить количество"
        )
        return
    
    parts = command.args.strip().split()
    if len(parts) < 2:
        await message.reply("❌ Недостаточно параметров")
        return
    
    action = parts[0].lower()
    user_id = parts[1]
    
    target = await resolve_target(user_id)
    if not target:
        await message.reply("❌ Пользователь не найден")
        return
    
    uuid = target['uuid']
    username = target.get('username', uuid)
    
    # Получаем текущие страйки
    row = await db.fetch_one("SELECT strikes FROM violations WHERE uuid=?", (uuid,))
    current_strikes = row[0] if row else 0
    
    if action == 'add':
        new_strikes = current_strikes + 1
        now = datetime.now()
        await db.execute(
            "INSERT OR REPLACE INTO violations (uuid, strikes, last_strike_time, last_forgiven) VALUES (?, ?, ?, ?)",
            (uuid, new_strikes, now.isoformat(), now.isoformat())
        )
        await message.reply(f"✅ Добавлен страйк для {username}\nСтрайки: {current_strikes} → {new_strikes}")
        
    elif action == 'remove':
        if current_strikes == 0:
            await message.reply(f"❌ У {username} нет страйков")
            return
        new_strikes = current_strikes - 1
        now = datetime.now()
        await db.execute(
            "UPDATE violations SET strikes=?, last_forgiven=? WHERE uuid=?",
            (new_strikes, now.isoformat(), uuid)
        )
        await message.reply(f"✅ Убран страйк для {username}\nСтрайки: {current_strikes} → {new_strikes}")
        
    elif action == 'set':
        if len(parts) < 3:
            await message.reply("❌ Укажите количество страйков")
            return
        try:
            new_strikes = int(parts[2])
            if new_strikes < 0:
                await message.reply("❌ Количество страйков не может быть отрицательным")
                return
            
            now = datetime.now()
            if new_strikes == 0:
                await db.execute("DELETE FROM violations WHERE uuid=?", (uuid,))
            else:
                await db.execute(
                    "INSERT OR REPLACE INTO violations (uuid, strikes, last_strike_time, last_forgiven) VALUES (?, ?, ?, ?)",
                    (uuid, new_strikes, now.isoformat(), now.isoformat())
                )
            await message.reply(f"✅ Установлены страйки для {username}\nСтрайки: {current_strikes} → {new_strikes}")
        except ValueError:
            await message.reply("❌ Неверное число")
            return
    else:
        await message.reply("❌ Неизвестное действие. Используйте: add, remove, set")
        return
    
    await notify_admin(
        f"📶 <b>#mobguard</b>\n"
        f"➖➖➖➖➖➖➖➖➖\n"
        f"⚖️ <b>Изменение страйков</b>\n\n"
        f"Админ: {message.from_user.first_name}\n"
        f"User: {escape_html(username)}\n"
        f"Действие: {action}\n"
        f"Страйки: {current_strikes} → {new_strikes}"
    )

@dp.message(Command("immune"))
async def cmd_immune(message: Message, command: CommandObject):
    """Управление иммунитетом от проверок"""
    if not is_admin(message.from_user.id): return
    
    if not command.args:
        # Показываем список пользователей с иммунитетом
        if not EXEMPT_UUIDS:
            await message.reply("📋 Нет пользователей с иммунитетом")
            return
        
        msg = "🛡️ <b>Пользователи с иммунитетом:</b>\n\n"
        for uuid in EXEMPT_UUIDS:
            user = await panel.get_user_data(uuid)
            username = user.get('username', uuid[:8]) if user else uuid[:8]
            msg += f"• {escape_html(username)} (<code>{uuid}</code>)\n"
        
        msg += f"\n<b>Использование:</b>\n"
        msg += "<code>/immune add &lt;user&gt;</code>\n"
        msg += "<code>/immune remove &lt;user&gt;</code>"
        
        await message.reply(msg)
        return
    
    parts = command.args.strip().split()
    if len(parts) < 2:
        await message.reply("❌ Недостаточно параметров")
        return
    
    action = parts[0].lower()
    user_id = parts[1]
    
    target = await resolve_target(user_id)
    if not target:
        await message.reply("❌ Пользователь не найден")
        return
    
    uuid = target['uuid']
    username = target.get('username', uuid)
    
    if action == 'add':
        if uuid in EXEMPT_UUIDS:
            await message.reply(f"ℹ️ {username} уже имеет иммунитет")
            return
        EXEMPT_UUIDS.add(uuid)
        await message.reply(f"✅ Иммунитет установлен для {username}")
        
    elif action == 'remove':
        if uuid not in EXEMPT_UUIDS:
            await message.reply(f"ℹ️ {username} не имеет иммунитета")
            return
        EXEMPT_UUIDS.remove(uuid)
        await message.reply(f"✅ Иммунитет снят с {username}")
        
    else:
        await message.reply("❌ Неизвестное действие. Используйте: add, remove")
        return
    
    await notify_admin(
        f"📶 <b>#mobguard</b>\n"
        f"➖➖➖➖➖➖➖➖➖\n"
        f"🛡️ <b>Изменение иммунитета</b>\n\n"
        f"Админ: {message.from_user.first_name}\n"
        f"User: {escape_html(username)}\n"
        f"Действие: {action}"
    )

@dp.message(Command("remove"))
async def cmd_remove(message: Message, command: CommandObject):
    """Полное удаление пользователя из БД"""
    if not is_admin(message.from_user.id): return
    
    if not command.args:
        await message.reply("Usage: /remove <uuid или telegram_id>")
        return
    
    target = await resolve_target(command.args)
    if not target:
        await message.reply("❌ Пользователь не найден")
        return
    
    uuid = target['uuid']
    username = target.get('username', uuid)
    
    # Удаляем все данные пользователя
    await db.execute("DELETE FROM violations WHERE uuid=?", (uuid,))
    await db.execute("DELETE FROM violation_history WHERE uuid=?", (uuid,))
    await db.execute("DELETE FROM active_trackers WHERE key LIKE ?", (f"{uuid}:%",))
    
    # Убираем из иммунитета если был
    if uuid in EXEMPT_UUIDS:
        EXEMPT_UUIDS.remove(uuid)
    
    await message.reply(f"✅ Пользователь {username} полностью удалён из базы данных")
    
    await notify_admin(
        f"📶 <b>#mobguard</b>\n"
        f"➖➖➖➖➖➖➖➖➖\n"
        f"🗑️ <b>Удаление из БД</b>\n\n"
        f"Админ: {message.from_user.first_name}\n"
        f"User: {escape_html(username)}"
    )

# ================= CORE LOGIC =================

async def process_log_line(line: str):
    global PROCESSING_LOCK
    
    if not any(tag in line for tag in CONFIG['mobile_tags']): return
    if "accepted" not in line: return
    
    tag = next((t for t in CONFIG['mobile_tags'] if t in line), "UNKNOWN")

    try:
        uuid_match = REGEX_UUID.search(line)
        ip_match = REGEX_IP.search(line)
        
        if not uuid_match or not ip_match: return
        raw_id, ip = uuid_match.group(1), ip_match.group(1)
        
        lock_key = f"{raw_id}:{ip}:{tag}"
        if lock_key in PROCESSING_LOCK:
            _dbg('IMPORTANT', f"[DEDUP] Already processing {lock_key}, skipping")
            return
        
        PROCESSING_LOCK.add(lock_key)
        
        try:
            user_data = await panel.get_user_data(raw_id)
            if not user_data: 
                _dbg('IMPORTANT', f"[SKIP] User not found: {raw_id}")
                return
            
            uuid = user_data['uuid']
            
            # Exempt checks
            if int(user_data.get('id', 0)) in CONFIG.get('exempt_ids', []): return
            if user_data.get('telegramId') and int(user_data['telegramId']) in CONFIG.get('exempt_tg_ids', []): return
            if uuid in EXEMPT_UUIDS: return

            manual_override = await platform_store.async_get_ip_override(ip)
            if not manual_override:
                manual_override = await db.get_unsure_pattern(ip)

            cached = None if manual_override else await db.get_cached_decision(ip)
            if cached:
                bundle = DecisionBundle.from_cache_record(ip, cached)
                _dbg(
                    'CACHE',
                    f"[CACHE] {ip} ({bundle.isp}) -> Status={bundle.verdict}, confidence={bundle.confidence_band}",
                )
            else:
                bundle = await network_analyzer.check_is_mobile(ip, uuid, tag)

                _dbg('ANALYSIS', f"[ANALYSIS] Анализ IP: {ip} (UUID: {uuid}):")
                for entry in bundle.log:
                    _dbg('ANALYSIS', f"[PROGRESS] {entry}")

                await db.cache_decision(ip, bundle.to_cache_payload())
                _dbg(
                    'ANALYSIS',
                    f"[RESULT] {ip} ({bundle.isp}): Status={bundle.verdict}, confidence={bundle.confidence_band}",
                )

            event_id = await platform_store.async_record_analysis_event(user_data, ip, tag, bundle)
            bundle.event_id = event_id

            review_reason = review_reason_for_bundle(bundle)
            if review_reason:
                review_case = await platform_store.async_ensure_review_case(
                    user_data, ip, tag, bundle, event_id, review_reason
                )
                bundle.case_id = review_case.id
                await send_unsure_notify(user_data, bundle, tag, review_reason)

            if bundle.verdict in ('MOBILE', 'UNSURE', 'SKIP'):
                cleared_count = await db.clear_trackers_for_uuid(uuid)
                if cleared_count > 0:
                    _dbg(
                        'IMPORTANT',
                        f"[TRACKER] Cleared {cleared_count} tracker(s) for {uuid} (status={bundle.verdict})",
                    )
                return

            if config_flag('manual_review_mixed_home_enabled', False) and bundle.asn in CONFIG.get('mixed_asns', []):
                _dbg('IMPORTANT', f"[MANUAL_REVIEW] Mixed ASN {bundle.asn} HOME → sending for manual review")
                if not review_reason:
                    review_case = await platform_store.async_ensure_review_case(
                        user_data, ip, tag, bundle, event_id, "manual_review_mixed_home"
                    )
                    bundle.case_id = review_case.id
                    await send_unsure_notify(user_data, bundle, tag, "manual_review_mixed_home")
                return

            await handle_violation(
                user_data,
                tag,
                bundle,
                warning_only=config_flag('warning_only_mode', False)
                or CONFIG['settings'].get('shadow_mode', True)
                or should_warning_only(bundle)
                or not bundle.punitive_eligible,
            )
        
        finally:
            # Снимаем блокировку сразу после обработки (успешной или с ошибкой),
            # не допускаем «вечного» лока при исключении
            PROCESSING_LOCK.discard(lock_key)

    except Exception as e:
        logger.error(f"Log parse error: {e}")
        await notify_error(f"Log parse error: {e}")

async def handle_violation(user: Dict, tag: str, bundle: DecisionBundle, warning_only: bool = False):
    """Handle HOME decisions with conservative punitive gating."""
    if bundle.verdict != 'HOME' or bundle.confidence_band not in ('HIGH_HOME', 'PROBABLE_HOME'):
        return

    uuid = user['uuid']
    ip = bundle.ip
    isp = bundle.isp
    asn = bundle.asn
    log = bundle.log
    now = datetime.now()
    tracker_key = f"{uuid}:{ip}"
    warning_timeout = int(enforcement_value('warning_timeout_seconds'))
    usage_threshold = int(enforcement_value('usage_time_threshold'))
    warnings_before_ban = max(int(enforcement_value('warnings_before_ban')), 1)
    ban_durations = enforcement_value('ban_durations_minutes')
    if not isinstance(ban_durations, list) or not ban_durations:
        ban_durations = ENFORCEMENT_SETTINGS_DEFAULTS['ban_durations_minutes']
    review_url = platform_store.build_review_url(bundle.case_id) if bundle.case_id else ""

    _dbg(
        'IMPORTANT',
        f"[VIOLATION] {uuid} confidence={bundle.confidence_band} punitive={bundle.punitive_eligible} warning_only={warning_only}",
    )

    row = await db.fetch_one(
        """
        SELECT strikes, unban_time, warning_time, warning_count,
               restriction_mode, saved_traffic_limit_bytes,
               saved_traffic_limit_strategy, applied_traffic_limit_bytes
        FROM violations WHERE uuid=?
        """,
        (uuid,),
    )
    strikes = row[0] if row else 0
    unban_time_str = row[1] if row else None
    warning_time_str = row[2] if row else None
    warning_count = row[3] if row and len(row) > 3 else 0
    active_restriction_state = _violation_state_from_row(row)

    if unban_time_str:
        unban_dt = datetime.fromisoformat(unban_time_str)
        if unban_dt > now:
            _dbg('IMPORTANT', f"[ENFORCEMENT] User {uuid} active while banned. Re-disabling.")
            if not DRY_RUN:
                reapplied = await apply_remote_restriction_state_async(
                    panel,
                    uuid,
                    settings(),
                    active_restriction_state,
                )
                if not reapplied:
                    mode = active_restriction_state["restriction_mode"]
                    logger.error(
                        "[ENFORCEMENT] Failed to re-apply %s restriction for %s: %s",
                        mode,
                        uuid,
                        panel.last_error or "unknown error",
                    )
            return

    start_time = await db.get_tracker_start(tracker_key)
    if not start_time:
        await db.update_tracker(tracker_key, now)
        _dbg('IMPORTANT', f"[TRACKER] Start {tracker_key}")
        return

    await db.update_tracker(tracker_key, start_time)
    duration = (now - start_time).total_seconds()
    _dbg('IMPORTANT', f"[TRACKER] {uuid} duration {int(duration)}s")
    if duration < usage_threshold:
        return

    tg_id = user.get('telegramId') or ""
    common_context = {
        "username": user.get('username', 'N/A'),
        "uuid": uuid,
        "system_id": user.get('id') or "",
        "telegram_id": tg_id,
        "ip": ip,
        "isp": isp,
        "tag": tag,
        "confidence_band": bundle.confidence_band,
        "review_url": review_url,
        "warnings_before_ban": warnings_before_ban,
        "warning_count": warning_count,
        "warnings_left": max(warnings_before_ban - warning_count, 0),
        "ban_minutes": 0,
        "ban_text": "",
    }

    if warning_only:
        if admin_event_notifications_enabled("warning_only"):
            admin_msg = render_runtime_template(
                "admin_warning_only_template",
                {**common_context, "confidence_band": f"{bundle.confidence_band} / punitive disabled"},
            )
            admin_msg += "\n<b>Основание:</b>\n"
            for entry in log:
                admin_msg += f"  • {escape_html(entry)}\n"
            await notify_admin(admin_msg)
        await db.delete_tracker(tracker_key)

        if not DRY_RUN and user.get('telegramId') and user_event_notifications_enabled("warning_only"):
            user_msg = render_runtime_template("user_warning_only_template", common_context)
            await notify_user(int(user['telegramId']), user_msg)
        return

    if warning_time_str:
        warning_time = datetime.fromisoformat(warning_time_str)
        elapsed_warn = (now - warning_time).total_seconds()
        if elapsed_warn < warning_timeout:
            return

        warning_count += 1
        if warning_count <= warnings_before_ban:
            await db.execute(
                "INSERT OR REPLACE INTO violations (uuid, strikes, unban_time, last_strike_time, warning_time, warning_count) VALUES (?, ?, NULL, ?, ?, ?)",
                (uuid, strikes, now.isoformat(), now.isoformat(), warning_count),
            )
            if admin_event_notifications_enabled("warning"):
                admin_msg = render_runtime_template(
                    "admin_warning_template",
                    {
                        **common_context,
                        "warning_count": warning_count,
                        "warnings_left": max(warnings_before_ban - warning_count, 0),
                    },
                )
                await notify_admin(admin_msg)
            await db.delete_tracker(tracker_key)
            if not DRY_RUN and user.get('telegramId') and user_event_notifications_enabled("warning"):
                user_msg = render_runtime_template(
                    "user_warning_template",
                    {
                        **common_context,
                        "warning_count": warning_count,
                        "warnings_left": max(warnings_before_ban - warning_count, 0),
                    },
                )
                await notify_user(int(user['telegramId']), user_msg)
            return

        strikes += 1
        if strikes > len(ban_durations):
            strikes = len(ban_durations)
        await db.delete_tracker(tracker_key)

        ban_min = int(ban_durations[min(strikes - 1, len(ban_durations) - 1)])
        ban_text = format_duration_text(ban_min)
        restriction_state = build_auto_restriction_state(user, settings())

        unban_dt = now + timedelta(minutes=ban_min)
        await db.execute(
            """INSERT OR REPLACE INTO violations
                          (uuid, strikes, unban_time, last_strike_time, last_forgiven, warning_time, warning_count,
                           restriction_mode, saved_traffic_limit_bytes, saved_traffic_limit_strategy, applied_traffic_limit_bytes)
                          VALUES (?, ?, ?, ?, ?, NULL, 0, ?, ?, ?, ?)""",
            (
                uuid,
                strikes,
                unban_dt.isoformat(),
                now.isoformat(),
                now.isoformat(),
                restriction_state["restriction_mode"],
                restriction_state["saved_traffic_limit_bytes"],
                restriction_state["saved_traffic_limit_strategy"],
                restriction_state["applied_traffic_limit_bytes"],
            ),
        )
        await db.execute(
            """INSERT INTO violation_history
                          (uuid, ip, isp, asn, tag, strike_number, punishment_duration, timestamp)
                          VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (uuid, ip, isp, asn, tag, strikes, ban_min, now.isoformat()),
        )

        if config_flag('manual_ban_approval_enabled', False):
            status_icon = "👮 <b>ТРЕБУЕТСЯ УТВЕРЖДЕНИЕ</b>"
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="✅ ОДОБРИТЬ", callback_data=f"ban_approve:{uuid}:{ip}:{strikes}:{ban_min}")],
                    [InlineKeyboardButton(text="❌ ОТМЕНИТЬ", callback_data=f"ban_reject:{uuid}:{ip}")],
                ]
            )
        else:
            status_icon = "⛔️" if not DRY_RUN else "[ОТЛАДКА] ⛔️"
            keyboard = None

        if admin_event_notifications_enabled("ban"):
            admin_msg = render_runtime_template(
                "admin_ban_template",
                {
                    **common_context,
                    "warning_count": warning_count,
                    "warnings_left": 0,
                    "ban_minutes": ban_min,
                    "ban_text": ban_text,
                },
            )
            admin_msg = admin_msg.replace(
                "<b>ОГРАНИЧЕНИЕ ДОСТУПА</b>",
                f"{status_icon} <b>ОГРАНИЧЕНИЕ ДОСТУПА</b>",
            )
            admin_msg += "\n<b>Основание:</b>\n"
            for entry in log:
                admin_msg += f"  • {escape_html(entry)}\n"
            if keyboard:
                await notify_admin(admin_msg, reply_markup=keyboard)
            else:
                await notify_admin(admin_msg)

        if config_flag('manual_ban_approval_enabled', False):
            _dbg('IMPORTANT', f"[MANUAL_REVIEW] Access restriction awaiting approval")
            return

        if not DRY_RUN:
            if restriction_state["restriction_mode"] == TRAFFIC_CAP_RESTRICTION_MODE:
                apply_result = await apply_remote_traffic_cap_async(
                    panel,
                    uuid,
                    user,
                    int(settings().get("traffic_cap_increment_gb", ENFORCEMENT_SETTINGS_DEFAULTS["traffic_cap_increment_gb"])),
                )
                restricted = bool(apply_result["remote_updated"])
            else:
                restricted = await apply_remote_access_state_async(
                    panel,
                    uuid,
                    settings(),
                    restricted=True,
                )
            if not restricted:
                mode = restriction_state["restriction_mode"]
                logger.error(
                    "[ENFORCEMENT] Failed to apply %s restriction for %s: %s",
                    mode,
                    uuid,
                    panel.last_error or "unknown error",
                )
                await notify_error(
                    f"Не удалось применить ограничение доступа для {uuid}: {panel.last_error or 'unknown error'}"
                )
                return
            if user.get('telegramId') and user_event_notifications_enabled("ban"):
                user_msg = render_runtime_template(
                    "user_ban_template",
                    {
                        **common_context,
                        "warning_count": warning_count,
                        "warnings_left": 0,
                        "ban_minutes": ban_min,
                        "ban_text": ban_text,
                    },
                )
                await notify_user(int(user['telegramId']), user_msg)
        return

    await db.execute(
        """INSERT OR REPLACE INTO violations
                  (uuid, strikes, unban_time, last_strike_time, warning_time, warning_count)
                  VALUES (?, ?, NULL, ?, ?, ?)""",
        (uuid, strikes, now.isoformat(), now.isoformat(), 1),
    )

    if admin_event_notifications_enabled("warning"):
        admin_msg = render_runtime_template(
            "admin_warning_template",
            {
                **common_context,
                "warning_count": 1,
                "warnings_left": max(warnings_before_ban - 1, 0),
            },
        )
        admin_msg += "\n<b>Основание:</b>\n"
        for entry in log:
            admin_msg += f"  • {escape_html(entry)}\n"
        await notify_admin(admin_msg)

    if not DRY_RUN and user.get('telegramId') and user_event_notifications_enabled("warning"):
        user_msg = render_runtime_template(
            "user_warning_template",
            {
                **common_context,
                "warning_count": 1,
                "warnings_left": max(warnings_before_ban - 1, 0),
            },
        )
        await notify_user(int(user['telegramId']), user_msg)

# ================= BACKGROUND WORKERS =================

async def telegram_queue_processor():
    global TG_MESSAGE_QUEUE, TG_LAST_MESSAGE_TIME
    logger.info("Starting Telegram Queue Processor...")
    
    TG_MESSAGE_QUEUE = asyncio.Queue()
    
    while True:
        try:
            msg_type, *args = await TG_MESSAGE_QUEUE.get()
            
            now = datetime.now()
            elapsed = (now - TG_LAST_MESSAGE_TIME).total_seconds()
            if elapsed < TG_MIN_INTERVAL:
                await asyncio.sleep(TG_MIN_INTERVAL - elapsed)
            
            try:
                if msg_type == 'admin':
                    text, reply_markup = args[0], args[1] if len(args) > 1 else None
                    if bot and TG_ADMIN_CHAT_ID and admin_notifications_enabled():
                        await bot.send_message(TG_ADMIN_CHAT_ID, text, message_thread_id=TG_TOPIC_ID or None, reply_markup=reply_markup)
                elif msg_type == 'user':
                    tg_id, text = args
                    if main_bot and user_notifications_enabled():
                        await main_bot.send_message(tg_id, text)
                
                TG_LAST_MESSAGE_TIME = datetime.now()
            
            except Exception as e:
                logger.error(f"TG Queue send error: {e}")
                if "Flood control" in str(e):
                    # Extract retry time from error message
                    import re
                    match = re.search(r'retry after (\d+)', str(e))
                    if match:
                        retry_seconds = int(match.group(1))
                        logger.warning(f"Flood control hit, waiting {retry_seconds}s")
                        await asyncio.sleep(retry_seconds + 1)
                        # Re-queue message
                        await TG_MESSAGE_QUEUE.put((msg_type, *args))
        
        except Exception as e:
            logger.error(f"TG Queue processor error: {e}")
            await asyncio.sleep(1)

async def log_reader_task():
    logger.info("Starting Log Reader...")
    log_file = CONFIG['settings']['log_file']
    
    while not os.path.exists(log_file):
        logger.warning(f"Log file {log_file} not found, waiting...")
        await asyncio.sleep(5)
    
    with open(log_file, 'r') as f:
        f.seek(0, 2)  # Seek to end
        while True:
            line = f.readline()
            if line:
                asyncio.create_task(process_log_line(line))
            else:
                await asyncio.sleep(0.1)

async def unbanner_task():
    logger.info("Starting Unbanner Worker...")
    while True:
        await asyncio.sleep(30)
        now = datetime.now()
        
        rows = await db.fetch_all(
            """
            SELECT uuid, unban_time, restriction_mode, saved_traffic_limit_bytes,
                   saved_traffic_limit_strategy, applied_traffic_limit_bytes
            FROM violations WHERE unban_time IS NOT NULL AND unban_time <= ?
            """,
            (now.isoformat(),),
        )
        
        for uuid, unban_time_str, restriction_mode, saved_limit_bytes, saved_strategy, applied_limit_bytes in rows:
            if DRY_RUN:
                await db.execute("UPDATE violations SET unban_time=NULL WHERE uuid=?", (uuid,))
                continue

            restore_result = await restore_remote_restriction_state_async(
                panel,
                uuid,
                settings(),
                {
                    "restriction_mode": restriction_mode,
                    "saved_traffic_limit_bytes": saved_limit_bytes,
                    "saved_traffic_limit_strategy": saved_strategy,
                    "applied_traffic_limit_bytes": applied_limit_bytes,
                },
            )
            if not restore_result["remote_updated"]:
                logger.error(
                    "[UNBAN] Failed to restore restriction state %s for %s: %s",
                    normalize_restriction_mode(restriction_mode),
                    uuid,
                    panel.last_error or "unknown error",
                )
                continue

            await db.execute("UPDATE violations SET unban_time=NULL WHERE uuid=?", (uuid,))
            logger.info(f"[UNBAN] {uuid}")
            user = await panel.get_user_data(uuid)
            if user and user.get('telegramId'):
                msg = "✅ Полный доступ восстановлен. Пожалуйста, соблюдайте правила использования."
                await notify_user(int(user['telegramId']), msg)
            
            await notify_admin(
                f"📶 <b>#mobguard</b>\n"
                f"➖➖➖➖➖➖➖➖➖\n"
                f"✅ <b>Автоматическое восстановление доступа</b>\n"
                f"User: {escape_html(user.get('username', uuid)) if user else uuid}"
            )

async def forgiveness_task():
    logger.info("Starting Forgiveness Worker...")
    while True:
        await asyncio.sleep(3600)
        now = datetime.now()
        
        rows = await db.fetch_all("""SELECT uuid, strikes, last_forgiven, last_strike_time FROM violations 
                                     WHERE strikes > 0 AND last_forgiven IS NOT NULL""", ())
        
        for uuid, strikes, last_forgiven_str, last_strike_str in rows:
            if strikes > 0 and last_forgiven_str:
                last_forgiven = datetime.fromisoformat(last_forgiven_str)
                days_since_forgiveness = (now - last_forgiven).days
                
                # Прощаем только если прошло >= 30 дней
                if days_since_forgiveness >= 30:
                    new_strikes = strikes - 1
                    await db.execute("""UPDATE violations SET strikes=?, last_forgiven=? WHERE uuid=?""",
                                   (new_strikes, now.isoformat(), uuid))
                    
                    user = await panel.get_user_data(uuid)
                    name = user.get('username', uuid) if user else uuid
                    
                    # Логируем для отладки
                    _dbg('IMPORTANT', f"[FORGIVENESS] {uuid} ({name}): {strikes} -> {new_strikes}, last_forgiven was {days_since_forgiveness} days ago")
                    
                    admin_msg = (
                        f"📶 <b>#mobguard</b>\n"
                        f"➖➖➖➖➖➖➖➖➖\n"
                        f"🎁 <b>Автопрощение (30 дней)</b>\n\n"
                        f"Username: {name}\n"
                        f"Страйки: {strikes} -> {new_strikes}\n"
                        f"Прошло дней: {days_since_forgiveness}"
                    )
                    await notify_admin(admin_msg)

async def daily_report_task():
    logger.info("Starting Daily Report Worker...")

    def _seconds_until_target():
        now = datetime.now()
        h, m = (int(x) for x in CONFIG['settings'].get('report_time', '06:00').split(':'))
        target = now.replace(hour=h, minute=m, second=0, microsecond=0)
        if target <= now: target += timedelta(days=1)
        return (target - now).total_seconds()

    wait = _seconds_until_target()
    logger.info(f"[REPORT] Waiting {wait/3600:.1f}h")
    await asyncio.sleep(wait)

    while True:
        now = datetime.now()
        active_bans = await db.fetch_one("SELECT COUNT(*) FROM violations WHERE unban_time IS NOT NULL AND unban_time > ?", (now.isoformat(),))
        active_warnings = await db.fetch_one("SELECT COUNT(*) FROM violations WHERE warning_time IS NOT NULL", ())
        total_strikes_today = await db.fetch_one("SELECT COUNT(*) FROM violation_history WHERE timestamp >= ?", ((now - timedelta(days=1)).isoformat(),))

        msg = (
            f"📶 <b>#mobguard</b>\n"
            f"➖➖➖➖➖➖➖➖➖\n"
            f"💚 <b>Ежедневный отчёт • {now.strftime('%d.%m %H:%M')}</b>\n\n"
            f"📊 <b>Сводка за сутки:</b>\n"
            f"  • Новых страйков: {total_strikes_today[0]}\n"
            f"  • Активных ограничений: {active_bans[0]}\n"
            f"  • Активных предупреждений: {active_warnings[0]}\n"
            f"  • Режим: {'⚠️ ОТЛАДКА' if DRY_RUN else '✅ ОГРАНИЧЕНИЯ'}\n"
        )

        # Перед чтением статистики принудительно сбрасываем буфер,
        # чтобы данные за последние ~5 минут не пропали
        await flush_stats_to_db()

        # Читаем статистику из БД за вчерашний день — именно эти сутки завершились к моменту отчёта
        yesterday = (now - timedelta(days=1)).strftime('%Y-%m-%d')
        keyword_rows = await db.get_daily_stats('keyword', date=yesterday)
        asn_rows = await db.get_daily_stats('asn', date=yesterday)
        potential_kw_rows = await db.get_daily_stats('potential_kw', date=yesterday)

        # Триггерные слова
        if keyword_rows:
            kw_dict: Dict[str, Dict[str, int]] = {}
            for kw, sub_key, value in keyword_rows:
                if kw not in kw_dict:
                    kw_dict[kw] = {'mobile': 0, 'home': 0}
                if sub_key in kw_dict[kw]:
                    kw_dict[kw][sub_key] = value
            sorted_kw = sorted(kw_dict.items(), key=lambda x: x[1]['mobile'] + x[1]['home'], reverse=True)
            msg += f"\n🏷️ <b>Триггерные слова (за сутки):</b>\n"
            for kw, counts in sorted_kw:
                total = counts['mobile'] + counts['home']
                msg += f"  • <code>{escape_html(kw)}</code> — всего {total}: ✅mob {counts['mobile']} / ⛔home {counts['home']}\n"
        else:
            msg += f"\n🏷️ <b>Триггерные слова:</b> не было срабатываний\n"

        # ASN статистика
        if asn_rows:
            asn_dict: Dict[str, Dict[str, int]] = {}
            for asn_key, sub_key, value in asn_rows:
                if asn_key not in asn_dict:
                    asn_dict[asn_key] = {'mobile': 0, 'home': 0, 'unsure': 0}
                if sub_key in asn_dict[asn_key]:
                    asn_dict[asn_key][sub_key] = value
            sorted_asn = sorted(asn_dict.items(), key=lambda x: x[1]['mobile'] + x[1]['home'] + x[1]['unsure'], reverse=True)
            msg += f"\n🌐 <b>ASN статистика (за сутки):</b>\n"
            for asn_key, counts in sorted_asn[:15]:
                total = counts['mobile'] + counts['home'] + counts['unsure']
                pct_mob = int(counts['mobile'] / total * 100) if total else 0
                msg += f"  • AS{asn_key} — всего {total}: ✅mob {counts['mobile']} ({pct_mob}%) / ⛔home {counts['home']} / ❓unsure {counts['unsure']}\n"
            
            # UNSURE статистика (отдельная секция из тех же данных)
            unsure_asns = [(k, v['unsure']) for k, v in asn_dict.items() if v['unsure'] > 0]
            if unsure_asns:
                sorted_unsure = sorted(unsure_asns, key=lambda x: x[1], reverse=True)[:10]
                msg += f"\n❓ <b>UNSURE статистика (за сутки):</b>\n"
                for asn_key, count in sorted_unsure:
                    msg += f"  • AS{asn_key} — {count} случаев неопределённости\n"
        else:
            msg += f"\n🌐 <b>ASN статистика:</b> нет данных\n"

        # Потенциальные триггеры
        if potential_kw_rows:
            top_potential = sorted(potential_kw_rows, key=lambda x: x[2], reverse=True)[:10]
            msg += f"\n🔍 <b>Потенциальные триггеры (не в базе, топ 10):</b>\n"
            for word, _, count in top_potential:
                msg += f"  • <code>{escape_html(word)}</code> — {count} раз\n"

        await notify_admin(msg)
        
        # Очищаем вчерашнюю статистику из БД после отправки отчёта,
        # а также удаляем совсем старые записи (старше 7 дней) на случай пропущенных отчётов
        await db.clear_daily_stats(date=yesterday)
        await db.cleanup_old_daily_stats(days=7)
        
        await asyncio.sleep(86400)

async def flush_stats_to_db():
    """
    Сбрасывает накопленный in-memory буфер статистики (_STATS_BUFFER) в таблицу daily_stats.
    Вызывается как фоновой задачей stats_flush_task(), так и принудительно перед отчётом.
    """
    global _STATS_BUFFER

    snapshot = _STATS_BUFFER
    _STATS_BUFFER = {'asn': {}, 'keyword': {}, 'potential_kw': {}}

    try:
        for asn, counts in snapshot['asn'].items():
            for sub_key, value in counts.items():
                if value > 0:
                    await db.increment_daily_stat('asn', str(asn), sub_key, amount=value)

        for kw, counts in snapshot['keyword'].items():
            for sub_key, value in counts.items():
                if value > 0:
                    await db.increment_daily_stat('keyword', kw, sub_key, amount=value)

        for word, count in snapshot['potential_kw'].items():
            if count > 0:
                await db.increment_daily_stat('potential_kw', word, '', amount=count)

    except Exception as e:
        logger.error(f"[STATS FLUSH] Ошибка при сбросе статистики в БД: {e}")
        # При ошибке возвращаем данные обратно в буфер, чтобы не потерять
        for asn, counts in snapshot['asn'].items():
            if asn not in _STATS_BUFFER['asn']:
                _STATS_BUFFER['asn'][asn] = {'mobile': 0, 'home': 0, 'unsure': 0}
            for sub_key, value in counts.items():
                _STATS_BUFFER['asn'][asn][sub_key] += value
        for kw, counts in snapshot['keyword'].items():
            if kw not in _STATS_BUFFER['keyword']:
                _STATS_BUFFER['keyword'][kw] = {'mobile': 0, 'home': 0}
            for sub_key, value in counts.items():
                _STATS_BUFFER['keyword'][kw][sub_key] += value
        for word, count in snapshot['potential_kw'].items():
            _STATS_BUFFER['potential_kw'][word] = _STATS_BUFFER['potential_kw'].get(word, 0) + count


async def stats_flush_task():
    """
    Фоновая задача: сбрасывает накопленный in-memory буфер статистики (_STATS_BUFFER)
    в таблицу daily_stats SQLite раз в 5 минут.

    Зачем: _record_stats() вызывается на каждый обработанный IP, иногда десятки раз
    в секунду. Если писать в БД сразу (через ensure_future), возникает шквал мелких
    транзакций — WAL-файл раздувается и диск переполняется. Батчевый сброс решает это.
    """
    logger.info("Starting Stats Flush Worker...")

    while True:
        await asyncio.sleep(300)  # сброс каждые 5 минут
        await flush_stats_to_db()


async def live_rules_refresh_task():
    logger.info("Starting Live Rules Refresh Worker...")
    while True:
        try:
            await asyncio.get_running_loop().run_in_executor(None, refresh_runtime_state_from_config)
        except Exception as e:
            logger.error(f"[LIVE RULES] Refresh failed: {e}")
        await asyncio.sleep(int(CONFIG['settings'].get('live_rules_refresh_seconds', 15)))


async def learning_promotion_task():
    logger.info("Starting Learning Promotion Worker...")
    while True:
        try:
            await platform_store.async_promote_learning_patterns()
        except Exception as e:
            logger.error(f"[LEARNING] Promotion failed: {e}")
        await asyncio.sleep(900)


async def core_heartbeat_task():
    logger.info("Starting Core Heartbeat Worker...")
    while True:
        try:
            await platform_store.async_update_service_heartbeat(
                "mobguard-core",
                "ok",
                {
                    "debug": DEBUG_LEVEL,
                    "dry_run": DRY_RUN,
                    "shadow_mode": CONFIG['settings'].get('shadow_mode', True),
                    "queue_size": TG_MESSAGE_QUEUE.qsize() if TG_MESSAGE_QUEUE else 0,
                    "review_ui_base_url": CONFIG['settings'].get('review_ui_base_url', ''),
                },
            )
        except Exception as e:
            logger.error(f"[HEARTBEAT] Failed to update core heartbeat: {e}")
        await asyncio.sleep(15)


async def cleanup_task():
    global UNSURE_NOTIFIED, PROCESSING_LOCK
    logger.info("Starting Cleanup Worker...")
    
    while True:
        await asyncio.sleep(600)
        now = datetime.now()
        
        # Clean old trackers (>1 hour inactive)
        limit_tracker = (now - timedelta(hours=1)).isoformat()
        await db.execute("DELETE FROM active_trackers WHERE last_seen < ?", (limit_tracker,))
        
        # Clean expired IP cache
        limit_ip = now.isoformat()
        await db.execute("DELETE FROM ip_decisions WHERE expires < ?", (limit_ip,))
        
        # Clean old UNSURE patterns (>7 days)
        await db.cleanup_old_unsure_patterns(7)
        
        # Clean old daily_stats (>7 days) — на случай если ежедневный отчёт не отработал
        await db.cleanup_old_daily_stats(7)

        # Clean exact override/session tables managed by web panel
        await db.execute("DELETE FROM exact_ip_overrides WHERE expires_at IS NOT NULL AND expires_at < ?", (limit_ip,))
        await db.execute("DELETE FROM admin_sessions WHERE expires_at < ?", (limit_ip,))
        
        # Clean UNSURE_NOTIFIED every 6 hours (36 iterations * 600s = 6h)
        if len(UNSURE_NOTIFIED) > 0 and now.hour % 6 == 0 and now.minute < 10:
            count = len(UNSURE_NOTIFIED)
            UNSURE_NOTIFIED.clear()
            logger.info(f"[CLEANUP] Cleared {count} UNSURE notifications from memory")
        
        # Clean PROCESSING_LOCK (shouldn't grow, but safety measure)
        if len(PROCESSING_LOCK) > 1000:
            PROCESSING_LOCK.clear()
            logger.warning("[CLEANUP] Cleared processing lock (>1000 entries)")

async def ip_api_pool_processor():
    global IP_API_RATE_LIMITED, IP_API_RATE_LIMIT_UNTIL, IP_API_PENDING_POOL
    logger.info("Starting IP-API Pool Processor...")
    
    while True:
        await asyncio.sleep(300)
        now = datetime.now()
        
        if not IP_API_RATE_LIMITED and len(IP_API_PENDING_POOL) > 0:
            logger.info(f"Processing pending IP pool: {len(IP_API_PENDING_POOL)} IPs")
            pending_ips = list(IP_API_PENDING_POOL)
            IP_API_PENDING_POOL.clear()
            
            processed = 0
            for i in range(0, len(pending_ips), 10):
                batch = pending_ips[i:i + 10]
                for ip in batch:
                    try:
                        await network_analyzer._check_ip_api(ip)
                        processed += 1
                        if IP_API_RATE_LIMITED:
                            remaining = pending_ips[i + batch.index(ip):]
                            IP_API_PENDING_POOL.update(remaining)
                            break
                    except Exception: 
                        pass
                
                if IP_API_RATE_LIMITED: break
                if i + 10 < len(pending_ips): await asyncio.sleep(1)
            
            if not IP_API_RATE_LIMITED and processed > 0:
                await notify_admin(
                    f"📶 <b>#mobguard</b>\n"
                    f"➖➖➖➖➖➖➖➖➖\n"
                    f"🔄 <b>IP-API Pool Processed</b>\n\n"
                    f"Обработано IP: {processed}\n"
                    f"Статус: ✅ Успешно"
                )
        
        elif IP_API_RATE_LIMITED and IP_API_RATE_LIMIT_UNTIL:
            if now >= IP_API_RATE_LIMIT_UNTIL:
                IP_API_RATE_LIMITED = False
                IP_API_RATE_LIMIT_UNTIL = None
                await notify_admin(
                    f"📶 <b>#mobguard</b>\n"
                    f"➖➖➖➖➖➖➖➖➖\n"
                    f"✅ <b>IP-API Recovered</b>\n\n"
                    f"Пул ожидания: {len(IP_API_PENDING_POOL)} IP"
                )

# ================= STARTUP & MAIN =================

def pre_flight_check():
    print("=" * 60)
    print("MobGuard - VPN Mobile Network Monitoring System")
    print("Version 0.9.3 - Polished")
    print("=" * 60)
    
    config_ok = True
    if not PANEL_TOKEN:
        print("❌ ERROR: Missing PANEL_TOKEN (.env)")
        config_ok = False
    if not os.getenv("IPINFO_TOKEN"):
        print("⚠️ WARNING: IPINFO_TOKEN missing. ASN/ISP detection will degrade and scores may collapse to 0.")
    if not TG_ADMIN_BOT_TOKEN:
        print("⚠️ WARNING: TG_ADMIN_BOT_TOKEN missing. Admin Telegram bot will be disabled.")
    if not TG_MAIN_BOT_TOKEN:
        print("⚠️ WARNING: TG_MAIN_BOT_TOKEN missing. User Telegram notifications will be disabled.")
        
    if not os.path.exists(CONFIG['settings']['log_file']):
        print(f"❌ ERROR: Log file not found: {CONFIG['settings']['log_file']}")
        config_ok = False
        
    if not config_ok:
        print("\nExiting due to configuration errors.")
        exit(1)
        
    db.init_db()
    platform_store.init_schema()
    refresh_runtime_state_from_config()
    print("✅ System Ready & DB Initialized")
    print(f"   • Debug: {DEBUG_LEVEL}")
    print(f"   • Mode: {'DRY RUN' if DRY_RUN else 'PRODUCTION'}")
    print(f"   • Shadow mode: {'ON' if CONFIG['settings'].get('shadow_mode', True) else 'OFF'}")
    print(f"   • Gray zone threshold: {CONFIG['settings']['gray_zone_threshold']}")
    print(f"   • Telegram rate limiting: {TG_MIN_INTERVAL}s")
    print(f"   • Admin bot: {'ENABLED' if admin_bot_available() else 'DISABLED'}")
    print(f"   • User bot: {'ENABLED' if main_bot_available() else 'DISABLED'}")
    print("=" * 60)

async def main():
    pre_flight_check()
    
    shared_http_session = aiohttp.ClientSession()
    panel.set_session(shared_http_session)
    network_analyzer.set_session(shared_http_session)
    await ipinfo_api.init_session(shared_http_session)
    
    asyncio.create_task(telegram_queue_processor())
    asyncio.create_task(log_reader_task())
    asyncio.create_task(unbanner_task())
    asyncio.create_task(cleanup_task())
    asyncio.create_task(forgiveness_task())
    asyncio.create_task(daily_report_task())
    asyncio.create_task(ip_api_pool_processor())
    asyncio.create_task(stats_flush_task())
    asyncio.create_task(live_rules_refresh_task())
    asyncio.create_task(learning_promotion_task())
    asyncio.create_task(core_heartbeat_task())
    
    await asyncio.sleep(1)
    
    admin_msg = (
        f"📶 <b>#mobguard</b>\n"
        f"➖➖➖➖➖➖➖➖➖\n"
        f"🚀 <b>MobGuard запущен</b>\n"
        f"Версия 0.9.0 web\n"
        f"Debug: {'ВКЛ' if DEBUG_MODE else 'ВЫКЛ'}\n"
        f"Режим: {'ОТЛАДКА' if DRY_RUN else 'ПРОД'}\n"
        f"Shadow mode: {'ВКЛ' if CONFIG['settings'].get('shadow_mode', True) else 'ВЫКЛ'}\n"
        f"Модель: MOBILE / HOME / UNSURE + ML"
    )
    await notify_admin(admin_msg)

    if admin_commands_enabled() and bot:
        await dp.start_polling(bot)
    else:
        await asyncio.Event().wait()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("\n[*] MobGuard Stopped.")
    except Exception as e:
        logger.critical(f"Critical error: {e}")
        print(f"\n[!] Critical error: {e}")
