import type { TranslationDictionary } from "../types";

export const ruDictionary: TranslationDictionary = {
  common: {
    loading: "Загрузка…",
    loadingLabel: "Загрузка",
    loadingSession: "Загружаю сессию…",
    notAvailable: "N/A",
    admin: "Администратор",
    system: "system",
    yes: "да",
    no: "нет",
    true: "true",
    false: "false",
    saved: "сохранено",
    unsavedChanges: "есть несохранённые изменения",
    configured: "Настроено",
    disabled: "Отключено",
    on: "ON",
    off: "OFF",
    showHint: "Показать подсказку",
    fieldHintLabel: "Подсказка для поля {field}",
    present: "задано",
    missing: "не задано",
    writable: "можно писать",
    readOnly: "только чтение",
    envFile: "Файл .env",
    currentValue: "Текущее значение",
    newValue: "Новое значение",
    secretValueStored: "На сервере значение хранится как скрытый секрет.",
    runtimeValue: "Значение времени выполнения, управляемое через .env.",
    leaveBlankToKeep:
      "Оставьте пустым, чтобы сохранить текущее секретное значение",
    restartRequired: "нужен перезапуск",
    close: "Закрыть",
    deviceSources: {
      panelUser: "Remnawave HWID",
      event: "access log",
    },
    scopeLabels: {
      deviceField: "Устройство",
      accountField: "Контекст аккаунта",
      contextField: "Контекст",
      ipDeviceScope: "Решение для IP в контексте устройства",
      subjectIpScope: "Решение для IP в контексте аккаунта",
      ipOnlyScope: "Решение только для этого IP",
      queueScopeDevice: "По устройству",
      queueScopeAccount: "По аккаунту",
      queueScopeIpOnly: "Только IP",
      ipDeviceHistoryTitle: "IP этого устройства",
      subjectIpHistoryTitle: "IP этого аккаунта",
      ipOnlyHistoryTitle: "Только этот IP",
      ipDeviceHistory: "IP этого устройства: {count}",
      subjectIpHistory: "IP этого аккаунта: {count}",
      ipOnlyHistory: "Только этот IP: {count}",
      subjectContext: "Контекст аккаунта",
      subjectContextValue: "Этот аккаунт",
      sharedAccountContext: "Контекст аккаунта, возможен общий доступ",
      sharedAccountWarning: "Есть признаки общего доступа к аккаунту",
      ipOnlyContext: "Точное устройство не зафиксировано",
    },
  },
  layout: {
    brandSubtitle: "Панель администратора",
    consoleBadge: "Оперконсоль",
    consoleDescription:
      "Операторский поток в духе Remnawave с аккуратной подачей Bedolaga.",
    groups: {
      monitor: "Мониторинг",
      configure: "Настройки",
      operate: "Операции",
    },
    nav: {
      overview: "Обзор",
      modules: "Модули",
      queue: "Очередь",
      decisions: "Решения",
      console: "Консоль",
      rules: "Правила детекта",
      telegram: "Telegram",
      access: "Доступ",
      data: "Данные",
      quality: "Качество",
    },
    subnav: {
      rules: {
        general: "Общие",
        thresholds: "Пороги",
        lists: "Списки",
        providers: "Провайдеры",
        policy: "Политика",
        learning: "Обучение",
        retention: "Хранение",
      },
      data: {
        console: "Консоль",
        users: "Пользователи",
        violations: "Нарушения",
        overrides: "Оверрайды",
        cache: "Кэш",
        learning: "Обучение",
        cases: "Кейсы",
        events: "События",
        exports: "Экспорты",
        audit: "Аудит",
      },
    },
    theme: {
      label: "Тема",
      system: "Системная",
      light: "Светлая",
      dark: "Тёмная",
    },
    palette: {
      label: "Палитра",
      green: "Зелёная",
      orange: "Оранжевая",
      blue: "Голубая",
      purple: "Фиолетовая",
      red: "Красная",
    },
    language: {
      label: "Язык",
      ru: "rus",
      en: "eng",
    },
    logout: "Выйти",
  },
  overview: {
    eyebrow: "Обзор оператора",
    title: "Обзор",
    description: "Короткая сводка по состоянию панели и модулей",
    lastUpdated: "Последняя синхронизация {value}",
    errors: {
      loadFailed: "Не удалось загрузить обзорный экран",
      showingLastGood: "Показан последний успешный снимок (возраст {value}).",
    },
    snapshotStale: "обзорный снимок устарел",
    attentionTitle: "Что требует внимания",
    attentionDescription:
      "Главные сигналы по модерации и фоновому разбору без перехода по разделам.",
    systemStatusTitle: "Текущее состояние панели",
    systemStatusDescription:
      "База, модуль скоринга, живые правила и базовые сигналы времени выполнения.",
    healthTitle: "Состояние панели",
    healthDescription:
      "Показывает, доступна ли база, встроенный модуль скоринга и когда обновлялись живые правила.",
    pipelineTitle: "Состояние конвейера обработки",
    pipelineDescription:
      "Очередь, лаг воркера и отложенные удалённые задачи применения. Только здесь, на главном экране.",
    attentionItems: {
      overviewStale:
        "Снимок обзора устарел. Проверьте фоновые обновления модели чтения.",
      pipelineStale:
        "Снимок конвейера обработки устарел. Возможна задержка в отображении очереди.",
      failedQueue:
        "В конвейере обработки есть ошибки: {count}. Нужно проверить повторы и dead-letter.",
      openCases: "В очереди ревью сейчас {count} открытых кейсов.",
      mixedConflicts: "Смешанные провайдеры дали {count} конфликтных кейсов.",
      quiet: "Критичных сигналов сейчас нет.",
    },
    health: {
      core: "Модуль скоринга",
      db: "База данных",
      rules: "Живые правила",
      embedded: "встроен",
      embeddedRuntime: "Встроен в API панели · обновлено {value}",
      updated: "Обновлено {value}",
      rulesBy: "Обновил {value}",
    },
    cards: {
      openQueue: "Открытая очередь",
      failedQueue: "Ошибки обработки",
      core: "Модуль скоринга",
      embeddedValue: "встроен",
      ipinfo: "Токен IPINFO",
      adminSessions: "Админ-сессии",
      scoreZeroRatio: "Доля score=0 (24 ч)",
      asnMissingRatio: "Доля случаев без ASN (24 ч)",
      mixedConflicts: "Конфликты смешанных провайдеров",
      promotedPatterns: "Продвинутые паттерны",
      automationMode: "Режим работы",
    },
    quickLinks: {
      queue: "Открыть очередь",
      quality: "Перейти в качество",
      policy: "Проверить политику",
      events: "Открыть консоль",
      exports: "Выгрузки калибровки",
    },
    mixedProvidersTitle: "Проблемные смешанные провайдеры",
    mixedProvidersDescription:
      "Провайдеры, которые чаще всего приводят к ручному ревью и конфликтам.",
    mixedProvidersItem:
      "{open} открыто · {conflict} конфликтов · {home} HOME · {mobile} MOBILE",
    mixedProvidersMetrics: {
      open: "Открыто",
      conflicts: "Конфликты",
      home: "HOME",
      mobile: "MOBILE",
    },
    emptyMixedProviders: "Сейчас нет проблемных mixed-провайдеров.",
    noisyAsnTitle: "Шумные ASN",
    noisyAsnDescription: "ASN, дающие наибольшую нагрузку на модерацию.",
    noisyAsnItem: "{count} кейсов ревью",
    emptyNoisyAsn: "Данных по шумным ASN пока нет.",
    latestCasesTitle: "Последние кейсы очереди",
    latestCasesDescription:
      "Свежие спорные кейсы, готовые к обработке оператором.",
    emptyLatestCases: "Сейчас открытых кейсов нет.",
    pipeline: {
      queueDepth: "Глубина очереди",
      queueMeta: "{queued} в очереди · {processing} обрабатывается",
      failed: "Dead-letter / ошибки",
      pendingRemote: "{count} удалённых задач ждут отправки",
      lag: "Текущий лаг",
      oldestQueued: "Самая старая запись в очереди {value}",
      lastDrain: "Последний полный проход",
      snapshotAge: "Возраст снимка {value}",
      stale: "снимок устарел",
    },
    automation: {
      modeTitle: "Режим автоматики",
      guardrailsTitle: "Активные guardrail’ы",
      noModeReasons: "Нет флагов, ограничивающих режим",
      noGuardrails: "Дополнительные guardrail’ы не включены",
    },
  },
  login: {
    eyebrow: "Remnawave + MobGuard",
    title: "Веб-панель модерации, данных и рабочих настроек",
    description:
      "Очередь спорных кейсов, управление данными, доставка в Telegram и рабочая конфигурация в одной панели.",
    telegramTitle: "Вход через Telegram",
    telegramNotConfigured: "Вход через Telegram не настроен.",
    telegramLoading: "Загружаю вход через Telegram…",
    localTitle: "Локальный вход",
    usernamePlaceholder: "Имя пользователя",
    passwordPlaceholder: "Пароль",
    signIn: "Войти",
    signingIn: "Выполняю вход…",
    localNotConfigured: "Локальный резервный вход не настроен.",
    authFailed: "Ошибка авторизации",
    localAuthFailed: "Ошибка локальной авторизации",
    totp: {
      setupTitle: "Настройка TOTP владельца",
      verifyTitle: "Проверка TOTP владельца",
      setupDescription:
        "Сохраните секрет в приложении-аутентификаторе и подтвердите настройку 6-значным кодом.",
      verifyDescription:
        "Введите 6-значный TOTP-код владельца, чтобы завершить вход.",
      secretLabel: "Секрет",
      issuerLabel: "Издатель",
      accountLabel: "Аккаунт",
      uriLabel: "URI для добавления",
      codePlaceholder: "123456",
      confirmButton: "Подтвердить настройку TOTP",
      verifyButton: "Проверить код",
      cancelButton: "Отмена",
      processing: "Проверяем…",
      failed: "Ошибка проверки TOTP",
    },
  },
  reviewQueue: {
    eyebrow: "Очередь ревью",
    title: "Ручная модерация",
    description:
      "Кейсы, по которым не получилось принять автоматическое решение",
    countSummary: "Кейсов: {count} · {page} страница",
    lastUpdated: "Обновлено {value}",
    searchPlaceholder:
      "Быстрый поиск по IP / имени пользователя / ISP / UUID / идентификаторам",
    clearFilters: "Сбросить фильтры",
    savedFilters: {
      save: "Сохранить текущие",
      apply: "Применить сохранённые",
      clear: "Очистить сохранённые",
      saved: "Текущие фильтры очереди сохранены",
      applied: "Сохранённые фильтры очереди применены",
      cleared: "Сохранённые фильтры очереди удалены",
      invalid: "Сохранённые фильтры очереди повреждены",
    },
    toggleFiltersTitle: "Переключить фильтры",
    filtersButton: "Фильтры",
    filterCount: "Фильтры ({count})",
    presets: {
      open: "Только открытые",
      providerConflict: "Конфликт провайдера",
      critical: "Критичные",
      punitive: "С санкцией",
    },
    filters: {
      moduleId: "ID модуля",
      username: "Имя пользователя",
      systemId: "System ID",
      telegramId: "Telegram ID",
      repeatMin: "Минимум повторов",
      repeatMax: "Максимум повторов",
      statusOpen: "OPEN",
      statusResolved: "RESOLVED",
      statusSkipped: "SKIPPED",
      allStatus: "Любой статус",
      confidenceUnsure: "UNSURE",
      confidenceProbableHome: "PROBABLE_HOME",
      confidenceHighHome: "HIGH_HOME",
      allConfidence: "Любая уверенность",
      reasonUnsure: "unsure",
      reasonProbableHome: "probable_home",
      reasonHomeRequiresReview: "home_requires_review",
      reasonManualMixedHome: "manual_review_mixed_home",
      reasonProviderConflict: "provider_conflict",
      allReasons: "Все причины",
      severityCritical: "critical",
      severityHigh: "high",
      severityMedium: "medium",
      severityLow: "low",
      allSeverity: "Любая срочность",
      punitiveAny: "Любой режим санкций",
      punitiveOnly: "Только с санкцией",
      reviewOnly: "Только ручное ревью",
      sortPriorityDesc: "Сначала высокий приоритет",
      sortPriorityAsc: "Сначала низкий приоритет",
      sortUpdatedDesc: "Сначала новые",
      sortScoreDesc: "Сначала высокий балл",
      sortRepeatDesc: "Сначала частые повторы",
      sortUpdatedAsc: "Сначала старые",
    },
    errors: {
      loadFailed: "Не удалось загрузить кейсы ревью",
      resolveFailed: "Не удалось применить решение",
    },
    identifiers: {
      user: "Пользователь",
      module: "Модуль",
      inbound: "Инбаунд",
      device: "Устройство",
      system: "System ID",
      telegram: "TG",
      uuid: "UUID",
    },
    card: {
      ip: "IP",
      sameDeviceHistory: "IP этого устройства: {count}",
      ipSeen: "Первое появление {first} · последнее {last}",
      asn: "ASN",
      asnValue: "AS{value}",
      decision: "Решение",
      providerName: "Провайдер",
      serviceHint: "Сервис: {value}",
      providerConflict: "Конфликт провайдера",
      reviewFirst: "Только вручную",
      autoReady: "Можно автоматически",
      priority: "Приоритет {value}",
      repeat: "Повторов: {count}",
      ipDeviceScope: "Решение для IP в контексте устройства",
      ipOnlyScope: "Решение только для этого IP",
      ipOnlyDevice: "Устройство не определено",
      activityObserved: "Активность кейса: {value}",
      activityObservedHint:
        "Сколько кейс остаётся активным в текущем наблюдаемом окне.",
      opened: "открыт {value}",
    },
    pageSize: {
      label: "Карточек на странице",
      option: "{value}",
    },
    actions: {
      mobile: "MOBILE",
      home: "HOME",
      skip: "Пропустить",
      openCase: "Открыть кейс",
      openEvents: "Консоль",
      bulkMobile: "Перевести выбранные в MOBILE",
      bulkHome: "Перевести выбранные в HOME",
      bulkSkip: "Пропустить выбранные",
      recheckVisible: "Перепроверить видимые",
      recheckDone: "Перепроверено {count} кейсов очереди",
      processing: "Обработка…",
      saved: "Решение по кейсу сохранено",
      bulkSaved: "Применено решение к {count} выбранным кейсам",
    },
    selection: {
      selectPage: "Выбрать страницу",
      clearPage: "Снять выбор со страницы",
      selectedCount: "Выбрано {count}",
    },
    footer: {
      previous: "Назад",
      next: "Дальше",
      pageSummary: "Страница {page} · показано {shown} из {total}",
    },
    reviewReasons: {
      provider_conflict: "Конфликт провайдера",
      unsure: "Недостаточно сигналов",
      probable_home: "Вероятный HOME",
      home_requires_review: "HOME требует review",
      manual_review_mixed_home: "Mixed HOME review",
    },
  },
  decisions: {
    eyebrow: "Автоматические решения",
    title: "Авто-решённые события",
    description: "Кейсы, которые были обработаны в рамках правил автомодерации",
    countSummary: "{count} решений · страница {page}",
    lastUpdated: "Обновлено {value}",
    loadFailed: "Не удалось загрузить автоматические решения",
    filtersTitle: "Фильтры",
    filtersDescription:
      "Фильтрация по решению, модулю, провайдеру, источнику и состоянию enforcement.",
    listTitle: "Автоматические решения",
    listDescription: "Последние решения",
    empty: "Для текущих фильтров автоматических решений нет",
    filters: {
      search: "Поиск по IP / провайдеру / inbound / устройству",
      moduleId: "ID модуля",
      provider: "Провайдер",
      anyVerdict: "Любой verdict",
      anySource: "Любой источник",
      anyEnforcement: "Любой enforcement",
    },
    meta: {
      module: "Модуль {value}",
      inbound: "Inbound {value}",
      provider: "Провайдер {value}",
      source: "Источник {value}",
      scope: "Контекст {value}",
      enforcement: "Enforcement {value}",
    },
    sources: {
      rule_engine: "Rule engine",
      cache: "Кэш",
      manual_override: "Ручной override",
    },
    enforcement: {
      none: "Без удалённого enforcement",
      attempts: "попыток {count}",
      status: {
        pending: "Ожидает",
        applied: "Применено",
        failed: "Ошибка",
      },
      jobType: {
        access_state: "Access squad",
        traffic_cap: "Traffic cap",
      },
    },
    pagination: {
      page: "Страница {page}/{total}",
      pageSize: "{value}",
      previous: "Назад",
      next: "Дальше",
    },
  },
  modules: {
    eyebrow: "Парк модулей",
    title: "Модули сборки данных",
    description:
      "Управляйте модулями сборки данных с нод и отслеживайте их состояние",
    count: "Модулей: {count}",
    loadFailed: "Не удалось загрузить список модулей",
    listTitle: "Подготовленные модули",
    listDescription:
      "Сначала создайте карточку, затем подключите сборщик и отслеживайте его состояние и ошибки.",
    selectionHint: "Выберите модуль или создайте новый",
    empty: "Модули ещё не созданы",
    create: "Создать модуль",
    save: "Сохранить изменения",
    open: "Открыть детали",
    createTitle: "Создание карточки модуля",
    createDescription:
      "Укажите отображаемое имя и INBOUND-теги для этого модуля. После сохранения панель сгенерирует module_id и API-токен.",
    detailsTitle: "Детали модуля",
    detailsDescription:
      "Редактируйте имя модуля и INBOUND-теги. Обновлённые теги придут в сборщик через удалённую конфигурацию без изменения сценария установки.",
    createSuccess: "Модуль создан",
    updateSuccess: "Модуль обновлён",
    saveFailed: "Не удалось сохранить модуль",
    pendingInstall: "ожидает установку",
    stale: "устарел",
    freshnessTitle: "Heartbeat",
    freshnessHint:
      "Модуль считается устаревшим, если heartbeat не приходит дольше {value}.",
    lastHeartbeatAge: "Возраст heartbeat",
    staleWindow: "Окно heartbeat",
    inboundTags: "INBOUND-теги",
    lastSeen: "Последний heartbeat",
    appliedRevision: "Применённая ревизия",
    openCases: "Открытые кейсы",
    analysisEvents: "События анализа",
    version: "Версия {value}",
    protocol: "Протокол {value}",
    moduleId: "ID модуля: {value}",
    generatedAfterCreate: "Будет сгенерирован после создания",
    healthTitle: "Состояние модуля",
    healthDescription:
      "Панель показывает последний заявленный модулем статус и вычисленное состояние устаревания.",
    healthStatus: "Состояние",
    lastValidationAt: "Последняя валидация",
    spoolDepth: "Глубина буфера",
    accessLogExists: "Файл access log найден",
    healthEmpty:
      "Создайте или откройте модуль, чтобы увидеть его текущее состояние.",
    installTitle: "Установка модуля",
    installDescription:
      "Скопируйте сгенерированный compose, раскройте токен и при необходимости измените ACCESS_LOG_PATH локально, если у ноды нестандартный путь к логу.",
    installPreviewEmpty:
      "Создайте или откройте модуль, чтобы увидеть сгенерированный docker-compose.yml",
    revealToken: "Показать токен",
    tokenRevealSuccess: "Токен модуля раскрыт",
    tokenRevealFailed: "Не удалось раскрыть токен модуля",
    tokenUnavailable:
      "Для этого модуля токен нельзя раскрыть повторно. У старых модулей хранится только хеш авторизации.",
    tokenTitle: "Токен модуля",
    tokenDescription:
      "Подставьте этот токен в MODULE_TOKEN внутри сгенерированного compose-файла перед запуском.",
    tokenValue: "Раскрытый токен",
    copyToken: "Скопировать токен",
    tokenCopied: "Токен скопирован в буфер",
    copyCompose: "Скопировать compose",
    composeCopied: "docker-compose.yml скопирован в буфер",
    copyFailed: "Не удалось скопировать в буфер",
    installSteps: {
      clone:
        "Склонируйте репозиторий модуля на целевую ноду и откройте его корень.",
      compose: "Замените локальный docker-compose.yml на compose preview ниже.",
      token:
        "Раскройте token в панели и замените MODULE_TOKEN=__PASTE_TOKEN__ перед запуском",
      start:
        "Запустите docker compose up -d && docker compose logs -f и дождитесь перехода модуля в online",
    },
    health: {
      ok: "ok",
      warn: "warn",
      error: "error",
    },
    freshness: {
      ok: "Обновлено",
      stale: "Давно не обновлялся",
    },
    fields: {
      moduleName: "Отображаемое имя",
      moduleId: "Сгенерированный module ID",
      inboundTags: "INBOUND тэги",
    },
    cards: {
      total: "Всего модулей",
      pending: "Ожидают установку",
      healthy: "Стабильны",
      warn: "Требуют внимания",
      error: "Ошибка",
      stale: "Давно не обновлялись",
      queueDepth: "Глубина очереди",
      failedQueue: "Dead-letter",
    },
    pipelineTitle: "Ingest-пайплайн",
    pipelineDescription:
      "Нагрузка очереди и статус фоновых воркеров для общего SQLite-пайплайна.",
    pipeline: {
      queueDepth: "Глубина очереди",
      pendingRemote: "Ожидают remote-задачи",
      lag: "Текущий лаг",
      lastDrain: "Последний полный drain",
      snapshotAge: "Возраст snapshot {value}",
      snapshotAgeLabel: "Свежесть snapshot",
      stale: "устаревший snapshot",
    },
  },
  reviewDetail: {
    eyebrow: "Детали кейса",
    title: "Кейс ревью #{caseId}",
    description:
      "Evidence, связанная история и sticky-зона решения для быстрой модерации.",
    loading: "Загрузка…",
    backToQueue: "Назад в очередь",
    queuePosition: "Очередь {current}/{total}",
    keyboardHint: "[ назад ] вперёд · M/H/S решение",
    copySuccess: "Скопировано в буфер",
    copyFailed: "Не удалось скопировать",
    errors: {
      resolveFailed: "Не удалось применить решение",
    },
    sections: {
      summary: "Сводка",
      reasons: "Причины",
      providerEvidence: "Провайдерские сигналы",
      ipInventory: "IP и история устройства",
      moduleInventory: "Затронутые модули",
      usageProfile: "Профиль использования",
      log: "Лог",
      history: "История решений",
      linkedContext: "Связанный контекст пользователя/IP",
      resolution: "Решение",
    },
    fields: {
      username: "Имя пользователя",
      systemId: "System ID",
      telegramId: "Telegram ID",
      uuid: "UUID",
      ip: "IP",
      device: "Устройство",
      asn: "ASN",
      tag: "Инбаунд",
      reviewReason: "Причина ревью",
      verdict: "Вердикт",
      confidence: "Уверенность",
      opened: "Открыт",
      updated: "Обновлён",
      isp: "Провайдер",
      reviewUrl: "URL ревью",
    },
    history: {
      empty: "Решений пока нет",
    },
    linkedCases: {
      empty: "Связанные кейсы не найдены",
      caseLabel: "Кейс #{id}",
    },
    resolution: {
      placeholder: "Комментарий для аудита",
      mobile: "Mark MOBILE",
      home: "Mark HOME",
      skip: "Skip",
      saved: "Решение по кейсу сохранено",
    },
    summaryHint:
      "Быстрые идентификаторы и контекст ревью без провала в raw payload.",
    resolutionHint:
      "Эта заметка попадёт в audit trail вместе с решением для IP {ip}.",
    copyIp: "Скопировать IP",
    copyUuid: "Скопировать UUID",
    copyTelegram: "Скопировать Telegram ID",
    openReviewUrl: "Открыть review URL",
    providerEvidence: {
      conflict: "Конфликт service markers",
      clear: "Прямого конфликта markers нет",
      reviewFirst: "Нужен review-first",
      autoReady: "Сигналов уже хватает для автоматики",
      homeSources: "Поддерживающие HOME-источники",
      mobileSources: "Поддерживающие MOBILE-источники",
      matchedAliases: "Совпавшие алиасы",
      mobileMarkers: "Совпавшие mobile markers",
      homeMarkers: "Совпавшие home markers",
    },
    sharedAccess: {
      signals: "Сигналы: {value}",
    },
    usageProfile: {
      empty: "Данных usage-profile пока нет",
      summary: "Снапшот",
      counts: "Счётчики",
      countsValue:
        "IP {ips} · Провайдеры {providers} · Устройства {devices} · Модули {modules}",
      devices: "Устройства",
      deviceInventoryNote:
        "Если доступен HWID-инвентарь Remnawave, он уже подмешан в этот список.",
      osFamilies: "Семейства ОС",
      nodes: "Распределение по нодам",
      softReasons: "Soft reasons",
      geo: "Геоистория",
      travel: "Аномалии перемещения",
      countryJumpOnly: "только country jump",
      topIps: "Топ недавних IP",
      topProviders: "Топ провайдеров",
      recentLocations: "Недавние локации",
      impossibleTravel: "Невозможное перемещение",
      ongoing: "Длительность окна",
      lastSeen: "Последний сигнал",
      updatedAt: "Обновлено",
    },
    reviewReasons: {
      provider_conflict: "Конфликт провайдера",
      unsure: "Недостаточно сигналов",
      probable_home: "Вероятный HOME",
      home_requires_review: "HOME требует review",
      manual_review_mixed_home: "Mixed HOME review",
    },
    ipInventory: {
      summary: "{count} срабатываний · {isp} · AS{asn}",
      observedInterval: "Наблюдаемый интервал {value}",
      firstSeen: "Первое появление {value}",
      lastSeen: "Последнее появление {value}",
    },
    moduleInventory: {
      moduleId: "Module ID {value}",
      firstSeen: "Первое появление {value}",
      lastSeen: "Последнее появление {value}",
    },
  },
  rules: {
    eyebrow: "Live Rules",
    title: "Настройки и правила детекта",
    saveRules: "Сохранить правила",
    rulesUpdated: "Правила обновлены",
    generalSaved: "Общие настройки сохранены",
    loadFailed: "Не удалось загрузить правила",
    saveFailed: "Не удалось сохранить изменения",
    revision: "Ревизия {value}",
    updatedAt: "Обновлено {value}",
    updatedBy: "Кем обновлено: {value}",
    general: {
      title: "Общие настройки",
      description:
        "Параметры эскалации runtime и переключения уровней доступа.",
      save: "Сохранить общие настройки",
    },
    sectionTitles: {
      thresholds: "Пороги, скоринг и поведение",
      policy: "Политика детекта",
      learning: "Контроль learning",
      retention: "Ретеншн базы данных",
    },
    sectionDescriptions: {
      general:
        "Runtime-wide параметры эскалации, предупреждений и переключения доступа в отдельной вкладке.",
      thresholds:
        "Пороговые значения, веса скоринга и окна поведенческих сигналов в одном месте.",
      lists:
        "ASN- и keyword-списки, формирующие первичное доказательство и исключения.",
      providers:
        "Алиасы, markers и операторские подсказки для review-first сценариев.",
      policy:
        "Живая policy-логика детекта плюс enforcement-настройки переключения доступа.",
      learning: "Пороги, при которых runtime-learning становится доверенным.",
      retention:
        "Окна хранения, которые ограничивают рост SQLite, не удаляя активные review-состояния.",
    },
    providerProfiles: {
      description:
        "Профили операторов с alias и service markers для осторожного review-first скоринга.",
      add: "Добавить профиль оператора",
      remove: "Удалить профиль",
      empty: "Профили операторов пока не настроены.",
      cardTitle: "Профиль оператора #{index}",
      cardSubtitle:
        "По одному значению на строку. ASN указываются только числами.",
      classifications: {
        mixed: "Смешанный",
        mobile: "Мобильный",
        home: "Домашний",
      },
      validation: {
        missingKey: "Профиль оператора #{index}: нужен key",
      },
      fields: {
        key: {
          label: "Ключ профиля",
          description:
            "Стабильный идентификатор для learning labels и quality-метрик.",
        },
        classification: {
          label: "Классификация",
          description:
            "Смешанные профили остаются в review-first режиме, пока их не подтвердит второй независимый фактор.",
        },
        aliases: {
          label: "Алиасы",
          description:
            "Имена оператора, бренды, PTR-фрагменты и org-алиасы для поиска в ISP/hostname.",
        },
        mobile_markers: {
          label: "Мобильные service markers",
          description:
            "Маркеры услуг, указывающие на мобильную сторону оператора.",
        },
        home_markers: {
          label: "Домашние service markers",
          description:
            "Маркеры услуг, указывающие на фиксированную/домашнюю сторону оператора.",
        },
        asns: {
          label: "Список ASN",
          description: "ASN, относящиеся к этому профилю оператора.",
        },
      },
    },
    listSectionDescription: "Редактируемые правила в формате списков.",
    settingSectionDescription: "Только каноничные редактируемые настройки.",
    automationStatus: {
      title: "Автоматические решения",
      description: "Текущие решения принимаются на основе настроек и обучения",
      modeLabel: "Эффективный режим",
      modeReasonsLabel: "Почему активен именно он",
      guardrailsLabel: "Какие guardrail’ы включены",
      noModeReasons: "Флагов, ограничивающих режим, нет",
      noGuardrails: "Дополнительные guardrail’ы не активны",
    },
    invalidNumber: "{field}: некорректное число",
    invalidValue: "{field}: некорректное значение '{value}'",
  },
  automationStatus: {
    modes: {
      observe: "Наблюдение",
      warning_only: "Предупреждения",
      enforce: "Ограничения",
    },
    reasons: {
      dry_run: "dry-run не даёт делать remote actions",
      shadow_mode: "shadow mode блокирует жёсткие действия",
      warning_only_mode: "эскалация ограничена предупреждениями",
    },
    flags: {
      auto_enforce_requires_hard_or_multi_signal:
        "Нужен hard или multi-signal для auto-enforce",
      provider_conflict_review_only:
        "Конфликты mixed-провайдеров остаются только в review",
      manual_review_mixed_home_enabled:
        "Mixed HOME-кейсы требуют ручного review",
      manual_ban_approval_enabled: "Ограничения требуют ручного одобрения",
    },
  },
  telegram: {
    eyebrow: "Telegram",
    title: "Настройки runtime-ботов и доставки сообщений",
    saveSettings: "Сохранить настройки Telegram",
    saveEnv: "Сохранить .env настройки",
    saveTemplates: "Сохранить шаблоны сообщений",
    settingsSaved: "Настройки Telegram сохранены",
    envSaved: ".env настройки Telegram сохранены",
    templatesSaved: "Шаблоны сообщений сохранены",
    loadFailed: "Не удалось загрузить настройки Telegram",
    saveFailed: "Не удалось сохранить изменения",
    invalidNumber: "{field}: некорректное число",
    capabilityStatusTitle: "Статус Telegram-возможностей",
    capabilityStatusDescription:
      "Токены и usernames ботов управляются только через `.env` на сервере.",
    deliveryTitle: "Доставка и поведение бота",
    deliveryDescription:
      "Эти настройки редактируются на лету и не требуют перезапуска.",
    adminNotificationsTitle: "Уведомления администратору",
    adminNotificationsDescription:
      "Настройки доставки по типам событий для админ-бота.",
    userNotificationsTitle: "Уведомления пользователю",
    userNotificationsDescription:
      "Настройки доставки по типам событий для пользовательского бота.",
    templatesTitle: "Шаблоны сообщений",
    templatesHintLabel: "Подсказка по шаблонам сообщений",
    templatesHint:
      "Многострочный текст сохраняется.\n\nПлейсхолдеры: {{username}}, {{warning_count}}, {{warnings_left}}, {{ban_text}}, {{review_url}}, {{usage_profile_summary}}.",
    userTemplates: "Пользовательские шаблоны",
    adminTemplates: "Админские шаблоны",
    envTitle: "Telegram .env",
    envDescription:
      "Токены и usernames ботов редактируются отдельно от live runtime-настроек.",
    envCount: "{present} из {total} задано",
    cards: {
      adminBot: "Админ-бот",
      userBot: "Пользовательский бот",
      adminBotConfigured: "Токен и username админ-бота",
      userBotConfigured: "Токен пользовательского бота",
      envFile: "Состояние env-файла",
    },
    sections: {
      delivery: "Доставка",
      admin: "Админ-уведомления",
      user: "Пользовательские уведомления",
    },
  },
  access: {
    eyebrow: "Доступ",
    title: "Способы входа и списки доступа",
    save: "Сохранить настройки доступа",
    saveEnv: "Сохранить .env настройки",
    saved: "Настройки доступа сохранены",
    envSaved: ".env настройки доступа сохранены",
    loadFailed: "Не удалось загрузить настройки доступа",
    saveFailed: "Не удалось сохранить изменения",
    invalidNumericValue: "Некорректное числовое значение '{value}'",
    cards: {
      telegramLogin: "Вход через Telegram",
      localFallback: "Локальный резервный вход",
      envFile: "Состояние env-файла",
    },
    authStatusTitle: "Статус аутентификации",
    authStatusDescription:
      "Учётные данные управляются только через `.env` на сервере.",
    authCards: {
      telegramPanel: "Авторизация панели через Telegram",
      localFallback: "Локальная резервная авторизация",
    },
    brandingTitle: "Оформление",
    brandingDescription:
      "Название сервиса, логотип и локальные настройки интерфейса для этой панели.",
    brandingSaved: "Оформление обновлено",
    saveBranding: "Сохранить оформление",
    brandingFields: {
      serviceName: "Название сервиса",
      serviceNameDescription:
        "Видимое название сервиса в панели и на экране входа.",
      logoUrl: "URL логотипа",
      logoUrlDescription:
        "Публичный URL изображения логотипа. Оставьте пустым, чтобы использовать встроенный логотип по умолчанию.",
      logoUrlPlaceholder: "https://example.com/logo.png",
    },
    interfaceTitle: "Интерфейс на этом устройстве",
    interfaceDescription:
      "Язык, палитра и тема применяются сразу и сохраняются локально в браузере.",
    interfaceSavedHint:
      "Эти параметры не требуют отдельного сохранения на сервере.",
    listsTitle: "Списки доступа",
    listsDescription:
      "Администраторы панели и рабочие исключения управляются отдельно.",
    envTitle: "Параметры доступа в .env",
    envDescription:
      "Локальные резервные учётки живут в `.env`, а секреты меняются только явной заменой.",
    envCount: "{present} из {total} задано",
  },
  data: {
    eyebrow: "Данные",
    title: "Оперативное управление данными",
    sectionDescriptions: {
      console:
        "Единая операторская консоль с системными логами панели, heartbeat модулей и входящими данными от модулей.",
      users:
        "Основной поток для поиска пользователя, разбора карточки, ограничений, исключений и экспортных снимков.",
      violations:
        "Глобальный обзор активных ограничений и истории нарушений из рабочего состояния.",
      overrides:
        "Ручные правила для IP и сомнительных шаблонов, которые переопределяют решения детекта.",
      cache:
        "Живые записи кэша, которые можно исправить или удалить без ожидания естественного истечения.",
      learning:
        "Продвинутые паттерны, накопленная уверенность и срезы обучения по провайдерам.",
      cases: "Недавние кейсы ревью с быстрым переходом в полные детали.",
      events:
        "Нормализованный поток событий анализа со сквозными фильтрами по IP, устройству, модулю и решению.",
      exports:
        "Сбор архива калибровки с показом готовности датасета и состава выгрузки.",
      audit:
        "История действий операторов по модерации, изменениям данных, настройкам и операциям с модулями.",
    },
    tabs: {
      console: "Консоль",
      users: "Пользователи",
      violations: "Нарушения",
      overrides: "Переопределения",
      cache: "Кэш",
      learning: "Обучение",
      cases: "Кейсы",
      events: "События",
      exports: "Выгрузки",
      audit: "Аудит",
    },
    errors: {
      loadTabFailed: "Не удалось загрузить вкладку данных",
      searchUsersFailed: "Не удалось найти пользователей",
      loadUserFailed: "Не удалось загрузить карточку пользователя",
      userActionFailed: "Не удалось выполнить действие над пользователем",
      exportUserFailed: "Не удалось собрать экспортную карточку пользователя",
      exportCalibrationFailed: "Не удалось сформировать архив калибровки",
      saveExactOverrideFailed: "Не удалось сохранить точное переопределение",
      saveUnsureOverrideFailed:
        "Не удалось сохранить переопределение для шаблона",
      saveCacheFailed: "Не удалось обновить запись кэша",
    },
    saved: {
      userUpdated: "Данные пользователя обновлены",
      exactOverride: "Точное переопределение сохранено",
      unsureOverride: "Переопределение для шаблона сохранено",
      cacheUpdated: "Запись кэша обновлена",
      learningUpdated: "Данные обучения обновлены",
      exportReady: "Экспортная карточка готова",
      exportDownloaded: "Экспортная карточка скачана",
      calibrationExportReady: "Архив калибровки сформирован",
    },
    users: {
      searchPlaceholder: "Поиск по uuid / system id / telegram id / username",
      search: "Искать",
      searching: "Ищу…",
      panelMatch: "Совпадение в панели: {value}",
      systemLabel: "sys:{value}",
      telegramLabel: "tg:{value}",
      cardTitle: "Карточка пользователя",
      exportHint:
        "Соберите структурированную export-карточку для калибровки или ручного разбора.",
      buildExport: "Собрать export-карточку",
      generatingExport: "Генерирую…",
      downloadExport: "Скачать JSON",
      exportPreviewTitle: "Предпросмотр export-карточки",
      exportGeneratedAt: "Сгенерировано {value}",
      actionsTitle: "Действия с пользователем",
      analysisTitle: "Недавний анализ и признаки провайдера",
      analysisEmpty: "Недавних событий анализа нет",
      usageProfileTitle: "Профиль использования",
      usageProfileEmpty: "Данных по профилю использования пока нет",
      usageProfileSummary: "Снимок",
      usageProfileOngoing: "Длительность окна",
      usageProfileDevices: "Устройства",
      usageProfileDeviceInventoryNote:
        "Если доступен HWID-инвентарь Remnawave, он уже подмешан в этот список.",
      usageProfileOs: "Семейства ОС",
      usageProfileNodes: "Распределение по нодам",
      usageProfileSignals: "Мягкие причины",
      usageProfileGeo: "Геоистория",
      usageProfileTravel: "Аномалии перемещения",
      usageProfileCountryJumpOnly: "только country jump",
      usageProfileTopIps: "Топ недавних IP",
      usageProfileTopProviders: "Топ провайдеров",
      openCasesTitle: "Открытые / недавние кейсы ревью",
      openCasesEmpty: "Локальных кейсов ревью нет",
      historyTitle: "История нарушений",
      historyEmpty: "Истории нарушений нет",
      providerConflict: "Есть конфликт маркеров провайдера",
      providerClear: "Маркеры провайдера согласованы",
      reviewFirst: "Только через ручное ревью",
      autoReady: "Есть второй независимый фактор",
      exportCards: {
        reviewCases: "Кейсы ревью",
        analysisEvents: "События анализа",
        history: "История",
        ipHistory: "История IP",
      },
      exportSections: {
        identity: "Identity",
        flags: "Flags",
        panel: "Panel user",
        reviewCases: "Review cases",
        analysisEvents: "Analysis events",
        history: "History",
        activeTrackers: "Active trackers",
        ipHistory: "IP history",
      },
      fields: {
        username: "Имя пользователя",
        uuid: "UUID",
        systemId: "System ID",
        telegramId: "Telegram ID",
        panelStatus: "Статус в панели",
        panelSquads: "Активные группы",
        trafficLimitBytes: "Лимит трафика",
        trafficLimitStrategy: "Стратегия лимита",
        usedTrafficBytes: "Текущий потраченный трафик",
        lifetimeUsedTrafficBytes: "Трафик за всё время",
        exemptSystemId: "Исключённый System ID",
        exemptTelegramId: "Исключённый Telegram ID",
        activeBan: "Активное ограничение",
        activeWarning: "Активное предупреждение",
      },
      actions: {
        banMinutes: "Минуты ограничения",
        startBan: "Ограничить доступ",
        unban: "Восстановить полный доступ",
        trafficCapGigabytes: "Лимит трафика: +GB от текущего расхода",
        applyTrafficCap: "Установить лимит трафика",
        restoreTrafficCap: "Восстановить прежний лимит",
        strikes: "Страйки",
        add: "Добавить",
        remove: "Удалить",
        set: "Установить",
        warnings: "Предупреждения",
        setWarning: "Установить предупреждение",
        clearWarning: "Очистить предупреждение",
        exemptions: "Исключения",
        exemptSystem: "Исключить систему",
        unexemptSystem: "Убрать исключение системы",
        exemptTelegram: "Исключить Telegram",
        unexemptTelegram: "Убрать исключение Telegram",
      },
    },
    violations: {
      activeTitle: "Активные нарушения / ограничения доступа",
      historyTitle: "История нарушений",
      strikes: "страйков {value}",
      warningCount: "предупреждений {value}",
      unban: "восстановление {value}",
      historyRow: "страйк {strike} · {duration} мин",
    },
    overrides: {
      exactTitle: "Точные переопределения IP",
      unsureTitle: "Переопределения для сомнительных шаблонов",
      ipPlaceholder: "IP",
      ipPatternPlaceholder: "IP pattern",
      save: "Сохранить",
      delete: "Удалить",
      expires: "истекает {value}",
    },
    decisions: {
      home: "HOME",
      mobile: "MOBILE",
      skip: "SKIP",
    },
    cache: {
      title: "Кэш IP",
      editTitle: "Редактировать запись кэша",
      edit: "Редактировать",
      delete: "Удалить",
      selectedIp: "Выбранный IP",
      status: "статус",
      confidence: "уверенность",
      details: "подробности",
      asn: "asn",
      asnValue: "ASN {value}",
      save: "Сохранить запись кэша",
    },
    learning: {
      promotedActiveTitle: "Активные promoted patterns",
      promotedStatsTitle: "Статистика promoted",
      legacyTitle: "Legacy learning",
      providerActiveTitle: "Promoted provider patterns",
      providerServiceActiveTitle: "Promoted provider service patterns",
      providerLegacyTitle: "Legacy provider patterns",
      empty: "Provider-specific learning пока пуст",
      support: "support {value}",
      precision: "precision {value}",
      total: "total {value}",
      confidence: "confidence {value}",
      plusOneConfidence: "+1 confidence",
      delete: "Удалить",
    },
    audit: {
      title: "Журнал действий операторов",
      description:
        "Журнал только для чтения с действиями администраторов, которые меняли состояние модерации, правила, настройки или модули.",
      empty: "Аудит-событий пока нет",
    },
    console: {
      title: "Консоль",
      description:
        "Живой поток системных логов панели, heartbeat модулей и входящих событий модулей.",
      filtersTitle: "Фильтры консоли",
      count: "Записей: {count}",
      empty: "По текущим фильтрам записей в консоли нет",
      payload: "Полезная нагрузка",
      metaPayload: "Метаданные",
      filters: {
        search: "Поиск по сообщению / payload",
        anySource: "Любой источник",
        anyLevel: "Любой уровень",
        moduleId: "ID модуля",
      },
      sources: {
        system: "Система",
        module_event: "Событие модуля",
        module_heartbeat: "Heartbeat",
      },
      levels: {
        info: "Инфо",
        warn: "Предупреждение",
        error: "Ошибка",
      },
      sourceCount: {
        system: "Система: {count}",
        moduleEvents: "События: {count}",
        moduleHeartbeats: "Heartbeat: {count}",
      },
      meta: {
        moduleName: "Модуль: {value}",
        logger: "Логгер: {value}",
        eventUid: "UID события: {value}",
      },
      pagination: {
        previous: "Назад",
        next: "Дальше",
        page: "Страница {page} из {total}",
        pageSizeOption: "{value} на страницу",
      },
    },
    cases: {
      title: "Кейсы",
    },
    events: {
      title: "События анализа",
      description:
        "Нормализованный поток событий анализа с фильтрами, привязкой к кейсам и раскрытием исходных данных.",
      filtersTitle: "Фильтры событий",
      count: "Найдено {count}",
      empty: "Событий по текущим фильтрам нет",
      ipOnly: "IP без устройства",
      noCase: "без кейса",
      filters: {
        search: "Поиск",
        ip: "IP",
        deviceId: "Device ID",
        moduleId: "Module ID",
        inbound: "Инбаунд",
        provider: "Провайдер",
        asn: "ASN",
        anyVerdict: "Любой вердикт",
        anyConfidence: "Любая уверенность",
        highMobile: "HIGH_MOBILE",
        anyCase: "С кейсом и без",
        withCase: "Только с кейсом",
        withoutCase: "Только без кейса",
      },
      meta: {
        module: "Модуль: {value}",
        inbound: "Инбаунд: {value}",
        provider: "Провайдер: {value}",
        asn: "ASN: {value}",
        scope: "Область: {value}",
        case: "Кейс: {value}",
      },
      details: {
        providerEvidence: "Признаки провайдера",
        reasons: "Причины",
        signalFlags: "Флаги сигналов",
        rawBundle: "Исходный пакет",
      },
      pagination: {
        previous: "Назад",
        next: "Дальше",
        page: "Страница {page} из {total}",
        pageSizeOption: "{value} на страницу",
      },
    },
    exports: {
      title: "Выгрузка калибровки",
      description:
        "Сформировать ZIP-архив с сырыми размеченными строками и сводкой для настройки правил.",
      generating: "Формирую…",
      generate: "Собрать ZIP",
      lastManifestTitle: "Состав последней выгрузки",
      readinessTitle: "Готовность пакета калибровки",
      readinessDescription:
        "Предварительный просмотр показывает, насколько выгрузка уже пригодна для обучения и настройки скоринга.",
      noManifest: "Предварительный просмотр готовности пока недоступен",
      datasetReady: "Датасет структурно пригоден для анализа",
      datasetNotReady:
        "Датасет пока непригоден для надёжной provider-калибровки",
      tuningReady: "По этой выгрузке уже можно начинать provider tuning",
      tuningNotReady: "Provider tuning пока заблокирован покрытием или support",
      blockersTitle: "Блокеры readiness",
      noBlockers: "Критичных blockers сейчас нет",
      checksTitle: "Текущие readiness checks",
      warningsTitle: "Предупреждения readiness-проверки",
      notReadyToast:
        "Calibration archive сформирован, но readiness checks не пройдены",
      filterSnapshot: "Применённые фильтры",
      coverageSnapshot: "Снимок покрытия",
      filters: {
        openedFrom: "Открыт с",
        openedTo: "Открыт по",
        reviewReason: "Причина ревью",
        providerKey: "Ключ провайдера",
        status: "Статус датасета",
        includeUnknown: "Включать unknown в агрегаты",
      },
      status: {
        resolvedOnly: "Только resolved",
        openOnly: "Только open",
        all: "Все кейсы",
      },
      cards: {
        overallReadiness: "Общая готовность",
        datasetReadiness: "Готовность dataset",
        tuningReadiness: "Готовность tuning",
        file: "Архив",
        rawRows: "Сырые rows",
        knownRows: "Размеченные rows",
        unknownRows: "Unknown rows",
        providerProfiles: "Профили провайдеров",
        providerCoverage: "Покрытие provider key",
        patternCandidates: "Кандидаты provider patterns",
      },
      readiness: {
        checks: {
          provider_profiles_present: "Provider profiles в snapshot",
          resolved_ratio: "Resolved ratio",
          provider_evidence_coverage: "Покрытие provider explainability",
          provider_key_coverage: "Покрытие provider key",
          min_provider_support: "Минимальный support по провайдерам",
        },
      },
      warnings: {
        live_rules_stale_or_unseeded:
          "Live rules snapshot был пуст и был слит с runtime config.",
        provider_profiles_missing: "В snapshot выгрузки нет provider profiles.",
        provider_key_coverage_zero: "В resolved rows вообще нет provider key.",
        provider_explainability_missing:
          "В экспортированных rows отсутствует provider explainability.",
        resolved_ratio_below_threshold:
          "Слишком много pending rows: resolved ratio ниже безопасного порога.",
        provider_key_coverage_below_target:
          "Покрытие provider key ниже целевого порога 0.6.",
        provider_support_below_target:
          "Хотя бы один provider/provider_service кандидат имеет меньше 5 известных resolved cases.",
      },
    },
  },
  quality: {
    eyebrow: "Качество",
    title: "Качество",
    description:
      "Метрики и графики принятых решений, шумных ASN и состояния обучения",
    allModules: "Все модули",
    loadFailed: "Не удалось загрузить метрики качества",
    cards: {
      openCases: "Открытые кейсы",
      totalCases: "Всего кейсов",
      resolvedHome: "Подтверждённые HOME",
      resolvedMobile: "Подтверждённые MOBILE",
      skipped: "Пропущено",
      activePatterns: "Активные паттерны",
      activeSessions: "Активные сессии",
      mixedProviderCases: "Открытые кейсы смешанных провайдеров",
      mixedConflictRate: "Доля конфликтов смешанных провайдеров",
      homeRatio: "Доля HOME",
      mobileRatio: "Доля MOBILE",
    },
    revision: "Ревизия правил {value}",
    updated: "Обновлено {value}",
    by: "Кем: {value}",
    asnSourceTitle: "Источник ASN",
    noAsnSource: "Источник ASN недоступен",
    resolutionMixTitle: "Смесь решений",
    resolutionMixDescription:
      "Как именно операторы сейчас разрешают спорные кейсы.",
    topNoisyAsnTitle: "Самые шумные ASN",
    noisyAsnDescription:
      "ASN, которые сейчас создают наибольшее давление на очередь ревью",
    topMixedProvidersTitle: "Смешанные провайдеры с наибольшим хвостом",
    mixedProvidersDescription:
      "Провайдеры с наибольшей нагрузкой по открытым кейсам и конфликтам.",
    noMixedProviders: "По смешанным провайдерам пока нет хвоста.",
    mixedProviderStats:
      "{open} открыто · {conflict} конфликтов · HOME {home} · MOBILE {mobile} · UNSURE {unsure}",
    reviewCases: "{count} кейсов ревью",
    topPromotedPatternsTitle: "Топ продвинутых паттернов",
    topPatternDetails:
      "{decision} · поддержка {support} · точность {precision}",
    learningStateTitle: "Состояние обучения",
    providerLearningTitle: "Обучение по операторам",
    promotedByTypeTitle: "Продвинутое обучение по типам",
    noPromotedData: "Продвинутых данных пока нет",
    legacyByTypeTitle: "Наследуемое обучение по типам",
    noLegacyData: "Наследуемое обучение пока пусто",
    topLegacyTitle: "Топ наследуемых паттернов",
    noLegacyPatterns: "Наследуемых паттернов пока нет",
    learningCards: {
      promotedPatterns: "Продвинутые паттерны",
      legacyPatterns: "Наследуемые паттерны",
      legacyConfidence: "Наследуемая уверенность",
      asnMinSupport: "Мин. поддержка ASN",
      asnMinPrecision: "Мин. точность ASN",
      comboMinSupport: "Мин. поддержка комбинаций",
      comboMinPrecision: "Мин. точность комбинаций",
    },
    providerLearning: {
      promoted: "Продвинутые паттерны провайдеров",
      legacy: "Наследуемые паттерны провайдеров",
    },
    patternStats:
      "{count} паттернов · поддержка {support} · средняя точность {precision}",
    legacyStats: "{count} паттернов · накопленная уверенность {confidence}",
    legacyConfidenceValue: "уверенность {value}",
  },
  tooltips: {
    info: "Подсказка",
  },
  rulesMeta: {
    sections: {
      access: "Доступ",
      asnLists: "ASN Lists",
      keywords: "Keywords",
      providers: "Профили операторов",
      thresholds: "Thresholds",
      scores: "Scores",
      behavior: "Behavior",
      policy: "Policy",
      learning: "Learning",
      retention: "Retention",
    },
    listFields: {
      admin_tg_ids: {
        label: "Owner Telegram IDs",
        description:
          "Telegram IDs, которым назначена owner-роль с полным доступом к платформе.",
        recommendation:
          "Держите этот список коротким и максимально доверенным.",
      },
      moderator_tg_ids: {
        label: "Moderator Telegram IDs",
        description:
          "Telegram IDs, которым разрешены queue resolution, recheck и data-admin мутации без доступа к platform settings.",
        recommendation:
          "Используйте для операторов ручной модерации и runtime-коррекций.",
      },
      viewer_tg_ids: {
        label: "Viewer Telegram IDs",
        description:
          "Telegram IDs для read-only доступа к overview, quality, modules, queue, data и audit.",
        recommendation:
          "Подходит для аналитиков и поддержки, которым не нужно менять состояние.",
      },
      exempt_ids: {
        label: "Excluded System IDs",
        description:
          "Системные user.id, исключённые из анализа и авто-санкций.",
        recommendation: "Добавляйте только служебные или доверенные аккаунты.",
      },
      exempt_tg_ids: {
        label: "Excluded Telegram IDs",
        description: "Telegram IDs, исключённые из анализа и авто-санкций.",
        recommendation:
          "Используйте, если удобнее администрировать исключения по Telegram ID.",
      },
      pure_mobile_asns: {
        label: "Pure mobile ASN list",
        description:
          "ASN, которые почти всегда считаются мобильными и дают сильный mobile-сигнал.",
        recommendation:
          "Добавляйте ASN только после подтверждённой чистой мобильной выборки.",
      },
      pure_home_asns: {
        label: "Pure home ASN list",
        description:
          "ASN, которые почти всегда считаются домашними и дают сильный home-сигнал.",
        recommendation:
          "Сюда должны попадать только стабильно домашние ASN без мобильной примеси.",
      },
      mixed_asns: {
        label: "Mixed ASN list",
        description:
          "ASN со смешанным профилем, где нужны дополнительные признаки и осторожность.",
        recommendation:
          "Используйте для спорных ASN, где одного ASN недостаточно для вердикта.",
      },
      allowed_isp_keywords: {
        label: "Mobile keywords",
        description:
          "Ключевые слова, усиливающие mobile-версию при совпадении в ISP/hostname.",
        recommendation:
          "Держите здесь короткие устойчивые mobile-маркеры, без широких слов.",
      },
      home_isp_keywords: {
        label: "Home keywords",
        description: "Ключевые слова, которые тянут решение в сторону home.",
        recommendation:
          "Добавляйте только маркеры фиксированных/домашних провайдеров.",
      },
      exclude_isp_keywords: {
        label: "Datacenter / hosting keywords",
        description:
          "Ключевые слова для детекта хостинга, датацентров и инфраструктурных сетей.",
        recommendation:
          "Держите список консервативным, чтобы не ловить обычных провайдеров.",
      },
    },
    settingFields: {
      threshold_mobile: {
        label: "MOBILE decision threshold",
        description:
          "Score, начиная с которого кейс считается уверенно мобильным.",
        recommendation: "Базовое безопасное значение: около 60.",
      },
      threshold_probable_mobile: {
        label: "Probable mobile threshold",
        description:
          "Порог для промежуточного mobile-сигнала до финального MOBILE.",
        recommendation: "Обычно держат ниже основного mobile threshold.",
      },
      threshold_home: {
        label: "HOME decision threshold",
        description:
          "Нижний score, после которого кейс считается уверенно домашним.",
        recommendation: "Чем выше значение, тем осторожнее будут home-решения.",
      },
      threshold_probable_home: {
        label: "Probable home threshold",
        description:
          "Порог для промежуточного home-сигнала до финального HOME.",
        recommendation: "Держите между threshold_home и нейтральной зоной.",
      },
      pure_asn_score: {
        label: "Pure mobile ASN bonus",
        description: "Бонус к score, если ASN найден в pure_mobile_asns.",
        recommendation:
          "Обычно это сильный бонус, сопоставимый с threshold_mobile.",
      },
      mixed_asn_score: {
        label: "Mixed ASN bonus",
        description:
          "Бонус к score для mixed ASN до учёта дополнительных признаков.",
        recommendation: "Держите заметно ниже pure mobile ASN bonus.",
      },
      ptr_home_penalty: {
        label: "Home keyword penalty",
        description: "Штраф за home keywords в ISP/hostname.",
        recommendation:
          "Небольшой минус, чтобы keyword не перевешивал жёсткие сигналы.",
      },
      mobile_kw_bonus: {
        label: "Mobile keyword bonus",
        description: "Бонус за mobile keywords в ISP/hostname.",
        recommendation:
          "Делайте меньше чистого ASN-бонуса, но достаточно значимым.",
      },
      provider_mobile_marker_bonus: {
        label: "Бонус за mobile marker оператора",
        description:
          "Дополнительный бонус, когда provider profile находит мобильный service marker.",
        recommendation:
          "Держите умеренным и не используйте как единственный автосигнал для mixed-провайдера.",
      },
      provider_home_marker_penalty: {
        label: "Штраф за home marker оператора",
        description:
          "Дополнительный штраф, когда provider profile находит домашний service marker.",
        recommendation:
          "Штраф должен быть заметным, но не единственной причиной для punitive по mixed-провайдеру.",
      },
      ip_api_mobile_bonus: {
        label: "ip-api mobile bonus",
        description:
          "Дополнительный bonus, если fallback ip-api подтверждает mobile сеть.",
        recommendation:
          "Используйте только как добивающий сигнал для mixed ASN.",
      },
      pure_home_asn_penalty: {
        label: "Pure home ASN penalty",
        description: "Штраф, если ASN попадает в pure_home_asns.",
        recommendation: "Обычно это сильный penalty для уверенного HOME.",
      },
      score_subnet_mobile_bonus: {
        label: "Subnet mobile bonus",
        description: "Бонус за исторические mobile-сигналы в той же подсети.",
        recommendation:
          "Делайте его умеренным, чтобы не переобучать редкие подсети.",
      },
      score_subnet_home_penalty: {
        label: "Subnet home penalty",
        description: "Штраф за исторические home-сигналы в подсети.",
        recommendation:
          "Подходит как корректирующий, а не доминирующий сигнал.",
      },
      score_churn_high_bonus: {
        label: "High churn bonus",
        description: "Бонус за очень высокую сменяемость IP/сессий.",
        recommendation: "Используйте как сильный поведенческий mobile-признак.",
      },
      score_churn_medium_bonus: {
        label: "Medium churn bonus",
        description: "Бонус за умеренную сменяемость IP/сессий.",
        recommendation: "Делайте заметно ниже high churn bonus.",
      },
      score_stationary_penalty: {
        label: "Stationary penalty",
        description: "Штраф за слишком долгую стационарность пользователя.",
        recommendation: "Обычно это мягкий penalty, не hard-stop.",
      },
      concurrency_threshold: {
        label: "Concurrency threshold",
        description:
          "Сколько одновременных пользователей на IP считать признаком мобильности.",
        recommendation: "Стартовая точка: 2–3.",
      },
      churn_window_hours: {
        label: "Churn window (hours)",
        description: "Окно в часах для расчёта churn и сменяемости IP.",
        recommendation:
          "Чем меньше окно, тем чувствительнее реакция на всплески.",
      },
      churn_mobile_threshold: {
        label: "Churn mobile threshold",
        description: "Сколько смен IP считать mobile-поведенческим сигналом.",
        recommendation: "Подбирайте по реальным mobile-паттернам без перегиба.",
      },
      lifetime_stationary_hours: {
        label: "Stationary lifetime (hours)",
        description:
          "После какой длительности одна и та же сессия выглядит слишком домашней.",
        recommendation: "Увеличивайте, если боитесь ложных home-срабатываний.",
      },
      subnet_mobile_ttl_days: {
        label: "Subnet mobile TTL (days)",
        description: "Сколько дней хранить mobile-историю по подсетям.",
        recommendation:
          "Более длинный TTL повышает память системы, но и риск устаревания.",
      },
      subnet_home_ttl_days: {
        label: "Subnet home TTL (days)",
        description: "Сколько дней хранить home-историю по подсетям.",
        recommendation: "Обычно меньше mobile TTL, чтобы быстрее забывать шум.",
      },
      subnet_mobile_min_evidence: {
        label: "Subnet mobile min evidence",
        description:
          "Минимум mobile-свидетельств до включения subnet mobile bonus.",
        recommendation: "Повышайте, если подсетей много и они шумные.",
      },
      subnet_home_min_evidence: {
        label: "Subnet home min evidence",
        description:
          "Минимум home-свидетельств до включения subnet home penalty.",
        recommendation: "Обычно требует больше подтверждений, чем mobile.",
      },
      shadow_mode: {
        label: "Shadow mode",
        description:
          "Если включено, система анализирует и пишет кейсы, но не применяет санкции жёстко.",
        recommendation: "Новый rollout безопаснее начинать с true.",
      },
      probable_home_warning_only: {
        label: "Probable home = warning only",
        description:
          "Ограничивает probable home кейсы предупреждением вместо punitive действий.",
        recommendation:
          "Рекомендуется держать включённым для осторожного режима.",
      },
      auto_enforce_requires_hard_or_multi_signal: {
        label: "Require hard or multi-signal for auto-enforce",
        description:
          "Авто-применение санкций разрешено только при сильном или многосигнальном HOME.",
        recommendation: "Безопаснее оставлять включённым.",
      },
      provider_conflict_review_only: {
        label: "Mixed provider conflicts только в review",
        description:
          "Оставляет конфликты mixed-провайдеров, отсутствие service markers и однофакторные carrier hints в ручном ревью.",
        recommendation:
          "Рекомендуется для review-first rollout по неоднозначным операторам.",
      },
      review_ui_base_url: {
        label: "Review UI base URL",
        description:
          "Базовый URL веб-панели, который используется в review links.",
        recommendation: "Укажите боевой HTTPS URL панели.",
      },
      live_rules_refresh_seconds: {
        label: "Live rules refresh interval",
        description: "Как часто runtime перечитывает live rules из storage.",
        recommendation: "Обычно достаточно 10–30 секунд.",
      },
      db_cleanup_interval_minutes: {
        label: "Интервал очистки БД (минуты)",
        description:
          "Как часто API-процесс запускает периодический maintenance-проход по SQLite.",
        recommendation:
          "30 минут — безопасное стартовое значение для steady-state очистки.",
      },
      module_heartbeats_retention_days: {
        label: "Хранение module heartbeat (дни)",
        description:
          "Сколько дней держать исторические heartbeat-записи модулей перед очисткой.",
        recommendation:
          "Держите коротко: актуальное состояние модуля и так хранится в таблице modules.",
      },
      ingested_raw_events_retention_days: {
        label: "Хранение сырых ingested events (дни)",
        description:
          "Сколько дней хранить события модулей после того, как они перестают быть нужны для обычной работы.",
        recommendation:
          "30 дней обычно достаточно, если вам не нужны длинные окна повторной подачи событий.",
      },
      ip_history_retention_days: {
        label: "Хранение IP history (дни)",
        description:
          "Сколько дней сохранять поведенческую историю IP для churn и long-window анализа.",
        recommendation:
          "Согласуйте это значение с самым длинным history-based окном скоринга, которому вы реально доверяете.",
      },
      orphan_analysis_events_retention_days: {
        label: "Хранение orphan analysis events (дни)",
        description:
          "Сколько дней держать analysis events, на которые больше не ссылается ни один review case.",
        recommendation:
          "Короткое окно заметно ограничивает рост базы, сохраняя недавний операторский контекст.",
      },
      resolved_review_retention_days: {
        label: "Хранение resolved review (дни)",
        description:
          "Сколько дней хранить resolved/skipped кейсы и связанную audit-историю.",
        recommendation:
          "Здесь держите длинное audit-окно; активные OPEN-кейсы эта настройка не удаляет.",
      },
      learning_promote_asn_min_support: {
        label: "Promoted ASN min support",
        description:
          "Минимум подтверждённых кейсов, чтобы ASN попал в promoted learning.",
        recommendation: "Повышайте, если боитесь раннего переобучения.",
      },
      learning_promote_asn_min_precision: {
        label: "Promoted ASN min precision",
        description: "Минимальная precision для promoted ASN pattern.",
        recommendation: "Консервативный режим обычно начинается около 0.95.",
      },
      learning_promote_combo_min_support: {
        label: "Promoted combo min support",
        description: "Минимум кейсов для promoted combo pattern.",
        recommendation: "Обычно ниже ASN support, но не слишком низко.",
      },
      learning_promote_combo_min_precision: {
        label: "Promoted combo min precision",
        description: "Минимальная precision для combo pattern.",
        recommendation: "Держите высокой, чтобы combo не давал шумных бонусов.",
      },
    },
    rulesGeneralFields: {
      usage_time_threshold: {
        label: "Minimum suspicious usage time (sec)",
        description:
          "Как долго подозрительная сессия должна оставаться активной до начала санкций.",
      },
      warning_timeout_seconds: {
        label: "Warning cooldown (sec)",
        description: "Минимальная задержка перед следующим предупреждением.",
      },
      warnings_before_ban: {
        label: "Предупреждений до первого ограничения",
        description:
          "Сколько предупреждений нужно до первого ограничения доступа.",
      },
      warning_only_mode: {
        label: "Only warnings mode",
        description:
          "Никогда не повышать санкции до ограничений доступа автоматически.",
      },
      manual_review_mixed_home_enabled: {
        label: "Review mixed HOME cases manually",
        description:
          "Отправлять смешанные HOME-результаты в ручное ревью до действия.",
      },
      manual_ban_approval_enabled: {
        label: "Требовать одобрение ограничения",
        description:
          "Останавливать применение ограничения до ручного одобрения админом.",
      },
      dry_run: {
        label: "Dry run",
        description:
          "Анализировать и уведомлять без удалённого переключения squads.",
      },
      ban_durations_minutes: {
        label: "Лестница ограничений (минуты)",
        description:
          "Одно значение на строку: первое ограничение, второе, третье и так далее.",
      },
      full_access_squad_name: {
        label: "Имя squad полного доступа",
        description:
          "Точное имя internal squad Remnawave, которое означает полный доступ.",
      },
      restricted_access_squad_name: {
        label: "Имя squad ограничения",
        description:
          "Точное имя internal squad Remnawave, которое выдаётся при нарушении.",
      },
      traffic_cap_increment_gb: {
        label: "Прирост traffic cap (GB)",
        description:
          "На сколько гигабайт увеличить лимит относительно текущего used traffic.",
      },
      traffic_cap_threshold_gb: {
        label: "Порог traffic cap (GB)",
        description:
          "Если пользователь уже израсходовал не меньше этого объёма, вместо скрытия мобильных конфигов применяется traffic cap.",
      },
    },
    telegramFields: {
      tg_admin_chat_id: {
        label: "ID администраторского чата",
        description: "Telegram chat id для уведомлений администраторам",
      },
      tg_topic_id: {
        label: "Топик уведомлений (необязательно)",
        description: "Необязательный topic/thread id внутри админского чата",
      },
      telegram_message_min_interval_seconds: {
        label: "Задержка между отправками",
        description: "Минимальная задержка между отправками Telegram",
      },
      telegram_admin_notifications_enabled: {
        label: "Уведомления администраторов",
        description: "Главный переключатель для всех уведомлений админ-бота",
      },
      telegram_user_notifications_enabled: {
        label: "Уведомления пользователей",
        description:
          "Главный переключатель для всех пользовательских сообщений бота",
      },
      telegram_admin_commands_enabled: {
        label: "Команды администратора",
        description: "Разрешает обработчики админских команд Telegram",
      },
      telegram_notify_admin_review_enabled: {
        label: "Ревью",
        description:
          "Отправлять админские сообщения, когда нужно ревью / ручная модерация",
      },
      telegram_notify_admin_warning_only_enabled: {
        label: "Нарушение",
        description:
          "Отправлять админские сообщения по неэскалирующим warning-only кейсам",
      },
      telegram_notify_admin_warning_enabled: {
        label: "Предупреждения",
        description: "Отправлять админские сообщения при выдаче предупреждения",
      },
      telegram_notify_admin_ban_enabled: {
        label: "Блокировка",
        description:
          "Отправлять админские сообщения при применении ограничения доступа",
      },
      telegram_notify_admin_usage_profile_risk_enabled: {
        label: "Notify usage-profile risk",
        description:
          "Отправлять админские сообщения с enriched usage-profile snapshot",
      },
      telegram_notify_admin_violation_continues_enabled: {
        label: "Продолжительные нарушения",
        description:
          "Отправлять админские сообщения, когда подозрительное поведение продолжается во времени",
      },
      telegram_notify_admin_traffic_limit_exceeded_enabled: {
        label: "Ограничения по трафику",
        description:
          "Отправлять админские сообщения, когда применяется traffic-cap ограничение",
      },
      telegram_notify_user_warning_only_enabled: {
        label: "Send warning-only messages",
        description:
          "Отправлять пользовательские сообщения по warning-only кейсам.",
      },
      telegram_notify_user_warning_enabled: {
        label: "Send warning messages",
        description:
          "Отправлять пользовательские сообщения при выдаче предупреждения.",
      },
      telegram_notify_user_ban_enabled: {
        label: "Send access restriction messages",
        description:
          "Отправлять пользовательские сообщения при применении ограничения доступа.",
      },
    },
    telegramTemplateFields: {
      user_warning_only_template: {
        label: "Warning-only message",
        description:
          "Пользовательское сообщение, когда кейс warning-only и не эскалируется.",
      },
      user_warning_template: {
        label: "Warning message",
        description:
          "Пользовательское сообщение для обычных предупреждений перед ограничением доступа.",
      },
      user_ban_template: {
        label: "Access restriction message",
        description:
          "Пользовательское сообщение, отправляемое при ограничении доступа.",
      },
      admin_warning_only_template: {
        label: "Warning-only message",
        description: "Текст админского уведомления по warning-only кейсам.",
      },
      admin_warning_template: {
        label: "Warning message",
        description: "Текст админского уведомления по предупреждениям.",
      },
      admin_ban_template: {
        label: "Access restriction message",
        description: "Текст админского уведомления по ограничениям доступа.",
      },
      admin_review_template: {
        label: "Review message",
        description:
          "Текст админского уведомления для кейсов ревью / ручной модерации.",
      },
      admin_usage_profile_risk_template: {
        label: "Usage-profile risk message",
        description:
          "Текст админского уведомления для enriched usage-profile snapshot.",
      },
      admin_violation_continues_template: {
        label: "Violation-continues message",
        description:
          "Текст админского уведомления, когда подозрительное поведение продолжает развиваться.",
      },
      admin_traffic_limit_exceeded_template: {
        label: "Traffic-limit-exceeded message",
        description:
          "Текст админского уведомления, когда применяется traffic-cap ограничение.",
      },
    },
  },
};
