import type { TranslationDictionary } from "../types";

export const ruDictionary: TranslationDictionary = {
  common: {
    loading: "Загрузка…",
    loadingLabel: "Загрузка",
    loadingSession: "Загружаю сессию…",
    notAvailable: "недоступно",
    admin: "Администратор",
    system: "Система",
    yes: "да",
    no: "нет",
    true: "да",
    false: "нет",
    saved: "сохранено",
    unsavedChanges: "есть несохранённые изменения",
    configured: "Настроено",
    disabled: "Отключено",
    on: "ВКЛ",
    off: "ВЫКЛ",
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
      panelUser: "Инвентарь HWID Remnawave",
      event: "журнал доступа",
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
      rules: "Правила",
      telegram: "Telegram",
      system: "Система",
      data: "Данные",
      quality: "Качество",
      bedolaga: "Bedolaga",
    },
    subnav: {
      data: {
        console: "Консоль",
        users: "Пользователи",
        aiSuggestions: "Рекомендации ИИ",
        violations: "Нарушения",
        overrides: "Оверрайды",
        cache: "Кэш",
        learning: "Обучение",
        cases: "Кейсы",
        events: "События",
        exports: "Экспорты",
        audit: "Аудит",
      },
      system: {
        access: "Доступ",
        branding: "Оформление",
        general: "Общие",
        thresholds: "Калибровка",
        lists: "Списки",
        providers: "Провайдеры",
        retention: "Хранение",
      },
      quality: {
        metrics: "Метрики",
        learning: "Обучение",
        aiSuggestions: "Рекомендации ИИ",
        aiOptimizer: "AI Оптимизатор",
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
      ru: "Русский",
      en: "Английский",
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
      "Ключевые рабочие сигналы: активные ограничения, доставка удалённых действий и текущий режим реакции.",
    pipelineTitle: "Состояние конвейера обработки",
    pipelineDescription:
      "Очередь, лаг воркера и отложенные удалённые задачи применения. Только здесь, на главном экране.",
    attentionItems: {
      overviewStale:
        "Снимок обзора устарел. Проверьте фоновые обновления модели чтения.",
      pipelineStale:
        "Снимок конвейера обработки устарел. Возможна задержка в отображении очереди.",
      failedQueue:
        "В конвейере обработки есть ошибки: {count}. Нужно проверить повторы и очередь ошибок.",
      openCases: "В очереди ревью сейчас {count} открытых кейсов.",
      mixedConflicts: "Смешанные провайдеры дали {count} конфликтных кейсов.",
      activeViolations:
        "Сейчас активно {count} ограничений или предупреждений.",
      laggingConfigs:
        "{count} модулей работают не на актуальной ревизии конфига.",
      staleModules: "{count} модулей давно не отчитывались.",
      quiet: "Критичных сигналов сейчас нет.",
    },
    health: {
      core: "Модуль скоринга",
      db: "База данных",
      rules: "Живые правила",
      moduleConfig: "Ревизия конфигов модулей",
      enforcement: "Активные ограничения",
      lastEnforcement: "Последнее действие",
      remoteDelivery: "Доставка ограничений",
      embedded: "встроен",
      embeddedRuntime: "Встроен в API панели · обновлено {value}",
      updated: "Обновлено {value}",
      rulesBy: "Обновил {value}",
    },
    cards: {
      openQueue: "Открытая очередь",
      failedQueue: "Ошибки обработки",
      activeViolations: "Активные нарушения",
      activeWarnings: "Активные предупреждения",
      activeBans: "Активные баны",
      violatingNow: "Сейчас нарушают",
      compliantNow: "Сейчас по правилам",
      activeUsers: "Активные пользователи",
      activeUsersHint: "Окно активности {value} сек",
      core: "Модуль скоринга",
      embeddedValue: "встроен",
      ipinfo: "Токен IPINFO",
      adminSessions: "Админ-сессии",
      scoreZeroRatio: "Доля событий с score=0 (24 ч)",
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
      "{open} открыто · {conflict} конфликтов · {home} домашний доступ · {mobile} мобильный доступ",
    mixedProvidersMetrics: {
      open: "Открыто",
      conflicts: "Конфликты",
      home: "Домашний доступ",
      mobile: "Мобильный доступ",
    },
    emptyMixedProviders: "Сейчас нет проблемных смешанных провайдеров.",
    noisyAsnTitle: "Самые шумные ASN",
    noisyAsnDescription: "ASN, создающие наибольшую нагрузку на модерацию.",
    noisyAsnItem: "{count} кейсов ревью",
    emptyNoisyAsn: "Данных по шумным ASN пока нет.",
    latestCasesTitle: "Последние кейсы очереди",
    latestCasesDescription:
      "Свежие спорные кейсы, готовые к обработке оператором.",
    emptyLatestCases: "Сейчас открытых кейсов нет.",
    pipeline: {
      queueDepth: "Глубина очереди",
      queueMeta: "{queued} в очереди · {processing} обрабатывается",
      failed: "Ошибки очереди",
      pendingRemote: "{count} удалённых задач ждут отправки",
      lag: "Текущий лаг",
      oldestQueued: "Самая старая запись в очереди {value}",
      lastDrain: "Последний полный проход",
      snapshotAge: "Возраст снимка {value}",
      stale: "снимок устарел",
    },
    automation: {
      modeTitle: "Режим автоматики",
      guardrailsTitle: "Активные ограничители",
      noModeReasons: "Нет флагов, ограничивающих режим",
      noGuardrails: "Дополнительные ограничители не включены",
    },
    enforcement: {
      activeSummary:
        "{violations} активных ограничений · {warnings} предупреждений · {bans} банов",
      configSummary:
        "rev {revision} · {current} на актуальной · {lagging} отстают · {stale} неактивны",
      lastWarning: "Последнее предупреждение {value}",
      lastBan: "Последнее ограничение {value}",
      lastBanDuration: "{value} мин",
      never: "Система пока не зафиксировала ограничений",
      remoteSummary:
        "{pending} ждут применения · {failed} с ошибкой · воркер {worker}",
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
      punitive: "С ограничением",
      shortActivity: "Активность < 12ч",
    },
    filters: {
      sections: {
        identity: "Кого ищем",
        identityHint: "Быстрый отбор по модулю и идентификаторам пользователя.",
        timing: "Когда и как долго",
        timingHint: "Фильтры по дате открытия, активности кейса и повторам.",
        decision: "Статус и приоритет",
        decisionHint: "Решение, причина ревью, срочность и сортировка.",
      },
      moduleId: "ID модуля",
      username: "Имя пользователя",
      systemId: "Системный ID",
      telegramId: "Telegram ID",
      openedFrom: "Открыт с",
      openedTo: "Открыт до",
      activityMinHours: "Активность от, ч",
      activityMaxHours: "Активность до, ч",
      repeatMin: "Минимум повторов",
      repeatMax: "Максимум повторов",
      statusOpen: "Открыт",
      statusResolved: "Закрыт",
      statusSkipped: "Пропущен",
      allStatus: "Любой статус",
      confidenceUnsure: "Неуверенно",
      confidenceProbableHome: "Вероятно домашний",
      confidenceHighHome: "Точно домашний",
      allConfidence: "Любая уверенность",
      reasonUnsure: "Недостаточно сигналов",
      reasonProbableHome: "Вероятный домашний доступ",
      reasonHomeRequiresReview: "Домашний доступ требует проверки",
      reasonManualMixedHome: "Смешанный домашний кейс",
      reasonProviderConflict: "Конфликт провайдера",
      allReasons: "Все причины",
      severityCritical: "Критично",
      severityHigh: "Высокий",
      severityMedium: "Средний",
      severityLow: "Низкий",
      allSeverity: "Любая срочность",
      punitiveAny: "Любой статус ограничений",
      punitiveOnly: "Только с ограничением",
      reviewOnly: "Только ручное ревью",
      sortPriorityDesc: "Сначала высокий приоритет",
      sortPriorityAsc: "Сначала низкий приоритет",
      sortActivityDesc: "Сначала длинная активность",
      sortActivityAsc: "Сначала короткая активность",
      sortUpdatedDesc: "Сначала новые",
      sortScoreDesc: "Сначала высокий балл",
      sortRepeatDesc: "Сначала частые повторы",
      sortUpdatedAsc: "Сначала старые",
      sortLabel: "Сортировка",
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
      system: "Системный ID",
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
      mobile: "Мобильный",
      home: "Домашний",
      skip: "Пропустить",
      openCase: "Открыть кейс",
      openEvents: "Консоль",
      bulkMobile: "Пометить как мобильные",
      bulkHome: "Пометить как домашние",
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
      probable_home: "Вероятный домашний доступ",
      home_requires_review: "Домашний доступ требует проверки",
      manual_review_mixed_home: "Смешанный домашний кейс",
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
      "Фильтрация по решению, модулю, провайдеру, источнику и состоянию применения.",
    listTitle: "Автоматические решения",
    listDescription: "Последние решения",
    empty: "Для текущих фильтров автоматических решений нет",
    filters: {
      search: "Поиск по IP / провайдеру / инбаунду / устройству / ID / логину",
      moduleId: "ID модуля",
      provider: "Провайдер",
      anyVerdict: "Любой вердикт",
      anySource: "Любой источник",
      anyEnforcement: "Любое применение",
    },
    meta: {
      module: "Модуль {value}",
      inbound: "Инбаунд {value}",
      provider: "Провайдер {value}",
      source: "Источник {value}",
      scope: "Контекст {value}",
      enforcement: "Применение {value}",
    },
    sources: {
      rule_engine: "Правила детекта",
      cache: "Кэш",
      manual_override: "Ручное переопределение",
    },
    enforcement: {
      none: "Без удалённого применения",
      attempts: "попыток {count}",
      status: {
        pending: "Ожидает",
        applied: "Применено",
        failed: "Ошибка",
      },
      jobType: {
        access_state: "Переключение доступа",
        traffic_cap: "Ограничение трафика",
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
    restart: "Перезапустить модуль",
    createTitle: "Создание карточки модуля",
    createDescription:
      "Укажите отображаемое имя и INBOUND-теги для этого модуля. После сохранения панель сгенерирует module_id и API-токен.",
    detailsTitle: "Детали модуля",
    detailsDescription:
      "Редактируйте имя модуля и INBOUND-теги. Обновлённые теги придут в сборщик через удалённую конфигурацию без изменения сценария установки.",
    createSuccess: "Модуль создан",
    updateSuccess: "Модуль обновлён",
    restartSuccess: "Команда перезапуска отправлена модулю",
    restartFailed: "Не удалось отправить команду перезапуска",
    saveFailed: "Не удалось сохранить модуль",
    pendingInstall: "ожидает установку",
    stale: "устарел",
    freshnessTitle: "Пульс модуля",
    freshnessHint:
      "Модуль считается устаревшим, если сигнал активности не приходит дольше {value}.",
    lastHeartbeatAge: "Возраст последнего сигнала",
    staleWindow: "Окно устаревания",
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
    accessLogExists: "Файл журнала доступа найден",
    healthEmpty:
      "Создайте или откройте модуль, чтобы увидеть его текущее состояние.",
    installTitle: "Установка модуля",
    installDescription:
      "Скопируйте сгенерированный compose, раскройте токен и при необходимости измените `ACCESS_LOG_PATH` локально, если у ноды нестандартный путь к логу.",
    installPreviewEmpty:
      "Создайте или откройте модуль, чтобы увидеть сгенерированный `docker-compose.yml`.",
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
    copyCompose: "Скопировать compose-файл",
    composeCopied: "`docker-compose.yml` скопирован в буфер",
    copyFailed: "Не удалось скопировать в буфер",
    installSteps: {
      clone:
        "Склонируйте репозиторий модуля на целевую ноду и откройте его корень.",
      compose: "Замените локальный docker-compose.yml на compose preview ниже.",
      token:
        "Раскройте токен в панели и замените `MODULE_TOKEN=__PASTE_TOKEN__` перед запуском",
      start:
        "Запустите `docker compose up -d && docker compose logs -f` и дождитесь перехода модуля в состояние «онлайн».",
    },
    health: {
      ok: "Норма",
      warn: "Предупреждение",
      error: "Ошибка",
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
      failedQueue: "Ошибки очереди",
    },
    pipelineTitle: "Конвейер приёма данных",
    pipelineDescription:
      "Нагрузка очереди и статус фоновых воркеров для общего конвейера на SQLite.",
    pipeline: {
      queueDepth: "Глубина очереди",
      pendingRemote: "Ожидают удалённые задачи",
      lag: "Текущий лаг",
      lastDrain: "Последний полный проход",
      snapshotAge: "Возраст снимка {value}",
      snapshotAgeLabel: "Свежесть снимка",
      stale: "снимок устарел",
    },
  },
  reviewDetail: {
    eyebrow: "Детали кейса",
    title: "Кейс ревью #{caseId}",
    description:
      "Сигналы, связанная история и закреплённая зона решения для быстрой модерации.",
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
      systemId: "Системный ID",
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
      reviewUrl: "Ссылка на ревью",
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
      mobile: "Пометить как мобильный доступ",
      home: "Пометить как домашний доступ",
      skip: "Пропустить",
      saved: "Решение по кейсу сохранено",
    },
    summaryHint:
      "Быстрые идентификаторы и контекст ревью без перехода к сырому payload.",
    resolutionHint:
      "Эта заметка попадёт в audit trail вместе с решением для IP {ip}.",
    copyIp: "Скопировать IP",
    copyUuid: "Скопировать UUID",
    copyTelegram: "Скопировать Telegram ID",
    openReviewUrl: "Открыть ссылку на ревью",
    providerEvidence: {
      conflict: "Конфликт маркеров сервиса",
      clear: "Прямого конфликта маркеров нет",
      reviewFirst: "Нужна ручная проверка перед действием",
      autoReady: "Сигналов уже хватает для автоматики",
      homeSources: "Поддерживающие HOME-источники",
      mobileSources: "Поддерживающие MOBILE-источники",
      matchedAliases: "Совпавшие алиасы",
      mobileMarkers: "Совпавшие мобильные маркеры",
      homeMarkers: "Совпавшие домашние маркеры",
    },
    sharedAccess: {
      signals: "Сигналы: {value}",
    },
    usageProfile: {
      empty: "Данных по профилю использования пока нет",
      summary: "Снапшот",
      counts: "Счётчики",
      countsValue:
        "IP {ips} · Провайдеры {providers} · Устройства {devices} · Модули {modules}",
      devices: "Устройства",
      deviceInventoryNote:
        "Если доступен HWID-инвентарь Remnawave, он уже подмешан в этот список.",
      osFamilies: "Семейства ОС",
      nodes: "Распределение по нодам",
      softReasons: "Мягкие причины",
      geo: "Геоистория",
      travel: "Аномалии перемещения",
      countryJumpOnly: "только скачок по стране",
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
      home_requires_review: "Домашний доступ требует проверки",
      manual_review_mixed_home: "Смешанный домашний кейс",
    },
    ipInventory: {
      summary: "{count} срабатываний · {isp} · AS{asn}",
      observedInterval: "Наблюдаемый интервал {value}",
      firstSeen: "Первое появление {value}",
      lastSeen: "Последнее появление {value}",
    },
    moduleInventory: {
      moduleId: "ID модуля {value}",
      firstSeen: "Первое появление {value}",
      lastSeen: "Последнее появление {value}",
    },
  },
  rules: {
    eyebrow: "Живые правила",
    title: "Правила",
    saveRules: "Сохранить правила",
    rulesUpdated: "Правила обновлены",
    generalSaved: "Общие настройки сохранены",
    policySaved: "Политика детекта сохранена",
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
    automationControls: {
      title: "Режим работы",
      description:
        "Понятные верхнеуровневые переключатели для наблюдения, реакции и эскалации.",
      save: "Сохранить переключатели",
      saved: "Переключатели автоматизации сохранены",
      workMode: {
        label: "Режим работы",
        description:
          "Наблюдение не применяет жёсткие действия, реакция включает полноценную обработку.",
        observe: "Наблюдение",
        react: "Реакция",
      },
      reactionMode: {
        label: "Реакция",
        description:
          "Определяет, будут ли нарушения ограничиваться предупреждениями или повышаться до ограничений.",
        enforce: "Ограничения",
        warningOnly: "Только предупреждения",
      },
    },
    sectionTitles: {
      thresholds: "Калибровка, скоринг и поведение",
      policy: "Политика детекта",
      learning: "Контроль обучения",
      aiOptimizer: "AI Оптимизатор порогов",
      retention: "Сроки хранения данных",
    },
    sectionDescriptions: {
      general:
        "Общие параметры эскалации, предупреждений и переключения доступа в отдельной вкладке.",
      thresholds:
        "Пороговые значения, веса скоринга, лимитер и поведение в одном месте.",
      lists:
        "Списки ASN и ключевых слов, формирующие первичные сигналы и исключения.",
      providers:
        "Алиасы, маркеры и подсказки по операторам для сценариев с ручной проверкой.",
      policy:
        "Живая логика детекта и настройки применения ограничений.",
      learning: "Пороги, при которых обучение начинает считаться надёжным.",
      aiOptimizer:
        "Интеллектуальная оптимизация пороговых настроек на основе анализа логов трафика с помощью Gemini LLM.",
      aiSuggestions:
        "Предложения ИИ Gemini по классификации неопределенных/спорных сетей и исправлению ошибок модераторов.",
      retention:
        "Периоды хранения, которые ограничивают рост SQLite, не удаляя активные кейсы ревью.",
    },
    providerProfiles: {
      description:
        "Профили операторов с алиасами и маркерами услуг для осторожного скоринга с ручной проверкой.",
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
            "Стабильный идентификатор для меток обучения и метрик качества.",
        },
        classification: {
          label: "Классификация",
          description:
            "Смешанные профили остаются в режиме ручной проверки, пока их не подтвердит второй независимый фактор.",
        },
        aliases: {
          label: "Алиасы",
          description:
            "Имена оператора, бренды, PTR-фрагменты и алиасы организации для поиска в ISP и hostname.",
        },
        mobile_markers: {
          label: "Мобильные маркеры услуг",
          description:
            "Маркеры услуг, указывающие на мобильную сторону оператора.",
        },
        home_markers: {
          label: "Домашние маркеры услуг",
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
      modeReasonsLabel: "Почему активен именно этот режим",
      guardrailsLabel: "Какие ограничители включены",
      noModeReasons: "Флагов, ограничивающих режим, нет",
      noGuardrails: "Дополнительные ограничители не активны",
    },
    aiOptimizer: {
      title: "Генеративный AI-оптимизатор правил",
      unconfiguredTitle: "Ключ Gemini API не настроен",
      unconfiguredDesc: "Для использования генеративной оптимизации правил вам необходимо указать ключ Gemini API в разделе настроек системы.",
      goToSettings: "Перейти к настройкам системы",
      generateButton: "Сгенерировать AI-рекомендации",
      generating: "Анализируем лог трафика и генерируем рекомендации через Gemini...",
      status: {
        lastRun: "Последнее обновление: {value}",
        neverRun: "Никогда",
        cooldownActive: "Доступно через"
      },
      overallSummary: "Общее заключение AI",
      recommendationsTitle: "Рекомендованные изменения",
      fieldLabel: "Настройка",
      currentValue: "Текущее",
      proposedValue: "Рекомендуемое",
      impact: "Эффект",
      reason: "Обоснование",
      accept: "Принять",
      reject: "Отклонить",
      edit: "Редактировать",
      saveChangesHint: "Рекомендации применены к черновику. Не забудьте нажать «Сохранить правила» для их окончательной записи.",
      estimatedFpReduction: "Снижение ложноположительных срабатываний на {value}%",
      noSuggestions: "Модель не обнаружила проблем в текущих правилах на основе суточной статистики."
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
      dry_run: "режим dry-run не даёт выполнять удалённые действия",
      shadow_mode: "теневой режим блокирует жёсткие действия",
      warning_only_mode: "эскалация ограничена предупреждениями",
      limiter_observe: "limiter работает в режиме наблюдения",
      limiter_warning_only: "limiter разрешает только предупреждения",
      limiter_enforce: "limiter разрешает автоматические ограничения",
    },
    flags: {
      auto_enforce_requires_hard_or_multi_signal:
        "Для авто-применения нужен сильный или многосигнальный признак",
      provider_conflict_review_only:
        "Конфликты смешанных провайдеров остаются только в ручной проверке",
      manual_review_mixed_home_enabled:
        "Смешанные домашние кейсы требуют ручной проверки",
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
      "Поддерживается многострочный текст и HTML-теги (<b>, <code>, <i>).\n\nОсновные плейсхолдеры:\n• {{username}}, {{uuid}}, {{system_id}}, {{telegram_id}}\n• {{ip}}, {{isp}}, {{tag}}, {{confidence_band}}, {{review_url}}\n• {{risk_title}}, {{warning_count}}, {{warnings_left}}, {{ban_minutes}}, {{ban_text}}\n\nПлейсхолдеры профиля использования:\n• {{usage_profile_summary}} (статистика по IP, провайдерам, нодам, ГЕО)\n• {{usage_profile_soft_reasons}} (активные флаги нарушений на русском)\n• {{usage_profile_ip_count}}, {{usage_profile_provider_count}}, {{usage_profile_node_count}}, {{usage_profile_device_count}}, {{usage_profile_os_count}}, {{usage_profile_country_count}}\n• {{usage_profile_top_ips}}, {{usage_profile_top_providers}}, {{usage_profile_countries}}\n• {{usage_profile_ongoing_duration_text}}, {{usage_profile_geo_country_jump}}, {{usage_profile_geo_impossible_travel}}\n• {{usage_profile_event_count}}, {{usage_profile_exact_device_count}}, {{usage_profile_hwid_device_limit}}, {{usage_profile_hwid_device_count_exact}}\n• {{usage_profile_device_labels}}, {{usage_profile_nodes}}, {{usage_profile_traffic_burst_bytes}}, {{usage_profile_traffic_burst_window}}.",
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
    integrationTitle: "Интеграции",
    integrationDescription:
      "Серверные подключения, которые используются для live-метрик и lookup пользователей.",
    integrationSaved: "Параметры интеграции обновлены",
    saveIntegration: "Сохранить интеграции",
    brandingFields: {
      serviceName: "Название сервиса",
      serviceNameDescription:
        "Видимое название сервиса в панели и на экране входа.",
      logoUrl: "URL логотипа",
      logoUrlDescription:
        "Публичный URL изображения логотипа. Оставьте пустым, чтобы использовать встроенный логотип по умолчанию.",
      logoUrlPlaceholder: "https://example.com/logo.png",
    },
    integrationFields: {
      remnawaveApiUrl: "URL Remnawave API",
      remnawaveApiUrlDescription:
        "Базовый URL Remnawave для online-метрик нод и lookup пользователей (допустимы варианты с /api и без).",
      remnawaveApiUrlPlaceholder: "https://panel.example.com",
      bedolagaApiUrl: "URL Bedolaga API",
      bedolagaApiUrlDescription: "Базовый URL сервиса Bedolaga для интеграции.",
      bedolagaApiToken: "Токен Bedolaga API",
      bedolagaApiTokenDescription: "Секретный токен для авторизации запросов в Bedolaga.",
      bedolagaTimeout: "Таймаут Bedolaga (сек)",
      bedolagaTimeoutDescription: "Максимальное время ожидания ответа от Bedolaga.",
      geminiApiKey: "Ключ Gemini API",
      geminiApiKeyDescription: "Секретный API-ключ от Google AI Studio для работы ИИ-оптимизатора правил.",
      geminiModelName: "Модель Gemini",
      geminiModelNameDescription: "Идентификатор модели ИИ, используемой для генерации (например, gemini-1.5-flash).",
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
    ownerSecurity: {
      title: "Безопасность владельцев",
      description:
        "Серверное состояние TOTP для владельцев. Отключение снимает проверку сразу для всех учётных записей владельца.",
      enabled: "OTP включён",
      disabled: "OTP отключён",
      statusLabel: "Статус одноразовых кодов",
      ownerCountLabel: "Учётных записей владельца",
      enabledCountLabel: "С включённым TOTP",
      pendingLabel: "Ожидают подтверждения",
      disableAction: "Отключить OTP для всех владельцев",
      disabling: "Отключаю…",
      disableSaved: "OTP для всех владельцев отключён",
    },
  },
  data: {
    eyebrow: "Данные",
    title: "Данные",
    sectionDescriptions: {
      console:
        "Единая операторская консоль с системными логами панели, heartbeat модулей и входящими данными от модулей.",
      users:
        "Основной поток для поиска пользователя, разбора карточки, ограничений, исключений и экспортных снимков.",
      aiSuggestions:
        "Предложения ИИ Gemini по классификации неопределенных/спорных сетей и исправлению ошибок модераторов.",
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
      suggestionAccepted: "Рекомендация ИИ успешно принята. Спорные кейсы отправлены на перепроверку с высоким приоритетом.",
      suggestionRejected: "Рекомендация ИИ отклонена.",
      cacheUpdated: "Запись кэша обновлена",
      learningUpdated: "Данные обучения обновлены",
      exportReady: "Экспортная карточка готова",
      exportDownloaded: "Экспортная карточка скачана",
      calibrationExportReady: "Архив калибровки сформирован",
    },
    aiSuggestions: {
      pageTitle: "Рекомендации ИИ по обучению",
      pageDescription: "Предложения ИИ Gemini по классификации неопределенных/спорных сетей и исправлению ошибок модераторов.",
      emptyTitle: "Рекомендации ИИ",
      empty: "Нет активных рекомендаций ИИ.",
      status: {
        lastRun: "Последнее обновление: {value}",
        neverRun: "Никогда",
        cooldownActive: "Доступно через",
        generating: "Аудит ИИ в процессе...",
        generateButton: "Обновить рекомендации"
      },
      loading: "Загрузка рекомендаций...",
      confidence: "Уверенность ИИ: {value}%",
      patternType: "Тип",
      patternValue: "Паттерн",
      decision: "Решение",
      suggestedDecision: "Рекомендуемое решение",
      currentDecision: "Текущее решение",
      reasoning: "Обоснование ИИ",
      operatorErrors: "Ошибки операторов",
      operatorErrorsDetail: "Найдено подозрений на ошибки в {count} кейсах",
      recheckReason: "Кейс #{id} отправлен на перепроверку",
      operatorProfile: "Рекомендуемый профиль оператора",
      profileKey: "Идентификатор (key)",
      profileClassification: "Классификация",
      profileAliases: "Ключевые слова (aliases)",
      profileMarkers: "Маркеры услуг",
      profileAsns: "Автономные системы (ASNs)",
      profileActionUpdate: "Обновление профиля",
      profileActionCreate: "Новый профиль",
      actions: {
        accept: "Принять",
        reject: "Отклонить",
        accepting: "Применение...",
        rejecting: "Отклонение..."
      }
    },
    users: {
      pageTitle: "Поиск пользователя",
      searchPlaceholder: "Поиск по UUID / system ID / Telegram ID / имени пользователя",
      search: "Искать",
      searching: "Ищу…",
      panelMatch: "Совпадение в панели: {value}",
      systemLabel: "sys:{value}",
      telegramLabel: "tg:{value}",
      cardTitle: "Карточка пользователя",
      exportHint:
        "Соберите структурированную экспортную карточку для калибровки или ручного разбора.",
      buildExport: "Собрать экспортную карточку",
      generatingExport: "Генерирую…",
      downloadExport: "Скачать JSON",
      exportPreviewTitle: "Предпросмотр экспортной карточки",
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
      usageProfileCountryJumpOnly: "только скачок по стране",
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
        identity: "Идентификаторы",
        flags: "Флаги",
        panel: "Данные панели",
        reviewCases: "Кейсы ревью",
        analysisEvents: "События анализа",
        history: "История",
        activeTrackers: "Активные трекеры",
        ipHistory: "История IP",
      },
      fields: {
        username: "Имя пользователя",
        uuid: "UUID",
        systemId: "Системный ID",
        telegramId: "Telegram ID",
        panelStatus: "Статус в панели",
        panelSquads: "Активные группы",
        trafficLimitBytes: "Лимит трафика",
        trafficLimitStrategy: "Стратегия лимита",
        usedTrafficBytes: "Текущий потраченный трафик",
        lifetimeUsedTrafficBytes: "Трафик за всё время",
        exemptSystemId: "Исключённый системный ID",
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
      promotedActiveTitle: "Активные продвинутые паттерны",
      promotedStatsTitle: "Статистика продвинутых паттернов",
      legacyTitle: "Наследуемое обучение",
      providerActiveTitle: "Продвинутые паттерны провайдеров",
      providerServiceActiveTitle: "Продвинутые сервисные паттерны провайдеров",
      providerLegacyTitle: "Наследуемые паттерны провайдеров",
      empty: "Обучение по провайдерам пока пусто",
      support: "поддержка {value}",
      precision: "точность {value}",
      total: "всего {value}",
      confidence: "уверенность {value}",
      plusOneConfidence: "+1 к уверенности",
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
        "Датасет пока непригоден для надёжной калибровки по провайдерам",
      tuningReady: "По этой выгрузке уже можно начинать настройку по провайдерам",
      tuningNotReady: "Настройка по провайдерам пока заблокирована покрытием или поддержкой",
      blockersTitle: "Блокеры readiness",
      noBlockers: "Критичных blockers сейчас нет",
      checksTitle: "Текущие readiness checks",
      warningsTitle: "Предупреждения readiness-проверки",
      notReadyToast:
        "Калибровочный архив сформирован, но проверки готовности не пройдены",
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
        resolvedOnly: "Только закрытые",
        openOnly: "Только открытые",
        all: "Все кейсы",
      },
      cards: {
        overallReadiness: "Общая готовность",
        datasetReadiness: "Готовность датасета",
        tuningReadiness: "Готовность настройки",
        file: "Архив",
        rawRows: "Сырые строки",
        knownRows: "Размеченные строки",
        unknownRows: "Неразмеченные строки",
        providerProfiles: "Профили провайдеров",
        providerCoverage: "Покрытие ключей провайдеров",
        patternCandidates: "Кандидаты в паттерны провайдеров",
      },
      readiness: {
        checks: {
          provider_profiles_present: "Профили провайдеров в снимке",
          resolved_ratio: "Доля закрытых кейсов",
          provider_evidence_coverage: "Покрытие объяснимости провайдера",
          provider_key_coverage: "Покрытие ключей провайдеров",
          min_provider_support: "Минимальная поддержка по провайдерам",
        },
      },
      warnings: {
        live_rules_stale_or_unseeded:
          "Снимок живых правил был пуст и был объединён с runtime-конфигом.",
        provider_profiles_missing: "В снимке выгрузки нет профилей провайдеров.",
        provider_key_coverage_zero: "В закрытых строках вообще нет ключей провайдеров.",
        provider_explainability_missing:
          "В экспортированных строках отсутствует объяснимость по провайдерам.",
        resolved_ratio_below_threshold:
          "Слишком много ожидающих строк: доля закрытых кейсов ниже безопасного порога.",
        provider_key_coverage_below_target:
          "Покрытие ключей провайдеров ниже целевого порога 0.6.",
        provider_support_below_target:
          "Хотя бы один кандидат по провайдеру или сервису провайдера имеет меньше 5 известных закрытых кейсов.",
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
      asnLists: "Списки ASN",
      keywords: "Ключевые слова",
      providers: "Профили операторов",
      thresholds: "Пороги",
      scores: "Баллы",
      behavior: "Поведение",
      policy: "Политика",
      learning: "Обучение",
      retention: "Хранение",
    },
    listFields: {
      admin_tg_ids: {
        label: "Telegram ID владельцев",
        description:
          "Telegram IDs, которым назначена owner-роль с полным доступом к платформе.",
        recommendation:
          "Держите этот список коротким и максимально доверенным.",
      },
      moderator_tg_ids: {
        label: "Telegram ID модераторов",
        description:
          "Telegram IDs, которым разрешены queue resolution, recheck и data-admin мутации без доступа к platform settings.",
        recommendation:
          "Используйте для операторов ручной модерации и runtime-коррекций.",
      },
      viewer_tg_ids: {
        label: "Telegram ID наблюдателей",
        description:
          "Telegram IDs для read-only доступа к overview, quality, modules, queue, data и audit.",
        recommendation:
          "Подходит для аналитиков и поддержки, которым не нужно менять состояние.",
      },
      exempt_ids: {
        label: "Исключённые системные ID",
        description:
          "Системные user.id, исключенные из анализа и авто-ограничений.",
        recommendation: "Добавляйте только служебные или доверенные аккаунты.",
      },
      exempt_tg_ids: {
        label: "Исключённые Telegram ID",
        description: "Telegram ID, исключенные из анализа и авто-ограничений.",
        recommendation:
          "Используйте, если удобнее администрировать исключения по Telegram ID.",
      },
      pure_mobile_asns: {
        label: "Список чисто мобильных ASN",
        description:
          "ASN, которые почти всегда считаются мобильными и дают сильный mobile-сигнал.",
        recommendation:
          "Добавляйте ASN только после подтверждённой чистой мобильной выборки.",
      },
      pure_home_asns: {
        label: "Список чисто домашних ASN",
        description:
          "ASN, которые почти всегда считаются домашними и дают сильный home-сигнал.",
        recommendation:
          "Сюда должны попадать только стабильно домашние ASN без мобильной примеси.",
      },
      mixed_asns: {
        label: "Список смешанных ASN",
        description:
          "ASN со смешанным профилем, где нужны дополнительные признаки и осторожность.",
        recommendation:
          "Используйте для спорных ASN, где одного ASN недостаточно для вердикта.",
      },
      allowed_isp_keywords: {
        label: "Ключевые слова мобильного доступа",
        description:
          "Ключевые слова, усиливающие mobile-версию при совпадении в ISP/hostname.",
        recommendation:
          "Держите здесь короткие устойчивые mobile-маркеры, без широких слов.",
      },
      home_isp_keywords: {
        label: "Ключевые слова домашнего доступа",
        description: "Ключевые слова, которые тянут решение в сторону home.",
        recommendation:
          "Добавляйте только маркеры фиксированных/домашних провайдеров.",
      },
      exclude_isp_keywords: {
        label: "Ключевые слова дата-центров и хостинга",
        description:
          "Ключевые слова для детекта хостинга, датацентров и инфраструктурных сетей.",
        recommendation:
          "Держите список консервативным, чтобы не ловить обычных провайдеров.",
      },
    },
    settingFields: {
      threshold_mobile: {
        label: "Порог решения для мобильного доступа",
        description:
          "Балловый порог, начиная с которого кейс считается уверенно мобильным.",
        recommendation: "Базовое безопасное значение: около 60.",
      },
      threshold_probable_mobile: {
        label: "Порог вероятно мобильного доступа",
        description:
          "Порог для промежуточного мобильного сигнала до финального решения.",
        recommendation: "Обычно держат ниже основного порога мобильного доступа.",
      },
      threshold_home: {
        label: "Порог решения для домашнего доступа",
        description:
          "Нижний балловый порог, после которого кейс считается уверенно домашним.",
        recommendation: "Чем выше значение, тем осторожнее будут home-решения.",
      },
      threshold_probable_home: {
        label: "Порог вероятно домашнего доступа",
        description:
          "Порог для промежуточного домашнего сигнала до финального решения.",
        recommendation: "Держите между порогом домашнего доступа и нейтральной зоной.",
      },
      pure_asn_score: {
        label: "Бонус за чисто мобильный ASN",
        description: "Бонус к баллу, если ASN найден в списке чисто мобильных.",
        recommendation:
          "Обычно это сильный бонус, сопоставимый с порогом мобильного доступа.",
      },
      mixed_asn_score: {
        label: "Бонус за смешанный ASN",
        description:
          "Бонус к баллу для смешанного ASN до учёта дополнительных признаков.",
        recommendation: "Держите заметно ниже бонуса за чисто мобильный ASN.",
      },
      ptr_home_penalty: {
        label: "Штраф за домашние ключевые слова",
        description: "Штраф за домашние ключевые слова в ISP или hostname.",
        recommendation:
          "Небольшой минус, чтобы ключевое слово не перевешивало жёсткие сигналы.",
      },
      mobile_kw_bonus: {
        label: "Бонус за мобильные ключевые слова",
        description: "Бонус за мобильные ключевые слова в ISP или hostname.",
        recommendation:
          "Делайте меньше бонуса за чисто мобильный ASN, но достаточно значимым.",
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
        label: "Бонус за подтверждение через ip-api",
        description:
          "Дополнительный бонус, если резервная проверка через ip-api подтверждает мобильную сеть.",
        recommendation:
          "Используйте только как добивающий сигнал для mixed ASN.",
      },
      pure_home_asn_penalty: {
        label: "Штраф за чисто домашний ASN",
        description: "Штраф, если ASN попадает в список чисто домашних.",
        recommendation: "Обычно это сильный штраф для уверенного домашнего доступа.",
      },
      score_subnet_mobile_bonus: {
        label: "Бонус за мобильную историю подсети",
        description: "Бонус за исторические мобильные сигналы в той же подсети.",
        recommendation:
          "Делайте его умеренным, чтобы не переобучать редкие подсети.",
      },
      score_subnet_home_penalty: {
        label: "Штраф за домашнюю историю подсети",
        description: "Штраф за исторические домашние сигналы в подсети.",
        recommendation:
          "Подходит как корректирующий, а не доминирующий сигнал.",
      },
      score_churn_high_bonus: {
        label: "Сильный бонус за churn",
        description: "Бонус за очень высокую сменяемость IP/сессий.",
        recommendation: "Используйте как сильный поведенческий mobile-признак.",
      },
      score_churn_medium_bonus: {
        label: "Средний бонус за churn",
        description: "Бонус за умеренную сменяемость IP/сессий.",
        recommendation: "Делайте заметно ниже high churn bonus.",
      },
      score_stationary_penalty: {
        label: "Штраф за стационарность",
        description: "Штраф за слишком долгую неподвижность поведения пользователя.",
        recommendation: "Обычно это мягкий штраф, а не жёсткая блокировка.",
      },
      concurrency_threshold: {
        label: "Порог одновременности",
        description:
          "Сколько одновременных пользователей на IP считать признаком мобильности.",
        recommendation: "Стартовая точка: 2–3.",
      },
      churn_window_hours: {
        label: "Окно churn (часы)",
        description: "Окно в часах для расчёта churn и сменяемости IP.",
        recommendation:
          "Чем меньше окно, тем чувствительнее реакция на всплески.",
      },
      churn_mobile_threshold: {
        label: "Порог churn для мобильного сигнала",
        description: "Сколько смен IP считать поведенческим признаком мобильного доступа.",
        recommendation: "Подбирайте по реальным паттернам мобильного доступа без перегиба.",
      },
      lifetime_stationary_hours: {
        label: "Порог стационарности (часы)",
        description:
          "После какой длительности одна и та же сессия начинает выглядеть слишком домашней.",
        recommendation: "Увеличивайте, если боитесь ложных срабатываний на домашний доступ.",
      },
      subnet_mobile_ttl_days: {
        label: "TTL мобильной истории подсети (дни)",
        description: "Сколько дней хранить мобильную историю по подсетям.",
        recommendation:
          "Более длинный TTL повышает память системы, но и риск устаревания.",
      },
      subnet_home_ttl_days: {
        label: "TTL домашней истории подсети (дни)",
        description: "Сколько дней хранить домашнюю историю по подсетям.",
        recommendation: "Обычно меньше TTL мобильной истории, чтобы быстрее забывать шум.",
      },
      subnet_mobile_min_evidence: {
        label: "Минимум мобильных подтверждений по подсети",
        description:
          "Минимум мобильных подтверждений до включения бонуса по подсети.",
        recommendation: "Повышайте, если подсетей много и они шумные.",
      },
      subnet_home_min_evidence: {
        label: "Минимум домашних подтверждений по подсети",
        description:
          "Минимум домашних подтверждений до включения штрафа по подсети.",
        recommendation: "Обычно требует больше подтверждений, чем мобильный сигнал.",
      },
      shadow_mode: {
        label: "Теневой режим",
        description:
          "Если включено, система анализирует и пишет кейсы, но не применяет ограничения доступа.",
        recommendation: "Новый запуск безопаснее начинать с включённого режима.",
      },
      probable_home_warning_only: {
        label: "Probable HOME: только предупреждение",
        description:
          "Для кейсов с вердиктом Probable HOME система ограничивается предупреждением и не применяет ограничения доступа.",
        recommendation:
          "Рекомендуется держать включённым для осторожного режима.",
      },
      auto_enforce_requires_hard_or_multi_signal: {
        label: "Авто-применение только при сильном сигнале",
        description:
          "Автоматически применять ограничения только если HOME подтверждён сильным сигналом или несколькими независимыми признаками.",
        recommendation: "Безопаснее оставлять включённым.",
      },
      provider_conflict_review_only: {
        label: "Конфликты mixed-провайдеров только через review",
        description:
          "Если источники и маркеры провайдера конфликтуют, блокировать авто-решение и отправлять кейс в review.",
        recommendation:
          "Рекомендуется для review-first rollout по неоднозначным операторам.",
      },
      review_ui_base_url: {
        label: "Базовый URL панели review",
        description:
          "Адрес панели, который используется для ссылок на кейсы и review-страницы.",
        recommendation: "Укажите боевой HTTPS URL панели.",
      },
      live_rules_refresh_seconds: {
        label: "Интервал обновления live rules",
        description: "Как часто runtime проверяет и подхватывает изменения live rules.",
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
        label: "Хранение сигналов модулей (дни)",
        description:
          "Сколько дней хранить исторические сигналы модулей перед очисткой.",
        recommendation:
          "Держите коротко: актуальное состояние модуля и так хранится в таблице модулей.",
      },
      ingested_raw_events_retention_days: {
        label: "Хранение сырых входящих событий (дни)",
        description:
          "Сколько дней хранить события модулей после того, как они перестают быть нужны для обычной работы.",
        recommendation:
          "30 дней обычно достаточно, если вам не нужны длинные окна повторной подачи событий.",
      },
      ip_history_retention_days: {
        label: "Хранение истории IP (дни)",
        description:
          "Сколько дней сохранять поведенческую историю IP для churn и long-window анализа.",
        recommendation:
          "Согласуйте это значение с самым длинным окном скоринга на основе истории, которому вы реально доверяете.",
      },
      orphan_analysis_events_retention_days: {
        label: "Хранение осиротевших событий анализа (дни)",
        description:
          "Сколько дней хранить события анализа, на которые больше не ссылается ни один кейс ревью.",
        recommendation:
          "Короткое окно заметно ограничивает рост базы, сохраняя недавний операторский контекст.",
      },
      resolved_review_retention_days: {
        label: "Хранение закрытых кейсов ревью (дни)",
        description:
          "Сколько дней хранить закрытые и пропущенные кейсы, а также связанную историю аудита.",
        recommendation:
          "Здесь держите длинное audit-окно; активные OPEN-кейсы эта настройка не удаляет.",
      },
      learning_promote_asn_min_support: {
        label: "Минимальная поддержка продвинутого ASN",
        description:
          "Минимум подтверждённых кейсов, чтобы ASN попал в продвинутое обучение.",
        recommendation: "Повышайте, если боитесь раннего переобучения.",
      },
      learning_promote_asn_min_precision: {
        label: "Минимальная точность продвинутого ASN",
        description: "Минимальная точность для продвинутого ASN-паттерна.",
        recommendation: "Консервативный режим обычно начинается около 0.95.",
      },
      learning_promote_combo_min_support: {
        label: "Минимальная поддержка продвинутой комбинации",
        description: "Минимум кейсов для продвинутого комбинированного паттерна.",
        recommendation: "Обычно ниже поддержки ASN, но не слишком низко.",
      },
      learning_promote_combo_min_precision: {
        label: "Минимальная точность продвинутой комбинации",
        description: "Минимальная точность для комбинированного паттерна.",
        recommendation: "Держите высокой, чтобы комбинации не давали шумных бонусов.",
      },
    },
    rulesGeneralFields: {
      usage_time_threshold: {
        label: "Минимальная длительность подозрительного использования (сек)",
        description:
          "Как долго подозрительная сессия должна оставаться активной до начала ограничений доступа.",
      },
      warning_timeout_seconds: {
        label: "Пауза между предупреждениями (сек)",
        description: "Минимальная задержка перед следующим предупреждением.",
      },
      warnings_before_ban: {
        label: "Предупреждений до первого ограничения",
        description:
          "Сколько предупреждений нужно до первого ограничения доступа.",
      },
      warning_only_mode: {
        label: "Режим только предупреждений",
        description:
          "Никогда не применять ограничения доступа автоматически.",
      },
      manual_review_mixed_home_enabled: {
        label: "Смешанные домашние кейсы только вручную",
        description:
          "Если итог остаётся HOME, но сам паттерн выглядит смешанным, всё равно требовать ручную проверку.",
      },
      manual_ban_approval_enabled: {
        label: "Требовать одобрение ограничения",
        description:
          "Останавливать применение ограничения до ручного одобрения админом.",
      },
      dry_run: {
        label: "Пробный режим",
        description:
          "Анализировать и уведомлять без удалённого переключения групп доступа.",
      },
      ban_durations_minutes: {
        label: "Лестница ограничений (минуты)",
        description:
          "Одно значение на строку: первое ограничение, второе, третье и так далее.",
      },
      full_access_squad_name: {
        label: "Имя группы полного доступа",
        description:
          "Точное имя внутренней группы Remnawave, которая означает полный доступ.",
      },
      restricted_access_squad_name: {
        label: "Имя группы ограничения",
        description:
          "Точное имя внутренней группы Remnawave, которая выдаётся при нарушении.",
      },
      traffic_cap_increment_gb: {
        label: "Прирост лимита трафика (ГБ)",
        description:
          "На сколько гигабайт увеличить лимит относительно уже израсходованного трафика.",
      },
      traffic_cap_threshold_gb: {
        label: "Порог лимита трафика (ГБ)",
        description:
          "Если пользователь уже израсходовал не меньше этого объёма, вместо скрытия мобильных конфигов применяется лимит трафика.",
      },
      limiter_enabled: {
        label: "Включить limiter",
        description: "Включает пороги/окно/cooldown/ignore для enforcement.",
      },
      limiter_threshold_count: {
        label: "Порог limiter",
        description: "Сколько нарушений в окне нужно до срабатывания limiter.",
      },
      limiter_window_seconds: {
        label: "Окно limiter (сек)",
        description: "Скользящее окно для подсчёта нарушений limiter.",
      },
      limiter_cooldown_seconds: {
        label: "Cooldown limiter (сек)",
        description: "Пауза перед следующим действием enforcement после срабатывания limiter.",
      },
      limiter_tolerance: {
        label: "Tolerance limiter",
        description: "Допустимое количество событий до жёсткого срабатывания порога.",
      },
      limiter_tolerance_multiplier: {
        label: "Множитель tolerance",
        description: "Множитель для tolerance при вычислении итогового порога.",
      },
      limiter_ignore_ttl_seconds: {
        label: "Ignore TTL (сек)",
        description: "После срабатывания limiter временно игнорировать этот scope.",
      },
      limiter_group_by_subnet: {
        label: "Группировать по subnet",
        description: "Использовать subnet как scope limiter при отсутствии UUID.",
      },
      limiter_group_by_asn: {
        label: "Группировать по ASN",
        description: "Использовать ASN как scope limiter при отсутствии UUID.",
      },
      limiter_rollout_mode: {
        label: "Режим rollout limiter",
        description: "Этап limiter: observe, warning_only или enforce.",
      }
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
      tg_topic_review: {
        label: "Топик: review",
        description: "ID топика админ-чата для review-событий",
      },
      tg_topic_warning_only: {
        label: "Топик: warning-only",
        description: "ID топика админ-чата для warning-only событий",
      },
      tg_topic_warning: {
        label: "Топик: warning",
        description: "ID топика админ-чата для предупреждений",
      },
      tg_topic_ban: {
        label: "Топик: ban",
        description: "ID топика админ-чата для ограничений доступа",
      },
      tg_topic_usage_profile_risk: {
        label: "Топик: usage-profile risk",
        description: "ID топика админ-чата для событий риска профиля использования",
      },
      tg_topic_violation_continues: {
        label: "Топик: violation-continues",
        description: "ID топика админ-чата для продолжающихся нарушений",
      },
      tg_topic_traffic_limit_exceeded: {
        label: "Топик: traffic-limit exceeded",
        description: "ID топика админ-чата для событий лимита трафика",
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
        label: "Риск по профилю использования",
        description:
          "Отправлять админские сообщения с расширенным снимком профиля использования",
      },
      telegram_notify_admin_violation_continues_enabled: {
        label: "Продолжительные нарушения",
        description:
          "Отправлять админские сообщения, когда подозрительное поведение продолжается во времени",
      },
      telegram_notify_admin_traffic_limit_exceeded_enabled: {
        label: "Ограничения по трафику",
        description:
          "Отправлять админские сообщения, когда применяется ограничение по трафику",
      },
      telegram_notify_user_warning_only_enabled: {
        label: "Отправлять сообщения без эскалации",
        description:
          "Отправлять пользовательские сообщения по warning-only кейсам.",
      },
      telegram_notify_user_warning_enabled: {
        label: "Отправлять предупреждения",
        description:
          "Отправлять пользовательские сообщения при выдаче предупреждения.",
      },
      telegram_notify_user_ban_enabled: {
        label: "Отправлять сообщения об ограничении доступа",
        description:
          "Отправлять пользовательские сообщения при применении ограничения доступа.",
      },
    },
    telegramTemplateFields: {
      user_warning_only_template: {
        label: "Сообщение без эскалации",
        description:
          "Пользовательское сообщение, когда кейс warning-only и не эскалируется.",
      },
      user_warning_template: {
        label: "Сообщение о предупреждении",
        description:
          "Пользовательское сообщение для обычных предупреждений перед ограничением доступа.",
      },
      user_ban_template: {
        label: "Сообщение об ограничении доступа",
        description:
          "Пользовательское сообщение, отправляемое при ограничении доступа.",
      },
      admin_warning_only_template: {
        label: "Сообщение без эскалации",
        description: "Текст админского уведомления по warning-only кейсам.",
      },
      admin_warning_template: {
        label: "Сообщение о предупреждении",
        description: "Текст админского уведомления по предупреждениям.",
      },
      admin_ban_template: {
        label: "Сообщение об ограничении доступа",
        description: "Текст админского уведомления по ограничениям доступа.",
      },
      admin_review_template: {
        label: "Сообщение для ревью",
        description:
          "Текст админского уведомления для кейсов ревью / ручной модерации.",
      },
      admin_usage_profile_risk_template: {
        label: "Сообщение о риске по профилю использования",
        description:
          "Текст админского уведомления для расширенного снимка профиля использования.",
      },
      admin_violation_continues_template: {
        label: "Сообщение о продолжающемся нарушении",
        description:
          "Текст админского уведомления, когда подозрительное поведение продолжает развиваться.",
      },
      admin_traffic_limit_exceeded_template: {
        label: "Сообщение о превышении лимита трафика",
        description:
          "Текст админского уведомления, когда применяется ограничение по трафику.",
      },
    },
  },
};
