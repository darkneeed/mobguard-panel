import {
  MouseEvent,
  startTransition,
  useEffect,
  useMemo,
  useState,
} from "react";
import { Link, useSearchParams } from "react-router-dom";

import { hasPermission } from "../app/permissions";
import { prefetchRouteModule } from "../app/routeModules";
import { api, ReviewItem, ReviewListResponse, Session } from "../api/client";
import { useToast } from "../components/ToastProvider";
import {
  describeHardFlag,
} from "../features/reviews/lib/signalBadges";
import { describeScopeContext } from "../features/reviews/lib/scopeContext";
import { useI18n } from "../localization";
import type { Language } from "../localization";
import { buildSearchParams } from "../shared/api/request";
import { useVisiblePolling } from "../shared/useVisiblePolling";
import {
  formatDisplayDateTime,
  formatObservedDuration,
} from "../utils/datetime";

type ReviewFilters = {
  status: string;
  confidence_band: string;
  review_reason: string;
  severity: string;
  punitive_eligible: string;
  module_id: string;
  q: string;
  username: string;
  system_id: string;
  telegram_id: string;
  opened_from: string;
  opened_to: string;
  repeat_count_min: string;
  repeat_count_max: string;
  page: number;
  page_size: number;
  sort: string;
};

const PAGE_SIZE_OPTIONS = [12, 24, 48, 96];
const SAVED_FILTERS_KEY = "mobguard.reviewQueue.savedFilters";
const DEFAULT_FILTERS: ReviewFilters = {
  status: "OPEN",
  confidence_band: "",
  review_reason: "",
  severity: "",
  punitive_eligible: "",
  module_id: "",
  q: "",
  username: "",
  system_id: "",
  telegram_id: "",
  opened_from: "",
  opened_to: "",
  repeat_count_min: "",
  repeat_count_max: "",
  page: 1,
  page_size: 24,
  sort: "priority_desc",
};

function normalizePageSize(value: string | null): number {
  const parsed = Number(value || DEFAULT_FILTERS.page_size);
  return PAGE_SIZE_OPTIONS.includes(parsed)
    ? parsed
    : DEFAULT_FILTERS.page_size;
}

function normalizeFilters(searchParams: URLSearchParams): ReviewFilters {
  return {
    status: searchParams.get("status") ?? DEFAULT_FILTERS.status,
    confidence_band: searchParams.get("confidence_band") ?? "",
    review_reason: searchParams.get("review_reason") ?? "",
    severity: searchParams.get("severity") ?? "",
    punitive_eligible: searchParams.get("punitive_eligible") ?? "",
    module_id: searchParams.get("module_id") ?? "",
    q: searchParams.get("q") ?? "",
    username: searchParams.get("username") ?? "",
    system_id: searchParams.get("system_id") ?? "",
    telegram_id: searchParams.get("telegram_id") ?? "",
    opened_from: searchParams.get("opened_from") ?? "",
    opened_to: searchParams.get("opened_to") ?? "",
    repeat_count_min: searchParams.get("repeat_count_min") ?? "",
    repeat_count_max: searchParams.get("repeat_count_max") ?? "",
    page: Number(searchParams.get("page") || DEFAULT_FILTERS.page),
    page_size: normalizePageSize(searchParams.get("page_size")),
    sort: searchParams.get("sort") ?? DEFAULT_FILTERS.sort,
  };
}

function filtersForStorage(filters: ReviewFilters): ReviewFilters {
  return { ...filters, page: 1 };
}

function compactLocation(item: Record<string, unknown>) {
  return [item.city, item.country]
    .map((value) => String(value || "").trim())
    .filter(Boolean)
    .join(", ");
}

type QueueBadge = {
  code: string;
  label: string;
  description: string;
};

function buildQueueHardFlagBadges(hardFlags: string[] | undefined): QueueBadge[] {
  return Array.from(
    new Set((hardFlags || []).map((code) => String(code || "").trim()).filter(Boolean)),
  ).map((code) => ({
    code,
    ...describeHardFlag(code),
  }));
}

