from typing import Tuple, Dict
import logging

logger = logging.getLogger("BehavioralAnalyzers")


class ConcurrencyDetector:
    
    def __init__(self, db, config):
        self.db = db
        self.config = config
    
    async def check(self, ip: str, uuid: str) -> Tuple[bool, int]:
        # Порог берётся из конфига (concurrency_threshold), по умолчанию 2
        threshold = self.config['settings'].get('concurrency_threshold', 2)
        concurrent_count = await self.db.count_concurrent_users(ip, minutes=15)
        immunity = concurrent_count >= threshold
        
        return immunity, concurrent_count
    
    async def get_bonus(self, ip: str, uuid: str) -> Tuple[int, str]:
        immunity, count = await self.check(ip, uuid)
        
        if immunity:
            # Это CGNAT — блокируем HOME
            log = f"⚡ CGNAT detected: {count} concurrent users"
            return 0, log  # Бонус 0, но иммунитет применяется отдельно
        
        return 0, ""


class ChurnAnalyzer:
    
    def __init__(self, db, config):
        self.db = db
        self.config = config
    
    async def calculate_churn(self, uuid: str, hours: int = 6) -> int:
        """Подсчёт уникальных IP за последние N часов"""
        return await self.db.get_churn_rate(uuid, hours)
    
    def get_mobility_score(self, churn_rate: int, hours: int) -> Tuple[int, str]:
        """
        Возвращает бонус и лог на основе уже вычисленного churn_rate
        """
        # Настройки берём из конфига
        high_threshold = self.config['settings'].get('churn_mobile_threshold', 3)
        high_bonus = self.config['settings'].get('score_churn_high_bonus', 30)
        medium_bonus = self.config['settings'].get('score_churn_medium_bonus', 15)
        
        if churn_rate >= high_threshold:
            log = f"+{high_bonus} High churn ({churn_rate} IPs/{hours}h)"
            return high_bonus, log
        elif churn_rate >= 2:
            log = f"+{medium_bonus} Medium churn ({churn_rate} IPs/{hours}h)"
            return medium_bonus, log
        else:
            return 0, ""


class LifetimeAnalyzer:
    
    def __init__(self, db, config):
        self.db = db
        self.config = config
    
    async def get_session_lifetime(self, uuid: str, ip: str) -> float:
        """Возвращает длительность текущей сессии в часах (запрос к БД)"""
        return await self.db.get_session_lifetime(uuid, ip)
    
    def get_stationarity_score(self, lifetime: float) -> Tuple[int, str]:
        """Оценка стационарности на основе уже полученного lifetime"""
        hours_threshold = self.config['settings'].get('lifetime_stationary_hours', 12)
        # Штраф за длительную стационарность берётся из конфига
        penalty = self.config['settings'].get('score_stationary_penalty', -5)
        is_stationary = lifetime > hours_threshold
        
        if is_stationary:
            log = f"{penalty} Long session ({lifetime:.1f}h)"
            return penalty, log
        
        return 0, ""


