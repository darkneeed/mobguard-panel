import aiohttp
import logging
import os
import re
from datetime import datetime, timedelta
from typing import Dict, Optional, Any
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def _resolve_runtime_dir() -> str:
    explicit = os.getenv("BAN_SYSTEM_DIR")
    if explicit:
        return explicit

    candidates = [
        os.path.join(BASE_DIR, "runtime"),
        "/opt/mobguard/runtime",
        "/opt/ban_system",
    ]
    for candidate in candidates:
        if os.path.exists(candidate):
            return candidate
    return candidates[1]


BAN_SYSTEM_DIR = _resolve_runtime_dir()
ENV_PATH = os.getenv("MOBGUARD_ENV_FILE", os.path.join(os.path.dirname(BAN_SYSTEM_DIR), ".env"))
load_dotenv(ENV_PATH)

logger = logging.getLogger("IPInfoAPI")

class IPInfoAPI:
    def __init__(self):
        self.token = os.getenv("IPINFO_TOKEN")
        self.base_url = "https://ipinfo.io"
        # Общая сессия aiohttp — инициализируется извне через init_session()
        self.session: Optional[aiohttp.ClientSession] = None
        self.cache = {}
        self.cache_ttl = timedelta(hours=24)
        
        # Ключевые слова для определения датацентров берутся из конфига (см. exclude_isp_keywords).
        # Этот список используется как fallback если конфиг ещё не передан.
        self._fallback_dc_keywords = {
            'hosting', 'datacenter', 'data center', 'cloud', 'vps', 'server',
            'dedicated', 'colocation', 'cdn', 'proxy', 'vpn', 'hetzner',
            'digitalocean', 'aws', 'amazon', 'google cloud', 'azure', 'oracle',
            'alibaba', 'tencent', 'ovh', 'linode', 'vultr', 'selectel'
        }
        # Будет заменён на данные из конфига после вызова set_config()
        self._dc_keywords: Optional[set] = None

    def set_config(self, config: dict):
        """Инициализирует список ключевых слов датацентров из конфига (exclude_isp_keywords)."""
        kw_list = config.get('exclude_isp_keywords', [])
        self._dc_keywords = set(kw_list)

    @property
    def dc_keywords(self) -> set:
        """Возвращает актуальный набор ключевых слов датацентров."""
        if self._dc_keywords is not None:
            return self._dc_keywords
        return self._fallback_dc_keywords

    async def init_session(self, session: Optional[aiohttp.ClientSession] = None):
        """
        Инициализирует сессию.
        Если передана внешняя сессия (shared) — использует её.
        Иначе создаёт собственную.
        """
        if session is not None:
            self.session = session
        elif not self.session:
            self.session = aiohttp.ClientSession(headers={
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/json"
            })

    async def close_session(self):
        """Закрывает сессию только если она была создана внутри класса."""
        if self.session and not self.session.closed:
            await self.session.close()
            self.session = None

    def _get_from_cache(self, ip: str) -> Optional[Dict]:
        if ip in self.cache:
            entry = self.cache[ip]
            if datetime.now() < entry['expires']:
                return entry['data']
            else:
                del self.cache[ip]
        return None

    def _save_to_cache(self, ip: str, data: Dict):
        self.cache[ip] = {
            'data': data,
            'expires': datetime.now() + self.cache_ttl
        }

    async def get_ip_info(self, ip: str) -> Dict[str, Any]:
        """Получение информации об IP с кешированием"""
        cached = self._get_from_cache(ip)
        if cached:
            return cached

        if not self.token:
            logger.warning("IPINFO_TOKEN не задан, возвращаем пустые данные")
            return {}

        try:
            if not self.session:
                await self.init_session()
            
            headers = {
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/json"
            }
            async with self.session.get(f"{self.base_url}/{ip}", headers=headers) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    self._save_to_cache(ip, data)
                    return data
                elif resp.status == 429:
                    logger.error("IPInfo: превышен лимит запросов (rate limit)")
                    return {}
                else:
                    logger.error(f"IPInfo ошибка {resp.status} для IP {ip}")
                    return {}
        except Exception as e:
            logger.error(f"IPInfo: запрос завершился с ошибкой: {e}")
            return {}

    def parse_asn(self, org_string: str) -> Optional[int]:
        """Извлекает ASN из строки org (например, 'AS12345 Google LLC')"""
        if not org_string:
            return None
        match = re.search(r'AS(\d+)', org_string, re.IGNORECASE)
        if match:
            return int(match.group(1))
        return None

    def normalize_isp_name(self, org_string: str) -> str:
        """Очищает название провайдера от ASN и мусора"""
        if not org_string:
            return "Unknown ISP"
        # Удаляем AS xxxxx
        name = re.sub(r'^AS\d+\s+', '', org_string).strip()
        return name

    def is_datacenter(self, org: str, hostname: str = "") -> bool:
        """Проверка на датацентр/хостинг по ключевым словам из конфига"""
        text = (f"{org} {hostname}").lower()
        for kw in self.dc_keywords:
            if kw in text:
                return True
        return False

# Глобальный экземпляр
ipinfo_api = IPInfoAPI()
