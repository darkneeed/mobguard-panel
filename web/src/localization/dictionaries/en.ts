import type { TranslationDictionary } from "../types";

export const enDictionary: TranslationDictionary = {
  common: {
    loading: "Loading…",
    loadingSession: "Loading session…",
    notAvailable: "N/A",
    admin: "Admin",
    system: "system",
    yes: "yes",
    no: "no",
    true: "true",
    false: "false",
    saved: "saved",
    unsavedChanges: "unsaved changes",
    configured: "Configured",
    disabled: "Disabled",
    on: "ON",
    off: "OFF",
    showHint: "Show hint",
    fieldHintLabel: "{field} hint"
  },
  layout: {
    brandSubtitle: "Admin panel",
    nav: {
      queue: "Queue",
      rules: "Detection Rules",
      telegram: "Telegram",
      access: "Access",
      data: "Data",
      quality: "Quality"
    },
    theme: {
      label: "Theme",
      system: "System",
      light: "Light",
      dark: "Dark"
    },
    language: {
      label: "Language",
      ru: "rus",
      en: "eng"
    },
    logout: "Logout"
  },
  login: {
    eyebrow: "Remnawave + MobGuard",
    title: "Moderation, data, and runtime settings web panel",
    description:
      "A single panel for disputed cases, data admin, Telegram delivery, and runtime configuration.",
    telegramTitle: "Telegram login",
    telegramNotConfigured: "Telegram auth is not configured.",
    telegramLoading: "Loading Telegram auth…",
    localTitle: "Local login",
    usernamePlaceholder: "Username",
    passwordPlaceholder: "Password",
    signIn: "Login",
    signingIn: "Signing in…",
    localNotConfigured: "Local fallback auth is not configured.",
    authFailed: "Auth failed",
    localAuthFailed: "Local auth failed"
  },
  reviewQueue: {
    eyebrow: "Review Queue",
    title: "Disputed decisions and manual moderation",
    countSummary: "{count} cases · page {page}",
    searchPlaceholder: "Quick search by IP / username / ISP / UUID / IDs",
    toggleFiltersTitle: "Toggle filters",
    filters: {
      username: "Username",
      systemId: "System ID",
      telegramId: "Telegram ID",
      repeatMin: "Repeat count min",
      repeatMax: "Repeat count max",
      allConfidence: "All confidence",
      allReasons: "All reasons",
      allSeverity: "All severity",
      punitiveAny: "Punitive any",
      punitiveOnly: "punitive only",
      reviewOnly: "review only",
      sortUpdatedDesc: "updated desc",
      sortScoreDesc: "score desc",
      sortRepeatDesc: "repeat desc",
      sortUpdatedAsc: "updated asc"
    },
    errors: {
      loadFailed: "Failed to load reviews",
      resolveFailed: "Resolve failed"
    },
    identifiers: {
      user: "User",
      system: "System",
      telegram: "TG",
      uuid: "UUID"
    },
    card: {
      ip: "IP",
      asn: "ASN",
      decision: "Decision",
      punitiveEligible: "punitive eligible",
      reviewOnly: "review only",
      repeat: "repeat x{count}",
      opened: "opened {value}"
    },
    actions: {
      mobile: "Mobile",
      home: "Home",
      skip: "Skip"
    },
    footer: {
      previous: "Prev",
      next: "Next",
      pageSummary: "Page {page} · showing {shown} of {total}"
    }
  },
  reviewDetail: {
    eyebrow: "Case Detail",
    title: "Review case #{caseId}",
    loading: "Loading…",
    errors: {
      resolveFailed: "Resolve failed"
    },
    sections: {
      summary: "Summary",
      reasons: "Reasons",
      log: "Log",
      history: "Resolution history",
      linkedContext: "Linked user/IP context",
      resolution: "Resolution"
    },
    fields: {
      username: "Username",
      systemId: "System ID",
      telegramId: "Telegram ID",
      uuid: "UUID",
      ip: "IP",
      tag: "Tag",
      verdict: "Verdict",
      confidence: "Confidence",
      punitive: "Punitive",
      opened: "Opened",
      updated: "Updated",
      isp: "ISP",
      reviewUrl: "Review URL"
    },
    history: {
      empty: "No resolutions yet"
    },
    linkedCases: {
      empty: "No related cases found",
      caseLabel: "Case #{id}"
    },
    resolution: {
      placeholder: "Audit comment",
      mobile: "Mark MOBILE",
      home: "Mark HOME",
      skip: "Skip"
    }
  },
  rules: {
    eyebrow: "Live Rules",
    title: "Readable live settings without editing raw keys",
    saveRules: "Save rules",
    rulesUpdated: "Rules updated",
    generalSaved: "General settings saved",
    loadFailed: "Failed to load rules",
    saveFailed: "Save failed",
    revision: "Revision {value}",
    updatedAt: "Updated at {value}",
    updatedBy: "Updated by {value}",
    general: {
      title: "General settings",
      description: "Runtime escalation and sanction controls.",
      save: "Save general settings"
    },
    listSectionDescription: "Editable list-based rules.",
    settingSectionDescription: "Canonical editable settings only.",
    invalidNumber: "{field}: invalid number",
    invalidValue: "{field}: invalid value '{value}'"
  },
  telegram: {
    eyebrow: "Telegram",
    title: "Bot runtime settings and message delivery",
    saveSettings: "Save telegram settings",
    saveTemplates: "Save message templates",
    settingsSaved: "Telegram settings saved",
    templatesSaved: "Message templates saved",
    loadFailed: "Failed to load Telegram settings",
    saveFailed: "Save failed",
    invalidNumber: "{field}: invalid number",
    capabilityStatusTitle: "Telegram capability status",
    capabilityStatusDescription: "Bot tokens and usernames are managed only through `.env` on the server.",
    deliveryTitle: "Delivery & bot behavior",
    deliveryDescription: "These settings are live-editable and do not require restart.",
    adminNotificationsTitle: "Admin notifications",
    adminNotificationsDescription: "Per-event delivery controls for the admin bot.",
    userNotificationsTitle: "User notifications",
    userNotificationsDescription: "Per-event delivery controls for user-facing bot messages.",
    templatesTitle: "Message templates",
    templatesHintLabel: "Message templates hint",
    templatesHint:
      "Multiline text is preserved.\n\nPlaceholders: {{username}}, {{warning_count}}, {{warnings_left}}, {{ban_text}}, {{review_url}}.",
    userTemplates: "User templates",
    adminTemplates: "Admin templates",
    cards: {
      adminBot: "Admin bot",
      userBot: "User bot",
      adminBotConfigured: "Admin bot token + username",
      userBotConfigured: "User bot token"
    },
    sections: {
      delivery: "Delivery",
      admin: "Admin notifications",
      user: "User notifications"
    }
  },
  access: {
    eyebrow: "Access",
    title: "Login methods and access lists",
    save: "Save access settings",
    saved: "Access settings saved",
    loadFailed: "Failed to load access settings",
    saveFailed: "Save failed",
    invalidNumericValue: "Invalid numeric value '{value}'",
    cards: {
      telegramLogin: "Telegram login",
      localFallback: "Local fallback login"
    },
    authStatusTitle: "Authentication status",
    authStatusDescription: "Credentials are managed only through `.env` on the server.",
    authCards: {
      telegramPanel: "Telegram panel auth",
      localFallback: "Local fallback auth"
    },
    listsTitle: "Access lists",
    listsDescription: "Panel admins and runtime exclusions are managed separately."
  },
  data: {
    eyebrow: "Data",
    title: "Operational runtime data admin",
    tabs: {
      users: "users",
      violations: "violations",
      overrides: "overrides",
      cache: "cache",
      learning: "learning",
      cases: "cases"
    },
    errors: {
      loadTabFailed: "Failed to load data tab",
      searchUsersFailed: "User search failed",
      loadUserFailed: "Failed to load user card",
      userActionFailed: "User action failed",
      saveExactOverrideFailed: "Failed to save exact override",
      saveUnsureOverrideFailed: "Failed to save unsure override",
      saveCacheFailed: "Failed to update cache entry"
    },
    saved: {
      userUpdated: "User data updated",
      exactOverride: "Exact override saved",
      unsureOverride: "Unsure override saved",
      cacheUpdated: "Cache entry updated"
    },
    users: {
      searchPlaceholder: "Search uuid / system id / telegram id / username",
      search: "Search",
      panelMatch: "Panel match: {value}",
      systemLabel: "sys:{value}",
      telegramLabel: "tg:{value}",
      cardTitle: "User card",
      actionsTitle: "User actions",
      openCasesTitle: "Open / recent review cases",
      openCasesEmpty: "No local review cases",
      historyTitle: "Violation history",
      historyEmpty: "No violation history",
      fields: {
        username: "Username",
        uuid: "UUID",
        systemId: "System ID",
        telegramId: "Telegram ID",
        panelStatus: "Panel status",
        exemptSystemId: "Exempt system ID",
        exemptTelegramId: "Exempt Telegram ID",
        activeBan: "Active ban",
        activeWarning: "Active warning"
      },
      actions: {
        banMinutes: "Ban minutes",
        startBan: "Start ban",
        unban: "Unban",
        strikes: "Strikes",
        add: "Add",
        remove: "Remove",
        set: "Set",
        warnings: "Warnings",
        setWarning: "Set warning",
        clearWarning: "Clear warning",
        exemptions: "Exemptions",
        exemptSystem: "Exempt system",
        unexemptSystem: "Unexempt system",
        exemptTelegram: "Exempt telegram",
        unexemptTelegram: "Unexempt telegram"
      }
    },
    violations: {
      activeTitle: "Active violations / bans",
      historyTitle: "Violation history",
      strikes: "strikes {value}",
      warningCount: "warning_count {value}",
      unban: "unban {value}",
      historyRow: "strike {strike} · {duration} min"
    },
    overrides: {
      exactTitle: "Exact IP overrides",
      unsureTitle: "Unsure pattern overrides",
      ipPlaceholder: "IP",
      ipPatternPlaceholder: "IP pattern",
      save: "Save",
      delete: "Delete",
      expires: "expires {value}"
    },
    cache: {
      title: "IP cache",
      editTitle: "Edit cache entry",
      edit: "Edit",
      delete: "Delete",
      selectedIp: "Selected IP",
      status: "status",
      confidence: "confidence",
      details: "details",
      asn: "asn",
      save: "Save cache entry"
    },
    learning: {
      promotedActiveTitle: "Promoted active patterns",
      promotedStatsTitle: "Promoted stats",
      legacyTitle: "Legacy learning",
      support: "support {value}",
      precision: "precision {value}",
      total: "total {value}",
      confidence: "confidence {value}",
      plusOneConfidence: "+1 confidence",
      delete: "Delete"
    },
    cases: {
      title: "Cases"
    }
  },
  quality: {
    eyebrow: "Quality",
    title: "Noisy ASN, review volume, and active patterns",
    loadFailed: "Failed to load quality metrics",
    cards: {
      openCases: "Open cases",
      totalCases: "Total cases",
      resolvedHome: "Resolved HOME",
      resolvedMobile: "Resolved MOBILE",
      skipped: "Skipped",
      activePatterns: "Active patterns",
      activeSessions: "Active sessions",
      homeRatio: "HOME ratio",
      mobileRatio: "MOBILE ratio"
    },
    revision: "Rules revision {value}",
    updated: "Updated {value}",
    by: "By {value}",
    asnSourceTitle: "ASN source",
    noAsnSource: "No ASN source available",
    topNoisyAsnTitle: "Top noisy ASN",
    reviewCases: "{count} review cases",
    topPromotedPatternsTitle: "Top promoted patterns",
    topPatternDetails: "{decision} · support {support} · precision {precision}",
    learningStateTitle: "Learning state",
    promotedByTypeTitle: "Promoted learning by type",
    noPromotedData: "No promoted data yet",
    legacyByTypeTitle: "Legacy learning by type",
    noLegacyData: "No legacy learning data yet",
    topLegacyTitle: "Top legacy learning patterns",
    noLegacyPatterns: "No legacy patterns yet",
    learningCards: {
      promotedPatterns: "Promoted patterns",
      legacyPatterns: "Legacy patterns",
      legacyConfidence: "Legacy confidence",
      asnMinSupport: "ASN min support",
      asnMinPrecision: "ASN min precision",
      comboMinSupport: "Combo min support",
      comboMinPrecision: "Combo min precision"
    },
    patternStats: "{count} patterns · support {support} · avg precision {precision}",
    legacyStats: "{count} patterns · accumulated confidence {confidence}"
  },
  tooltips: {
    info: "Hint"
  },
  rulesMeta: {
    sections: {
      access: "Access",
      asnLists: "ASN Lists",
      keywords: "Keywords",
      thresholds: "Thresholds",
      scores: "Scores",
      behavior: "Behavior",
      policy: "Policy",
      learning: "Learning"
    },
    listFields: {
      admin_tg_ids: {
        label: "Admin Telegram IDs",
        description: "Telegram IDs allowed to log into the web panel.",
        recommendation: "Keep only panel moderators and admins here."
      },
      exempt_ids: {
        label: "Excluded System IDs",
        description: "System user.id values excluded from analysis and auto-sanctions.",
        recommendation: "Add only service or trusted accounts."
      },
      exempt_tg_ids: {
        label: "Excluded Telegram IDs",
        description: "Telegram IDs excluded from analysis and auto-sanctions.",
        recommendation: "Use this if Telegram ID is more convenient for exclusion management."
      },
      pure_mobile_asns: {
        label: "Pure mobile ASN list",
        description: "ASN values that are almost always mobile and provide a strong mobile signal.",
        recommendation: "Add ASN only after confirmed pure mobile samples."
      },
      pure_home_asns: {
        label: "Pure home ASN list",
        description: "ASN values that are almost always home and provide a strong home signal.",
        recommendation: "Only consistently home ASN values without mobile overlap should go here."
      },
      mixed_asns: {
        label: "Mixed ASN list",
        description: "ASN values with mixed profiles where extra signals and caution are required.",
        recommendation: "Use for disputed ASN values where ASN alone is not enough for a verdict."
      },
      allowed_isp_keywords: {
        label: "Mobile keywords",
        description: "Keywords that strengthen the mobile verdict when matched in ISP/hostname.",
        recommendation: "Keep short stable mobile markers here, without broad terms."
      },
      home_isp_keywords: {
        label: "Home keywords",
        description: "Keywords that push a decision toward home.",
        recommendation: "Add only markers of fixed/home providers."
      },
      exclude_isp_keywords: {
        label: "Datacenter / hosting keywords",
        description: "Keywords for detecting hosting, datacenters, and infrastructure networks.",
        recommendation: "Keep the list conservative to avoid matching regular providers."
      }
    },
    settingFields: {
      threshold_mobile: {
        label: "MOBILE decision threshold",
        description: "Score at which a case is considered confidently mobile.",
        recommendation: "A safe baseline is around 60."
      },
      threshold_probable_mobile: {
        label: "Probable mobile threshold",
        description: "Threshold for an intermediate mobile signal before final MOBILE.",
        recommendation: "Usually lower than the main mobile threshold."
      },
      threshold_home: {
        label: "HOME decision threshold",
        description: "Lower score after which a case is considered confidently home.",
        recommendation: "Higher values make home decisions more conservative."
      },
      threshold_probable_home: {
        label: "Probable home threshold",
        description: "Threshold for an intermediate home signal before final HOME.",
        recommendation: "Keep it between threshold_home and the neutral zone."
      },
      pure_asn_score: {
        label: "Pure mobile ASN bonus",
        description: "Score bonus if ASN is found in pure_mobile_asns.",
        recommendation: "Usually a strong bonus comparable to threshold_mobile."
      },
      mixed_asn_score: {
        label: "Mixed ASN bonus",
        description: "Score bonus for mixed ASN before considering extra signals.",
        recommendation: "Keep it noticeably below the pure mobile ASN bonus."
      },
      ptr_home_penalty: {
        label: "Home keyword penalty",
        description: "Penalty for home keywords in ISP/hostname.",
        recommendation: "A small minus so a keyword does not outweigh hard signals."
      },
      mobile_kw_bonus: {
        label: "Mobile keyword bonus",
        description: "Bonus for mobile keywords in ISP/hostname.",
        recommendation: "Keep it below the pure ASN bonus, but still meaningful."
      },
      ip_api_mobile_bonus: {
        label: "ip-api mobile bonus",
        description: "Additional bonus when fallback ip-api confirms a mobile network.",
        recommendation: "Use only as a finishing signal for mixed ASN."
      },
      pure_home_asn_penalty: {
        label: "Pure home ASN penalty",
        description: "Penalty when ASN appears in pure_home_asns.",
        recommendation: "Usually a strong penalty for confident HOME."
      },
      score_subnet_mobile_bonus: {
        label: "Subnet mobile bonus",
        description: "Bonus for historical mobile signals in the same subnet.",
        recommendation: "Keep it moderate to avoid overfitting rare subnets."
      },
      score_subnet_home_penalty: {
        label: "Subnet home penalty",
        description: "Penalty for historical home signals in a subnet.",
        recommendation: "Use as a correcting rather than dominant signal."
      },
      score_churn_high_bonus: {
        label: "High churn bonus",
        description: "Bonus for very high IP/session churn.",
        recommendation: "Use as a strong behavioral mobile signal."
      },
      score_churn_medium_bonus: {
        label: "Medium churn bonus",
        description: "Bonus for moderate IP/session churn.",
        recommendation: "Keep it clearly below the high churn bonus."
      },
      score_stationary_penalty: {
        label: "Stationary penalty",
        description: "Penalty for a user being stationary for too long.",
        recommendation: "Usually a soft penalty, not a hard stop."
      },
      concurrency_threshold: {
        label: "Concurrency threshold",
        description: "How many simultaneous users on an IP count as a mobile signal.",
        recommendation: "A common starting point is 2–3."
      },
      churn_window_hours: {
        label: "Churn window (hours)",
        description: "Window in hours used to calculate churn and IP switching.",
        recommendation: "Smaller windows react more strongly to spikes."
      },
      churn_mobile_threshold: {
        label: "Churn mobile threshold",
        description: "How many IP changes count as a mobile behavioral signal.",
        recommendation: "Tune against real mobile patterns without overreacting."
      },
      lifetime_stationary_hours: {
        label: "Stationary lifetime (hours)",
        description: "How long the same session can last before looking too home-like.",
        recommendation: "Increase it if you want fewer false home signals."
      },
      subnet_mobile_ttl_days: {
        label: "Subnet mobile TTL (days)",
        description: "How many days to keep mobile history for subnets.",
        recommendation: "Longer TTL increases memory and staleness risk."
      },
      subnet_home_ttl_days: {
        label: "Subnet home TTL (days)",
        description: "How many days to keep home history for subnets.",
        recommendation: "Usually lower than mobile TTL to forget noise faster."
      },
      subnet_mobile_min_evidence: {
        label: "Subnet mobile min evidence",
        description: "Minimum mobile evidence before enabling subnet mobile bonus.",
        recommendation: "Raise it when you have many noisy subnets."
      },
      subnet_home_min_evidence: {
        label: "Subnet home min evidence",
        description: "Minimum home evidence before enabling subnet home penalty.",
        recommendation: "Usually needs more confirmation than mobile."
      },
      shadow_mode: {
        label: "Shadow mode",
        description: "When enabled, the system analyzes and records cases without hard sanctions.",
        recommendation: "Safer rollouts usually start with true."
      },
      probable_home_warning_only: {
        label: "Probable home = warning only",
        description: "Limits probable home cases to warnings instead of punitive actions.",
        recommendation: "Recommended for a cautious mode."
      },
      auto_enforce_requires_hard_or_multi_signal: {
        label: "Require hard or multi-signal for auto-enforce",
        description: "Auto-sanctions are allowed only for strong or multi-signal HOME cases.",
        recommendation: "Safer to keep enabled."
      },
      review_ui_base_url: {
        label: "Review UI base URL",
        description: "Base URL of the web panel used in review links.",
        recommendation: "Set the production HTTPS URL of the panel."
      },
      live_rules_refresh_seconds: {
        label: "Live rules refresh interval",
        description: "How often the runtime reloads live rules from storage.",
        recommendation: "10–30 seconds is usually enough."
      },
      learning_promote_asn_min_support: {
        label: "Promoted ASN min support",
        description: "Minimum confirmed cases before ASN enters promoted learning.",
        recommendation: "Raise it if you want to avoid early overfitting."
      },
      learning_promote_asn_min_precision: {
        label: "Promoted ASN min precision",
        description: "Minimum precision for a promoted ASN pattern.",
        recommendation: "A conservative setup usually starts around 0.95."
      },
      learning_promote_combo_min_support: {
        label: "Promoted combo min support",
        description: "Minimum cases for a promoted combo pattern.",
        recommendation: "Usually lower than ASN support, but not too low."
      },
      learning_promote_combo_min_precision: {
        label: "Promoted combo min precision",
        description: "Minimum precision for a combo pattern.",
        recommendation: "Keep it high to avoid noisy combo bonuses."
      }
    },
    rulesGeneralFields: {
      usage_time_threshold: {
        label: "Minimum suspicious usage time (sec)",
        description: "How long a suspicious session must stay active before enforcement starts."
      },
      warning_timeout_seconds: {
        label: "Warning cooldown (sec)",
        description: "Minimum delay before the next warning can be sent."
      },
      warnings_before_ban: {
        label: "Warnings before first ban",
        description: "How many warning events are required before the first ban."
      },
      warning_only_mode: {
        label: "Only warnings mode",
        description: "Never escalate to bans automatically."
      },
      manual_review_mixed_home_enabled: {
        label: "Review mixed HOME cases manually",
        description: "Send mixed HOME outcomes to manual review before action."
      },
      manual_ban_approval_enabled: {
        label: "Require admin approval for bans",
        description: "Pause ban execution until admin approves it."
      },
      dry_run: {
        label: "Dry run",
        description: "Analyze and notify without applying remote disable actions."
      },
      ban_durations_minutes: {
        label: "Ban durations ladder (minutes)",
        description: "One duration per line: first ban, second ban, third ban, and so on."
      }
    },
    telegramFields: {
      tg_admin_chat_id: {
        label: "Admin chat destination",
        description: "Telegram chat id for admin notifications."
      },
      tg_topic_id: {
        label: "Admin thread/topic",
        description: "Optional topic/thread id inside the admin chat."
      },
      telegram_message_min_interval_seconds: {
        label: "Message interval (sec)",
        description: "Minimum delay between Telegram sends."
      },
      telegram_admin_notifications_enabled: {
        label: "Send admin notifications",
        description: "Master switch for all admin bot notifications."
      },
      telegram_user_notifications_enabled: {
        label: "Send user notifications",
        description: "Master switch for all user-facing bot messages."
      },
      telegram_admin_commands_enabled: {
        label: "Enable admin bot commands",
        description: "Allows Telegram admin command handlers to run."
      },
      telegram_notify_admin_review_enabled: {
        label: "Notify review cases",
        description: "Send admin messages when review/manual moderation is needed."
      },
      telegram_notify_admin_warning_only_enabled: {
        label: "Notify warning-only cases",
        description: "Send admin messages for non-escalating warning-only events."
      },
      telegram_notify_admin_warning_enabled: {
        label: "Notify warnings",
        description: "Send admin messages when a warning is issued."
      },
      telegram_notify_admin_ban_enabled: {
        label: "Notify bans",
        description: "Send admin messages when a ban is issued."
      },
      telegram_notify_user_warning_only_enabled: {
        label: "Send warning-only messages",
        description: "Send user-facing messages for non-escalating warning-only events."
      },
      telegram_notify_user_warning_enabled: {
        label: "Send warning messages",
        description: "Send user-facing messages when a warning is issued."
      },
      telegram_notify_user_ban_enabled: {
        label: "Send ban messages",
        description: "Send user-facing messages when a ban is issued."
      }
    },
    telegramTemplateFields: {
      user_warning_only_template: {
        label: "Warning-only message",
        description: "User-facing message when the case is warning-only and does not escalate."
      },
      user_warning_template: {
        label: "Warning message",
        description: "User-facing message for standard warnings before a ban."
      },
      user_ban_template: {
        label: "Ban message",
        description: "User-facing message sent when a ban is applied."
      },
      admin_warning_only_template: {
        label: "Warning-only message",
        description: "Admin notification text for warning-only cases."
      },
      admin_warning_template: {
        label: "Warning message",
        description: "Admin notification text for warning events."
      },
      admin_ban_template: {
        label: "Ban message",
        description: "Admin notification text for ban events."
      },
      admin_review_template: {
        label: "Review message",
        description: "Admin notification text for review/manual moderation cases."
      }
    }
  }
};
