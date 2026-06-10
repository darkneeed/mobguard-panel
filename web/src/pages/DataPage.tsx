import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";

import { hasPermission } from "../app/permissions";
import {
  AnalysisEventListResponse,
  api,
  ConsoleListResponse,
  Session,
  UserCardExportResponse,
  UserCardResponse,
  UserSearchResponse,
} from "../api/client";
import { useToast } from "../components/ToastProvider";
import { useI18n } from "../localization";
import { downloadBlob } from "../shared/api/request";
import { useVisiblePolling } from "../shared/useVisiblePolling";
import { EventsDataSection } from "./data/EventsDataSection";
import { ConsoleDataSection } from "./data/ConsoleDataSection";
import { UserDataSection } from "./data/UserDataSection";
import { AiLearningSuggestionsSection } from "./data/AiLearningSuggestionsSection";

type DataTab =
  | "console"
  | "users"
  | "ai-suggestions"
  | "violations"
  | "overrides"
  | "cache"
  | "learning"
  | "cases"
  | "events"
  | "exports"
  | "audit";
type DataView = "users" | "events";
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
  "ai-suggestions",
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
  const [searchParams] = useSearchParams();
  const tab = useMemo<DataTab>(() => {
    return DATA_TABS.includes(section as DataTab)
      ? (section as DataTab)
      : "users";
  }, [section]);
  const dataView = useMemo<DataView>(() => {
    return tab === "events" || tab === "console" || tab === "cases" || tab === "audit" || tab === "exports"
      ? "events"
      : "users";
  }, [tab]);
  const [pageError, setPageError] = useState("");
  const [pending, setPending] = useState<Partial<Record<PendingKey, boolean>>>(
    {},
  );
  const [activeUserAction, setActiveUserAction] = useState("");

  const [userQuery, setUserQuery] = useState("");
  const [userSearch, setUserSearch] = useState<UserSearchResponse | null>(null);
  const [userCard, setUserCard] = useState<UserCardResponse | null>(null);
  const [userCardExport, setUserCardExport] =
    useState<UserCardExportResponse | null>(null);
  const [banMinutes, setBanMinutes] = useState("15");
  const [trafficCapGigabytes, setTrafficCapGigabytes] = useState("10");
  const [strikeCount, setStrikeCount] = useState("1");
  const [warningCount, setWarningCount] = useState("1");

  const [events, setEvents] = useState<AnalysisEventListResponse | null>(null);
  const [consoleData, setConsoleData] = useState<ConsoleListResponse | null>(
    null,
  );
  const canWriteData = hasPermission(session, "data.write");
  const [consoleFilters, setConsoleFilters] = useState<ConsoleFilters>({
    q: "",
    source: "",
    level: "",
    module_id: "",
    page: 1,
    page_size: 50,
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
    page_size: 20,
  });

  const handledQueryRef = useRef("");
  const handledIdentifierRef = useRef("");
  const pageTitle = dataView === "users" ? t("data.users.pageTitle") : t("data.tabs.events");

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

  useEffect(() => {
    let cancelled = false;
    setPageError("");

    async function load() {
      try {
        if (tab === "console") {
          return;
        }
        const eventsPayload = await api.getAnalysisEvents({
          compact: true,
          ...eventFilters,
          page_size: Math.min(eventFilters.page_size, 20),
          skip_count: true,
          sort: "created_desc",
        });
        if (!cancelled) {
          setEvents(eventsPayload);
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

  useVisiblePolling(dataView === "events", loadConsoleTab, 5000, [
    consoleFilters,
    t,
  ]);

  async function searchUsers(queryOverride?: unknown) {
    const targetQuery =
      typeof queryOverride === "string" ? queryOverride.trim() : userQuery.trim();
    if (!targetQuery) return;
    try {
      const payload = await withPending("userSearch", () =>
        api.searchUsers(targetQuery),
      );
      setUserSearch(payload);
      const panelMatch = payload.panel_match as Record<string, unknown> | null;
      const fallbackIdentifier = String(
        (panelMatch?.uuid as string | undefined) ||
          (panelMatch?.id as number | undefined) ||
          (panelMatch?.username as string | undefined) ||
          "",
      ).trim();
      if (payload.items.length === 0 && fallbackIdentifier) {
        await loadUser(fallbackIdentifier);
      }
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
    actionName: string,
    action: () => Promise<UserCardResponse>,
    successMessage: string,
  ) {
    setActiveUserAction(actionName);
    try {
      const payload = await withPending("userAction", action);
      setUserCard(payload);
      pushToast("success", successMessage);
    } catch (err) {
      pushToast(
        "error",
        err instanceof Error ? err.message : t("data.errors.userActionFailed"),
      );
    } finally {
      setActiveUserAction("");
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

  useEffect(() => {
    if (dataView !== "users") return;
    const queryFromUrl = searchParams.get("query")?.trim() || "";
    const identifierFromUrl = searchParams.get("identifier")?.trim() || "";

    if (queryFromUrl && queryFromUrl !== userQuery) {
      setUserQuery(queryFromUrl);
    }
    if (queryFromUrl && handledQueryRef.current !== queryFromUrl) {
      handledQueryRef.current = queryFromUrl;
      void searchUsers(queryFromUrl);
    }
    if (identifierFromUrl && handledIdentifierRef.current !== identifierFromUrl) {
      handledIdentifierRef.current = identifierFromUrl;
      void loadUser(identifierFromUrl);
    }
  }, [dataView, loadUser, searchParams, searchUsers, userQuery]);

  return (
    <section className="page">
      <div className="page-header page-header-stack">
        <div>
          <h1>{pageTitle}</h1>
          <p className="page-lede">
            {dataView === "users" ? t("data.sectionDescriptions.users") : t("data.sectionDescriptions.events")}
          </p>
        </div>
      </div>

      {pageError ? <div className="error-box">{pageError}</div> : null}

      {dataView === "users" ? (
        tab === "ai-suggestions" ? (
          <AiLearningSuggestionsSection
            t={t}
            language={language}
            canWriteData={canWriteData}
          />
        ) : (
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
            activeUserAction={activeUserAction}
          />
        )
      ) : null}
      {dataView === "events" ? (
        <>
          <ConsoleDataSection
            t={t}
            consoleData={consoleData}
            filters={consoleFilters}
            setFilters={(updater) => setConsoleFilters((prev) => updater(prev))}
          />
          <EventsDataSection
            t={t}
            language={language}
            events={events}
            filters={eventFilters}
            setFilters={(updater) => setEventFilters((prev) => updater(prev))}
          />
        </>
      ) : null}
    </section>
  );
}