class SubnetIntelligence:
    """
    Коллективный анализ подсетей /24
    
    Логика (АСИММЕТРИЧНАЯ):
    
    MOBILE /24:
    - Триггер: 1-2 подтверждённых MOBILE в подсети
    - Действие: Вся подсеть считается MOBILE
    - TTL: 45-60 дней
    - Вес: СИЛЬНЫЙ бонус (+40)
    - Приоритет: ВЫСОКИЙ
    
    HOME /24:
    - Триггер: Минимум 3 разных UUID = HOME
    - Условия: ASN mixed, нет Concurrency
    - TTL: 15-30 дней
    - Вес: СЛАБЫЙ штраф (-10)
    - Приоритет: НИЗКИЙ
    """
    
    def __init__(self, db, config):
        self.db = db
        self.config = config
    
    async def record_signal(self, ip: str, uuid: str, signal_type: str):
        """Записывает сигнал в БД"""
        await self.db.record_subnet_signal(ip, uuid, signal_type)
    
    async def get_evidence(self, ip: str) -> Dict[str, int]:
        """
        Возвращает статистику по подсети:
        {'MOBILE': 2, 'HOME': 0}
        """
        return await self.db.get_subnet_evidence(ip)
    
    async def get_subnet_bonus(self, ip: str) -> Tuple[int, str]:
        """
        Возвращает бонус/штраф на основе evidence
        
        АСИММЕТРИЧНАЯ ЛОГИКА:
        - 1+ MOBILE: +40 (сильный бонус, высокий приоритет)
        - 3+ HOME: -10 (слабый штраф, низкий приоритет)
        """
        mobile_bonus = self.config['settings'].get('score_subnet_mobile_bonus', 40)
        home_penalty = self.config['settings'].get('score_subnet_home_penalty', -10)
        mobile_threshold = self.config['settings'].get('subnet_mobile_min_evidence', 1)
        home_threshold = self.config['settings'].get('subnet_home_min_evidence', 3)
        
        evidence = await self.get_evidence(ip)
        subnet = self.db.get_subnet(ip)
        
        if evidence['MOBILE'] >= mobile_threshold:
            log = f"+{mobile_bonus} Subnet {subnet}.0/24 has {evidence['MOBILE']} MOBILE evidence"
            return mobile_bonus, log
        elif evidence['HOME'] >= home_threshold:
            log = f"{home_penalty} Subnet {subnet}.0/24 has {evidence['HOME']} HOME evidence"
            return home_penalty, log
        else:
            return 0, ""


class BehavioralEngine:
    def __init__(self, db, config):
        self.db = db
        self.config = config
        
        self.concurrency = ConcurrencyDetector(db, config)
        self.churn = ChurnAnalyzer(db, config)
        self.lifetime = LifetimeAnalyzer(db, config)
        self.subnet = SubnetIntelligence(db, config)
    
    async def analyze(self, uuid: str, ip: str, tag: str) -> Dict:
        logs = []
        total_score = 0
        
        # 1. Concurrency (CGNAT detection)
        concurrency_immunity, concurrent_users = await self.concurrency.check(ip, uuid)
        if concurrency_immunity:
            logs.append(f"⚡ CGNAT: {concurrent_users} concurrent users → HOME blocked")
        
        # 2. Churn (мобильность) — ОПТИМИЗИРОВАНО
        churn_hours = self.config['settings'].get('churn_window_hours', 6)
        
        # 1 запрос к БД
        churn_rate = await self.churn.calculate_churn(uuid, churn_hours)
        
        # Чистая логика (без БД)
        churn_bonus, churn_log = self.churn.get_mobility_score(churn_rate, churn_hours)
        
        if churn_log:
            logs.append(churn_log)
        total_score += churn_bonus
        
        # 3. Lifetime (стационарность) — ОПТИМИЗИРОВАНО
        # 1 запрос к БД
        lifetime_hours = await self.lifetime.get_session_lifetime(uuid, ip)
        
        # Чистая логика (без БД)
        lifetime_penalty, lifetime_log = self.lifetime.get_stationarity_score(lifetime_hours)
        
        # Порог стационарности из конфига
        stat_threshold = self.config['settings'].get('lifetime_stationary_hours', 12)
        is_stationary = lifetime_hours > stat_threshold
        
        if lifetime_log:
            logs.append(lifetime_log)
        total_score += lifetime_penalty
        
        # 4. Subnet intelligence
        subnet_bonus, subnet_log = await self.subnet.get_subnet_bonus(ip)
        if subnet_log:
            logs.append(subnet_log)
        total_score += subnet_bonus
        
        # Обновляем историю и сессии
        await self.db.update_ip_history(uuid, ip)
        await self.db.update_session(uuid, ip, tag)
        
        return {
            'concurrency_immunity': concurrency_immunity,
            'concurrent_users': concurrent_users,
            'churn_rate': churn_rate,
            'churn_bonus': churn_bonus,
            'lifetime_hours': lifetime_hours,
            'is_stationary': is_stationary,
            'lifetime_penalty': lifetime_penalty,
            'subnet_bonus': subnet_bonus,
            'total_behavior_score': total_score,
            'logs': logs
        }
    
    async def record_decision(self, ip: str, uuid: str, decision: str):
        if decision in ('MOBILE', 'HOME'):
            await self.subnet.record_signal(ip, uuid, decision)
