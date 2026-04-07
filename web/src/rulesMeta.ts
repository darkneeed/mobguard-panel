export type RuleListKey =
  | "admin_tg_ids"
  | "exempt_ids"
  | "exempt_tg_ids"
  | "pure_mobile_asns"
  | "pure_home_asns"
  | "mixed_asns"
  | "allowed_isp_keywords"
  | "home_isp_keywords"
  | "exclude_isp_keywords";

export type RuleSettingKey =
  | "pure_asn_score"
  | "mixed_asn_score"
  | "ptr_home_penalty"
  | "mobile_kw_bonus"
  | "ip_api_mobile_bonus"
  | "pure_home_asn_penalty"
  | "concurrency_threshold"
  | "churn_window_hours"
  | "churn_mobile_threshold"
  | "lifetime_stationary_hours"
  | "subnet_mobile_ttl_days"
  | "subnet_home_ttl_days"
  | "subnet_mobile_min_evidence"
  | "subnet_home_min_evidence"
  | "score_subnet_mobile_bonus"
  | "score_subnet_home_penalty"
  | "score_churn_high_bonus"
  | "score_churn_medium_bonus"
  | "score_stationary_penalty"
  | "threshold_probable_home"
  | "threshold_probable_mobile"
  | "threshold_home"
  | "threshold_mobile"
  | "shadow_mode"
  | "probable_home_warning_only"
  | "auto_enforce_requires_hard_or_multi_signal"
  | "review_ui_base_url"
  | "learning_promote_asn_min_support"
  | "learning_promote_asn_min_precision"
  | "learning_promote_combo_min_support"
  | "learning_promote_combo_min_precision"
  | "live_rules_refresh_seconds";

export type RuleSettingValue = string | number | boolean | null | undefined;

export type RulesDraft = Partial<Record<RuleListKey, Array<string | number>>> & {
  settings?: Partial<Record<RuleSettingKey, RuleSettingValue>>;
};

export type RuleListFieldMeta = {
  key: RuleListKey;
  section: string;
  label: string;
  description: string;
  recommendation: string;
  itemType: "number" | "string";
};

export type RuleSettingFieldMeta = {
  key: RuleSettingKey;
  section: string;
  label: string;
  description: string;
  recommendation: string;
  inputType: "number" | "boolean" | "text";
  step?: number;
};

export const RULE_LIST_FIELDS: RuleListFieldMeta[] = [
  {
    key: "admin_tg_ids",
    section: "Access",
    label: "Admin Telegram IDs",
    description: "Telegram IDs, которым разрешён вход в веб-панель.",
    recommendation: "Держите здесь только модераторов и администраторов панели.",
    itemType: "number"
  },
  {
    key: "exempt_ids",
    section: "Access",
    label: "Excluded System IDs",
    description: "Системные user.id, исключённые из анализа и авто-санкций.",
    recommendation: "Добавляйте только служебные или доверенные аккаунты.",
    itemType: "number"
  },
  {
    key: "exempt_tg_ids",
    section: "Access",
    label: "Excluded Telegram IDs",
    description: "Telegram IDs, исключённые из анализа и авто-санкций.",
    recommendation: "Используйте, если удобнее администрировать исключения по Telegram ID.",
    itemType: "number"
  },
  {
    key: "pure_mobile_asns",
    section: "ASN Lists",
    label: "Pure mobile ASN list",
    description: "ASN, которые почти всегда считаются мобильными и дают сильный mobile-сигнал.",
    recommendation: "Добавляйте ASN только после подтверждённой чистой мобильной выборки.",
    itemType: "number"
  },
  {
    key: "pure_home_asns",
    section: "ASN Lists",
    label: "Pure home ASN list",
    description: "ASN, которые почти всегда считаются домашними и дают сильный home-сигнал.",
    recommendation: "Сюда должны попадать только стабильно домашние ASN без мобильной примеси.",
    itemType: "number"
  },
  {
    key: "mixed_asns",
    section: "ASN Lists",
    label: "Mixed ASN list",
    description: "ASN со смешанным профилем, где нужны дополнительные признаки и осторожность.",
    recommendation: "Используйте для спорных ASN, где одного ASN недостаточно для вердикта.",
    itemType: "number"
  },
  {
    key: "allowed_isp_keywords",
    section: "Keywords",
    label: "Mobile keywords",
    description: "Ключевые слова, усиливающие mobile-версию при совпадении в ISP/hostname.",
    recommendation: "Держите здесь короткие устойчивые mobile-маркеры, без широких слов.",
    itemType: "string"
  },
  {
    key: "home_isp_keywords",
    section: "Keywords",
    label: "Home keywords",
    description: "Ключевые слова, которые тянут решение в сторону home.",
    recommendation: "Добавляйте только маркеры фиксированных/домашних провайдеров.",
    itemType: "string"
  },
  {
    key: "exclude_isp_keywords",
    section: "Keywords",
    label: "Datacenter / hosting keywords",
    description: "Ключевые слова для детекта хостинга, датацентров и инфраструктурных сетей.",
    recommendation: "Держите список консервативным, чтобы не ловить обычных провайдеров.",
    itemType: "string"
  }
];