function formatInventoryChipLabel(
  ip: string,
  hitCount: number,
  firstSeenAt: string,
  lastSeenAt: string,
  language: Language,
): string {
  const duration = formatObservedDuration(
    firstSeenAt,
    lastSeenAt,
    "",
    language,
  );
  return duration ? `${ip} ×${hitCount} · ${duration}` : `${ip} ×${hitCount}`;
}

export function ReviewQueuePage({ session }: { session?: Session }) {
  const { t, language } = useI18n();
  const { pushToast } = useToast();
  const [searchParams, setSearchParams] = useSearchParams();
  const [loading, setLoading] = useState(true);
  const [list, setList] = useState<ReviewListResponse>({
    items: [],
    count: 0,
    page: 1,
    page_size: DEFAULT_FILTERS.page_size,
  });
  const [error, setError] = useState("");
  const [resolvingId, setResolvingId] = useState<number | null>(null);
  const [filters, setFilters] = useState<ReviewFilters>(() =>
    normalizeFilters(searchParams),
  );
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [lastUpdatedAt, setLastUpdatedAt] = useState("");
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [debouncedQuery, setDebouncedQuery] = useState(filters.q);
  const [savedFiltersPresent, setSavedFiltersPresent] = useState(() =>
    Boolean(window.localStorage.getItem(SAVED_FILTERS_KEY)),
  );

  useEffect(() => {
    const nextFilters = normalizeFilters(searchParams);
    setFilters((prev) =>
      JSON.stringify(prev) === JSON.stringify(nextFilters) ? prev : nextFilters,
    );
  }, [searchParams]);

  useEffect(() => {
    const query = buildSearchParams(filters);
    setSearchParams(new URLSearchParams(query), { replace: true });
  }, [filters, setSearchParams]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setDebouncedQuery(filters.q);
    }, 220);
    return () => window.clearTimeout(timer);
  }, [filters.q]);

  const effectiveFilters = useMemo(
    () => ({ ...filters, q: debouncedQuery }),
    [filters, debouncedQuery],
  );
  const requestFilters = useMemo(
    () => ({ ...effectiveFilters, view: "compact" }),
    [effectiveFilters],
  );
  const queueSearch = useMemo(
    () => buildSearchParams(effectiveFilters),
    [effectiveFilters],
  );
  const visibleQueueIds = useMemo(
    () => list.items.map((item) => item.id),
    [list.items],
  );
  const canResolve = hasPermission(session, "reviews.resolve");
  const canRecheck = hasPermission(session, "reviews.recheck");
  const canReadData = hasPermission(session, "data.read");

  function formatIdentifier(
    label: string,
    value: string | number | null | undefined,
  ) {
    return `${label}: ${value === null || value === undefined || value === "" ? t("common.notAvailable") : value}`;
  }

  function formatReviewReason(reason: string | null | undefined) {
    const key = `reviewQueue.reviewReasons.${String(reason || "").trim()}`;
    const translated = t(key);
    return translated === key
      ? String(reason || t("common.notAvailable"))
      : translated;
  }

  function formatInventoryDate(value: string | undefined) {
    return formatDisplayDateTime(
      value || "",
      t("common.notAvailable"),
      language,
    );
  }

  async function load() {
    try {
      const payload = await api.listReviews(requestFilters);
      startTransition(() => {
        setList(payload);
        setError("");
        setLastUpdatedAt(new Date().toISOString());
      });
    } catch (err) {
      setError(
        err instanceof Error ? err.message : t("reviewQueue.errors.loadFailed"),
      );
    } finally {
      setLoading(false);
    }
  }

  useVisiblePolling(true, load, 15000, [requestFilters, t]);

  useEffect(() => {
    setSelectedIds((prev) =>
      prev.filter((id) => list.items.some((item) => item.id === id)),
    );
  }, [list.items]);

  async function quickResolve(
    event: MouseEvent<HTMLButtonElement>,
    item: ReviewItem,
    resolution: "MOBILE" | "HOME" | "SKIP",
  ) {
    event.preventDefault();
    event.stopPropagation();
    try {
      setResolvingId(item.id);
      await api.resolveReview(
        String(item.id),
        resolution,
        "quick action from queue",
      );
      const payload = await api.listReviews(requestFilters);
      setList(payload);
      pushToast("success", t("reviewQueue.actions.saved"));
    } catch (err) {
      const message =
        err instanceof Error
          ? err.message
          : t("reviewQueue.errors.resolveFailed");
      setError(message);
      pushToast("error", message);
    } finally {
      setResolvingId(null);
    }
  }

  async function resolveSelected(resolution: "MOBILE" | "HOME" | "SKIP") {
    if (selectedIds.length === 0) return;
    try {
      setResolvingId(-1);
      for (const id of selectedIds) {
        await api.resolveReview(
          String(id),
          resolution,
          `bulk action from queue (${selectedIds.length})`,
        );
      }
      const payload = await api.listReviews(requestFilters);
      setList(payload);
      setSelectedIds([]);
      pushToast(
        "success",
        t("reviewQueue.actions.bulkSaved", { count: selectedIds.length }),
      );
    } catch (err) {
      const message =
        err instanceof Error
          ? err.message
          : t("reviewQueue.errors.resolveFailed");
      setError(message);
      pushToast("error", message);
    } finally {
      setResolvingId(null);
    }
  }

  async function recheckVisible() {
    try {
      const payload = await api.recheckReviews({
        limit: Math.max(
          1,
          Math.min(list.items.length || filters.page_size, 100),
        ),
        module_id: filters.module_id || undefined,
        review_reason: filters.review_reason || undefined,
      });
      const refreshed = await api.listReviews(requestFilters);
      setList(refreshed);
      pushToast(
        "success",
        t("reviewQueue.actions.recheckDone", {
          count: Number(payload.count || 0),
        }),
      );
    } catch (err) {
      const message =
        err instanceof Error
          ? err.message
          : t("reviewQueue.errors.resolveFailed");
      setError(message);
      pushToast("error", message);
    }
  }

  function saveCurrentFilters() {
    window.localStorage.setItem(
      SAVED_FILTERS_KEY,
      JSON.stringify(filtersForStorage(filters)),
    );
    setSavedFiltersPresent(true);
    pushToast("success", t("reviewQueue.savedFilters.saved"));
  }

  function applySavedFilters() {
    const raw = window.localStorage.getItem(SAVED_FILTERS_KEY);
    if (!raw) return;
    try {
      const parsed = JSON.parse(raw) as ReviewFilters;
      setFilters({
        ...DEFAULT_FILTERS,
        ...parsed,
        page: 1,
        page_size: normalizePageSize(
          String(parsed.page_size || DEFAULT_FILTERS.page_size),
        ),
      });
      pushToast("info", t("reviewQueue.savedFilters.applied"));
    } catch {
      pushToast("error", t("reviewQueue.savedFilters.invalid"));
    }
  }

  function clearSavedFilters() {
    window.localStorage.removeItem(SAVED_FILTERS_KEY);
    setSavedFiltersPresent(false);
    pushToast("info", t("reviewQueue.savedFilters.cleared"));
  }

  const allSelected =
    list.items.length > 0 && selectedIds.length === list.items.length;
  const activeFilterCount = useMemo(
    () =>
      [
        filters.confidence_band,
        filters.review_reason,
        filters.severity,
        filters.punitive_eligible,
        filters.module_id,
        filters.username,
        filters.system_id,
        filters.telegram_id,
        filters.opened_from,
        filters.opened_to,
        filters.repeat_count_min,
        filters.repeat_count_max,
      ].filter((value) => value !== "").length,
    [filters],
  );
  const presets = useMemo(
    () => [
      {
        key: "open",
        label: t("reviewQueue.presets.open"),
        apply: () =>
          setFilters((prev) => ({
            ...DEFAULT_FILTERS,
            q: prev.q,
            status: "OPEN",
            page_size: prev.page_size,
          })),
      },
      {
        key: "conflict",
        label: t("reviewQueue.presets.providerConflict"),
        apply: () =>
          setFilters((prev) => ({
            ...DEFAULT_FILTERS,
            review_reason: "provider_conflict",
            status: "OPEN",
            page_size: prev.page_size,
          })),
      },
      {
        key: "critical",
        label: t("reviewQueue.presets.critical"),
        apply: () =>
          setFilters((prev) => ({
            ...DEFAULT_FILTERS,
            severity: "critical",
            status: "OPEN",
            page_size: prev.page_size,
          })),
      },
      {
        key: "punitive",
        label: t("reviewQueue.presets.punitive"),
        apply: () =>
          setFilters((prev) => ({
            ...DEFAULT_FILTERS,
            punitive_eligible: "true",
            status: "OPEN",
            page_size: prev.page_size,
          })),
      },
    ],
    [t],
  );

  return (
    <section className="page">
      <div className="page-header page-header-stack">
        <div>
          <h1>{t("reviewQueue.title")}</h1>
          <p className="page-lede">{t("reviewQueue.description")}</p>
        </div>
        <div className="dashboard-meta">
          <div className="chip">
            {t("reviewQueue.countSummary", {
              count: list.count,
              page: list.page,
            })}
          </div>
          <span className="muted">
            {t("reviewQueue.lastUpdated", {
              value: formatDisplayDateTime(
                lastUpdatedAt,
                t("common.notAvailable"),
                language,
              ),
            })}
          </span>
        </div>
      </div>

      <div className="panel queue-toolbar">
        <div className="search-strip compact-search-strip">
          <input
            placeholder={t("reviewQueue.searchPlaceholder")}
            value={filters.q}
            onChange={(event) =>
              setFilters((prev) => ({
                ...prev,
                q: event.target.value,
                page: 1,
              }))
            }
          />
          <button
            className="ghost icon-button"
            onClick={() => setFiltersOpen((prev) => !prev)}
            title={t("reviewQueue.toggleFiltersTitle")}
          >
            {activeFilterCount > 0
              ? t("reviewQueue.filterCount", { count: activeFilterCount })
              : t("reviewQueue.filtersButton")}
          </button>
          <button
            className="ghost icon-button"
            onClick={() => setFilters(DEFAULT_FILTERS)}
            title={t("reviewQueue.clearFilters")}
          >
            {t("reviewQueue.clearFilters")}
          </button>
          <button
            className="ghost icon-button"
            onClick={saveCurrentFilters}
            title={t("reviewQueue.savedFilters.save")}
          >
            {t("reviewQueue.savedFilters.save")}
          </button>
          <button
            className="ghost icon-button"
            onClick={applySavedFilters}
            disabled={!savedFiltersPresent}
            title={t("reviewQueue.savedFilters.apply")}
          >
            {t("reviewQueue.savedFilters.apply")}
          </button>
          <button
            className="ghost icon-button"
            onClick={clearSavedFilters}
            disabled={!savedFiltersPresent}
            title={t("reviewQueue.savedFilters.clear")}
          >
            {t("reviewQueue.savedFilters.clear")}
          </button>
          <label className="queue-page-size-picker">
            <span>{t("reviewQueue.pageSize.label")}</span>
            <select
              aria-label={t("reviewQueue.pageSize.label")}
              value={filters.page_size}
              onChange={(event) =>
                setFilters((prev) => ({
                  ...prev,
                  page_size: Number(event.target.value),
                  page: 1,
                }))
              }
            >
              {PAGE_SIZE_OPTIONS.map((size) => (
                <option key={size} value={size}>
                  {t("reviewQueue.pageSize.option", { value: size })}
                </option>
              ))}
            </select>
          </label>
        </div>
        <div className="queue-bulkbar">
          <div className="queue-bulkbar-meta">
            <button
              className="ghost small-button"
              onClick={() =>
                setSelectedIds(
                  allSelected ? [] : list.items.map((item) => item.id),
                )
              }
            >
              {allSelected
                ? t("reviewQueue.selection.clearPage")
                : t("reviewQueue.selection.selectPage")}
            </button>
            <span className="chip">
              {t("reviewQueue.selection.selectedCount", {
                count: selectedIds.length,
              })}
            </span>
          </div>
          <div className="queue-bulk-actions">
            {canReadData ? (
              <Link
                to="/data/console"
                className="button-link ghost small-button"
                onMouseEnter={() => prefetchRouteModule("/data/console")}
                onFocus={() => prefetchRouteModule("/data/console")}
              >
                {t("reviewQueue.actions.openEvents")}
              </Link>
            ) : null}
            {canRecheck ? (
              <button
                className="ghost small-button"
                disabled={resolvingId !== null}
                onClick={recheckVisible}
              >
                {t("reviewQueue.actions.recheckVisible")}
              </button>
            ) : null}
            <button
              className="small-button"
              disabled={
                !canResolve || selectedIds.length === 0 || resolvingId !== null
              }
              onClick={() => resolveSelected("MOBILE")}
            >
              {t("reviewQueue.actions.bulkMobile")}
            </button>
            <button
              className="small-button"
              disabled={
                !canResolve || selectedIds.length === 0 || resolvingId !== null
              }
              onClick={() => resolveSelected("HOME")}
            >
              {t("reviewQueue.actions.bulkHome")}
            </button>
            <button
              className="ghost small-button"
              disabled={
                !canResolve || selectedIds.length === 0 || resolvingId !== null
              }
              onClick={() => resolveSelected("SKIP")}
            >
              {t("reviewQueue.actions.bulkSkip")}
            </button>
          </div>
        </div>
      </div>

      {filtersOpen ? (
        <div className="panel filters reveal-panel filter-drawer">
          <div className="queue-presets">
            {presets.map((preset) => (
              <button
                className="ghost small-button"
                key={preset.key}
                onClick={preset.apply}
              >
                {preset.label}
              </button>
            ))}
          </div>
          <input
            placeholder={t("reviewQueue.filters.moduleId")}
            value={String(filters.module_id ?? "")}
            onChange={(event) =>
              setFilters((prev) => ({
                ...prev,
                module_id: event.target.value,
                page: 1,
              }))
            }
          />
          <input
            placeholder={t("reviewQueue.filters.username")}
            value={String(filters.username ?? "")}
            onChange={(event) =>
              setFilters((prev) => ({
                ...prev,
                username: event.target.value,
                page: 1,
              }))
            }
          />
          <input
            placeholder={t("reviewQueue.filters.systemId")}
            value={String(filters.system_id ?? "")}
            onChange={(event) =>
              setFilters((prev) => ({
                ...prev,
                system_id: event.target.value,
                page: 1,
              }))
            }
          />
          <input
            placeholder={t("reviewQueue.filters.telegramId")}
            value={String(filters.telegram_id ?? "")}
            onChange={(event) =>
              setFilters((prev) => ({
                ...prev,
                telegram_id: event.target.value,
                page: 1,
              }))
            }
          />
          <input
            type="date"
            value={String(filters.opened_from ?? "")}
            onChange={(event) =>
              setFilters((prev) => ({
                ...prev,
                opened_from: event.target.value,
                page: 1,
              }))
            }
          />
          <input
            type="date"
            value={String(filters.opened_to ?? "")}
            onChange={(event) =>
              setFilters((prev) => ({
                ...prev,
                opened_to: event.target.value,
                page: 1,
              }))
            }
          />
          <input
            type="number"
            min={0}
            placeholder={t("reviewQueue.filters.repeatMin")}
            value={String(filters.repeat_count_min ?? "")}
            onChange={(event) =>
              setFilters((prev) => ({
                ...prev,
                repeat_count_min: event.target.value,
                page: 1,
              }))
            }
          />
          <input
            type="number"
            min={0}
            placeholder={t("reviewQueue.filters.repeatMax")}
            value={String(filters.repeat_count_max ?? "")}
            onChange={(event) =>
              setFilters((prev) => ({
                ...prev,
                repeat_count_max: event.target.value,
                page: 1,
              }))
            }
          />
          <select
            value={filters.status}
            onChange={(event) =>
              setFilters((prev) => ({
                ...prev,
                status: event.target.value,
                page: 1,
              }))
            }
          >
            <option value="OPEN">{t("reviewQueue.filters.statusOpen")}</option>
            <option value="RESOLVED">
              {t("reviewQueue.filters.statusResolved")}
            </option>
            <option value="SKIPPED">
              {t("reviewQueue.filters.statusSkipped")}
            </option>
            <option value="">{t("reviewQueue.filters.allStatus")}</option>
          </select>
          <select
            value={filters.confidence_band}
            onChange={(event) =>
              setFilters((prev) => ({
                ...prev,
                confidence_band: event.target.value,
                page: 1,
              }))
            }
          >
            <option value="">{t("reviewQueue.filters.allConfidence")}</option>
            <option value="UNSURE">
              {t("reviewQueue.filters.confidenceUnsure")}
            </option>
            <option value="PROBABLE_HOME">
              {t("reviewQueue.filters.confidenceProbableHome")}
            </option>
            <option value="HIGH_HOME">
              {t("reviewQueue.filters.confidenceHighHome")}
            </option>
          </select>
          <select
            value={filters.review_reason}
            onChange={(event) =>
              setFilters((prev) => ({
                ...prev,
                review_reason: event.target.value,
                page: 1,
              }))
            }
          >
            <option value="">{t("reviewQueue.filters.allReasons")}</option>
            <option value="unsure">
              {t("reviewQueue.filters.reasonUnsure")}
            </option>
            <option value="probable_home">
              {t("reviewQueue.filters.reasonProbableHome")}
            </option>
            <option value="home_requires_review">
              {t("reviewQueue.filters.reasonHomeRequiresReview")}
            </option>
            <option value="manual_review_mixed_home">
              {t("reviewQueue.filters.reasonManualMixedHome")}
            </option>
            <option value="provider_conflict">
              {t("reviewQueue.filters.reasonProviderConflict")}
            </option>
          </select>
          <select
            value={filters.severity}
            onChange={(event) =>
              setFilters((prev) => ({
                ...prev,
                severity: event.target.value,
                page: 1,
              }))
            }
          >
            <option value="">{t("reviewQueue.filters.allSeverity")}</option>
            <option value="critical">
              {t("reviewQueue.filters.severityCritical")}
            </option>
            <option value="high">
              {t("reviewQueue.filters.severityHigh")}
            </option>
            <option value="medium">
              {t("reviewQueue.filters.severityMedium")}
            </option>
            <option value="low">{t("reviewQueue.filters.severityLow")}</option>
          </select>
          <select
            value={filters.punitive_eligible}
            onChange={(event) =>
              setFilters((prev) => ({
                ...prev,
                punitive_eligible: event.target.value,
                page: 1,
              }))
            }
          >
            <option value="">{t("reviewQueue.filters.punitiveAny")}</option>
            <option value="true">
              {t("reviewQueue.filters.punitiveOnly")}
            </option>
            <option value="false">{t("reviewQueue.filters.reviewOnly")}</option>
          </select>
          <select
            value={filters.sort}
            onChange={(event) =>
              setFilters((prev) => ({ ...prev, sort: event.target.value }))
            }
          >
            <option value="priority_desc">
              {t("reviewQueue.filters.sortPriorityDesc")}
            </option>
            <option value="priority_asc">
              {t("reviewQueue.filters.sortPriorityAsc")}
            </option>
            <option value="updated_desc">
              {t("reviewQueue.filters.sortUpdatedDesc")}
            </option>
            <option value="score_desc">
              {t("reviewQueue.filters.sortScoreDesc")}
            </option>
            <option value="repeat_desc">
              {t("reviewQueue.filters.sortRepeatDesc")}
            </option>
            <option value="updated_asc">
              {t("reviewQueue.filters.sortUpdatedAsc")}
            </option>
          </select>
        </div>
      ) : null}

      {error ? <div className="error-box">{error}</div> : null}

      {loading ? (
        <div className="queue-grid review-queue-grid">
          {Array.from({ length: 6 }).map((_, index) => (
            <div className="queue-card skeleton-card" key={index}>
              <div className="queue-card-top">
                <span className="skeleton-line medium" />
                <span className="skeleton-chip" />
              </div>
              <div className="queue-card-identifiers">
                <span className="skeleton-line long" />
                <span className="skeleton-line medium" />
                <span className="skeleton-line long" />
              </div>
              <div className="loading-stack">
                <span className="skeleton-line long" />
                <span className="skeleton-line medium" />
                <span className="skeleton-line short" />
              </div>
            </div>
          ))}
        </div>
      ) : null}

      {!loading ? (
        <div className="queue-grid review-queue-grid">
          {list.items.map((item, index) => (
            <article key={item.id} className="queue-card">
              {(() => {
                const ipInventory =
                  Array.isArray(item.ip_inventory) &&
                  item.ip_inventory.length > 0
                    ? item.ip_inventory
                    : [
                        {
                          ip: item.ip,
                          hit_count: Math.max(item.repeat_count || 1, 1),
                          first_seen_at: item.opened_at,
                          last_seen_at: item.updated_at,
                          isp: item.isp,
                          asn: item.asn,
                        },
                      ];
                const sameDeviceHistory =
                  Array.isArray(item.same_device_ip_history) &&
                  item.same_device_ip_history.length > 0
                    ? item.same_device_ip_history
                    : ipInventory;
                const primaryIp = item.target_ip || item.ip;
                const scopeContext = describeScopeContext(
                  t,
                  item.target_scope_type || item.scope_type,
                  Boolean(item.shared_account_suspected),
                  sameDeviceHistory.length,
                );
                const deviceDisplay =
                  item.device_display || t("common.notAvailable");
                const providerDisplay =
                  item.isp || item.provider_key || t("common.notAvailable");
                const hardFlagBadges = buildQueueHardFlagBadges(item.hard_flags);
                return (
                  <>
                    <div className="queue-card-top">
                      <label className="inline-check queue-check">
                        <input
                          type="checkbox"
                          checked={selectedIds.includes(item.id)}
                          onChange={(event) =>
                            setSelectedIds((prev) =>
                              event.target.checked
                                ? [...prev, item.id]
                                : prev.filter((value) => value !== item.id),
                            )
                          }
                        />
                      </label>
                      <div>
                        <strong>{primaryIp}</strong>
                        <div className="muted">
                          {scopeContext.queueScopeLabel}
                        </div>
                      </div>
                      {item.status !== "OPEN" ? (
                        <span
                          className={`status-badge status-${item.status.toLowerCase()}`}
                        >
                          {item.status}
                        </span>
                      ) : null}
                    </div>
                    <div className="queue-card-identifiers">
                      <strong>
                        {item.username ||
                          formatIdentifier(
                            t("reviewQueue.identifiers.user"),
                            item.system_id,
                          )}
                      </strong>
                      <span>
                        {formatIdentifier(
                          t("reviewQueue.identifiers.module"),
                          item.module_name || item.module_id,
                        )}
                      </span>
                      {scopeContext.scopeType === "ip_device" ? (
                        <span>
                          {formatIdentifier(
                            t("reviewQueue.identifiers.device"),
                            deviceDisplay,
                          )}
                        </span>
                      ) : null}
                      {item.system_id !== null &&
                      item.system_id !== undefined ? (
                        <span>
                          {formatIdentifier(
                            t("reviewQueue.identifiers.system"),
                            item.system_id,
                          )}
                        </span>
                      ) : null}
                      {item.telegram_id ? (
                        <span>
                          {formatIdentifier(
                            t("reviewQueue.identifiers.telegram"),
                            item.telegram_id,
                          )}
                        </span>
                      ) : null}
                    </div>
                    <div className="queue-card-stack">
                      <div className="queue-card-meta">
                        <span>{t("reviewQueue.card.decision")}</span>
                        <strong>
                          {item.verdict} / {item.confidence_band}
                        </strong>
                      </div>
                      <div className="queue-card-meta">
                        <span>{t("reviewQueue.card.providerName")}</span>
                        <strong>{providerDisplay}</strong>
                      </div>
                      <div className="queue-card-meta">
                        <span>{t("reviewQueue.card.asn")}</span>
                        <strong>
                          {t("reviewQueue.card.asnValue", {
                            value: item.asn ?? "?",
                          })}
                        </strong>
                      </div>
                    </div>
                    <div className="queue-card-flags">
                      <span className="tag">
                        {t("reviewQueue.card.repeat", {
                          count: item.repeat_count,
                        })}
                      </span>
                      {hardFlagBadges.map((badge) => (
                        <span
                          key={badge.code}
                          className="tag"
                          title={badge.description}
                        >
                          {badge.label}
                        </span>
                      ))}
                    </div>
                    <div className="queue-card-inventory">
                      <span className="queue-card-section-label">
                        {scopeContext.historyLabel}
                      </span>
                      <div className="queue-card-chip-list">
                        {sameDeviceHistory.map((entry) => (
                          <span
                            key={`${entry.ip}-${entry.last_seen_at}`}
                            className="tag queue-inventory-tag"
                            title={[
                              t("reviewQueue.card.ipSeen", {
                                first: formatInventoryDate(entry.first_seen_at),
                                last: formatInventoryDate(entry.last_seen_at),
                              }),
                              formatObservedDuration(
                                entry.first_seen_at,
                                entry.last_seen_at,
                                "",
                                language,
                              ),
                              entry.isp || "",
                              compactLocation(entry as Record<string, unknown>),
                            ]
                              .filter(Boolean)
                              .join(" · ")}
                          >
                            {formatInventoryChipLabel(
                              entry.ip,
                              entry.hit_count,
                              entry.first_seen_at,
                              entry.last_seen_at,
                              language,
                            )}
                          </span>
                        ))}
                      </div>
                    </div>
                    <div className="action-row queue-card-actions">
                      <Link
                        to={`/reviews/${item.id}`}
                        state={{
                          reviewQueueSearch: queueSearch,
                          reviewQueueItemIds: visibleQueueIds,
                          reviewQueueCurrentIndex: index,
                        }}
                        className="button-link ghost small-button"
                        onMouseEnter={() =>
                          prefetchRouteModule(`/reviews/${item.id}`)
                        }
                        onFocus={() =>
                          prefetchRouteModule(`/reviews/${item.id}`)
                        }
                      >
                        {t("reviewQueue.actions.openCase")}
                      </Link>
                    </div>
                    {item.status === "OPEN" && canResolve ? (
                      <div className="action-row">
                        <button
                          className="small-button"
                          disabled={resolvingId === item.id}
                          onClick={(event) =>
                            quickResolve(event, item, "MOBILE")
                          }
                        >
                          {resolvingId === item.id
                            ? t("reviewQueue.actions.processing")
                            : t("reviewQueue.actions.mobile")}
                        </button>
                        <button
                          className="small-button"
                          disabled={resolvingId === item.id}
                          onClick={(event) => quickResolve(event, item, "HOME")}
                        >
                          {t("reviewQueue.actions.home")}
                        </button>
                        <button
                          className="small-button ghost"
                          disabled={resolvingId === item.id}
                          onClick={(event) => quickResolve(event, item, "SKIP")}
                        >
                          {t("reviewQueue.actions.skip")}
                        </button>
                      </div>
                    ) : null}
                    <div className="queue-card-bottom">
                      <span title={t("reviewQueue.card.activityObservedHint")}>
                        {t("reviewQueue.card.activityObserved", {
                          value:
                            item.usage_profile_ongoing_duration_text ||
                            t("common.notAvailable"),
                        })}
                      </span>
                      <span>
                        {t("reviewQueue.card.opened", {
                          value: formatDisplayDateTime(
                            item.opened_at,
                            t("common.notAvailable"),
                            language,
                          ),
                        })}
                      </span>
                      <span>
                        {formatDisplayDateTime(
                          item.updated_at,
                          t("common.notAvailable"),
                          language,
                        )}
                      </span>
                    </div>
                  </>
                );
              })()}
            </article>
          ))}
        </div>
      ) : null}

      <div className="panel queue-footer">
        <label className="queue-page-size-picker queue-footer-page-size">
          <span>{t("reviewQueue.pageSize.label")}</span>
          <select
            aria-label={t("reviewQueue.pageSize.label")}
            value={filters.page_size}
            onChange={(event) =>
              setFilters((prev) => ({
                ...prev,
                page_size: Number(event.target.value),
                page: 1,
              }))
            }
          >
            {PAGE_SIZE_OPTIONS.map((size) => (
              <option key={size} value={size}>
                {t("reviewQueue.pageSize.option", { value: size })}
              </option>
            ))}
          </select>
        </label>
        <button
          className="ghost"
          disabled={filters.page <= 1}
          onClick={() =>
            setFilters((prev) => ({
              ...prev,
              page: Math.max(prev.page - 1, 1),
            }))
          }
        >
          {t("reviewQueue.footer.previous")}
        </button>
        <span>
          {t("reviewQueue.footer.pageSummary", {
            page: list.page,
            shown: list.items.length,
            total: list.count,
          })}
        </span>
        <button
          className="ghost"
          disabled={list.page * list.page_size >= list.count}
          onClick={() =>
            setFilters((prev) => ({ ...prev, page: prev.page + 1 }))
          }
        >
          {t("reviewQueue.footer.next")}
        </button>
      </div>
    </section>
  );
}
