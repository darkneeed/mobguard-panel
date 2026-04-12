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
    secretValueStored: "На сервере значение хранится как скрытый секрет.",
    runtimeValue: "Runtime-значение, управляемое через .env.",
    leaveBlankToKeep: "Оставьте пустым, чтобы сохранить текущее секретное значение",
    restartRequired: "нужен перезапуск"
  },
  layout: {
    brandSubtitle: "Панель администратора",
    consoleBadge: "Hybrid console",
    consoleDescription: "Операторский поток в духе Remnawave с более polished подачей Bedolaga.",
    groups: {
      monitor: "Мониторинг",
      configure: "Настройки",
      operate: "Операции"
    },
    nav: {
      overview: "Обзор",
      modules: "Модули",
      queue: "Очередь",
      rules: "Правила детекта",
      telegram: "Telegram",
      access: "Доступ",
      data: "Данные",
      quality: "Качество"
    },
    subnav: {
      rules: {
        general: "Общие",
        thresholds: "Пороги",
        lists: "Списки",
        providers: "Провайдеры",
        policy: "Политика",
        learning: "Learning"
      },
      data: {
        users: "Пользователи",
        violations: "Нарушения",
        overrides: "Оверрайды",
        cache: "Кэш",
        learning: "Learning",
        cases: "Кейсы",
        exports: "Экспорты"
      }
    },
    theme: {
      label: "Тема",
      system: "Системная",
      light: "Светлая",
      dark: "Тёмная"
    },
    language: {
      label: "Язык",
      ru: "rus",
      en: "eng"
    },
    logout: "Выйти"
  },
  overview: {
    eyebrow: "Operator Overview",
    title: "Здоровье системы, давление очереди и runtime-поза",
    description: "Один экран для live-state, модерационной нагрузки, качества learning и рискованных зон.",
    lastUpdated: "Последняя синхронизация {value}",
    errors: {
      loadFailed: "Не удалось загрузить обзорный экран"
    },
    systemStatusTitle: "Live-состояние операторской панели",
    systemStatusDescription: "Core, очередь, live rules и готовность экспортов на одном экране.",
    healthTitle: "Снимок здоровья",
    healthDescription: "Heartbeat backend-сервисов и статус control-plane.",
    health: {
      core: "Heartbeat core",
      db: "База данных",
      rules: "Live rules",
      updated: "Обновлено {value}",
      rulesBy: "Обновил {value}"
    },
    cards: {
      openQueue: "Открытая очередь",
      core: "Core healthy",
      ipinfo: "IPINFO token",
      adminSessions: "Админ-сессии",
      scoreZeroRatio: "Доля score=0 (24ч)",
      asnMissingRatio: "Доля ASN-missing (24ч)",
      mixedConflicts: "Конфликты mixed-провайдеров",
      promotedPatterns: "Promoted patterns"
    },
    quickLinks: {
      queue: "Открыть очередь",
      quality: "Перейти в quality",
      policy: "Проверить policy",
      exports: "Calibration exports"
    },
    mixedProvidersTitle: "Проблемные mixed-провайдеры",
    mixedProvidersDescription: "Провайдеры, которые чаще всего приводят к review-first и конфликтам.",
    mixedProvidersItem: "{open} open · {conflict} conflicts · {home} HOME · {mobile} MOBILE",
    emptyMixedProviders: "Сейчас нет проблемных mixed-провайдеров.",
    noisyAsnTitle: "Шумные ASN",
    noisyAsnDescription: "ASN, дающие наибольшую нагрузку на модерацию.",
    noisyAsnItem: "{count} кейсов ревью",
    emptyNoisyAsn: "Данных по шумным ASN пока нет.",
    latestCasesTitle: "Последние кейсы очереди",
    latestCasesDescription: "Свежие спорные кейсы, готовые к обработке оператором.",
    emptyLatestCases: "Сейчас открытых кейсов нет."
  },
  login: {
    eyebrow: "Remnawave + MobGuard",
    title: "Веб-панель модерации, данных и runtime-настроек",
    description:
      "Очередь спорных кейсов, data-admin, Telegram delivery и runtime-конфигурация в одной панели.",
    telegramTitle: "Telegram вход",
    telegramNotConfigured: "Telegram auth не настроен.",
    telegramLoading: "Загружаю Telegram auth…",
    localTitle: "Локальный вход",
    usernamePlaceholder: "Имя пользователя",
    passwordPlaceholder: "Пароль",
    signIn: "Войти",
    signingIn: "Выполняю вход…",
    localNotConfigured: "Local fallback auth не настроен.",
    authFailed: "Ошибка авторизации",
    localAuthFailed: "Ошибка локальной авторизации"
  },
  reviewQueue: {
    eyebrow: "Очередь ревью",
    title: "Спорные решения и ручная модерация",
    description: "Явные фильтры, bulk-решения и более плотный операторский workflow для живой очереди.",
    countSummary: "{count} кейсов · страница {page}",
    lastUpdated: "Обновлено {value}",
    searchPlaceholder: "Быстрый поиск по IP / username / ISP / UUID / IDs",
    clearFilters: "Сбросить фильтры",
    toggleFiltersTitle: "Переключить фильтры",
    filtersButton: "Фильтры",
    filterCount: "Фильтры ({count})",
    presets: {
      open: "Только open",
      providerConflict: "Provider conflict",
      critical: "Critical",
      punitive: "Punitive"
    },
    filters: {
      moduleId: "Module ID",
      username: "Имя пользователя",
      systemId: "System ID",
      telegramId: "Telegram ID",
      repeatMin: "Минимум повторов",
      repeatMax: "Максимум повторов",
      allStatus: "Любой статус",
      allConfidence: "Любая confidence",
      allReasons: "Все причины",
      allSeverity: "Любая severity",
      punitiveAny: "Любой punitive статус",
      punitiveOnly: "Только punitive",
      reviewOnly: "Только review",
      sortUpdatedDesc: "Сначала новые",
      sortScoreDesc: "Сначала высокий score",
      sortRepeatDesc: "Сначала частые повторы",
      sortUpdatedAsc: "Сначала старые"
    },
    errors: {
      loadFailed: "Не удалось загрузить кейсы ревью",
      resolveFailed: "Не удалось применить решение"
    },
    identifiers: {
      user: "Пользователь",
      module: "Модуль",
      system: "System",
      telegram: "TG",
      uuid: "UUID"
    },
    card: {
      ip: "IP",
      asn: "ASN",
      decision: "Решение",
      punitiveEligible: "punitive eligible",
      reviewOnly: "review only",
      repeat: "повтор x{count}",
      opened: "открыт {value}"
    },
    actions: {
      mobile: "Mobile",
      home: "Home",
      skip: "Skip",
      openCase: "Открыть кейс",
      bulkMobile: "Поставить selected в MOBILE",
      bulkHome: "Поставить selected в HOME",
      bulkSkip: "Пропустить selected",
      processing: "Обработка…",
      saved: "Решение по кейсу сохранено",
      bulkSaved: "Применено решение к {count} выбранным кейсам"
    },
    selection: {
      selectPage: "Выбрать страницу",
      clearPage: "Снять выбор со страницы",
      selectedCount: "Выбрано {count}"
    },
    footer: {
      previous: "Назад",
      next: "Дальше",
      pageSummary: "Страница {page} · показано {shown} из {total}"
    }
  },
  modules: {
    eyebrow: "Fleet",
    title: "MobGuard Modules",
    description: "Управляйте collector-модулями, их INBOUND тэгами и последним runtime health snapshot из панели.",
    count: "{count} модулей",
    loadFailed: "Не удалось загрузить список модулей",
    listTitle: "Подготовленные модули",
    listDescription: "Сначала создайте карточку, затем подключите collector и отслеживайте его health/error state.",
    selectionHint: "Выберите модуль или создайте новый",
    empty: "Модули ещё не созданы",
    create: "Создать модуль",
    save: "Сохранить изменения",
    open: "Открыть детали",
    createTitle: "Создание карточки модуля",
    createDescription: "Укажите отображаемое имя и INBOUND тэги для этого модуля. После сохранения панель сгенерирует module_id и API token.",
    detailsTitle: "Детали модуля",
    detailsDescription: "Редактируйте имя модуля и INBOUND тэги. Обновлённые тэги придут в collector через remote config без изменения install flow.",
    createSuccess: "Модуль создан",
    updateSuccess: "Модуль обновлён",
    saveFailed: "Не удалось сохранить модуль",
    pendingInstall: "ожидает установку",
    stale: "stale",
    inboundTags: "INBOUND тэги",
    lastSeen: "Последний heartbeat",
    appliedRevision: "Применённая ревизия",
    openCases: "Открытые кейсы",
    analysisEvents: "Analysis events",
    version: "Версия {value}",
    protocol: "Протокол {value}",
    moduleId: "Module ID: {value}",
    generatedAfterCreate: "Будет сгенерирован после создания",
    healthTitle: "Runtime health",
    healthDescription: "Панель показывает последний self-reported status модуля и derived stale-состояние.",
    healthStatus: "Health status",
    lastValidationAt: "Последняя валидация",
    spoolDepth: "Глубина spool",
    accessLogExists: "Access log найден",
    healthEmpty: "Создайте или откройте модуль, чтобы увидеть последний runtime health.",
    installTitle: "Install bundle",
    installDescription: "Скопируйте generated compose, раскройте token и при необходимости измените ACCESS_LOG_PATH локально, если у ноды нестандартный путь к логу.",
    installPreviewEmpty: "Создайте или откройте модуль, чтобы увидеть сгенерированный docker-compose.yml",
    revealToken: "Показать token",
    tokenRevealSuccess: "Token модуля раскрыт",
    tokenRevealFailed: "Не удалось раскрыть token модуля",
    tokenUnavailable: "Для этого модуля token нельзя раскрыть повторно. У legacy-модулей хранится только auth hash.",
    tokenTitle: "Module token",
    tokenDescription: "Подставьте этот token в MODULE_TOKEN внутри сгенерированного compose-файла перед запуском.",
    tokenValue: "Раскрытый token",
    copyToken: "Скопировать token",
    tokenCopied: "Token скопирован в буфер",
    copyCompose: "Скопировать compose",
    composeCopied: "docker-compose.yml скопирован в буфер",
    copyFailed: "Не удалось скопировать в буфер",
    installSteps: {
      clone: "Склонируйте репозиторий модуля на целевую ноду и откройте его корень.",
      compose: "Замените локальный docker-compose.yml на compose preview ниже.",
      token: "Раскройте token в панели и замените MODULE_TOKEN=__PASTE_TOKEN__ перед запуском.",
      start: "Запустите docker compose up -d && docker compose logs -f -t и дождитесь перехода модуля в online."
    },
    health: {
      ok: "ok",
      warn: "warn",
      error: "error"
    },
    fields: {
      moduleName: "Отображаемое имя",
      moduleId: "Сгенерированный module ID",
      inboundTags: "INBOUND тэги"
    },
    cards: {
      total: "Всего модулей",
      pending: "Ожидают установку",
      error: "Error",
      stale: "Stale"
    }
  },
  reviewDetail: {
    eyebrow: "Детали кейса",
    title: "Кейс ревью #{caseId}",
    description: "Evidence, связанная история и sticky-зона решения для быстрой модерации.",
    loading: "Загрузка…",
    backToQueue: "Назад в очередь",
    copySuccess: "Скопировано в буфер",
    copyFailed: "Не удалось скопировать",
    errors: {
      resolveFailed: "Не удалось применить решение"
    },
    sections: {
      summary: "Сводка",
      reasons: "Причины",
      providerEvidence: "Провайдерские сигналы",
      log: "Лог",
      history: "История решений",
      linkedContext: "Связанный контекст пользователя/IP",
      resolution: "Решение"
    },
    fields: {
      username: "Имя пользователя",
      systemId: "System ID",
      telegramId: "Telegram ID",
      uuid: "UUID",
      ip: "IP",
      tag: "Тег",
      verdict: "Вердикт",
      confidence: "Confidence",
      punitive: "Punitive",
      opened: "Открыт",
      updated: "Обновлён",
      isp: "ISP",
      reviewUrl: "URL ревью"
    },
    history: {
      empty: "Решений пока нет"
    },
    linkedCases: {
      empty: "Связанные кейсы не найдены",
      caseLabel: "Кейс #{id}"
    },
    resolution: {
      placeholder: "Комментарий для аудита",
      mobile: "Mark MOBILE",
      home: "Mark HOME",
      skip: "Skip",
      saved: "Решение по кейсу сохранено"
    },
    summaryHint: "Быстрые идентификаторы и контекст ревью без провала в raw payload.",
    resolutionHint: "Эта заметка попадёт в audit trail вместе с выбранным результатом.",
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
      homeMarkers: "Совпавшие home markers"
    }
  },
  rules: {
    eyebrow: "Live Rules",
    title: "Понятные live-настройки без редактирования сырых ключей",
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
      description: "Параметры эскалации runtime и переключения уровней доступа.",
      save: "Сохранить общие настройки"
    },
    sectionTitles: {
      thresholds: "Пороги, скоринг и поведение",
      policy: "Политика детекта",
      learning: "Контроль learning"
    },
    sectionDescriptions: {
      general: "Runtime-wide параметры эскалации, предупреждений и переключения доступа в отдельной вкладке.",
      thresholds: "Пороговые значения, веса скоринга и окна поведенческих сигналов в одном месте.",
      lists: "ASN- и keyword-списки, формирующие первичное доказательство и исключения.",
      providers: "Алиасы, markers и операторские подсказки для review-first сценариев.",
      policy: "Живая policy-логика детекта плюс enforcement-настройки переключения доступа.",
      learning: "Пороги, при которых runtime-learning становится доверенным."
    },
    providerProfiles: {
      description: "Профили операторов с alias и service markers для осторожного review-first скоринга.",
      add: "Добавить профиль оператора",
      remove: "Удалить профиль",
      empty: "Профили операторов пока не настроены.",
      cardTitle: "Профиль оператора #{index}",
      cardSubtitle: "По одному значению на строку. ASN указываются только числами.",
      classifications: {
        mixed: "Смешанный",
        mobile: "Мобильный",
        home: "Домашний"
      },
      validation: {
        missingKey: "Профиль оператора #{index}: нужен key"
      },
      fields: {
        key: {
          label: "Ключ профиля",
          description: "Стабильный идентификатор для learning labels и quality-метрик."
        },
        classification: {
          label: "Классификация",
          description: "Смешанные профили остаются в review-first режиме, пока их не подтвердит второй независимый фактор."
        },
        aliases: {
          label: "Алиасы",
          description: "Имена оператора, бренды, PTR-фрагменты и org-алиасы для поиска в ISP/hostname."
        },
        mobile_markers: {
          label: "Мобильные service markers",
          description: "Маркеры услуг, указывающие на мобильную сторону оператора."
        },
        home_markers: {
          label: "Домашние service markers",
          description: "Маркеры услуг, указывающие на фиксированную/домашнюю сторону оператора."
        },
        asns: {
          label: "Список ASN",
          description: "ASN, относящиеся к этому профилю оператора."
        }
      }
    },
    listSectionDescription: "Редактируемые правила в формате списков.",
    settingSectionDescription: "Только каноничные редактируемые настройки.",
    invalidNumber: "{field}: некорректное число",
    invalidValue: "{field}: некорректное значение '{value}'"
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
    capabilityStatusDescription: "Токены и usernames ботов управляются только через `.env` на сервере.",
    deliveryTitle: "Доставка и поведение бота",
    deliveryDescription: "Эти настройки редактируются на лету и не требуют перезапуска.",
    adminNotificationsTitle: "Уведомления администратору",
    adminNotificationsDescription: "Настройки доставки по типам событий для админ-бота.",
    userNotificationsTitle: "Уведомления пользователю",
    userNotificationsDescription: "Настройки доставки по типам событий для пользовательского бота.",
    templatesTitle: "Шаблоны сообщений",
    templatesHintLabel: "Подсказка по шаблонам сообщений",
    templatesHint:
      "Многострочный текст сохраняется.\n\nПлейсхолдеры: {{username}}, {{warning_count}}, {{warnings_left}}, {{ban_text}}, {{review_url}}.",
    userTemplates: "Пользовательские шаблоны",
    adminTemplates: "Админские шаблоны",
    envTitle: "Telegram .env",
    envDescription: "Токены и usernames ботов редактируются отдельно от live runtime-настроек.",
    envCount: "{present} из {total} задано",
    cards: {
      adminBot: "Админ-бот",
      userBot: "Пользовательский бот",
      adminBotConfigured: "Токен и username админ-бота",
      userBotConfigured: "Токен пользовательского бота",
      envFile: "Состояние env-файла"
    },
    sections: {
      delivery: "Доставка",
      admin: "Админ-уведомления",
      user: "Пользовательские уведомления"
    }
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
      telegramLogin: "Telegram вход",
      localFallback: "Local fallback вход",
      envFile: "Состояние env-файла"
    },
    authStatusTitle: "Статус аутентификации",
    authStatusDescription: "Учётные данные управляются только через `.env` на сервере.",
    authCards: {
      telegramPanel: "Telegram auth панели",
      localFallback: "Local fallback auth"
    },
    listsTitle: "Списки доступа",
    listsDescription: "Администраторы панели и runtime-исключения управляются отдельно.",
    envTitle: "Access .env",
    envDescription: "Локальные fallback-учётки живут в `.env`, а секреты меняются только явной заменой.",
    envCount: "{present} из {total} задано"
  },
  data: {
    eyebrow: "Данные",
    title: "Оперативный data-admin для runtime",
    sectionDescriptions: {
      users: "Основной operator-flow для поиска пользователя, разбора карточки, ограничений, исключений и export-снимков.",
      violations: "Глобальный обзор активных ограничений и истории нарушений из runtime state.",
      overrides: "Ручные IP- и unsure-override правила, которые шорткатят detection-решения.",
      cache: "Live cache-записи, которые можно исправить или удалить без ожидания естественного TTL.",
      learning: "Promoted patterns, legacy confidence и provider-learning срезы.",
      cases: "Недавние кейсы ревью с быстрым переходом в полный detail.",
      exports: "Генерация calibration-архива с видимостью dataset readiness и manifest."
    },
    tabs: {
      users: "Пользователи",
      violations: "Нарушения",
      overrides: "Overrides",
      cache: "Кэш",
      learning: "Обучение",
      cases: "Кейсы",
      exports: "Выгрузки"
    },
    errors: {
      loadTabFailed: "Не удалось загрузить вкладку данных",
      searchUsersFailed: "Не удалось найти пользователей",
      loadUserFailed: "Не удалось загрузить карточку пользователя",
      userActionFailed: "Не удалось выполнить действие над пользователем",
      exportUserFailed: "Не удалось собрать export-карточку пользователя",
      exportCalibrationFailed: "Не удалось сформировать calibration export",
      saveExactOverrideFailed: "Не удалось сохранить exact override",
      saveUnsureOverrideFailed: "Не удалось сохранить unsure override",
      saveCacheFailed: "Не удалось обновить запись кэша"
    },
    saved: {
      userUpdated: "Данные пользователя обновлены",
      exactOverride: "Exact override сохранён",
      unsureOverride: "Unsure override сохранён",
      cacheUpdated: "Запись кэша обновлена",
      learningUpdated: "Данные обучения обновлены",
      exportReady: "Export-карточка готова",
      exportDownloaded: "Export-карточка скачана",
      calibrationExportReady: "Calibration archive сформирован"
    },
    users: {
      searchPlaceholder: "Поиск по uuid / system id / telegram id / username",
      search: "Искать",
      searching: "Ищу…",
      panelMatch: "Совпадение в панели: {value}",
      systemLabel: "sys:{value}",
      telegramLabel: "tg:{value}",
      cardTitle: "Карточка пользователя",
      exportHint: "Соберите структурированную export-карточку для калибровки или ручного разбора.",
      buildExport: "Собрать export-карточку",
      generatingExport: "Генерирую…",
      downloadExport: "Скачать JSON",
      exportPreviewTitle: "Предпросмотр export-карточки",
      exportGeneratedAt: "Сгенерировано {value}",
      actionsTitle: "Действия с пользователем",
      analysisTitle: "Недавний анализ и provider evidence",
      analysisEmpty: "Недавних analysis events нет",
      openCasesTitle: "Открытые / недавние кейсы ревью",
      openCasesEmpty: "Локальных кейсов ревью нет",
      historyTitle: "История нарушений",
      historyEmpty: "Истории нарушений нет",
      providerConflict: "Есть конфликт provider markers",
      providerClear: "Provider markers согласованы",
      reviewFirst: "Только через review-first",
      autoReady: "Есть второй независимый фактор",
      exportCards: {
        reviewCases: "Кейсы ревью",
        analysisEvents: "События анализа",
        history: "История",
        ipHistory: "История IP"
      },
      exportSections: {
        identity: "Identity",
        flags: "Flags",
        panel: "Panel user",
        reviewCases: "Review cases",
        analysisEvents: "Analysis events",
        history: "History",
        activeTrackers: "Active trackers",
        ipHistory: "IP history"
      },
      fields: {
        username: "Имя пользователя",
        uuid: "UUID",
        systemId: "System ID",
        telegramId: "Telegram ID",
        panelStatus: "Статус в панели",
        panelSquads: "Активные squads",
        trafficLimitBytes: "Лимит трафика",
        trafficLimitStrategy: "Стратегия лимита",
        usedTrafficBytes: "Текущий потраченный трафик",
        lifetimeUsedTrafficBytes: "Трафик за всё время",
        exemptSystemId: "Исключённый System ID",
        exemptTelegramId: "Исключённый Telegram ID",
        activeBan: "Активное ограничение",
        activeWarning: "Активное предупреждение"
      },
      actions: {
        banMinutes: "Минуты ограничения",
        startBan: "Ограничить доступ",
        unban: "Восстановить полный доступ",
        trafficCapGigabytes: "Traffic cap: +GB от текущего расхода",
        applyTrafficCap: "Поставить traffic cap",
        restoreTrafficCap: "Восстановить прежний лимит",
        strikes: "Страйки",
        add: "Добавить",
        remove: "Удалить",
        set: "Установить",
        warnings: "Предупреждения",
        setWarning: "Установить предупреждение",
        clearWarning: "Очистить предупреждение",
        exemptions: "Исключения",
        exemptSystem: "Исключить system",
        unexemptSystem: "Убрать исключение system",
        exemptTelegram: "Исключить telegram",
        unexemptTelegram: "Убрать исключение telegram"
      }
    },
    violations: {
      activeTitle: "Активные нарушения / ограничения доступа",
      historyTitle: "История нарушений",
      strikes: "strikes {value}",
      warningCount: "warning_count {value}",
      unban: "восстановление {value}",
      historyRow: "strike {strike} · {duration} min"
    },
    overrides: {
      exactTitle: "Exact IP overrides",
      unsureTitle: "Unsure pattern overrides",
      ipPlaceholder: "IP",
      ipPatternPlaceholder: "IP pattern",
      save: "Сохранить",
      delete: "Удалить",
      expires: "истекает {value}"
    },
    cache: {
      title: "IP cache",
      editTitle: "Редактировать запись кэша",
      edit: "Редактировать",
      delete: "Удалить",
      selectedIp: "Выбранный IP",
      status: "status",
      confidence: "confidence",
      details: "details",
      asn: "asn",
      save: "Сохранить запись кэша"
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
      delete: "Удалить"
    },
    cases: {
      title: "Кейсы"
    },
    exports: {
      title: "Calibration export",
      description: "Сформировать ZIP-архив с сырыми resolved rows и summary для настройки правил.",
      generating: "Формирую…",
      generate: "Собрать ZIP",
      lastManifestTitle: "Manifest последней выгрузки",
      noManifest: "Calibration export ещё не формировался",
      datasetReady: "Датасет структурно пригоден для анализа",
      datasetNotReady: "Датасет пока непригоден для надёжной provider-калибровки",
      tuningReady: "По этой выгрузке уже можно начинать provider tuning",
      tuningNotReady: "Provider tuning пока заблокирован покрытием или support",
      warningsTitle: "Предупреждения readiness-проверки",
      notReadyToast: "Calibration archive сформирован, но readiness checks не пройдены",
      filterSnapshot: "Применённые фильтры",
      coverageSnapshot: "Снимок покрытия",
      filters: {
        openedFrom: "Открыт с",
        openedTo: "Открыт по",
        reviewReason: "Причина ревью",
        providerKey: "Ключ провайдера",
        status: "Статус датасета",
        includeUnknown: "Включать unknown в агрегаты"
      },
      status: {
        resolvedOnly: "Только resolved",
        openOnly: "Только open",
        all: "Все кейсы"
      },
      cards: {
        file: "Архив",
        rawRows: "Сырые rows",
        knownRows: "Размеченные rows",
        unknownRows: "Unknown rows",
        providerProfiles: "Профили провайдеров",
        providerCoverage: "Покрытие provider key",
        patternCandidates: "Кандидаты provider patterns"
      },
      warnings: {
        live_rules_stale_or_unseeded: "Live rules snapshot был пуст и был слит с runtime config.",
        provider_profiles_missing: "В snapshot выгрузки нет provider profiles.",
        provider_key_coverage_zero: "В resolved rows вообще нет provider key.",
        provider_explainability_missing: "В экспортированных rows отсутствует provider explainability.",
        resolved_ratio_below_threshold: "Слишком много pending rows: resolved ratio ниже безопасного порога.",
        provider_key_coverage_below_target: "Покрытие provider key ниже целевого порога 0.6.",
        provider_support_below_target: "Хотя бы один provider/provider_service кандидат имеет меньше 5 известных resolved cases."
      }
    }
  },
  quality: {
    eyebrow: "Качество",
    title: "Шумные ASN, объём ревью и активные паттерны",
    description: "Графики и ranked cards для resolution mix, шумных ASN и здоровья learning.",
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
      mixedProviderCases: "Открытые mixed-provider кейсы",
      mixedConflictRate: "Conflict-rate mixed providers",
      homeRatio: "Доля HOME",
      mobileRatio: "Доля MOBILE"
    },
    revision: "Ревизия правил {value}",
    updated: "Обновлено {value}",
    by: "Кем: {value}",
    asnSourceTitle: "Источник ASN",
    noAsnSource: "Источник ASN недоступен",
    resolutionMixTitle: "Смесь решений",
    resolutionMixDescription: "Как именно операторы сейчас разрешают спорные кейсы.",
    topNoisyAsnTitle: "Самые шумные ASN",
    noisyAsnDescription: "ASN, которые сейчас создают наибольшее давление на очередь ревью.",
    topMixedProvidersTitle: "Mixed providers с наибольшим backlog",
    mixedProvidersDescription: "Провайдеры с наибольшей нагрузкой по open-кейсам и конфликтам.",
    noMixedProviders: "Mixed-provider backlog пока пуст",
    mixedProviderStats: "{open} open · {conflict} conflicts · HOME {home} · MOBILE {mobile} · UNSURE {unsure}",
    reviewCases: "{count} кейсов ревью",
    topPromotedPatternsTitle: "Топ promoted patterns",
    topPatternDetails: "{decision} · support {support} · precision {precision}",
    learningStateTitle: "Состояние обучения",
    providerLearningTitle: "Обучение по операторам",
    promotedByTypeTitle: "Promoted learning по типам",
    noPromotedData: "Promoted-данных пока нет",
    legacyByTypeTitle: "Legacy learning по типам",
    noLegacyData: "Legacy learning пока пуст",
    topLegacyTitle: "Топ legacy patterns",
    noLegacyPatterns: "Legacy patterns пока нет",
    learningCards: {
      promotedPatterns: "Promoted patterns",
      legacyPatterns: "Legacy patterns",
      legacyConfidence: "Legacy confidence",
      asnMinSupport: "ASN min support",
      asnMinPrecision: "ASN min precision",
      comboMinSupport: "Combo min support",
      comboMinPrecision: "Combo min precision"
    },
    providerLearning: {
      promoted: "Promoted provider patterns",
      legacy: "Legacy provider patterns"
    },
    patternStats: "{count} patterns · support {support} · avg precision {precision}",
    legacyStats: "{count} patterns · accumulated confidence {confidence}"
  },
  tooltips: {
    info: "Подсказка"
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
      learning: "Learning"
    },
    listFields: {
      admin_tg_ids: {
        label: "Admin Telegram IDs",
        description: "Telegram IDs, которым разрешён вход в веб-панель.",
        recommendation: "Держите здесь только модераторов и администраторов панели."
      },
      exempt_ids: {
        label: "Excluded System IDs",
        description: "Системные user.id, исключённые из анализа и авто-санкций.",
        recommendation: "Добавляйте только служебные или доверенные аккаунты."
      },
      exempt_tg_ids: {
        label: "Excluded Telegram IDs",
        description: "Telegram IDs, исключённые из анализа и авто-санкций.",
        recommendation: "Используйте, если удобнее администрировать исключения по Telegram ID."
      },
      pure_mobile_asns: {
        label: "Pure mobile ASN list",
        description: "ASN, которые почти всегда считаются мобильными и дают сильный mobile-сигнал.",
        recommendation: "Добавляйте ASN только после подтверждённой чистой мобильной выборки."
      },
      pure_home_asns: {
        label: "Pure home ASN list",
        description: "ASN, которые почти всегда считаются домашними и дают сильный home-сигнал.",
        recommendation: "Сюда должны попадать только стабильно домашние ASN без мобильной примеси."
      },
      mixed_asns: {
        label: "Mixed ASN list",
        description: "ASN со смешанным профилем, где нужны дополнительные признаки и осторожность.",
        recommendation: "Используйте для спорных ASN, где одного ASN недостаточно для вердикта."
      },
      allowed_isp_keywords: {
        label: "Mobile keywords",
        description: "Ключевые слова, усиливающие mobile-версию при совпадении в ISP/hostname.",
        recommendation: "Держите здесь короткие устойчивые mobile-маркеры, без широких слов."
      },
      home_isp_keywords: {
        label: "Home keywords",
        description: "Ключевые слова, которые тянут решение в сторону home.",
        recommendation: "Добавляйте только маркеры фиксированных/домашних провайдеров."
      },
      exclude_isp_keywords: {
        label: "Datacenter / hosting keywords",
        description: "Ключевые слова для детекта хостинга, датацентров и инфраструктурных сетей.",
        recommendation: "Держите список консервативным, чтобы не ловить обычных провайдеров."
      }
    },
    settingFields: {
      threshold_mobile: {
        label: "MOBILE decision threshold",
        description: "Score, начиная с которого кейс считается уверенно мобильным.",
        recommendation: "Базовое безопасное значение: около 60."
      },
      threshold_probable_mobile: {
        label: "Probable mobile threshold",
        description: "Порог для промежуточного mobile-сигнала до финального MOBILE.",
        recommendation: "Обычно держат ниже основного mobile threshold."
      },
      threshold_home: {
        label: "HOME decision threshold",
        description: "Нижний score, после которого кейс считается уверенно домашним.",
        recommendation: "Чем выше значение, тем осторожнее будут home-решения."
      },
      threshold_probable_home: {
        label: "Probable home threshold",
        description: "Порог для промежуточного home-сигнала до финального HOME.",
        recommendation: "Держите между threshold_home и нейтральной зоной."
      },
      pure_asn_score: {
        label: "Pure mobile ASN bonus",
        description: "Бонус к score, если ASN найден в pure_mobile_asns.",
        recommendation: "Обычно это сильный бонус, сопоставимый с threshold_mobile."
      },
      mixed_asn_score: {
        label: "Mixed ASN bonus",
        description: "Бонус к score для mixed ASN до учёта дополнительных признаков.",
        recommendation: "Держите заметно ниже pure mobile ASN bonus."
      },
      ptr_home_penalty: {
        label: "Home keyword penalty",
        description: "Штраф за home keywords в ISP/hostname.",
        recommendation: "Небольшой минус, чтобы keyword не перевешивал жёсткие сигналы."
      },
      mobile_kw_bonus: {
        label: "Mobile keyword bonus",
        description: "Бонус за mobile keywords в ISP/hostname.",
        recommendation: "Делайте меньше чистого ASN-бонуса, но достаточно значимым."
      },
      provider_mobile_marker_bonus: {
        label: "Бонус за mobile marker оператора",
        description: "Дополнительный бонус, когда provider profile находит мобильный service marker.",
        recommendation: "Держите умеренным и не используйте как единственный автосигнал для mixed-провайдера."
      },
      provider_home_marker_penalty: {
        label: "Штраф за home marker оператора",
        description: "Дополнительный штраф, когда provider profile находит домашний service marker.",
        recommendation: "Штраф должен быть заметным, но не единственной причиной для punitive по mixed-провайдеру."
      },
      ip_api_mobile_bonus: {
        label: "ip-api mobile bonus",
        description: "Дополнительный bonus, если fallback ip-api подтверждает mobile сеть.",
        recommendation: "Используйте только как добивающий сигнал для mixed ASN."
      },
      pure_home_asn_penalty: {
        label: "Pure home ASN penalty",
        description: "Штраф, если ASN попадает в pure_home_asns.",
        recommendation: "Обычно это сильный penalty для уверенного HOME."
      },
      score_subnet_mobile_bonus: {
        label: "Subnet mobile bonus",
        description: "Бонус за исторические mobile-сигналы в той же подсети.",
        recommendation: "Делайте его умеренным, чтобы не переобучать редкие подсети."
      },
      score_subnet_home_penalty: {
        label: "Subnet home penalty",
        description: "Штраф за исторические home-сигналы в подсети.",
        recommendation: "Подходит как корректирующий, а не доминирующий сигнал."
      },
      score_churn_high_bonus: {
        label: "High churn bonus",
        description: "Бонус за очень высокую сменяемость IP/сессий.",
        recommendation: "Используйте как сильный поведенческий mobile-признак."
      },
      score_churn_medium_bonus: {
        label: "Medium churn bonus",
        description: "Бонус за умеренную сменяемость IP/сессий.",
        recommendation: "Делайте заметно ниже high churn bonus."
      },
      score_stationary_penalty: {
        label: "Stationary penalty",
        description: "Штраф за слишком долгую стационарность пользователя.",
        recommendation: "Обычно это мягкий penalty, не hard-stop."
      },
      concurrency_threshold: {
        label: "Concurrency threshold",
        description: "Сколько одновременных пользователей на IP считать признаком мобильности.",
        recommendation: "Стартовая точка: 2–3."
      },
      churn_window_hours: {
        label: "Churn window (hours)",
        description: "Окно в часах для расчёта churn и сменяемости IP.",
        recommendation: "Чем меньше окно, тем чувствительнее реакция на всплески."
      },
      churn_mobile_threshold: {
        label: "Churn mobile threshold",
        description: "Сколько смен IP считать mobile-поведенческим сигналом.",
        recommendation: "Подбирайте по реальным mobile-паттернам без перегиба."
      },
      lifetime_stationary_hours: {
        label: "Stationary lifetime (hours)",
        description: "После какой длительности одна и та же сессия выглядит слишком домашней.",
        recommendation: "Увеличивайте, если боитесь ложных home-срабатываний."
      },
      subnet_mobile_ttl_days: {
        label: "Subnet mobile TTL (days)",
        description: "Сколько дней хранить mobile-историю по подсетям.",
        recommendation: "Более длинный TTL повышает память системы, но и риск устаревания."
      },
      subnet_home_ttl_days: {
        label: "Subnet home TTL (days)",
        description: "Сколько дней хранить home-историю по подсетям.",
        recommendation: "Обычно меньше mobile TTL, чтобы быстрее забывать шум."
      },
      subnet_mobile_min_evidence: {
        label: "Subnet mobile min evidence",
        description: "Минимум mobile-свидетельств до включения subnet mobile bonus.",
        recommendation: "Повышайте, если подсетей много и они шумные."
      },
      subnet_home_min_evidence: {
        label: "Subnet home min evidence",
        description: "Минимум home-свидетельств до включения subnet home penalty.",
        recommendation: "Обычно требует больше подтверждений, чем mobile."
      },
      shadow_mode: {
        label: "Shadow mode",
        description: "Если включено, система анализирует и пишет кейсы, но не применяет санкции жёстко.",
        recommendation: "Новый rollout безопаснее начинать с true."
      },
      probable_home_warning_only: {
        label: "Probable home = warning only",
        description: "Ограничивает probable home кейсы предупреждением вместо punitive действий.",
        recommendation: "Рекомендуется держать включённым для осторожного режима."
      },
      auto_enforce_requires_hard_or_multi_signal: {
        label: "Require hard or multi-signal for auto-enforce",
        description: "Авто-применение санкций разрешено только при сильном или многосигнальном HOME.",
        recommendation: "Безопаснее оставлять включённым."
      },
      provider_conflict_review_only: {
        label: "Mixed provider conflicts только в review",
        description: "Оставляет конфликты mixed-провайдеров, отсутствие service markers и однофакторные carrier hints в ручном ревью.",
        recommendation: "Рекомендуется для review-first rollout по неоднозначным операторам."
      },
      review_ui_base_url: {
        label: "Review UI base URL",
        description: "Базовый URL веб-панели, который используется в review links.",
        recommendation: "Укажите боевой HTTPS URL панели."
      },
      live_rules_refresh_seconds: {
        label: "Live rules refresh interval",
        description: "Как часто runtime перечитывает live rules из storage.",
        recommendation: "Обычно достаточно 10–30 секунд."
      },
      learning_promote_asn_min_support: {
        label: "Promoted ASN min support",
        description: "Минимум подтверждённых кейсов, чтобы ASN попал в promoted learning.",
        recommendation: "Повышайте, если боитесь раннего переобучения."
      },
      learning_promote_asn_min_precision: {
        label: "Promoted ASN min precision",
        description: "Минимальная precision для promoted ASN pattern.",
        recommendation: "Консервативный режим обычно начинается около 0.95."
      },
      learning_promote_combo_min_support: {
        label: "Promoted combo min support",
        description: "Минимум кейсов для promoted combo pattern.",
        recommendation: "Обычно ниже ASN support, но не слишком низко."
      },
      learning_promote_combo_min_precision: {
        label: "Promoted combo min precision",
        description: "Минимальная precision для combo pattern.",
        recommendation: "Держите высокой, чтобы combo не давал шумных бонусов."
      }
    },
    rulesGeneralFields: {
      usage_time_threshold: {
        label: "Minimum suspicious usage time (sec)",
        description: "Как долго подозрительная сессия должна оставаться активной до начала санкций."
      },
      warning_timeout_seconds: {
        label: "Warning cooldown (sec)",
        description: "Минимальная задержка перед следующим предупреждением."
      },
      warnings_before_ban: {
        label: "Предупреждений до первого ограничения",
        description: "Сколько предупреждений нужно до первого ограничения доступа."
      },
      warning_only_mode: {
        label: "Only warnings mode",
        description: "Никогда не повышать санкции до ограничений доступа автоматически."
      },
      manual_review_mixed_home_enabled: {
        label: "Review mixed HOME cases manually",
        description: "Отправлять смешанные HOME-результаты в ручное ревью до действия."
      },
      manual_ban_approval_enabled: {
        label: "Требовать одобрение ограничения",
        description: "Останавливать применение ограничения до ручного одобрения админом."
      },
      dry_run: {
        label: "Dry run",
        description: "Анализировать и уведомлять без удалённого переключения squads."
      },
      ban_durations_minutes: {
        label: "Лестница ограничений (минуты)",
        description: "Одно значение на строку: первое ограничение, второе, третье и так далее."
      },
      full_access_squad_name: {
        label: "Имя squad полного доступа",
        description: "Точное имя internal squad Remnawave, которое означает полный доступ."
      },
      restricted_access_squad_name: {
        label: "Имя squad ограничения",
        description: "Точное имя internal squad Remnawave, которое выдаётся при нарушении."
      },
      traffic_cap_increment_gb: {
        label: "Прирост traffic cap (GB)",
        description: "На сколько гигабайт увеличить лимит относительно текущего used traffic."
      },
      traffic_cap_threshold_gb: {
        label: "Порог traffic cap (GB)",
        description: "Если пользователь уже израсходовал не меньше этого объёма, вместо скрытия мобильных конфигов применяется traffic cap."
      }
    },
    telegramFields: {
      tg_admin_chat_id: {
        label: "Admin chat destination",
        description: "Telegram chat id для уведомлений администраторам."
      },
      tg_topic_id: {
        label: "Admin thread/topic",
        description: "Необязательный topic/thread id внутри админского чата."
      },
      telegram_message_min_interval_seconds: {
        label: "Message interval (sec)",
        description: "Минимальная задержка между отправками Telegram."
      },
      telegram_admin_notifications_enabled: {
        label: "Send admin notifications",
        description: "Главный переключатель для всех уведомлений админ-бота."
      },
      telegram_user_notifications_enabled: {
        label: "Send user notifications",
        description: "Главный переключатель для всех пользовательских сообщений бота."
      },
      telegram_admin_commands_enabled: {
        label: "Enable admin bot commands",
        description: "Разрешает обработчики админских команд Telegram."
      },
      telegram_notify_admin_review_enabled: {
        label: "Notify review cases",
        description: "Отправлять админские сообщения, когда нужно ревью / ручная модерация."
      },
      telegram_notify_admin_warning_only_enabled: {
        label: "Notify warning-only cases",
        description: "Отправлять админские сообщения по неэскалирующим warning-only кейсам."
      },
      telegram_notify_admin_warning_enabled: {
        label: "Notify warnings",
        description: "Отправлять админские сообщения при выдаче предупреждения."
      },
      telegram_notify_admin_ban_enabled: {
        label: "Notify access restrictions",
        description: "Отправлять админские сообщения при применении ограничения доступа."
      },
      telegram_notify_user_warning_only_enabled: {
        label: "Send warning-only messages",
        description: "Отправлять пользовательские сообщения по warning-only кейсам."
      },
      telegram_notify_user_warning_enabled: {
        label: "Send warning messages",
        description: "Отправлять пользовательские сообщения при выдаче предупреждения."
      },
      telegram_notify_user_ban_enabled: {
        label: "Send access restriction messages",
        description: "Отправлять пользовательские сообщения при применении ограничения доступа."
      }
    },
    telegramTemplateFields: {
      user_warning_only_template: {
        label: "Warning-only message",
        description: "Пользовательское сообщение, когда кейс warning-only и не эскалируется."
      },
      user_warning_template: {
        label: "Warning message",
        description: "Пользовательское сообщение для обычных предупреждений перед ограничением доступа."
      },
      user_ban_template: {
        label: "Access restriction message",
        description: "Пользовательское сообщение, отправляемое при ограничении доступа."
      },
      admin_warning_only_template: {
        label: "Warning-only message",
        description: "Текст админского уведомления по warning-only кейсам."
      },
      admin_warning_template: {
        label: "Warning message",
        description: "Текст админского уведомления по предупреждениям."
      },
      admin_ban_template: {
        label: "Access restriction message",
        description: "Текст админского уведомления по ограничениям доступа."
      },
      admin_review_template: {
        label: "Review message",
        description: "Текст админского уведомления для кейсов ревью / ручной модерации."
      }
    }
  }
};
