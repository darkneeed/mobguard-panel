import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { api, CalibrationExportPreview, CalibrationReadinessCheck } from "../api/client";
import { useToast } from "../components/ToastProvider";
import { useI18n } from "../localization";
import { downloadBlob } from "../shared/api/request";
import { formatDisplayDateTime } from "../utils/datetime";

type DataTab = "users" | "violations" | "overrides" | "cache" | "learning" | "cases" | "exports";
type PendingKey =
  | "userSearch"
  | "userLoad"
  | "userAction"
  | "userExport"
  | "exactOverride"
  | "unsureOverride"
  | "cacheSave"
  | "calibrationPreview"
  | "calibrationExport";

const DATA_TABS: DataTab[] = [
  "users",
  "violations",
  "overrides",
  "cache",
  "learning",
  "cases",
  "exports"
];

export function DataPage() {
  const { t, language } = useI18n();
  const { pushToast } = useToast();
  const { section } = useParams();
  const navigate = useNavigate();
  const tab = useMemo<DataTab>(() => {
    return DATA_TABS.includes(section as DataTab) ? (section as DataTab) : "users";
  }, [section]);
  const [pageError, setPageError] = useState("");
  const [pending, setPending] = useState<Partial<Record<PendingKey, boolean>>>({});

  const [userQuery, setUserQuery] = useState("");
  const [userSearch, setUserSearch] = useState<Record<string, unknown> | null>(null);
  const [userCard, setUserCard] = useState<Record<string, unknown> | null>(null);
  const [userCardExport, setUserCardExport] = useState<Record<string, unknown> | null>(null);
  const [banMinutes, setBanMinutes] = useState("15");
  const [trafficCapGigabytes, setTrafficCapGigabytes] = useState("10");
  const [strikeCount, setStrikeCount] = useState("1");
  const [warningCount, setWarningCount] = useState("1");

  const [violations, setViolations] = useState<Record<string, unknown> | null>(null);
  const [overrides, setOverrides] = useState<Record<string, unknown> | null>(null);
  const [cache, setCache] = useState<Record<string, unknown> | null>(null);
  const [learning, setLearning] = useState<Record<string, unknown> | null>(null);
  const [cases, setCases] = useState<Record<string, unknown> | null>(null);

  const [exactOverrideIp, setExactOverrideIp] = useState("");
  const [exactOverrideDecision, setExactOverrideDecision] = useState("HOME");
  const [unsureOverrideIp, setUnsureOverrideIp] = useState("");
  const [unsureOverrideDecision, setUnsureOverrideDecision] = useState("HOME");
  const [selectedCacheIp, setSelectedCacheIp] = useState("");
  const [cacheDraft, setCacheDraft] = useState<Record<string, string>>({});

  const [calibrationFilters, setCalibrationFilters] = useState<Record<string, string | boolean>>({
    opened_from: "",
    opened_to: "",
    review_reason: "",
    provider_key: "",
    include_unknown: false,
    status: "resolved_only"
  });
  const [lastCalibrationManifest, setLastCalibrationManifest] = useState<CalibrationExportPreview | null>(null);
  const [lastCalibrationFilename, setLastCalibrationFilename] = useState("");
  const [previewError, setPreviewError] = useState("");

  useEffect(() => {
    if (section && DATA_TABS.includes(section as DataTab)) {
      return;
    }
    navigate("/data/users", { replace: true });
  }, [navigate, section]);

  function displayValue(value: unknown): string {
    return value === null || value === undefined || value === "" ? t("common.notAvailable") : String(value);
  }

  function formatPanelSquads(value: unknown): string {
    if (!Array.isArray(value) || value.length === 0) {
      return t("common.notAvailable");
    }
    const names = value
      .map((item) => {
        if (!item || typeof item !== "object") return "";
        const squad = item as Record<string, unknown>;
        return String(squad.name || squad.uuid || "").trim();
      })
      .filter(Boolean);
    return names.length > 0 ? names.join(", ") : t("common.notAvailable");
  }

  function formatTrafficBytes(value: unknown): string {
    const numeric =
      typeof value === "number" ? value : typeof value === "string" && value.trim() ? Number(value) : NaN;
    if (!Number.isFinite(numeric) || numeric < 0) {
      return t("common.notAvailable");
    }
    const gib = numeric / (1024 ** 3);
    return `${gib.toFixed(2)} GB`;
  }

  function setPendingKey(key: PendingKey, active: boolean) {
    setPending((prev) => ({ ...prev, [key]: active }));
  }

  function isPending(...keys: PendingKey[]) {
    return keys.some((key) => Boolean(pending[key]));
  }

  async function withPending<T>(key: PendingKey, action: () => Promise<T>): Promise<T> {
    setPendingKey(key, true);
    try {
      return await action();
    } finally {
      setPendingKey(key, false);
    }
  }

  function parseManifestHeader(header: string | null): Record<string, unknown> | null {
    if (!header) return null;
    try {
      const binary = atob(header);
      const bytes = Uint8Array.from(binary, (item) => item.charCodeAt(0));
      return JSON.parse(new TextDecoder().decode(bytes)) as Record<string, unknown>;
    } catch {
      return null;
    }
  }

  useEffect(() => {
    let cancelled = false;
    setPageError("");

    async function load() {
      try {
        if (tab === "violations") {
          const payload = await api.getViolations();
          if (!cancelled) setViolations(payload);
        } else if (tab === "overrides") {
          const payload = await api.getOverrides();
          if (!cancelled) setOverrides(payload);
        } else if (tab === "cache") {
          const payload = await api.getCache();
          if (!cancelled) setCache(payload);
        } else if (tab === "learning") {
          const payload = await api.getLearningAdmin();
          if (!cancelled) setLearning(payload);
        } else if (tab === "cases") {
          const payload = await api.listCases({ page: 1, page_size: 50 });
          if (!cancelled) setCases(payload);
        }
      } catch (err) {
        if (!cancelled) {
          setPageError(err instanceof Error ? err.message : t("data.errors.loadTabFailed"));
        }
      }
    }

    load();
    return () => {
      cancelled = true;
    };
  }, [tab, t]);

  useEffect(() => {
    if (tab !== "exports") return undefined;

    let cancelled = false;
    const timer = window.setTimeout(async () => {
      try {
        const payload = (await withPending("calibrationPreview", () =>
          api.previewCalibration(calibrationFilters as Record<string, string | number | boolean | undefined>)
        )) as CalibrationExportPreview;
        if (cancelled) return;
        setLastCalibrationManifest(payload);
        setPreviewError("");
      } catch (err) {
        if (cancelled) return;
        setPreviewError(err instanceof Error ? err.message : t("data.errors.exportCalibrationFailed"));
      }
    }, 220);

    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [tab, calibrationFilters, t]);

  async function searchUsers() {
    try {
      const payload = await withPending("userSearch", () => api.searchUsers(userQuery));
      setUserSearch(payload);
    } catch (err) {
      pushToast("error", err instanceof Error ? err.message : t("data.errors.searchUsersFailed"));
    }
  }

  async function loadUser(identifier: string) {
    try {
      const payload = await withPending("userLoad", () => api.getUserCard(identifier));
      setUserCard(payload);
      setUserCardExport(null);
    } catch (err) {
      pushToast("error", err instanceof Error ? err.message : t("data.errors.loadUserFailed"));
    }
  }

  async function runUserAction(action: () => Promise<Record<string, unknown>>, successMessage: string) {
    try {
      const payload = await withPending("userAction", action);
      setUserCard(payload);
      pushToast("success", successMessage);
    } catch (err) {
      pushToast("error", err instanceof Error ? err.message : t("data.errors.userActionFailed"));
    }
  }

  async function saveExactOverride() {
    try {
      await withPending("exactOverride", () => api.upsertExactOverride(exactOverrideIp, exactOverrideDecision));
      setOverrides(await api.getOverrides());
      pushToast("success", t("data.saved.exactOverride"));
    } catch (err) {
      pushToast("error", err instanceof Error ? err.message : t("data.errors.saveExactOverrideFailed"));
    }
  }

  async function saveUnsureOverride() {
    try {
      await withPending("unsureOverride", () => api.upsertUnsureOverride(unsureOverrideIp, unsureOverrideDecision));
      setOverrides(await api.getOverrides());
      pushToast("success", t("data.saved.unsureOverride"));
    } catch (err) {
      pushToast("error", err instanceof Error ? err.message : t("data.errors.saveUnsureOverrideFailed"));
    }
  }

  async function saveCachePatch() {
    if (!selectedCacheIp) return;
    try {
      await withPending("cacheSave", () =>
        api.patchCache(selectedCacheIp, {
          status: cacheDraft.status,
          confidence: cacheDraft.confidence,
          details: cacheDraft.details,
          asn: cacheDraft.asn ? Number(cacheDraft.asn) : null
        })
      );
      setCache(await api.getCache());
      pushToast("success", t("data.saved.cacheUpdated"));
    } catch (err) {
      pushToast("error", err instanceof Error ? err.message : t("data.errors.saveCacheFailed"));
    }
  }

  async function buildUserExport(identifier: string) {
    try {
      const payload = await withPending("userExport", () => api.getUserCardExport(identifier));
      setUserCardExport(payload);
      pushToast("success", t("data.saved.exportReady"));
    } catch (err) {
      pushToast("error", err instanceof Error ? err.message : t("data.errors.exportUserFailed"));
    }
  }

  function downloadUserExport() {
    if (!userCardExport) return;
    const identity = (userCardExport.identity as Record<string, unknown> | undefined) || {};
    const baseName = String(identity.username || identity.uuid || identity.system_id || identity.telegram_id || "user-card").replace(/[^\w.-]+/g, "_");
    const blob = new Blob([JSON.stringify(userCardExport, null, 2)], { type: "application/json" });
    downloadBlob(`${baseName}-export.json`, blob);
    pushToast("info", t("data.saved.exportDownloaded"));
  }

  async function generateCalibrationExport() {
    try {
      const response = await withPending("calibrationExport", () =>
        api.exportCalibration(calibrationFilters as Record<string, string | number | boolean | undefined>)
      );
      const manifest = parseManifestHeader(response.headers.get("X-MobGuard-Export-Manifest"));
      setLastCalibrationManifest((manifest as CalibrationExportPreview | null) ?? null);
      setLastCalibrationFilename(response.filename);
      downloadBlob(response.filename, response.blob);
      pushToast("success", t("data.saved.calibrationExportReady"));
      if (manifest && manifest.dataset_ready === false) {
        pushToast("warning", t("data.exports.notReadyToast"));
      }
    } catch (err) {
      pushToast("error", err instanceof Error ? err.message : t("data.errors.exportCalibrationFailed"));
    }
  }

  function renderProviderEvidence(providerEvidence: Record<string, unknown> | undefined) {
    if (!providerEvidence || Object.keys(providerEvidence).length === 0) {
      return <span>{t("common.notAvailable")}</span>;
    }
    return (
      <div className="provider-evidence">
        <span>{displayValue(providerEvidence.provider_key)} · {displayValue(providerEvidence.service_type_hint)}</span>
        <span>{Boolean(providerEvidence.service_conflict) ? t("data.users.providerConflict") : t("data.users.providerClear")}</span>
        <span>{Boolean(providerEvidence.review_recommended) ? t("data.users.reviewFirst") : t("data.users.autoReady")}</span>
      </div>
    );
  }

  function formatExportWarning(code: string): string {
    const translated = t(`data.exports.warnings.${code}`);
    return translated === `data.exports.warnings.${code}` ? code : translated;
  }

  function formatDecisionLabel(value: unknown): string {
    const key = `data.decisions.${String(value || "").toLowerCase()}`;
    const translated = t(key);
    return translated === key ? displayValue(value) : translated;
  }

  function formatReadinessCheckLabel(key: string): string {
    const translated = t(`data.exports.readiness.checks.${key}`);
    return translated === `data.exports.readiness.checks.${key}` ? key.replace(/_/g, " ") : translated;
  }

  function formatReadinessCheckValue(check: CalibrationReadinessCheck): string {
    if (check.key === "provider_profiles_present") {
      return `${check.current > 0 ? t("common.yes") : t("common.no")} / ${check.target > 0 ? t("common.yes") : t("common.no")}`;
    }
    if (check.key === "min_provider_support") {
      return `${displayValue(check.current)} / ${displayValue(check.target)}`;
    }
    return `${Math.round(check.current * 100)}% / ${Math.round(check.target * 100)}%`;
  }

  function renderUserExportPreview() {
    if (!userCardExport) return null;
    const exportMeta = (userCardExport.export_meta as Record<string, unknown> | undefined) || {};
    const recordCounts = (exportMeta.record_counts as Record<string, unknown> | undefined) || {};
    const sections: Array<[string, unknown]> = [
      [t("data.users.exportSections.identity"), userCardExport.identity],
      [t("data.users.exportSections.flags"), userCardExport.flags],
      [t("data.users.exportSections.panel"), userCardExport.panel_user],
      [t("data.users.exportSections.reviewCases"), userCardExport.review_cases],
      [t("data.users.exportSections.analysisEvents"), userCardExport.analysis_events],
      [t("data.users.exportSections.history"), userCardExport.history],
      [t("data.users.exportSections.activeTrackers"), userCardExport.active_trackers],
      [t("data.users.exportSections.ipHistory"), userCardExport.ip_history]
    ];

    return (
      <div className="panel">
        <div className="panel-heading panel-heading-row">
          <div>
            <h2>{t("data.users.exportPreviewTitle")}</h2>
            <p className="muted">{t("data.users.exportGeneratedAt", { value: formatDisplayDateTime(String(exportMeta.generated_at || ""), t("common.notAvailable"), language) })}</p>
          </div>
          <button className="ghost" onClick={downloadUserExport} disabled={isPending("userExport")}>{t("data.users.downloadExport")}</button>
        </div>
        <div className="stats-grid">
          <div className="stat-card"><span>{t("data.users.exportCards.reviewCases")}</span><strong>{displayValue(recordCounts.review_cases)}</strong></div>
          <div className="stat-card"><span>{t("data.users.exportCards.analysisEvents")}</span><strong>{displayValue(recordCounts.analysis_events)}</strong></div>
          <div className="stat-card"><span>{t("data.users.exportCards.history")}</span><strong>{displayValue(recordCounts.history)}</strong></div>
          <div className="stat-card"><span>{t("data.users.exportCards.ipHistory")}</span><strong>{displayValue(recordCounts.ip_history)}</strong></div>
        </div>
        <div className="export-sections">
          {sections.map(([label, value]) => (
            <details className="export-section" key={label} open={label === t("data.users.exportSections.identity")}>
              <summary>{label}</summary>
              <pre className="log-box">{JSON.stringify(value ?? null, null, 2)}</pre>
            </details>
          ))}
        </div>
      </div>
    );
  }

  function renderUsersTab() {
    const items = (userSearch?.items as Array<Record<string, unknown>> | undefined) || [];
    const panelMatch = userSearch?.panel_match as Record<string, unknown> | undefined;
    const identity = userCard?.identity as Record<string, unknown> | undefined;
    const flags = userCard?.flags as Record<string, unknown> | undefined;
    const reviewCases = (userCard?.review_cases as Array<Record<string, unknown>> | undefined) || [];
    const history = (userCard?.history as Array<Record<string, unknown>> | undefined) || [];
    const analysisEvents = (userCard?.analysis_events as Array<Record<string, unknown>> | undefined) || [];
    const panelUser = userCard?.panel_user as Record<string, unknown> | undefined;
    const userTraffic = (panelUser?.userTraffic as Record<string, unknown> | undefined) || undefined;
    const identifier = String(identity?.uuid || identity?.system_id || identity?.telegram_id || "");

    return (
      <>
        <div className="panel">
          <div className="search-strip compact-search-strip">
            <input placeholder={t("data.users.searchPlaceholder")} value={userQuery} onChange={(event) => setUserQuery(event.target.value)} />
            <button onClick={searchUsers} disabled={isPending("userSearch") || !userQuery.trim()}>
              {isPending("userSearch") ? t("data.users.searching") : t("data.users.search")}
            </button>
          </div>
          {panelMatch ? (
            <div className="tag">
              {t("data.users.panelMatch", {
                value: String(panelMatch.username || panelMatch.uuid || panelMatch.id)
              })}
            </div>
          ) : null}
          <ul className="reason-list">
            {items.map((item) => (
              <li key={String(item.uuid || item.system_id || item.telegram_id)}>
                <button className="ghost" disabled={isPending("userLoad")} onClick={() => loadUser(String(item.uuid || item.system_id || item.telegram_id))}>
                  {String(item.username || item.uuid || item.system_id)} · {t("data.users.systemLabel", { value: displayValue(item.system_id) })} · {t("data.users.telegramLabel", { value: displayValue(item.telegram_id) })}
                </button>
              </li>
            ))}
          </ul>
        </div>

        {identity ? (
          <div className="detail-grid">
            <div className="panel">
              <div className="panel-heading panel-heading-row">
                <div>
                  <h2>{t("data.users.cardTitle")}</h2>
                  <p className="muted">{t("data.users.exportHint")}</p>
                </div>
                <button onClick={() => buildUserExport(identifier)} disabled={isPending("userExport") || !identifier}>
                  {isPending("userExport") ? t("data.users.generatingExport") : t("data.users.buildExport")}
                </button>
              </div>
              <dl className="detail-list">
                <div><dt>{t("data.users.fields.username")}</dt><dd>{displayValue(identity.username)}</dd></div>
                <div><dt>{t("data.users.fields.uuid")}</dt><dd>{displayValue(identity.uuid)}</dd></div>
                <div><dt>{t("data.users.fields.systemId")}</dt><dd>{displayValue(identity.system_id)}</dd></div>
                <div><dt>{t("data.users.fields.telegramId")}</dt><dd>{displayValue(identity.telegram_id)}</dd></div>
                <div><dt>{t("data.users.fields.panelStatus")}</dt><dd>{displayValue(panelUser?.status)}</dd></div>
                <div><dt>{t("data.users.fields.panelSquads")}</dt><dd>{formatPanelSquads(panelUser?.activeInternalSquads)}</dd></div>
                <div><dt>{t("data.users.fields.trafficLimitBytes")}</dt><dd>{formatTrafficBytes(panelUser?.trafficLimitBytes)}</dd></div>
                <div><dt>{t("data.users.fields.trafficLimitStrategy")}</dt><dd>{displayValue(panelUser?.trafficLimitStrategy)}</dd></div>
                <div><dt>{t("data.users.fields.usedTrafficBytes")}</dt><dd>{formatTrafficBytes(userTraffic?.usedTrafficBytes)}</dd></div>
                <div><dt>{t("data.users.fields.lifetimeUsedTrafficBytes")}</dt><dd>{formatTrafficBytes(userTraffic?.lifetimeUsedTrafficBytes)}</dd></div>
                <div><dt>{t("data.users.fields.exemptSystemId")}</dt><dd>{displayValue(flags?.exempt_system_id)}</dd></div>
                <div><dt>{t("data.users.fields.exemptTelegramId")}</dt><dd>{displayValue(flags?.exempt_telegram_id)}</dd></div>
                <div><dt>{t("data.users.fields.activeBan")}</dt><dd>{displayValue(flags?.active_ban)}</dd></div>
                <div><dt>{t("data.users.fields.activeWarning")}</dt><dd>{displayValue(flags?.active_warning)}</dd></div>
              </dl>
            </div>

            <div className="panel">
              <h2>{t("data.users.actionsTitle")}</h2>
              <div className="form-grid">
                <div className="rule-field">
                  <strong>{t("data.users.actions.banMinutes")}</strong>
                  <input value={banMinutes} onChange={(event) => setBanMinutes(event.target.value)} />
                  <button disabled={isPending("userAction")} onClick={() => runUserAction(() => api.banUser(identifier, Number(banMinutes)), t("data.saved.userUpdated"))}>{t("data.users.actions.startBan")}</button>
                  <button className="ghost" disabled={isPending("userAction")} onClick={() => runUserAction(() => api.unbanUser(identifier), t("data.saved.userUpdated"))}>{t("data.users.actions.unban")}</button>
                </div>
                <div className="rule-field">
                  <strong>{t("data.users.actions.trafficCapGigabytes")}</strong>
                  <input value={trafficCapGigabytes} onChange={(event) => setTrafficCapGigabytes(event.target.value)} />
                  <div className="action-row">
                    <button disabled={isPending("userAction")} onClick={() => runUserAction(() => api.applyUserTrafficCap(identifier, Number(trafficCapGigabytes)), t("data.saved.userUpdated"))}>{t("data.users.actions.applyTrafficCap")}</button>
                    <button className="ghost" disabled={isPending("userAction")} onClick={() => runUserAction(() => api.restoreUserTrafficCap(identifier), t("data.saved.userUpdated"))}>{t("data.users.actions.restoreTrafficCap")}</button>
                  </div>
                </div>
                <div className="rule-field">
                  <strong>{t("data.users.actions.strikes")}</strong>
                  <input value={strikeCount} onChange={(event) => setStrikeCount(event.target.value)} />
                  <div className="action-row">
                    <button className="ghost" disabled={isPending("userAction")} onClick={() => runUserAction(() => api.updateUserStrikes(identifier, "add", Number(strikeCount)), t("data.saved.userUpdated"))}>{t("data.users.actions.add")}</button>
                    <button className="ghost" disabled={isPending("userAction")} onClick={() => runUserAction(() => api.updateUserStrikes(identifier, "remove", Number(strikeCount)), t("data.saved.userUpdated"))}>{t("data.users.actions.remove")}</button>
                    <button disabled={isPending("userAction")} onClick={() => runUserAction(() => api.updateUserStrikes(identifier, "set", Number(strikeCount)), t("data.saved.userUpdated"))}>{t("data.users.actions.set")}</button>
                  </div>
                </div>
                <div className="rule-field">
                  <strong>{t("data.users.actions.warnings")}</strong>
                  <input value={warningCount} onChange={(event) => setWarningCount(event.target.value)} />
                  <div className="action-row">
                    <button disabled={isPending("userAction")} onClick={() => runUserAction(() => api.updateUserWarnings(identifier, "set", Number(warningCount)), t("data.saved.userUpdated"))}>{t("data.users.actions.setWarning")}</button>
                    <button className="ghost" disabled={isPending("userAction")} onClick={() => runUserAction(() => api.updateUserWarnings(identifier, "clear", 0), t("data.saved.userUpdated"))}>{t("data.users.actions.clearWarning")}</button>
                  </div>
                </div>
                <div className="rule-field">
                  <strong>{t("data.users.actions.exemptions")}</strong>
                  <div className="action-row">
                    <button disabled={isPending("userAction")} onClick={() => runUserAction(() => api.updateUserExempt(identifier, "system", true), t("data.saved.userUpdated"))}>{t("data.users.actions.exemptSystem")}</button>
                    <button className="ghost" disabled={isPending("userAction")} onClick={() => runUserAction(() => api.updateUserExempt(identifier, "system", false), t("data.saved.userUpdated"))}>{t("data.users.actions.unexemptSystem")}</button>
                  </div>
                  <div className="action-row">
                    <button disabled={isPending("userAction")} onClick={() => runUserAction(() => api.updateUserExempt(identifier, "telegram", true), t("data.saved.userUpdated"))}>{t("data.users.actions.exemptTelegram")}</button>
                    <button className="ghost" disabled={isPending("userAction")} onClick={() => runUserAction(() => api.updateUserExempt(identifier, "telegram", false), t("data.saved.userUpdated"))}>{t("data.users.actions.unexemptTelegram")}</button>
                  </div>
                </div>
              </div>
            </div>

            <div className="panel">
              <h2>{t("data.users.analysisTitle")}</h2>
              <ul className="reason-list">
                {analysisEvents.length === 0 ? <li><span>{t("data.users.analysisEmpty")}</span></li> : null}
                {analysisEvents.map((item) => (
                  <li key={String(item.id)}>
                    <strong>{displayValue(item.ip)} · {displayValue(item.verdict)} / {displayValue(item.confidence_band)}</strong>
                    <span>{displayValue(item.isp)} · AS{displayValue(item.asn)}</span>
                    {renderProviderEvidence(item.provider_evidence as Record<string, unknown> | undefined)}
                    <span>{formatDisplayDateTime(String(item.created_at ?? ""), t("common.notAvailable"), language)}</span>
                  </li>
                ))}
              </ul>
            </div>

            <div className="panel">
              <h2>{t("data.users.openCasesTitle")}</h2>
              <ul className="reason-list">
                {reviewCases.length === 0 ? <li><span>{t("data.users.openCasesEmpty")}</span></li> : null}
                {reviewCases.map((item) => (
                  <li key={String(item.id)}>
                    <Link to={`/reviews/${item.id}`}>
                      #{String(item.id)} · {String(item.review_reason)} · {String(item.ip)} · {formatDisplayDateTime(String(item.updated_at ?? ""), t("common.notAvailable"), language)}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>

            <div className="panel">
              <h2>{t("data.users.historyTitle")}</h2>
              <ul className="reason-list">
                {history.length === 0 ? <li><span>{t("data.users.historyEmpty")}</span></li> : null}
                {history.map((item) => (
                  <li key={`${String(item.timestamp)}-${String(item.ip)}`}>
                    <strong>{String(item.ip)}</strong>
                    <span>{String(item.tag)} · {t("data.violations.historyRow", { strike: String(item.strike_number), duration: String(item.punishment_duration) })}</span>
                    <span>{formatDisplayDateTime(String(item.timestamp ?? ""), t("common.notAvailable"), language)}</span>
                  </li>
                ))}
              </ul>
            </div>

            {renderUserExportPreview()}
          </div>
        ) : null}
      </>
    );
  }

  function renderViolationsTab() {
    const active = (violations?.active as Array<Record<string, unknown>> | undefined) || [];
    const history = (violations?.history as Array<Record<string, unknown>> | undefined) || [];
    return (
      <div className="detail-grid">
        <div className="panel">
          <h2>{t("data.violations.activeTitle")}</h2>
          <div className="record-list">
            {active.map((item) => (
              <div className="record-item" key={String(item.uuid)}>
                <div className="record-main">
                  <span className="record-title">{String(item.uuid)}</span>
                  <span className="tag">{String(item.restriction_mode || t("common.notAvailable"))}</span>
                </div>
                <div className="record-meta">
                  <span>{t("data.violations.strikes", { value: String(item.strikes) })}</span>
                  <span>{t("data.violations.warningCount", { value: String(item.warning_count) })}</span>
                  <span>{t("data.violations.unban", { value: formatDisplayDateTime(String(item.unban_time ?? ""), t("common.notAvailable"), language) })}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
        <div className="panel">
          <h2>{t("data.violations.historyTitle")}</h2>
          <div className="record-list">
            {history.map((item) => (
              <div className="record-item" key={String(item.id)}>
                <div className="record-main">
                  <span className="record-title">{String(item.uuid)}</span>
                  <span>{String(item.ip)}</span>
                </div>
                <div className="record-meta">
                  <span>{t("data.violations.historyRow", { strike: String(item.strike_number), duration: String(item.punishment_duration) })}</span>
                  <span>{formatDisplayDateTime(String(item.timestamp ?? ""), t("common.notAvailable"), language)}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    );
  }

  function renderOverridesTab() {
    const exactIp = (overrides?.exact_ip as Array<Record<string, unknown>> | undefined) || [];
    const unsure = (overrides?.unsure_patterns as Array<Record<string, unknown>> | undefined) || [];
    return (
      <div className="detail-grid">
        <div className="panel">
          <h2>{t("data.overrides.exactTitle")}</h2>
          <div className="action-row">
            <input placeholder={t("data.overrides.ipPlaceholder")} value={exactOverrideIp} onChange={(event) => setExactOverrideIp(event.target.value)} />
            <select value={exactOverrideDecision} onChange={(event) => setExactOverrideDecision(event.target.value)}>
              <option value="HOME">{t("data.decisions.home")}</option>
              <option value="MOBILE">{t("data.decisions.mobile")}</option>
              <option value="SKIP">{t("data.decisions.skip")}</option>
            </select>
            <button disabled={isPending("exactOverride")} onClick={saveExactOverride}>{t("data.overrides.save")}</button>
          </div>
          <div className="record-list">
            {exactIp.map((item) => (
              <div className="record-item" key={String(item.ip)}>
                <div className="record-main">
                  <span className="record-title">{String(item.ip)}</span>
                  <span className="tag">{formatDecisionLabel(item.decision)}</span>
                </div>
                <div className="record-meta">
                  <span>{t("data.overrides.expires", { value: formatDisplayDateTime(String(item.expires_at ?? ""), t("common.notAvailable"), language) })}</span>
                </div>
                <div className="record-actions">
                <button className="ghost" disabled={isPending("exactOverride")} onClick={async () => {
                  try {
                    await withPending("exactOverride", () => api.deleteExactOverride(String(item.ip)));
                    setOverrides(await api.getOverrides());
                    pushToast("success", t("data.saved.exactOverride"));
                  } catch (err) {
                    pushToast("error", err instanceof Error ? err.message : t("data.errors.saveExactOverrideFailed"));
                  }
                }}>{t("data.overrides.delete")}</button>
                </div>
              </div>
            ))}
          </div>
        </div>
        <div className="panel">
          <h2>{t("data.overrides.unsureTitle")}</h2>
          <div className="action-row">
            <input placeholder={t("data.overrides.ipPatternPlaceholder")} value={unsureOverrideIp} onChange={(event) => setUnsureOverrideIp(event.target.value)} />
            <select value={unsureOverrideDecision} onChange={(event) => setUnsureOverrideDecision(event.target.value)}>
              <option value="HOME">{t("data.decisions.home")}</option>
              <option value="MOBILE">{t("data.decisions.mobile")}</option>
              <option value="SKIP">{t("data.decisions.skip")}</option>
            </select>
            <button disabled={isPending("unsureOverride")} onClick={saveUnsureOverride}>{t("data.overrides.save")}</button>
          </div>
          <div className="record-list">
            {unsure.map((item) => (
              <div className="record-item" key={String(item.ip_pattern)}>
                <div className="record-main">
                  <span className="record-title">{String(item.ip_pattern)}</span>
                  <span className="tag">{formatDecisionLabel(item.decision)}</span>
                </div>
                <div className="record-meta">
                  <span>{formatDisplayDateTime(String(item.timestamp ?? ""), t("common.notAvailable"), language)}</span>
                </div>
                <div className="record-actions">
                <button className="ghost" disabled={isPending("unsureOverride")} onClick={async () => {
                  try {
                    await withPending("unsureOverride", () => api.deleteUnsureOverride(String(item.ip_pattern)));
                    setOverrides(await api.getOverrides());
                    pushToast("success", t("data.saved.unsureOverride"));
                  } catch (err) {
                    pushToast("error", err instanceof Error ? err.message : t("data.errors.saveUnsureOverrideFailed"));
                  }
                }}>{t("data.overrides.delete")}</button>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    );
  }

  function renderCacheTab() {
    const items = (cache?.items as Array<Record<string, unknown>> | undefined) || [];
    return (
      <div className="detail-grid">
        <div className="panel">
          <h2>{t("data.cache.title")}</h2>
          <div className="record-list">
            {items.map((item) => (
              <div className="record-item" key={String(item.ip)}>
                <div className="record-main">
                  <span className="record-title">{String(item.ip)}</span>
                  <span className="tag">{String(item.status)} / {String(item.confidence)}</span>
                </div>
                <div className="record-meta">
                  <span>{t("data.cache.asnValue", { value: displayValue(item.asn) })}</span>
                  <span>{String(item.details || t("common.notAvailable"))}</span>
                </div>
                <div className="record-actions">
                  <button className="ghost" onClick={() => {
                    setSelectedCacheIp(String(item.ip));
                    setCacheDraft({
                      status: String(item.status || ""),
                      confidence: String(item.confidence || ""),
                      details: String(item.details || ""),
                      asn: String(item.asn || "")
                    });
                  }}>{t("data.cache.edit")}</button>
                  <button className="ghost" onClick={async () => {
                    try {
                      await api.deleteCache(String(item.ip));
                      setCache(await api.getCache());
                      pushToast("success", t("data.saved.cacheUpdated"));
                    } catch (err) {
                      pushToast("error", err instanceof Error ? err.message : t("data.errors.saveCacheFailed"));
                    }
                  }}>{t("data.cache.delete")}</button>
                </div>
              </div>
            ))}
          </div>
        </div>
        <div className="panel">
          <div className="panel-heading">
            <h2>{t("data.cache.editTitle")}</h2>
            <p className="muted">{t("data.sectionDescriptions.cache")}</p>
          </div>
          <div className="form-grid compact-form-grid">
            <div className="rule-field compact-rule-field">
              <strong>{t("data.cache.selectedIp")}</strong>
              <input placeholder={t("data.cache.selectedIp")} value={selectedCacheIp} onChange={(event) => setSelectedCacheIp(event.target.value)} />
            </div>
            <div className="rule-field compact-rule-field">
              <strong>{t("data.cache.status")}</strong>
              <input placeholder={t("data.cache.status")} value={cacheDraft.status || ""} onChange={(event) => setCacheDraft((prev) => ({ ...prev, status: event.target.value }))} />
            </div>
            <div className="rule-field compact-rule-field">
              <strong>{t("data.cache.confidence")}</strong>
              <input placeholder={t("data.cache.confidence")} value={cacheDraft.confidence || ""} onChange={(event) => setCacheDraft((prev) => ({ ...prev, confidence: event.target.value }))} />
            </div>
            <div className="rule-field rule-field-wide compact-rule-field">
              <strong>{t("data.cache.details")}</strong>
              <textarea className="note-box compact-note-box" placeholder={t("data.cache.details")} value={cacheDraft.details || ""} onChange={(event) => setCacheDraft((prev) => ({ ...prev, details: event.target.value }))} />
            </div>
            <div className="rule-field compact-rule-field">
              <strong>{t("data.cache.asn")}</strong>
              <input placeholder={t("data.cache.asn")} value={cacheDraft.asn || ""} onChange={(event) => setCacheDraft((prev) => ({ ...prev, asn: event.target.value }))} />
            </div>
          </div>
          <button onClick={saveCachePatch} disabled={!selectedCacheIp || isPending("cacheSave")}>{t("data.cache.save")}</button>
        </div>
      </div>
    );
  }

  function renderLearningTab() {
    const promotedActive = (learning?.promoted_active as Array<Record<string, unknown>> | undefined) || [];
    const promotedStats = (learning?.promoted_stats as Array<Record<string, unknown>> | undefined) || [];
    const legacy = (learning?.legacy as Array<Record<string, unknown>> | undefined) || [];
    const promotedProviderActive = (learning?.promoted_provider_active as Array<Record<string, unknown>> | undefined) || [];
    const promotedProviderServiceActive = (learning?.promoted_provider_service_active as Array<Record<string, unknown>> | undefined) || [];
    const legacyProvider = (learning?.legacy_provider as Array<Record<string, unknown>> | undefined) || [];
    const legacyProviderService = (learning?.legacy_provider_service as Array<Record<string, unknown>> | undefined) || [];
    return (
      <div className="detail-grid">
        <div className="panel">
          <h2>{t("data.learning.promotedActiveTitle")}</h2>
          <div className="record-list">
            {promotedActive.map((item) => (
              <div className="record-item" key={`${String(item.pattern_type)}:${String(item.pattern_value)}`}>
                <div className="record-main">
                  <span className="record-title">{String(item.pattern_type)}:{String(item.pattern_value)}</span>
                  <span className="tag">{String(item.decision)}</span>
                </div>
                <div className="record-meta">
                  <span>{t("data.learning.support", { value: String(item.support) })}</span>
                  <span>{t("data.learning.precision", { value: String(item.precision) })}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
        <div className="panel">
          <h2>{t("data.learning.promotedStatsTitle")}</h2>
          <div className="record-list">
            {promotedStats.map((item) => (
              <div className="record-item" key={`${String(item.pattern_type)}:${String(item.pattern_value)}:${String(item.decision)}`}>
                <div className="record-main">
                  <span className="record-title">{String(item.pattern_type)}:{String(item.pattern_value)}</span>
                  <span className="tag">{String(item.decision)}</span>
                </div>
                <div className="record-meta">
                  <span>{t("data.learning.total", { value: String(item.total) })}</span>
                  <span>{t("data.learning.precision", { value: String(item.precision) })}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
        <div className="panel">
          <h2>{t("data.learning.legacyTitle")}</h2>
          <div className="record-list">
            {legacy.map((item) => (
              <div className="record-item" key={String(item.id)}>
                <div className="record-main">
                  <span className="record-title">{String(item.pattern_type)}:{String(item.pattern_value)}</span>
                  <span className="tag">{String(item.decision)}</span>
                </div>
                <div className="record-meta">
                  <span>{t("data.learning.confidence", { value: String(item.confidence) })}</span>
                </div>
                <div className="record-actions">
                  <button className="ghost" onClick={async () => {
                    try {
                      await api.patchLegacyLearning(Number(item.id), { confidence: Number(item.confidence) + 1 });
                      setLearning(await api.getLearningAdmin());
                      pushToast("success", t("data.saved.learningUpdated"));
                    } catch (err) {
                      pushToast("error", err instanceof Error ? err.message : t("data.errors.loadTabFailed"));
                    }
                  }}>{t("data.learning.plusOneConfidence")}</button>
                  <button className="ghost" onClick={async () => {
                    try {
                      await api.deleteLegacyLearning(Number(item.id));
                      setLearning(await api.getLearningAdmin());
                      pushToast("success", t("data.saved.learningUpdated"));
                    } catch (err) {
                      pushToast("error", err instanceof Error ? err.message : t("data.errors.loadTabFailed"));
                    }
                  }}>{t("data.learning.delete")}</button>
                </div>
              </div>
            ))}
          </div>
        </div>
        <div className="panel">
          <h2>{t("data.learning.providerActiveTitle")}</h2>
          <div className="record-list">
            {promotedProviderActive.length === 0 ? <div className="provider-empty"><span>{t("data.learning.empty")}</span></div> : null}
            {promotedProviderActive.map((item) => (
              <div className="record-item" key={`${String(item.pattern_type)}:${String(item.pattern_value)}`}>
                <div className="record-main"><span className="record-title">{String(item.pattern_value)}</span><span className="tag">{String(item.decision)}</span></div>
                <div className="record-meta"><span>{t("data.learning.support", { value: String(item.support) })}</span><span>{t("data.learning.precision", { value: String(item.precision) })}</span></div>
              </div>
            ))}
          </div>
        </div>
        <div className="panel">
          <h2>{t("data.learning.providerServiceActiveTitle")}</h2>
          <div className="record-list">
            {promotedProviderServiceActive.length === 0 ? <div className="provider-empty"><span>{t("data.learning.empty")}</span></div> : null}
            {promotedProviderServiceActive.map((item) => (
              <div className="record-item" key={`${String(item.pattern_type)}:${String(item.pattern_value)}`}>
                <div className="record-main"><span className="record-title">{String(item.pattern_value)}</span><span className="tag">{String(item.decision)}</span></div>
                <div className="record-meta"><span>{t("data.learning.support", { value: String(item.support) })}</span><span>{t("data.learning.precision", { value: String(item.precision) })}</span></div>
              </div>
            ))}
          </div>
        </div>
        <div className="panel">
          <h2>{t("data.learning.providerLegacyTitle")}</h2>
          <div className="record-list">
            {[...legacyProvider, ...legacyProviderService].length === 0 ? <div className="provider-empty"><span>{t("data.learning.empty")}</span></div> : null}
            {[...legacyProvider, ...legacyProviderService].map((item) => (
              <div className="record-item" key={String(item.id)}>
                <div className="record-main"><span className="record-title">{String(item.pattern_type)}:{String(item.pattern_value)}</span><span className="tag">{String(item.decision)}</span></div>
                <div className="record-meta"><span>{t("data.learning.confidence", { value: String(item.confidence) })}</span></div>
              </div>
            ))}
          </div>
        </div>
      </div>
    );
  }

  function renderCasesTab() {
    const items = ((cases?.items as Array<Record<string, unknown>>) || []);
    return (
      <div className="panel">
        <h2>{t("data.cases.title")}</h2>
        <div className="record-list">
          {items.map((item) => (
            <Link className="record-item inline-link" key={String(item.id)} to={`/reviews/${item.id}`}>
              <div className="record-main">
                <span className="record-title">#{String(item.id)} · {String(item.username || item.uuid || t("common.notAvailable"))}</span>
                <span className="tag">{String(item.review_reason)}</span>
              </div>
              <div className="record-meta">
                <span>{String(item.ip)}</span>
                <span>{formatDisplayDateTime(String(item.updated_at ?? ""), t("common.notAvailable"), language)}</span>
              </div>
            </Link>
          ))}
        </div>
      </div>
    );
  }

  function renderExportsTab() {
    const rowCounts = (lastCalibrationManifest?.row_counts as Record<string, unknown> | undefined) || {};
    const filters = (lastCalibrationManifest?.filters as Record<string, unknown> | undefined) || {};
    const coverage = (lastCalibrationManifest?.coverage as Record<string, unknown> | undefined) || {};
    const warnings = (lastCalibrationManifest?.warnings as string[] | undefined) || [];
    const readiness = lastCalibrationManifest?.readiness;
    const blockers = readiness?.blockers || [];
    const checks = readiness?.checks || [];
    const datasetReady = Boolean(lastCalibrationManifest?.dataset_ready);
    const tuningReady = Boolean(lastCalibrationManifest?.tuning_ready);
    return (
      <div className="detail-grid">
        <div className="panel">
          <div className="panel-heading panel-heading-row">
            <div>
              <h2>{t("data.exports.title")}</h2>
              <p className="muted">{t("data.exports.description")}</p>
            </div>
            <button onClick={generateCalibrationExport} disabled={isPending("calibrationExport")}>
              {isPending("calibrationExport") ? t("data.exports.generating") : t("data.exports.generate")}
            </button>
          </div>
          <div className="form-grid">
            <div className="rule-field">
              <strong>{t("data.exports.filters.openedFrom")}</strong>
              <input type="date" value={String(calibrationFilters.opened_from)} onChange={(event) => setCalibrationFilters((prev) => ({ ...prev, opened_from: event.target.value }))} />
            </div>
            <div className="rule-field">
              <strong>{t("data.exports.filters.openedTo")}</strong>
              <input type="date" value={String(calibrationFilters.opened_to)} onChange={(event) => setCalibrationFilters((prev) => ({ ...prev, opened_to: event.target.value }))} />
            </div>
            <div className="rule-field">
              <strong>{t("data.exports.filters.reviewReason")}</strong>
              <input value={String(calibrationFilters.review_reason)} onChange={(event) => setCalibrationFilters((prev) => ({ ...prev, review_reason: event.target.value }))} />
            </div>
            <div className="rule-field">
              <strong>{t("data.exports.filters.providerKey")}</strong>
              <input value={String(calibrationFilters.provider_key)} onChange={(event) => setCalibrationFilters((prev) => ({ ...prev, provider_key: event.target.value }))} />
            </div>
            <div className="rule-field">
              <strong>{t("data.exports.filters.status")}</strong>
              <select value={String(calibrationFilters.status)} onChange={(event) => setCalibrationFilters((prev) => ({ ...prev, status: event.target.value }))}>
                <option value="resolved_only">{t("data.exports.status.resolvedOnly")}</option>
                <option value="open_only">{t("data.exports.status.openOnly")}</option>
                <option value="all">{t("data.exports.status.all")}</option>
              </select>
            </div>
            <div className="rule-field">
              <strong>{t("data.exports.filters.includeUnknown")}</strong>
              <select value={String(calibrationFilters.include_unknown)} onChange={(event) => setCalibrationFilters((prev) => ({ ...prev, include_unknown: event.target.value === "true" }))}>
                <option value="false">{t("common.no")}</option>
                <option value="true">{t("common.yes")}</option>
              </select>
            </div>
          </div>
        </div>
        <div className="panel">
          <div className="panel-heading">
            <h2>{t("data.exports.readinessTitle")}</h2>
            <p className="muted">{t("data.exports.readinessDescription")}</p>
          </div>
          {isPending("calibrationPreview") && !lastCalibrationManifest ? <p className="muted">{t("common.loading")}</p> : null}
          {previewError ? <div className="error-box">{previewError}</div> : null}
          {!lastCalibrationManifest && !isPending("calibrationPreview") ? <p className="muted">{t("data.exports.noManifest")}</p> : null}
          {lastCalibrationManifest ? (
            <>
              <div className="stats-grid">
                <div className="stat-card"><span>{t("data.exports.cards.overallReadiness")}</span><strong>{readiness?.overall_percent ?? 0}%</strong></div>
                <div className="stat-card"><span>{t("data.exports.cards.datasetReadiness")}</span><strong>{readiness?.dataset_percent ?? 0}%</strong></div>
                <div className="stat-card"><span>{t("data.exports.cards.tuningReadiness")}</span><strong>{readiness?.tuning_percent ?? 0}%</strong></div>
                <div className="stat-card"><span>{t("data.exports.cards.file")}</span><strong>{displayValue(lastCalibrationFilename)}</strong></div>
                <div className="stat-card"><span>{t("data.exports.cards.rawRows")}</span><strong>{displayValue(rowCounts.raw_rows)}</strong></div>
                <div className="stat-card"><span>{t("data.exports.cards.knownRows")}</span><strong>{displayValue(rowCounts.known_rows)}</strong></div>
                <div className="stat-card"><span>{t("data.exports.cards.unknownRows")}</span><strong>{displayValue(rowCounts.unknown_rows)}</strong></div>
                <div className="stat-card"><span>{t("data.exports.cards.providerProfiles")}</span><strong>{displayValue(coverage.provider_profiles_count)}</strong></div>
                <div className="stat-card"><span>{t("data.exports.cards.providerCoverage")}</span><strong>{displayValue(coverage.provider_key_coverage)}</strong></div>
                <div className="stat-card"><span>{t("data.exports.cards.patternCandidates")}</span><strong>{displayValue(coverage.provider_pattern_candidates)}</strong></div>
              </div>
              <div className={datasetReady ? "ok-box" : "error-box"}>
                {datasetReady ? t("data.exports.datasetReady") : t("data.exports.datasetNotReady")}
              </div>
              <div className={tuningReady ? "ok-box" : "error-box"}>
                {tuningReady ? t("data.exports.tuningReady") : t("data.exports.tuningNotReady")}
              </div>
              {blockers.length > 0 ? (
                <div className="panel export-warning-panel">
                  <h3>{t("data.exports.blockersTitle")}</h3>
                  <ul className="reason-list">
                    {blockers.map((blocker) => (
                      <li key={blocker}><span>{formatReadinessCheckLabel(blocker)}</span></li>
                    ))}
                  </ul>
                </div>
              ) : (
                <div className="ok-box">{t("data.exports.noBlockers")}</div>
              )}
              {warnings.length > 0 ? (
                <div className="panel export-warning-panel">
                  <h3>{t("data.exports.warningsTitle")}</h3>
                  <ul className="reason-list">
                    {warnings.map((warning) => (
                      <li key={warning}><span>{formatExportWarning(warning)}</span></li>
                    ))}
                  </ul>
                </div>
              ) : null}
              <div className="panel export-checks-panel">
                <h3>{t("data.exports.checksTitle")}</h3>
                <div className="record-list">
                  {checks.map((check) => (
                    <div className="record-item" key={`${check.scope}:${check.key}`}>
                      <div className="record-main">
                        <span className="record-title">{formatReadinessCheckLabel(check.key)}</span>
                        <span className={check.ready ? "tag status-resolved" : "tag severity-high"}>
                          {check.percent}%
                        </span>
                      </div>
                      <div className="record-meta">
                        <span>{check.scope}</span>
                        <span>{formatReadinessCheckValue(check)}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
              <details className="export-section" open>
                <summary>{t("data.exports.filterSnapshot")}</summary>
                <pre className="log-box">{JSON.stringify(filters, null, 2)}</pre>
              </details>
              <details className="export-section">
                <summary>{t("data.exports.coverageSnapshot")}</summary>
                <pre className="log-box">{JSON.stringify(coverage, null, 2)}</pre>
              </details>
            </>
          ) : null}
        </div>
      </div>
    );
  }

  return (
    <section className="page">
      <div className="page-header page-header-stack">
        <div>
          <span className="eyebrow">{t("data.eyebrow")}</span>
          <h1>{t("data.title")}</h1>
          <p className="page-lede">{t(`data.sectionDescriptions.${tab}`)}</p>
        </div>
        <span className="chip">{t(`data.tabs.${tab}`)}</span>
      </div>

      {pageError ? <div className="error-box">{pageError}</div> : null}

      {tab === "users" ? renderUsersTab() : null}
      {tab === "violations" ? renderViolationsTab() : null}
      {tab === "overrides" ? renderOverridesTab() : null}
      {tab === "cache" ? renderCacheTab() : null}
      {tab === "learning" ? renderLearningTab() : null}
      {tab === "cases" ? renderCasesTab() : null}
      {tab === "exports" ? renderExportsTab() : null}
    </section>
  );
}
