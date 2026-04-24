import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { hasPermission } from "../app/permissions";
import {
  AnalysisEventListResponse,
  api,
  AuditTrailResponse,
  CacheAdminResponse,
  CalibrationExportPreview,
  CalibrationReadinessCheck,
  ConsoleListResponse,
  LearningAdminResponse,
  OverridesResponse,
  ReviewListResponse,
  Session,
  UserCardExportResponse,
  UserCardResponse,
  UserSearchResponse,
  ViolationsResponse,
} from "../api/client";
import { useToast } from "../components/ToastProvider";
import { useI18n } from "../localization";
import { downloadBlob } from "../shared/api/request";
import { useVisiblePolling } from "../shared/useVisiblePolling";
import { ExportsDataSection } from "./data/ExportsDataSection";
import { AuditTrailSection } from "./data/AuditTrailSection";
import { ConsoleDataSection } from "./data/ConsoleDataSection";
import { EventsDataSection } from "./data/EventsDataSection";
import { LearningCasesSection } from "./data/LearningCasesSection";
import { OperationsDataSection } from "./data/OperationsDataSection";
import { UserDataSection } from "./data/UserDataSection";

type DataTab =
  | "console"
  | "users"
  | "violations"
  | "overrides"
  | "cache"
  | "learning"
  | "cases"
  | "events"
  | "exports"
  | "audit";
type ConsoleFilters = {
  q: string;
  source: string;
  level: string;
  module_id: string;
  page: number;
  page_size: number;
};
type EventFilters = {
  q: string;
  ip: string;
  device_id: string;
  module_id: string;
  tag: string;
  provider: string;
  asn: string;
  verdict: string;
  confidence_band: string;
  has_review_case: string;
  page: number;
  page_size: number;
};
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
  "console",
  "users",
  "violations",
  "overrides",
  "cache",
  "learning",
  "cases",
  "events",
  "exports",
  "audit",
];