export const RULE_SETTING_FIELDS: RuleSettingFieldMeta[] = [
  {
    key: "threshold_mobile",
    section: "Thresholds",
    label: "MOBILE decision threshold",
    description: "Score, начиная с которого кейс считается уверенно мобильным.",
    recommendation: "Базовое безопасное значение: около 60.",
    inputType: "number"
  },
  {
    key: "threshold_probable_mobile",
    section: "Thresholds",
    label: "Probable mobile threshold",
    description: "Порог для промежуточного mobile-сигнала до финального MOBILE.",
    recommendation: "Обычно держат ниже основного mobile threshold.",
    inputType: "number"
  },
  {
    key: "threshold_home",
    section: "Thresholds",
    label: "HOME decision threshold",
    description: "Нижний score, после которого кейс считается уверенно домашним.",
    recommendation: "Чем выше значение, тем осторожнее будут home-решения.",
    inputType: "number"
  },
  {
    key: "threshold_probable_home",
    section: "Thresholds",
    label: "Probable home threshold",
    description: "Порог для промежуточного home-сигнала до финального HOME.",
    recommendation: "Держите между threshold_home и нейтральной зоной.",
    inputType: "number"
  },
  {
    key: "pure_asn_score",
    section: "Scores",
    label: "Pure mobile ASN bonus",
    description: "Бонус к score, если ASN найден в pure_mobile_asns.",
    recommendation: "Обычно это сильный бонус, сопоставимый с threshold_mobile.",
    inputType: "number"
  },
  {
    key: "mixed_asn_score",
    section: "Scores",
    label: "Mixed ASN bonus",
    description: "Бонус к score для mixed ASN до учёта дополнительных признаков.",
    recommendation: "Держите заметно ниже pure mobile ASN bonus.",
    inputType: "number"
  },
  {
    key: "ptr_home_penalty",
    section: "Scores",
    label: "Home keyword penalty",
    description: "Штраф за home keywords в ISP/hostname.",
    recommendation: "Небольшой минус, чтобы keyword не перевешивал жёсткие сигналы.",
    inputType: "number"
  },
  {
    key: "mobile_kw_bonus",
    section: "Scores",
    label: "Mobile keyword bonus",
    description: "Бонус за mobile keywords в ISP/hostname.",
    recommendation: "Делайте меньше чистого ASN-бонуса, но достаточно значимым.",
    inputType: "number"
  },
  {
    key: "ip_api_mobile_bonus",
    section: "Scores",
    label: "ip-api mobile bonus",
    description: "Дополнительный bonus, если fallback ip-api подтверждает mobile сеть.",
    recommendation: "Используйте только как добивающий сигнал для mixed ASN.",
    inputType: "number"
  },
  {
    key: "pure_home_asn_penalty",
    section: "Scores",
    label: "Pure home ASN penalty",
    description: "Штраф, если ASN попадает в pure_home_asns.",
    recommendation: "Обычно это сильный penalty для уверенного HOME.",
    inputType: "number"
  },
  {
    key: "score_subnet_mobile_bonus",
    section: "Scores",
    label: "Subnet mobile bonus",
    description: "Бонус за исторические mobile-сигналы в той же подсети.",
    recommendation: "Делайте его умеренным, чтобы не переобучать редкие подсети.",
    inputType: "number"
  },
  {
    key: "score_subnet_home_penalty",
    section: "Scores",
    label: "Subnet home penalty",
    description: "Штраф за исторические home-сигналы в подсети.",
    recommendation: "Подходит как корректирующий, а не доминирующий сигнал.",
    inputType: "number"
  },
  {
    key: "score_churn_high_bonus",
    section: "Scores",
    label: "High churn bonus",
    description: "Бонус за очень высокую сменяемость IP/сессий.",
    recommendation: "Используйте как сильный поведенческий mobile-признак.",
    inputType: "number"
  },
  {
    key: "score_churn_medium_bonus",
    section: "Scores",
    label: "Medium churn bonus",
    description: "Бонус за умеренную сменяемость IP/сессий.",
    recommendation: "Делайте заметно ниже high churn bonus.",
    inputType: "number"
  },
  {
    key: "score_stationary_penalty",
    section: "Scores",
    label: "Stationary penalty",
    description: "Штраф за слишком долгую стационарность пользователя.",
    recommendation: "Обычно это мягкий penalty, не hard-stop.",
    inputType: "number"
  },
  {
    key: "concurrency_threshold",
    section: "Behavior",
    label: "Concurrency threshold",
    description: "Сколько одновременных пользователей на IP считать признаком мобильности.",
    recommendation: "Стартовая точка: 2–3.",
    inputType: "number"
  },
  {
    key: "churn_window_hours",
    section: "Behavior",
    label: "Churn window (hours)",
    description: "Окно в часах для расчёта churn и сменяемости IP.",
    recommendation: "Чем меньше окно, тем чувствительнее реакция на всплески.",
    inputType: "number"
  },
  {
    key: "churn_mobile_threshold",
    section: "Behavior",
    label: "Churn mobile threshold",
    description: "Сколько смен IP считать mobile-поведенческим сигналом.",
    recommendation: "Подбирайте по реальным mobile-паттернам без перегиба.",
    inputType: "number"
  },
  {
    key: "lifetime_stationary_hours",
    section: "Behavior",
    label: "Stationary lifetime (hours)",
    description: "После какой длительности одна и та же сессия выглядит слишком домашней.",
    recommendation: "Увеличивайте, если боитесь ложных home-срабатываний.",
    inputType: "number",
    step: 0.5
  },
  {
    key: "subnet_mobile_ttl_days",
    section: "Behavior",
    label: "Subnet mobile TTL (days)",
    description: "Сколько дней хранить mobile-историю по подсетям.",
    recommendation: "Более длинный TTL повышает память системы, но и риск устаревания.",
    inputType: "number"
  },
  {
    key: "subnet_home_ttl_days",
    section: "Behavior",
    label: "Subnet home TTL (days)",
    description: "Сколько дней хранить home-историю по подсетям.",
    recommendation: "Обычно меньше mobile TTL, чтобы быстрее забывать шум.",
    inputType: "number"
  },
  {
    key: "subnet_mobile_min_evidence",
    section: "Behavior",
    label: "Subnet mobile min evidence",
    description: "Минимум mobile-свидетельств до включения subnet mobile bonus.",
    recommendation: "Повышайте, если подсетей много и они шумные.",
    inputType: "number"
  },
  {
    key: "subnet_home_min_evidence",
    section: "Behavior",
    label: "Subnet home min evidence",
    description: "Минимум home-свидетельств до включения subnet home penalty.",
    recommendation: "Обычно требует больше подтверждений, чем mobile.",
    inputType: "number"
  },
  {
    key: "shadow_mode",
    section: "Policy",
    label: "Shadow mode",
    description: "Если включено, система анализирует и пишет кейсы, но не применяет санкции жёстко.",
    recommendation: "Новый rollout безопаснее начинать с true.",
    inputType: "boolean"
  },
  {
    key: "probable_home_warning_only",
    section: "Policy",
    label: "Probable home = warning only",
    description: "Ограничивает probable home кейсы предупреждением вместо punitive действий.",
    recommendation: "Рекомендуется держать включённым для осторожного режима.",
    inputType: "boolean"
  },
  {
    key: "auto_enforce_requires_hard_or_multi_signal",
    section: "Policy",
    label: "Require hard or multi-signal for auto-enforce",
    description: "Авто-применение санкций разрешено только при сильном или многосигнальном HOME.",
    recommendation: "Безопаснее оставлять включённым.",
    inputType: "boolean"
  },
  {
    key: "review_ui_base_url",
    section: "Policy",
    label: "Review UI base URL",
    description: "Базовый URL веб-панели, который используется в review links.",
    recommendation: "Укажите боевой HTTPS URL панели.",
    inputType: "text"
  },
  {
    key: "live_rules_refresh_seconds",
    section: "Policy",
    label: "Live rules refresh interval",
    description: "Как часто runtime перечитывает live rules из storage.",
    recommendation: "Обычно достаточно 10–30 секунд.",
    inputType: "number"
  },
  {
    key: "learning_promote_asn_min_support",
    section: "Learning",
    label: "Promoted ASN min support",
    description: "Минимум подтверждённых кейсов, чтобы ASN попал в promoted learning.",
    recommendation: "Повышайте, если боитесь раннего переобучения.",
    inputType: "number"
  },
  {
    key: "learning_promote_asn_min_precision",
    section: "Learning",
    label: "Promoted ASN min precision",
    description: "Минимальная precision для promoted ASN pattern.",
    recommendation: "Консервативный режим обычно начинается около 0.95.",
    inputType: "number",
    step: 0.01
  },
  {
    key: "learning_promote_combo_min_support",
    section: "Learning",
    label: "Promoted combo min support",
    description: "Минимум кейсов для promoted combo pattern.",
    recommendation: "Обычно ниже ASN support, но не слишком низко.",
    inputType: "number"
  },
  {
    key: "learning_promote_combo_min_precision",
    section: "Learning",
    label: "Promoted combo min precision",
    description: "Минимальная precision для combo pattern.",
    recommendation: "Держите высокой, чтобы combo не давал шумных бонусов.",
    inputType: "number",
    step: 0.01
  }
];
