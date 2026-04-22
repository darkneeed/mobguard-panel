import type { TranslationDictionary } from "../types";

export const enDictionary: TranslationDictionary = {
  common: {
    loading: "Loading…",
    loadingLabel: "Loading",
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
    fieldHintLabel: "{field} hint",
    present: "present",
    missing: "missing",
    writable: "writable",
    readOnly: "read only",
    envFile: ".env file",
    currentValue: "Current value",
    newValue: "New value",
    secretValueStored: "Stored on the server as a masked secret.",
    runtimeValue: "Runtime value managed through .env.",
    leaveBlankToKeep: "Leave blank to keep the current secret value",
    restartRequired: "restart required",
    close: "Close"
  },
  layout: {
    brandSubtitle: "Admin panel",
    consoleBadge: "Hybrid console",
    consoleDescription: "Remnawave-style operator flow with Bedolaga polish.",
    groups: {
      monitor: "Monitor",
      configure: "Configure",
      operate: "Operate"
    },
    nav: {
      overview: "Overview",
      modules: "Modules",
      queue: "Queue",
      rules: "Detection Rules",
      telegram: "Telegram",
      access: "Access",
      data: "Data",
      quality: "Quality"
    },
    subnav: {
      rules: {
        general: "General",
        thresholds: "Thresholds",
        lists: "Lists",
        providers: "Providers",
        policy: "Policy",
        learning: "Learning",
        retention: "Retention"
      },
      data: {
        users: "Users",
        violations: "Violations",
        overrides: "Overrides",
        cache: "Cache",
        learning: "Learning",
        cases: "Cases",
        exports: "Exports",
        audit: "Audit"
      }
    },
    theme: {
      label: "Theme",
      system: "System",
      light: "Light",
      dark: "Dark"
    },
    palette: {
      label: "Palette",
      green: "Green",
      orange: "Orange",
      blue: "Blue",
      purple: "Purple",
      red: "Red"
    },
    language: {
      label: "Language",
      ru: "rus",
      en: "eng"
    },
    logout: "Logout"
  },
  overview: {
    eyebrow: "Operator Overview",
    title: "System health, queue pressure, and runtime posture",
    description: "One screen for live state, moderation pressure, learning quality, and risky hotspots.",
    lastUpdated: "Last synced {value}",
    errors: {
      loadFailed: "Failed to load overview data"
    },
    systemStatusTitle: "Live operator status",
    systemStatusDescription: "Core, queue, runtime rules, and export readiness in one glance.",
    healthTitle: "Health snapshot",
    healthDescription: "Back-end heartbeat and control-plane status.",
    health: {
      core: "Scoring runtime",
      db: "Database",
      rules: "Live rules",
      embedded: "embedded",
      embeddedRuntime: "Embedded in the panel API process · updated {value}",
      updated: "Updated {value}",
      rulesBy: "Updated by {value}"
    },
    cards: {
      openQueue: "Open queue",
      core: "Scoring runtime",
      embeddedValue: "embedded",
      ipinfo: "IPINFO token",
      adminSessions: "Admin sessions",
      scoreZeroRatio: "Score zero ratio (24h)",
      asnMissingRatio: "ASN missing ratio (24h)",
      mixedConflicts: "Mixed-provider conflicts",
      promotedPatterns: "Promoted patterns"
    },
    quickLinks: {
      queue: "Open queue",
      quality: "Go to quality",
      policy: "Review policy",
      exports: "Calibration exports"
    },
    mixedProvidersTitle: "Top mixed providers",
    mixedProvidersDescription: "Providers that keep landing in review-first or conflict-heavy states.",
    mixedProvidersItem: "{open} open · {conflict} conflicts · {home} HOME · {mobile} MOBILE",
    mixedProvidersMetrics: {
      open: "Open",
      conflicts: "Conflicts",
      home: "HOME",
      mobile: "MOBILE"
    },
    emptyMixedProviders: "No mixed-provider hotspots right now.",
    noisyAsnTitle: "Noisy ASNs",
    noisyAsnDescription: "ASNs contributing the largest moderation load.",
    noisyAsnItem: "{count} review cases",
    emptyNoisyAsn: "No noisy ASN data yet.",
    latestCasesTitle: "Latest queue cases",
    latestCasesDescription: "Fresh disputed cases ready for operator action.",
    emptyLatestCases: "No open queue items right now."
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
    localAuthFailed: "Local auth failed",
    totp: {
      setupTitle: "Set up owner TOTP",
      verifyTitle: "Owner TOTP verification",
      setupDescription: "Save the secret in your authenticator app, then confirm with a 6-digit code.",
      verifyDescription: "Enter the 6-digit owner TOTP code to finish login.",
      secretLabel: "Secret",
      issuerLabel: "Issuer",
      accountLabel: "Account",
      uriLabel: "Provisioning URI",
      codePlaceholder: "123456",
      confirmButton: "Confirm TOTP setup",
      verifyButton: "Verify code",
      cancelButton: "Cancel",
      processing: "Checking…",
      failed: "TOTP verification failed"
    }
  },
  reviewQueue: {
    eyebrow: "Review Queue",
    title: "Disputed decisions and manual moderation",
    description: "Explicit filters, bulk resolution, and a denser operator workflow for live queue handling.",
    countSummary: "{count} cases · page {page}",
    lastUpdated: "Updated {value}",
    searchPlaceholder: "Quick search by IP / username / ISP / UUID / IDs",
    clearFilters: "Reset filters",
    savedFilters: {
      save: "Save current",
      apply: "Apply saved",
      clear: "Clear saved",
      saved: "Saved current queue filters",
      applied: "Applied saved queue filters",
      cleared: "Saved queue filters cleared",
      invalid: "Saved queue filters are invalid"
    },
    toggleFiltersTitle: "Toggle filters",
    filtersButton: "Filters",
    filterCount: "Filters ({count})",
    presets: {
      open: "Open only",
      providerConflict: "Provider conflict",
      critical: "Critical",
      punitive: "Punitive"
    },
    filters: {
      moduleId: "Module ID",
      username: "Username",
      systemId: "System ID",
      telegramId: "Telegram ID",
      repeatMin: "Repeat count min",
      repeatMax: "Repeat count max",
      statusOpen: "OPEN",
      statusResolved: "RESOLVED",
      statusSkipped: "SKIPPED",
      allStatus: "All status",
      confidenceUnsure: "UNSURE",
      confidenceProbableHome: "PROBABLE_HOME",
      confidenceHighHome: "HIGH_HOME",
      allConfidence: "All confidence",
      reasonUnsure: "unsure",
      reasonProbableHome: "probable_home",
      reasonHomeRequiresReview: "home_requires_review",
      reasonManualMixedHome: "manual_review_mixed_home",
      reasonProviderConflict: "provider_conflict",
      allReasons: "All reasons",
      severityCritical: "critical",
      severityHigh: "high",
      severityMedium: "medium",
      severityLow: "low",
      allSeverity: "All severity",
      punitiveAny: "Punitive any",
      punitiveOnly: "punitive only",
      reviewOnly: "review only",
      sortPriorityDesc: "priority desc",
      sortPriorityAsc: "priority asc",
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
      module: "Module",
      system: "System",
      telegram: "TG",
      uuid: "UUID"
    },
    card: {
      ip: "IP",
      ipInventory: "{count} linked IPs",
      ipSeen: "First seen {first} · last seen {last}",
      asn: "ASN",
      asnValue: "AS{value}",
      decision: "Decision",
      provider: "provider {value}",
      serviceHint: "service {value}",
      providerConflict: "Provider conflict",
      reviewFirst: "Review-first",
      autoReady: "Auto-ready",
      moduleCount: "{count} modules",
      punitiveEligible: "punitive eligible",
      reviewOnly: "review only",
      priority: "priority {value}",
      usageSignals: "usage {count}",
      repeat: "repeat x{count}",
      ongoing: "ongoing {value}",
      opened: "opened {value}"
    },
    pageSize: {
      label: "Cards per page",
      option: "{value}"
    },
    actions: {
      mobile: "Mobile",
      home: "Home",
      skip: "Skip",
      openCase: "Open case",
      bulkMobile: "Set selected to MOBILE",
      bulkHome: "Set selected to HOME",
      bulkSkip: "Skip selected",
      recheckVisible: "Recheck visible",
      recheckDone: "Rechecked {count} queue cases",
      processing: "Processing…",
      saved: "Review decision saved",
      bulkSaved: "{count} selected cases resolved"
    },
    selection: {
      selectPage: "Select page",
      clearPage: "Clear page selection",
      selectedCount: "{count} selected"
    },
    footer: {
      previous: "Prev",
      next: "Next",
      pageSummary: "Page {page} · showing {shown} of {total}"
    }
  },
  modules: {
    eyebrow: "Fleet",
    title: "MobGuard Modules",
    description: "Manage provisioned collector modules, per-module INBOUND tags, and the latest runtime health snapshot.",
    count: "{count} modules",
    loadFailed: "Failed to load modules",
    listTitle: "Provisioned modules",
    listDescription: "Create the module card first, then connect the collector and watch its health/error state.",
    selectionHint: "Select a module or create a new one",
    empty: "No modules created yet",
    create: "Create module",
    save: "Save changes",
    open: "Open details",
    createTitle: "Create module card",
    createDescription: "Set the display name and per-module INBOUND tags. The panel will generate module_id and API token after save.",
    detailsTitle: "Module details",
    detailsDescription: "Edit the module name and INBOUND tags. Updated tags are delivered through remote config without changing auth or install flow.",
    createSuccess: "Module created",
    updateSuccess: "Module updated",
    saveFailed: "Failed to save module",
    pendingInstall: "pending install",
    stale: "stale",
    inboundTags: "INBOUND tags",
    lastSeen: "Last heartbeat",
    appliedRevision: "Applied revision",
    openCases: "Open cases",
    analysisEvents: "Analysis events",
    version: "Version {value}",
    protocol: "Protocol {value}",
    moduleId: "Module ID: {value}",
    generatedAfterCreate: "Generated after create",
    healthTitle: "Runtime health",
    healthDescription: "The panel shows the latest self-reported module validation state and derived stale status.",
    healthStatus: "Health status",
    lastValidationAt: "Last validation",
    spoolDepth: "Spool depth",
    accessLogExists: "Access log exists",
    healthEmpty: "Create or open a module to see the latest runtime health.",
    installTitle: "Install bundle",
    installDescription: "Copy the generated compose, reveal the token, and edit ACCESS_LOG_PATH locally only if the node uses a non-default log path.",
    installPreviewEmpty: "Create or open a module to see its generated docker-compose.yml",
    revealToken: "Reveal token",
    tokenRevealSuccess: "Module token revealed",
    tokenRevealFailed: "Failed to reveal module token",
    tokenUnavailable: "Token reveal is unavailable for this module. Legacy modules only store the auth hash.",
    tokenTitle: "Module token",
    tokenDescription: "Paste this token into MODULE_TOKEN in the generated compose file before start.",
    tokenValue: "Revealed token",
    copyToken: "Copy token",
    tokenCopied: "Token copied to clipboard",
    copyCompose: "Copy compose",
    composeCopied: "docker-compose.yml copied to clipboard",
    copyFailed: "Failed to copy to clipboard",
    installSteps: {
      clone: "Clone the module repo on the target node and open its root directory.",
      compose: "Replace the local docker-compose.yml with the generated compose preview below.",
      token: "Reveal the token in the panel and replace MODULE_TOKEN=__PASTE_TOKEN__ before start.",
      start: "Run docker compose up -d && docker compose logs -f -t, then wait for the module to move online."
    },
    health: {
      ok: "ok",
      warn: "warn",
      error: "error"
    },
    fields: {
      moduleName: "Display name",
      moduleId: "Generated module ID",
      inboundTags: "INBOUND tags"
    },
    cards: {
      total: "Total modules",
      pending: "Pending install",
      error: "Error",
      stale: "Stale"
    }
  },
  reviewDetail: {
    eyebrow: "Case Detail",
    title: "Review case #{caseId}",
    description: "Evidence, linked history, and a sticky resolution rail for fast moderation.",
    loading: "Loading…",
    backToQueue: "Back to queue",
    queuePosition: "Queue {current}/{total}",
    keyboardHint: "[ prev ] next · M/H/S resolve",
    copySuccess: "Copied to clipboard",
    copyFailed: "Failed to copy",
    errors: {
      resolveFailed: "Resolve failed"
    },
    sections: {
      summary: "Summary",
      reasons: "Reasons",
      providerEvidence: "Provider evidence",
      ipInventory: "Linked IP inventory",
      moduleInventory: "Touched modules",
      usageProfile: "Usage profile",
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
      skip: "Skip",
      saved: "Review decision saved"
    },
    summaryHint: "Fast identifiers and review context without digging through raw payloads.",
    resolutionHint: "This note is written into the audit trail together with the chosen outcome.",
    copyIp: "Copy IP",
    copyUuid: "Copy UUID",
    copyTelegram: "Copy Telegram ID",
    openReviewUrl: "Open review URL",
    providerEvidence: {
      conflict: "Conflicting service markers",
      clear: "No direct marker conflict",
      reviewFirst: "Review-first recommended",
      autoReady: "Has enough signals for automation",
      homeSources: "Supporting HOME sources",
      mobileSources: "Supporting MOBILE sources",
      matchedAliases: "Matched aliases",
      mobileMarkers: "Matched mobile markers",
      homeMarkers: "Matched home markers"
    },
    usageProfile: {
      empty: "No usage-profile evidence yet",
      summary: "Snapshot",
      devices: "Devices",
      osFamilies: "OS families",
      nodes: "Node spread",
      softReasons: "Soft reasons",
      geo: "Geo history",
      travel: "Travel anomalies",
      countryJumpOnly: "country jump only",
      topIps: "Top recent IPs",
      topProviders: "Top providers",
      recentLocations: "Recent locations",
      impossibleTravel: "Impossible travel",
      ongoing: "Ongoing duration",
      lastSeen: "Last seen",
      updatedAt: "Updated"
    },
    ipInventory: {
      summary: "{count} hits · {isp} · AS{asn}",
      firstSeen: "First seen {value}",
      lastSeen: "Last seen {value}"
    },
    moduleInventory: {
      moduleId: "Module ID {value}",
      firstSeen: "First seen {value}",
      lastSeen: "Last seen {value}"
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
      description: "Runtime escalation and access switching controls.",
      save: "Save general settings"
    },
    sectionTitles: {
      thresholds: "Thresholds, scores, and behavior",
      policy: "Detection policy",
      learning: "Learning controls",
      retention: "Database retention"
    },
    sectionDescriptions: {
      general: "Runtime-wide escalation, warning, and access switching settings in one dedicated place.",
      thresholds: "Decision thresholds, score weights, and behavior windows tuned in one place.",
      lists: "ASN and keyword lists that shape primary evidence and exclusions.",
      providers: "Provider aliases, markers, and carrier-specific hints used in review-first flows.",
      policy: "Live decision policy plus enforcement-side access switching controls.",
      learning: "Promotion thresholds that decide when runtime learning becomes trusted.",
      retention: "Storage retention windows that cap SQLite growth without removing active review state."
    },
    providerProfiles: {
      description: "Carrier-specific aliases and service markers for mixed-provider review-first scoring.",
      add: "Add provider profile",
      remove: "Remove profile",
      empty: "No provider profiles configured yet.",
      cardTitle: "Provider profile #{index}",
      cardSubtitle: "One alias or marker per line. ASN values should stay numeric.",
      classifications: {
        mixed: "Mixed",
        mobile: "Mobile",
        home: "Home"
      },
      validation: {
        missingKey: "Provider profile #{index}: key is required"
      },
      fields: {
        key: {
          label: "Profile key",
          description: "Stable identifier used in learning labels and quality metrics."
        },
        classification: {
          label: "Classification",
          description: "Mixed profiles stay review-first until another independent factor confirms the verdict."
        },
        aliases: {
          label: "Aliases",
          description: "Carrier names, brands, PTR fragments, or org aliases matched in ISP/hostname."
        },
        mobile_markers: {
          label: "Mobile service markers",
          description: "Service-specific hints that indicate a mobile side of this provider."
        },
        home_markers: {
          label: "Home service markers",
          description: "Service-specific hints that indicate a fixed/home side of this provider."
        },
        asns: {
          label: "ASN list",
          description: "ASN values associated with this provider profile."
        }
      }
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
    saveEnv: "Save .env settings",
    saveTemplates: "Save message templates",
    settingsSaved: "Telegram settings saved",
    envSaved: "Telegram .env settings saved",
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
      "Multiline text is preserved.\n\nPlaceholders: {{username}}, {{warning_count}}, {{warnings_left}}, {{ban_text}}, {{review_url}}, {{usage_profile_summary}}.",
    userTemplates: "User templates",
    adminTemplates: "Admin templates",
    envTitle: "Telegram .env",
    envDescription: "Bot tokens and usernames are edited separately from live runtime settings.",
    envCount: "{present} of {total} configured",
    cards: {
      adminBot: "Admin bot",
      userBot: "User bot",
      adminBotConfigured: "Admin bot token + username",
      userBotConfigured: "User bot token",
      envFile: "Env file state"
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
    saveEnv: "Save .env settings",
    saved: "Access settings saved",
    envSaved: "Access .env settings saved",
    loadFailed: "Failed to load access settings",
    saveFailed: "Save failed",
    invalidNumericValue: "Invalid numeric value '{value}'",
    cards: {
      telegramLogin: "Telegram login",
      localFallback: "Local fallback login",
      envFile: "Env file state"
    },
    authStatusTitle: "Authentication status",
    authStatusDescription: "Credentials are managed only through `.env` on the server.",
    authCards: {
      telegramPanel: "Telegram panel auth",
      localFallback: "Local fallback auth"
    },
    brandingTitle: "Service branding",
    brandingDescription: "Set the service name and logo URL used across login, loading, and the operator shell.",
    brandingSaved: "Branding updated",
    saveBranding: "Save branding",
    brandingFields: {
      serviceName: "Service name",
      serviceNameDescription: "Visible service name in the panel shell and login screen.",
      logoUrl: "Logo URL",
      logoUrlDescription: "Public image URL for the service logo. Leave empty to use the default built-in logo.",
      logoUrlPlaceholder: "https://example.com/logo.png"
    },
    listsTitle: "Access lists",
    listsDescription: "Panel admins and runtime exclusions are managed separately.",
    envTitle: "Access .env",
    envDescription: "Local fallback credentials live in `.env` and require explicit replacement for secrets.",
    envCount: "{present} of {total} configured"
  },
  data: {
    eyebrow: "Data",
    title: "Operational runtime data admin",
    sectionDescriptions: {
      users: "Primary operator workflow for user lookup, card inspection, exemptions, restrictions, and export snapshots.",
      violations: "Global view of active restrictions and violation history stored in runtime state.",
      overrides: "Manual IP and unsure-pattern overrides that short-circuit detection decisions.",
      cache: "Live cache entries that can be corrected or removed without waiting for natural expiry.",
      learning: "Promoted patterns, legacy confidence rows, and provider-learning slices.",
      cases: "Recent review cases with a compact operator jump-list into full detail.",
      exports: "Calibration archive generation with dataset readiness and manifest visibility.",
      audit: "Operator action history for moderation, data mutations, settings, and module operations."
    },
    tabs: {
      users: "users",
      violations: "violations",
      overrides: "overrides",
      cache: "cache",
      learning: "learning",
      cases: "cases",
      exports: "exports",
      audit: "audit"
    },
    errors: {
      loadTabFailed: "Failed to load data tab",
      searchUsersFailed: "User search failed",
      loadUserFailed: "Failed to load user card",
      userActionFailed: "User action failed",
      exportUserFailed: "Failed to build user export card",
      exportCalibrationFailed: "Failed to generate calibration export",
      saveExactOverrideFailed: "Failed to save exact override",
      saveUnsureOverrideFailed: "Failed to save unsure override",
      saveCacheFailed: "Failed to update cache entry"
    },
    saved: {
      userUpdated: "User data updated",
      exactOverride: "Exact override saved",
      unsureOverride: "Unsure override saved",
      cacheUpdated: "Cache entry updated",
      learningUpdated: "Learning data updated",
      exportReady: "Export card is ready",
      exportDownloaded: "Export card downloaded",
      calibrationExportReady: "Calibration archive generated"
    },
    users: {
      searchPlaceholder: "Search uuid / system id / telegram id / username",
      search: "Search",
      searching: "Searching…",
      panelMatch: "Panel match: {value}",
      systemLabel: "sys:{value}",
      telegramLabel: "tg:{value}",
      cardTitle: "User card",
      exportHint: "Build a structured export snapshot for calibration or offline review.",
      buildExport: "Build export card",
      generatingExport: "Generating…",
      downloadExport: "Download JSON",
      exportPreviewTitle: "Export preview",
      exportGeneratedAt: "Generated {value}",
      actionsTitle: "User actions",
      analysisTitle: "Recent analysis & provider evidence",
      analysisEmpty: "No recent analysis events",
      usageProfileTitle: "Usage profile",
      usageProfileEmpty: "No usage-profile evidence yet",
      usageProfileSummary: "Snapshot",
      usageProfileOngoing: "Ongoing duration",
      usageProfileDevices: "Devices",
      usageProfileOs: "OS families",
      usageProfileNodes: "Node spread",
      usageProfileSignals: "Soft reasons",
      usageProfileGeo: "Geo history",
      usageProfileTravel: "Travel anomalies",
      usageProfileCountryJumpOnly: "country jump only",
      usageProfileTopIps: "Top recent IPs",
      usageProfileTopProviders: "Top providers",
      openCasesTitle: "Open / recent review cases",
      openCasesEmpty: "No local review cases",
      historyTitle: "Violation history",
      historyEmpty: "No violation history",
      providerConflict: "Conflicting provider markers",
      providerClear: "Provider markers are consistent",
      reviewFirst: "Review-first",
      autoReady: "Second factor present",
      exportCards: {
        reviewCases: "Review cases",
        analysisEvents: "Analysis events",
        history: "History",
        ipHistory: "IP history"
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
        username: "Username",
        uuid: "UUID",
        systemId: "System ID",
        telegramId: "Telegram ID",
        panelStatus: "Panel status",
        panelSquads: "Active squads",
        trafficLimitBytes: "Traffic limit",
        trafficLimitStrategy: "Traffic limit strategy",
        usedTrafficBytes: "Current used traffic",
        lifetimeUsedTrafficBytes: "Lifetime used traffic",
        exemptSystemId: "Exempt system ID",
        exemptTelegramId: "Exempt Telegram ID",
        activeBan: "Active access restriction",
        activeWarning: "Active warning"
      },
      actions: {
        banMinutes: "Restriction minutes",
        startBan: "Restrict access",
        unban: "Restore full access",
        trafficCapGigabytes: "Traffic cap: +GB from current usage",
        applyTrafficCap: "Apply traffic cap",
        restoreTrafficCap: "Restore previous limit",
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
      activeTitle: "Active violations / access restrictions",
      historyTitle: "Violation history",
      strikes: "strikes {value}",
      warningCount: "warning_count {value}",
      unban: "restore {value}",
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
    decisions: {
      home: "HOME",
      mobile: "MOBILE",
      skip: "SKIP"
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
      asnValue: "ASN {value}",
      save: "Save cache entry"
    },
    learning: {
      promotedActiveTitle: "Promoted active patterns",
      promotedStatsTitle: "Promoted stats",
      legacyTitle: "Legacy learning",
      providerActiveTitle: "Promoted provider patterns",
      providerServiceActiveTitle: "Promoted provider service patterns",
      providerLegacyTitle: "Legacy provider patterns",
      empty: "No provider-specific learning data yet",
      support: "support {value}",
      precision: "precision {value}",
      total: "total {value}",
      confidence: "confidence {value}",
      plusOneConfidence: "+1 confidence",
      delete: "Delete"
    },
    audit: {
      title: "Operator audit trail",
      description: "Read-only log of admin actions that changed moderation state, rules, settings, or modules.",
      empty: "No audit events yet"
    },
    cases: {
      title: "Cases"
    },
    exports: {
      title: "Calibration export",
      description: "Generate a ZIP archive with raw resolved rows and summaries for rule tuning.",
      generating: "Generating…",
      generate: "Generate ZIP",
      lastManifestTitle: "Last export manifest",
      readinessTitle: "Calibration readiness",
      readinessDescription: "Live preview shows how ready the export is for learning and scoring adjustments.",
      noManifest: "No readiness preview available yet",
      datasetReady: "Dataset is structurally ready for analysis",
      datasetNotReady: "Dataset is not ready for reliable provider calibration",
      tuningReady: "Provider tuning can start from this export",
      tuningNotReady: "Provider tuning is still blocked by coverage/support",
      blockersTitle: "Readiness blockers",
      noBlockers: "No critical blockers right now",
      checksTitle: "Current readiness checks",
      warningsTitle: "Readiness warnings",
      notReadyToast: "Calibration archive generated, but readiness checks failed",
      filterSnapshot: "Applied filters",
      coverageSnapshot: "Coverage snapshot",
      filters: {
        openedFrom: "Opened from",
        openedTo: "Opened to",
        reviewReason: "Review reason",
        providerKey: "Provider key",
        status: "Dataset status",
        includeUnknown: "Include unknown in aggregates"
      },
      status: {
        resolvedOnly: "Resolved only",
        openOnly: "Open only",
        all: "All cases"
      },
      cards: {
        overallReadiness: "Overall readiness",
        datasetReadiness: "Dataset readiness",
        tuningReadiness: "Tuning readiness",
        file: "Archive",
        rawRows: "Raw rows",
        knownRows: "Known rows",
        unknownRows: "Unknown rows",
        providerProfiles: "Provider profiles",
        providerCoverage: "Provider key coverage",
        patternCandidates: "Provider pattern candidates"
      },
      readiness: {
        checks: {
          provider_profiles_present: "Provider profiles in snapshot",
          resolved_ratio: "Resolved ratio",
          provider_evidence_coverage: "Provider explainability coverage",
          provider_key_coverage: "Provider key coverage",
          min_provider_support: "Minimum provider support"
        }
      },
      warnings: {
        live_rules_stale_or_unseeded: "Live rules snapshot was empty and had to be merged from runtime config.",
        provider_profiles_missing: "No provider profiles were present in the export snapshot.",
        provider_key_coverage_zero: "Resolved rows contain zero provider keys.",
        provider_explainability_missing: "Provider explainability is missing in exported rows.",
        resolved_ratio_below_threshold: "Too many pending rows: resolved ratio is below the safety threshold.",
        provider_key_coverage_below_target: "Provider key coverage is below the target 0.6 threshold.",
        provider_support_below_target: "At least one provider/provider_service candidate has fewer than 5 known resolved cases."
      }
    }
  },
  quality: {
    eyebrow: "Quality",
    title: "Noisy ASN, review volume, and active patterns",
    description: "Charts and ranked cards for resolution mix, noisy ASN pressure, and learning health.",
    allModules: "All modules",
    loadFailed: "Failed to load quality metrics",
    cards: {
      openCases: "Open cases",
      totalCases: "Total cases",
      resolvedHome: "Resolved HOME",
      resolvedMobile: "Resolved MOBILE",
      skipped: "Skipped",
      activePatterns: "Active patterns",
      activeSessions: "Active sessions",
      mixedProviderCases: "Mixed-provider open cases",
      mixedConflictRate: "Mixed-provider conflict rate",
      homeRatio: "HOME ratio",
      mobileRatio: "MOBILE ratio"
    },
    revision: "Rules revision {value}",
    updated: "Updated {value}",
    by: "By {value}",
    asnSourceTitle: "ASN source",
    noAsnSource: "No ASN source available",
    resolutionMixTitle: "Resolution mix",
    resolutionMixDescription: "How human operators are resolving disputed decisions right now.",
    topNoisyAsnTitle: "Top noisy ASN",
    noisyAsnDescription: "The ASNs that currently create the most review pressure.",
    topMixedProvidersTitle: "Top mixed providers by open cases",
    mixedProvidersDescription: "Providers with the highest open-case load and conflict pressure.",
    noMixedProviders: "No mixed-provider backlog yet",
    mixedProviderStats: "{open} open · {conflict} conflicts · HOME {home} · MOBILE {mobile} · UNSURE {unsure}",
    reviewCases: "{count} review cases",
    topPromotedPatternsTitle: "Top promoted patterns",
    topPatternDetails: "{decision} · support {support} · precision {precision}",
    learningStateTitle: "Learning state",
    providerLearningTitle: "Provider learning",
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
    providerLearning: {
      promoted: "Promoted provider patterns",
      legacy: "Legacy provider patterns"
    },
    patternStats: "{count} patterns · support {support} · avg precision {precision}",
    legacyStats: "{count} patterns · accumulated confidence {confidence}",
    legacyConfidenceValue: "confidence {value}"
  },
  tooltips: {
    info: "Hint"
  },
  rulesMeta: {
    sections: {
      access: "Access",
      asnLists: "ASN Lists",
      keywords: "Keywords",
      providers: "Provider Profiles",
      thresholds: "Thresholds",
      scores: "Scores",
      behavior: "Behavior",
      policy: "Policy",
      learning: "Learning",
      retention: "Retention"
    },
    listFields: {
      admin_tg_ids: {
        label: "Owner Telegram IDs",
        description: "Telegram IDs mapped to the owner role with full platform control.",
        recommendation: "Keep this list short and highly trusted."
      },
      moderator_tg_ids: {
        label: "Moderator Telegram IDs",
        description: "Telegram IDs allowed to resolve queue items and mutate data-admin state without touching platform settings.",
        recommendation: "Use for operators responsible for moderation and runtime data correction."
      },
      viewer_tg_ids: {
        label: "Viewer Telegram IDs",
        description: "Telegram IDs allowed to inspect overview, quality, modules, queue, data, and audit in read-only mode.",
        recommendation: "Use for analysts and support staff who should not mutate state."
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
      provider_mobile_marker_bonus: {
        label: "Provider mobile marker bonus",
        description: "Bonus applied when a provider profile matches a mobile service marker.",
        recommendation: "Use as a moderate signal and wait for a second factor before automation on mixed providers."
      },
      provider_home_marker_penalty: {
        label: "Provider home marker penalty",
        description: "Penalty applied when a provider profile matches a fixed/home service marker.",
        recommendation: "Keep it meaningful, but do not let a single carrier marker auto-punish a mixed provider."
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
      provider_conflict_review_only: {
        label: "Review mixed provider conflicts only",
        description: "Keep mixed-provider conflicts, missing service markers, and single-factor carrier hints in manual review.",
        recommendation: "Recommended for review-first rollout of ambiguous carriers."
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
      db_cleanup_interval_minutes: {
        label: "DB cleanup interval (minutes)",
        description: "How often the API process runs the periodic SQLite maintenance pass.",
        recommendation: "30 minutes is a safe default for steady-state cleanup."
      },
      module_heartbeats_retention_days: {
        label: "Module heartbeat retention (days)",
        description: "How long to keep historical module heartbeat rows before pruning them.",
        recommendation: "Keep it short because current module status is stored in the modules table."
      },
      ingested_raw_events_retention_days: {
        label: "Raw ingested event retention (days)",
        description: "How long to keep ingested module events once they are old enough for normal operations.",
        recommendation: "30 days is a practical default unless you rely on long replay windows."
      },
      ip_history_retention_days: {
        label: "IP history retention (days)",
        description: "How many days of behavioral IP history to preserve for churn and long-window analysis.",
        recommendation: "Keep this aligned with the longest history-based scoring window you actually trust."
      },
      orphan_analysis_events_retention_days: {
        label: "Orphan analysis event retention (days)",
        description: "How long to keep analysis events that are no longer referenced by any review case.",
        recommendation: "A shorter window limits growth while keeping recent operator context available."
      },
      resolved_review_retention_days: {
        label: "Resolved review retention (days)",
        description: "How long to keep resolved or skipped review cases and related audit history.",
        recommendation: "Use the long audit window here; active OPEN cases are never pruned by this setting."
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
        label: "Warnings before first restriction",
        description: "How many warning events are required before the first access restriction."
      },
      warning_only_mode: {
        label: "Only warnings mode",
        description: "Never escalate to access restrictions automatically."
      },
      manual_review_mixed_home_enabled: {
        label: "Review mixed HOME cases manually",
        description: "Send mixed HOME outcomes to manual review before action."
      },
      manual_ban_approval_enabled: {
        label: "Require approval for restrictions",
        description: "Pause access restriction until an admin approves it."
      },
      dry_run: {
        label: "Dry run",
        description: "Analyze and notify without applying remote squad switching."
      },
      ban_durations_minutes: {
        label: "Restriction ladder (minutes)",
        description: "One duration per line: first restriction, second restriction, third restriction, and so on."
      },
      full_access_squad_name: {
        label: "Full-access squad name",
        description: "Exact Remnawave internal squad name used for normal full access."
      },
      restricted_access_squad_name: {
        label: "Restricted squad name",
        description: "Exact Remnawave internal squad name assigned when a violation is enforced."
      },
      traffic_cap_increment_gb: {
        label: "Traffic cap increment (GB)",
        description: "How many gigabytes to add on top of the user’s current used traffic."
      },
      traffic_cap_threshold_gb: {
        label: "Traffic cap threshold (GB)",
        description: "If the user has already spent at least this amount, apply traffic cap instead of hiding mobile configs."
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
        label: "Notify access restrictions",
        description: "Send admin messages when an access restriction is applied."
      },
      telegram_notify_admin_usage_profile_risk_enabled: {
        label: "Notify usage-profile risk",
        description: "Send admin messages for enriched usage-profile risk snapshots."
      },
      telegram_notify_admin_violation_continues_enabled: {
        label: "Notify ongoing violations",
        description: "Send admin messages when suspicious behaviour continues over time."
      },
      telegram_notify_admin_traffic_limit_exceeded_enabled: {
        label: "Notify traffic-limit exceeded",
        description: "Send admin messages when traffic-cap restriction is used."
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
        label: "Send restriction messages",
        description: "Send user-facing messages when an access restriction is applied."
      }
    },
    telegramTemplateFields: {
      user_warning_only_template: {
        label: "Warning-only message",
        description: "User-facing message when the case is warning-only and does not escalate."
      },
      user_warning_template: {
        label: "Warning message",
        description: "User-facing message for standard warnings before an access restriction."
      },
      user_ban_template: {
        label: "Access restriction message",
        description: "User-facing message sent when an access restriction is applied."
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
        label: "Access restriction message",
        description: "Admin notification text for access restriction events."
      },
      admin_review_template: {
        label: "Review message",
        description: "Admin notification text for review/manual moderation cases."
      },
      admin_usage_profile_risk_template: {
        label: "Usage-profile risk message",
        description: "Admin notification text for enriched usage-profile risk snapshots."
      },
      admin_violation_continues_template: {
        label: "Violation-continues message",
        description: "Admin notification text when suspicious behaviour keeps going."
      },
      admin_traffic_limit_exceeded_template: {
        label: "Traffic-limit-exceeded message",
        description: "Admin notification text when traffic-cap restriction is used."
      }
    }
  }
};