export function DataPage({ session }: { session?: Session }) {
  const { t, language } = useI18n();
  const { pushToast } = useToast();
  const { section } = useParams();
  const navigate = useNavigate();
  const tab = useMemo<DataTab>(() => {
    return DATA_TABS.includes(section as DataTab)
      ? (section as DataTab)
      : "users";
  }, [section]);
  const [pageError, setPageError] = useState("");
  const [pending, setPending] = useState<Partial<Record<PendingKey, boolean>>>(
    {},
  );

  const [userQuery, setUserQuery] = useState("");
  const [userSearch, setUserSearch] = useState<UserSearchResponse | null>(null);
  const [userCard, setUserCard] = useState<UserCardResponse | null>(null);
  const [userCardExport, setUserCardExport] =
    useState<UserCardExportResponse | null>(null);
  const [banMinutes, setBanMinutes] = useState("15");
  const [trafficCapGigabytes, setTrafficCapGigabytes] = useState("10");
  const [strikeCount, setStrikeCount] = useState("1");
  const [warningCount, setWarningCount] = useState("1");

  const [violations, setViolations] = useState<ViolationsResponse | null>(null);
  const [overrides, setOverrides] = useState<OverridesResponse | null>(null);
  const [cache, setCache] = useState<CacheAdminResponse | null>(null);
  const [learning, setLearning] = useState<LearningAdminResponse | null>(null);
  const [cases, setCases] = useState<ReviewListResponse | null>(null);
  const [events, setEvents] = useState<AnalysisEventListResponse | null>(null);
  const [consoleData, setConsoleData] = useState<ConsoleListResponse | null>(
    null,
  );
  const [audit, setAudit] = useState<AuditTrailResponse | null>(null);
  const canWriteData = hasPermission(session, "data.write");
  const [consoleFilters, setConsoleFilters] = useState<ConsoleFilters>({
    q: "",
    source: "",
    level: "",
    module_id: "",
    page: 1,
    page_size: 100,
  });
  const [eventFilters, setEventFilters] = useState<EventFilters>({
    q: "",
    ip: "",
    device_id: "",
    module_id: "",
    tag: "",
    provider: "",
    asn: "",
    verdict: "",
    confidence_band: "",
    has_review_case: "",
    page: 1,
    page_size: 50,
  });

  const [exactOverrideIp, setExactOverrideIp] = useState("");
  const [exactOverrideDecision, setExactOverrideDecision] = useState("HOME");
  const [unsureOverrideIp, setUnsureOverrideIp] = useState("");
  const [unsureOverrideDecision, setUnsureOverrideDecision] = useState("HOME");
  const [selectedCacheIp, setSelectedCacheIp] = useState("");
  const [cacheDraft, setCacheDraft] = useState<Record<string, string>>({});

  const [calibrationFilters, setCalibrationFilters] = useState<
    Record<string, string | boolean>
  >({
    opened_from: "",
    opened_to: "",
    review_reason: "",
    provider_key: "",
    include_unknown: false,
    status: "resolved_only",
  });
  const [lastCalibrationManifest, setLastCalibrationManifest] =
    useState<CalibrationExportPreview | null>(null);
  const [lastCalibrationFilename, setLastCalibrationFilename] = useState("");
  const [previewError, setPreviewError] = useState("");

  async function loadConsoleTab() {
    try {
      const payload = await api.getConsoleEntries(consoleFilters);
      setConsoleData(payload);
      setPageError("");
    } catch (err) {
      setPageError(
        err instanceof Error ? err.message : t("data.errors.loadTabFailed"),
      );
    }
  }

  useEffect(() => {
    if (section && DATA_TABS.includes(section as DataTab)) {
      return;
    }
    navigate("/data/users", { replace: true });
  }, [navigate, section]);

  function displayValue(value: unknown): string {
    return value === null || value === undefined || value === ""
      ? t("common.notAvailable")
      : String(value);
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
      typeof value === "number"
        ? value
        : typeof value === "string" && value.trim()
          ? Number(value)
          : NaN;
    if (!Number.isFinite(numeric) || numeric < 0) {
      return t("common.notAvailable");
    }
    const gib = numeric / 1024 ** 3;
    return `${gib.toFixed(2)} GB`;
  }

  function setPendingKey(key: PendingKey, active: boolean) {
    setPending((prev) => ({ ...prev, [key]: active }));
  }

  function isPending(...keys: PendingKey[]) {
    return keys.some((key) => Boolean(pending[key]));
  }

  async function withPending<T>(
    key: PendingKey,
    action: () => Promise<T>,
  ): Promise<T> {
    setPendingKey(key, true);
    try {
      return await action();
    } finally {
      setPendingKey(key, false);
    }
  }

  function parseManifestHeader(
    header: string | null,
  ): Record<string, unknown> | null {
    if (!header) return null;
    try {
      const binary = atob(header);
      const bytes = Uint8Array.from(binary, (item) => item.charCodeAt(0));
      return JSON.parse(new TextDecoder().decode(bytes)) as Record<
        string,
        unknown
      >;
    } catch {
      return null;
    }
  }

  useEffect(() => {
    let cancelled = false;
    setPageError("");

    async function load() {
      try {
        if (tab === "console") {
          return;
        } else if (tab === "violations") {
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
        } else if (tab === "events") {
          const payload = await api.getAnalysisEvents({
            ...eventFilters,
            sort: "created_desc",
          });
          if (!cancelled) setEvents(payload);
        } else if (tab === "audit") {
          const payload = await api.getAuditTrail();
          if (!cancelled) setAudit(payload);
        }
      } catch (err) {
        if (!cancelled) {
          setPageError(
            err instanceof Error ? err.message : t("data.errors.loadTabFailed"),
          );
        }
      }
    }

    load();
    return () => {
      cancelled = true;
    };
  }, [consoleFilters, eventFilters, tab, t]);

  useVisiblePolling(tab === "console", loadConsoleTab, 3000, [
    consoleFilters,
    t,
  ]);

  useEffect(() => {
    if (tab !== "exports") return undefined;

    let cancelled = false;
    const timer = window.setTimeout(async () => {
      try {
        const payload = await withPending("calibrationPreview", () =>
          api.previewCalibration(
            calibrationFilters as Record<
              string,
              string | number | boolean | undefined
            >,
          ),
        );
        if (cancelled) return;
        setLastCalibrationManifest(payload);
        setPreviewError("");
      } catch (err) {
        if (cancelled) return;
        setPreviewError(
          err instanceof Error
            ? err.message
            : t("data.errors.exportCalibrationFailed"),
        );
      }
    }, 220);

    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [tab, calibrationFilters, t]);

  async function searchUsers() {
    try {
      const payload = await withPending("userSearch", () =>
        api.searchUsers(userQuery),
      );
      setUserSearch(payload);
    } catch (err) {
      pushToast(
        "error",
        err instanceof Error ? err.message : t("data.errors.searchUsersFailed"),
      );
    }
  }

  async function loadUser(identifier: string) {
    try {
      const payload = await withPending("userLoad", () =>
        api.getUserCard(identifier),
      );
      setUserCard(payload);
      setUserCardExport(null);
    } catch (err) {
      pushToast(
        "error",
        err instanceof Error ? err.message : t("data.errors.loadUserFailed"),
      );
    }
  }

  async function runUserAction(
    action: () => Promise<UserCardResponse>,
    successMessage: string,
  ) {
    try {
      const payload = await withPending("userAction", action);
      setUserCard(payload);
      pushToast("success", successMessage);
    } catch (err) {
      pushToast(
        "error",
        err instanceof Error ? err.message : t("data.errors.userActionFailed"),
      );
    }
  }

  async function saveExactOverride() {
    try {
      await withPending("exactOverride", () =>
        api.upsertExactOverride(exactOverrideIp, exactOverrideDecision),
      );
      setOverrides(await api.getOverrides());
      pushToast("success", t("data.saved.exactOverride"));
    } catch (err) {
      pushToast(
        "error",
        err instanceof Error
          ? err.message
          : t("data.errors.saveExactOverrideFailed"),
      );
    }
  }

  async function saveUnsureOverride() {
    try {
      await withPending("unsureOverride", () =>
        api.upsertUnsureOverride(unsureOverrideIp, unsureOverrideDecision),
      );
      setOverrides(await api.getOverrides());
      pushToast("success", t("data.saved.unsureOverride"));
    } catch (err) {
      pushToast(
        "error",
        err instanceof Error
          ? err.message
          : t("data.errors.saveUnsureOverrideFailed"),
      );
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
          asn: cacheDraft.asn ? Number(cacheDraft.asn) : null,
        }),
      );
      setCache(await api.getCache());
      pushToast("success", t("data.saved.cacheUpdated"));
    } catch (err) {
      pushToast(
        "error",
        err instanceof Error ? err.message : t("data.errors.saveCacheFailed"),
      );
    }
  }

  async function buildUserExport(identifier: string) {
    try {
      const payload = await withPending("userExport", () =>
        api.getUserCardExport(identifier),
      );
      setUserCardExport(payload);
      pushToast("success", t("data.saved.exportReady"));
    } catch (err) {
      pushToast(
        "error",
        err instanceof Error ? err.message : t("data.errors.exportUserFailed"),
      );
    }
  }

  function downloadUserExport() {
    if (!userCardExport) return;
    const identity =
      (userCardExport.identity as Record<string, unknown> | undefined) || {};
    const baseName = String(
      identity.username ||
        identity.uuid ||
        identity.system_id ||
        identity.telegram_id ||
        "user-card",
    ).replace(/[^\w.-]+/g, "_");
    const blob = new Blob([JSON.stringify(userCardExport, null, 2)], {
      type: "application/json",
    });
    downloadBlob(`${baseName}-export.json`, blob);
    pushToast("info", t("data.saved.exportDownloaded"));
  }

  async function generateCalibrationExport() {
    try {
      const response = await withPending("calibrationExport", () =>
        api.exportCalibration(
          calibrationFilters as Record<
            string,
            string | number | boolean | undefined
          >,
        ),
      );
      const manifest = parseManifestHeader(
        response.headers.get("X-MobGuard-Export-Manifest"),
      );
      setLastCalibrationManifest(
        (manifest as CalibrationExportPreview | null) ?? null,
      );
      setLastCalibrationFilename(response.filename);
      downloadBlob(response.filename, response.blob);
      pushToast("success", t("data.saved.calibrationExportReady"));
      if (manifest && manifest.dataset_ready === false) {
        pushToast("warning", t("data.exports.notReadyToast"));
      }
    } catch (err) {
      pushToast(
        "error",
        err instanceof Error
          ? err.message
          : t("data.errors.exportCalibrationFailed"),
      );
    }
  }

  function renderProviderEvidence(
    providerEvidence: Record<string, unknown> | undefined,
  ) {
    if (!providerEvidence || Object.keys(providerEvidence).length === 0) {
      return <span>{t("common.notAvailable")}</span>;
    }
    return (
      <div className="provider-evidence">
        <span>
          {displayValue(providerEvidence.provider_key)} ·{" "}
          {displayValue(providerEvidence.service_type_hint)}
        </span>
        <span>
          {Boolean(providerEvidence.service_conflict)
            ? t("data.users.providerConflict")
            : t("data.users.providerClear")}
        </span>
        <span>
          {Boolean(providerEvidence.review_recommended)
            ? t("data.users.reviewFirst")
            : t("data.users.autoReady")}
        </span>
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
    return translated === `data.exports.readiness.checks.${key}`
      ? key.replace(/_/g, " ")
      : translated;
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

  return (
    <section className="page">
      <div className="page-header page-header-stack">
        <div>
          <h1>{t("data.title")}</h1>
          <p className="page-lede">{t(`data.sectionDescriptions.${tab}`)}</p>
        </div>
      </div>

      {pageError ? <div className="error-box">{pageError}</div> : null}

      {tab === "users" ? (
        <UserDataSection
          t={t}
          language={language}
          userQuery={userQuery}
          setUserQuery={setUserQuery}
          userSearch={userSearch}
          userCard={userCard}
          userCardExport={userCardExport}
          banMinutes={banMinutes}
          setBanMinutes={setBanMinutes}
          trafficCapGigabytes={trafficCapGigabytes}
          setTrafficCapGigabytes={setTrafficCapGigabytes}
          strikeCount={strikeCount}
          setStrikeCount={setStrikeCount}
          warningCount={warningCount}
          setWarningCount={setWarningCount}
          canWriteData={canWriteData}
          searchUsers={searchUsers}
          loadUser={loadUser}
          runUserAction={runUserAction}
          buildUserExport={buildUserExport}
          downloadUserExport={downloadUserExport}
          isPending={isPending}
          displayValue={displayValue}
          formatPanelSquads={formatPanelSquads}
          formatTrafficBytes={formatTrafficBytes}
          renderProviderEvidence={renderProviderEvidence}
        />
      ) : null}
      {tab === "console" ? (
        <ConsoleDataSection
          t={t}
          consoleData={consoleData}
          filters={consoleFilters}
          setFilters={(updater) => setConsoleFilters((prev) => updater(prev))}
        />
      ) : null}
      {tab === "violations" || tab === "overrides" || tab === "cache" ? (
        <OperationsDataSection
          mode={tab}
          t={t}
          language={language}
          violations={violations}
          overrides={overrides}
          cache={cache}
          exactOverrideIp={exactOverrideIp}
          setExactOverrideIp={setExactOverrideIp}
          exactOverrideDecision={exactOverrideDecision}
          setExactOverrideDecision={setExactOverrideDecision}
          unsureOverrideIp={unsureOverrideIp}
          setUnsureOverrideIp={setUnsureOverrideIp}
          unsureOverrideDecision={unsureOverrideDecision}
          setUnsureOverrideDecision={setUnsureOverrideDecision}
          selectedCacheIp={selectedCacheIp}
          setSelectedCacheIp={setSelectedCacheIp}
          cacheDraft={cacheDraft}
          setCacheDraft={setCacheDraft}
          canWriteData={canWriteData}
          saveExactOverride={saveExactOverride}
          saveUnsureOverride={saveUnsureOverride}
          saveCachePatch={saveCachePatch}
          setOverrides={setOverrides}
          setCache={setCache}
          pushToast={pushToast}
          withPending={withPending}
          isPending={isPending}
          displayValue={displayValue}
          formatDecisionLabel={formatDecisionLabel}
        />
      ) : null}
      {tab === "learning" || tab === "cases" ? (
        <LearningCasesSection
          mode={tab}
          t={t}
          language={language}
          learning={learning}
          cases={cases}
          canWriteData={canWriteData}
          setLearning={setLearning}
          pushToast={pushToast}
        />
      ) : null}
      {tab === "events" ? (
        <EventsDataSection
          t={t}
          language={language}
          events={events}
          filters={eventFilters}
          setFilters={(updater) => setEventFilters((prev) => updater(prev))}
        />
      ) : null}
      {tab === "exports" ? (
        <ExportsDataSection
          t={t}
          isPending={isPending}
          calibrationFilters={calibrationFilters}
          setCalibrationFilters={setCalibrationFilters}
          generateCalibrationExport={generateCalibrationExport}
          lastCalibrationManifest={lastCalibrationManifest}
          lastCalibrationFilename={lastCalibrationFilename}
          previewError={previewError}
          displayValue={displayValue}
          formatExportWarning={formatExportWarning}
          formatReadinessCheckLabel={formatReadinessCheckLabel}
          formatReadinessCheckValue={formatReadinessCheckValue}
        />
      ) : null}
      {tab === "audit" ? (
        <AuditTrailSection t={t} language={language} audit={audit} />
      ) : null}
    </section>
  );
}
