import {
  MouseEvent,
  startTransition,
  useEffect,
  useMemo,
  useState,
} from "react";
import { Link, useSearchParams } from "react-router-dom";
import {
  Copy,
  Check,
  ExternalLink,
  ShieldAlert,
  Home,
  Smartphone,
  AlertTriangle,
  X,
  User,
  Clock,
  SlidersHorizontal,
  Loader2
} from "lucide-react";

import { hasPermission } from "../app/permissions";
import { prefetchRouteModule } from "../app/routeModules";
import { api, ReviewItem, ReviewListResponse, Session } from "../api/client";
import { useToast } from "../components/ToastProvider";

import {
  describeHardFlag,
  describeSoftReason,
} from "../features/reviews/lib/signalBadges";
import { describeScopeContext } from "../features/reviews/lib/scopeContext";
import { useI18n } from "../localization";
import type { Language } from "../localization";
import { buildSearchParams } from "../shared/api/request";
import { useVisibleItems } from "../shared/useVisibleItems";
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
  activity_duration_min_hours: string;
  activity_duration_max_hours: string;
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
  activity_duration_min_hours: "",
  activity_duration_max_hours: "",
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
    activity_duration_min_hours:
      searchParams.get("activity_duration_min_hours") ?? "",
    activity_duration_max_hours:
      searchParams.get("activity_duration_max_hours") ?? "",
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

function formatBytes(bytes: number): string {
  if (bytes === 0) return "0 B";
  const k = 1024;
  const sizes = ["B", "KB", "MB", "GB", "TB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + sizes[i];
}

function getViolationType(item: any): "devices" | "connection" | "traffic" | "continues" | "generic" {
  const profileReasons = item.usage_profile?.soft_reasons || [];
  const dbReasons = item.usage_profile_soft_reasons || [];
  const softReasons = Array.from(new Set([...profileReasons, ...dbReasons]));

  const limit = item.hwid_device_limit;
  const count = item.hwid_device_count_exact;
  const isDeviceLimitExceeded = limit !== undefined && count !== undefined && count > limit;
  const isDeviceViolation = softReasons.includes("device_rotation") || softReasons.includes("device_os_mismatch") || isDeviceLimitExceeded;

  const isTrafficViolation = softReasons.includes("traffic_burst") || (item.review_reason === "traffic_limit_exceeded");
  const isConnectionViolation = item.verdict?.toUpperCase() === "HOME" || softReasons.includes("provider_fanout");
  const hasOngoing = Boolean(item.usage_profile_ongoing_duration_seconds && item.usage_profile_ongoing_duration_seconds > 0);

  if (isDeviceViolation) return "devices";
  if (isTrafficViolation) return "traffic";
  if (isConnectionViolation) return "connection";
  if (hasOngoing) return "continues";
  
  return "generic";
}

export function ReviewQueuePage({
  session,
  isViolationsQueue = false,
}: {
  session?: Session;
  isViolationsQueue?: boolean;
}) {
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
  const [resolvingAction, setResolvingAction] = useState<string | null>(null);
  const [rechecking, setRechecking] = useState(false);
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
    () => ({
      ...filters,
      q: debouncedQuery,
      queue_type: isViolationsQueue ? "violations" : "review",
    }),
    [filters, debouncedQuery, isViolationsQueue],
  );
  const requestFilters = useMemo(
    () => ({ ...effectiveFilters, view: "compact" }),
    [effectiveFilters],
  );
  const {
    visibleItems: visibleQueueItems,
    hasMore: hasMoreQueueItems,
    loadMoreRef: loadMoreQueueItemsRef,
  } = useVisibleItems(list.items, {
    initialCount: filters.page_size,
    step: filters.page_size,
  });
  const queueSearch = useMemo(
    () => buildSearchParams(effectiveFilters),
    [effectiveFilters],
  );
  const visibleQueueIds = useMemo(
    () => visibleQueueItems.map((item) => item.id),
    [visibleQueueItems],
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
      setResolvingAction(resolution);
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
      setResolvingAction(null);
    }
  }

  async function resolveSelected(resolution: "MOBILE" | "HOME" | "SKIP") {
    if (selectedIds.length === 0) return;
    try {
      setResolvingId(-1);
      setResolvingAction(resolution);
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
      setResolvingAction(null);
    }
  }

  async function recheckVisible() {
    try {
      setRechecking(true);
      const payload = await api.recheckReviews({
        limit: Math.max(
          1,
          Math.min(list.items.length || filters.page_size, 100),
        ),
        case_ids: visibleQueueIds,
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
    } finally {
      setRechecking(false);
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
        filters.activity_duration_min_hours,
        filters.activity_duration_max_hours,
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
      {
        key: "short-activity",
        label: t("reviewQueue.presets.shortActivity"),
        apply: () =>
          setFilters((prev) => ({
            ...DEFAULT_FILTERS,
            status: "OPEN",
            activity_duration_max_hours: "12",
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
          <h1>
            {isViolationsQueue
              ? t("reviewQueue.violationsTitle")
              : t("reviewQueue.reviewTitle")}
          </h1>
          <p className="page-lede">
            {isViolationsQueue
              ? t("reviewQueue.violationsDescription")
              : t("reviewQueue.reviewDescription")}
          </p>
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
      {filtersOpen ? (
        <div className="panel reveal-panel filter-drawer queue-filters-shell" style={{ border: "1px solid var(--line)", background: "var(--bg-panel-glass, rgba(30, 30, 40, 0.45))", backdropFilter: "blur(16px)", padding: "1.25rem", borderRadius: "var(--radius-lg)" }}>
          <div className="queue-presets" style={{ borderBottom: "1px solid var(--line)", paddingBottom: "0.85rem", display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
            {presets.map((preset) => {
              const isActive = (preset.key === "open" && filters.status === "OPEN" && !filters.review_reason && !filters.severity && !filters.punitive_eligible && !filters.activity_duration_max_hours) ||
                (preset.key === "conflict" && filters.status === "OPEN" && filters.review_reason === "provider_conflict") ||
                (preset.key === "critical" && filters.status === "OPEN" && filters.severity === "critical") ||
                (preset.key === "punitive" && filters.status === "OPEN" && filters.punitive_eligible === "true") ||
                (preset.key === "short-activity" && filters.status === "OPEN" && filters.activity_duration_max_hours === "12");
              return (
                <button
                  key={preset.key}
                  onClick={preset.apply}
                  className={isActive ? "primary small-button" : "ghost small-button"}
                  style={{
                    borderRadius: "20px",
                    padding: "0.35rem 0.9rem",
                    fontWeight: 600,
                    fontSize: "0.8rem",
                    transition: "all 0.2s ease-in-out",
                    ...(isActive ? {
                      background: "var(--accent)",
                      borderColor: "var(--accent)",
                      color: "#fff",
                      boxShadow: "0 2px 8px rgba(99, 102, 241, 0.35)"
                    } : {
                      border: "1px solid var(--line)"
                    })
                  }}
                >
                  {preset.label}
                </button>
              );
            })}
          </div>
          <div className="queue-filter-sections">
            <section className="queue-filter-section">
              <div className="queue-filter-section-header">
                <div>
                  <h3 style={{ display: "flex", alignItems: "center", gap: "0.5rem", fontSize: "0.95rem", fontWeight: 700 }}>
                    <User size={16} style={{ color: "var(--accent)" }} />
                    {t("reviewQueue.filters.sections.identity")}
                  </h3>
                  <p>{t("reviewQueue.filters.sections.identityHint")}</p>
                </div>
              </div>
              <div className="queue-filter-grid">
                <label className="queue-filter-field">
                  <span>{t("reviewQueue.filters.moduleId")}</span>
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
                </label>
                <label className="queue-filter-field">
                  <span>{t("reviewQueue.filters.username")}</span>
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
                </label>
                <label className="queue-filter-field">
                  <span>{t("reviewQueue.filters.systemId")}</span>
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
                </label>
                <label className="queue-filter-field">
                  <span>{t("reviewQueue.filters.telegramId")}</span>
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
                </label>
              </div>
            </section>

            <section className="queue-filter-section">
              <div className="queue-filter-section-header">
                <div>
                  <h3 style={{ display: "flex", alignItems: "center", gap: "0.5rem", fontSize: "0.95rem", fontWeight: 700 }}>
                    <Clock size={16} style={{ color: "var(--accent)" }} />
                    {t("reviewQueue.filters.sections.timing")}
                  </h3>
                  <p>{t("reviewQueue.filters.sections.timingHint")}</p>
                </div>
              </div>
              <div className="queue-filter-grid">
                <label className="queue-filter-field">
                  <span>{t("reviewQueue.filters.openedFrom")}</span>
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
                </label>
                <label className="queue-filter-field">
                  <span>{t("reviewQueue.filters.openedTo")}</span>
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
                </label>
                <label className="queue-filter-field">
                  <span>{t("reviewQueue.filters.activityMinHours")}</span>
                  <input
                    type="number"
                    min={0}
                    step="0.5"
                    placeholder={t("reviewQueue.filters.activityMinHours")}
                    value={String(filters.activity_duration_min_hours ?? "")}
                    onChange={(event) =>
                      setFilters((prev) => ({
                        ...prev,
                        activity_duration_min_hours: event.target.value,
                        page: 1,
                      }))
                    }
                  />
                </label>
                <label className="queue-filter-field">
                  <span>{t("reviewQueue.filters.activityMaxHours")}</span>
                  <input
                    type="number"
                    min={0}
                    step="0.5"
                    placeholder={t("reviewQueue.filters.activityMaxHours")}
                    value={String(filters.activity_duration_max_hours ?? "")}
                    onChange={(event) =>
                      setFilters((prev) => ({
                        ...prev,
                        activity_duration_max_hours: event.target.value,
                        page: 1,
                      }))
                    }
                  />
                </label>
                <label className="queue-filter-field">
                  <span>{t("reviewQueue.filters.repeatMin")}</span>
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
                </label>
                <label className="queue-filter-field">
                  <span>{t("reviewQueue.filters.repeatMax")}</span>
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
                </label>
              </div>
            </section>

            <section className="queue-filter-section">
              <div className="queue-filter-section-header">
                <div>
                  <h3 style={{ display: "flex", alignItems: "center", gap: "0.5rem", fontSize: "0.95rem", fontWeight: 700 }}>
                    <SlidersHorizontal size={16} style={{ color: "var(--accent)" }} />
                    {t("reviewQueue.filters.sections.decision")}
                  </h3>
                  <p>{t("reviewQueue.filters.sections.decisionHint")}</p>
                </div>
              </div>
              <div className="queue-filter-grid">
                <label className="queue-filter-field">
                  <span>{t("reviewQueue.filters.allStatus")}</span>
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
                </label>
                <label className="queue-filter-field">
                  <span>{t("reviewQueue.filters.allConfidence")}</span>
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
                </label>
                <label className="queue-filter-field">
                  <span>{t("reviewQueue.filters.allReasons")}</span>
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
                </label>
                <label className="queue-filter-field">
                  <span>{t("reviewQueue.filters.allSeverity")}</span>
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
                </label>
                <label className="queue-filter-field">
                  <span>{t("reviewQueue.filters.punitiveAny")}</span>
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
                </label>
                <label className="queue-filter-field">
                  <span>{t("reviewQueue.filters.sortLabel")}</span>
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
                    <option value="activity_desc">
                      {t("reviewQueue.filters.sortActivityDesc")}
                    </option>
                    <option value="activity_asc">
                      {t("reviewQueue.filters.sortActivityAsc")}
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
                </label>
              </div>
            </section>
          </div>
        </div>
      ) : null}
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
                disabled={resolvingId !== null || rechecking || visibleQueueIds.length === 0}
                onClick={recheckVisible}
              >
                {rechecking && (
                  <Loader2 size={12} className="spinner" style={{ marginRight: "4px" }} />
                )}
                {t("reviewQueue.actions.recheckVisible")}
              </button>
            ) : null}
            <button
              className="small-button"
              style={{ background: "var(--success)", color: "#fff", border: "1px solid var(--success)" }}
              disabled={
                !canResolve || selectedIds.length === 0 || resolvingId !== null
              }
              onClick={() => resolveSelected("MOBILE")}
            >
              {resolvingId === -1 && resolvingAction === "MOBILE" && (
                <Loader2 size={12} className="spinner" style={{ marginRight: "4px" }} />
              )}
              {isViolationsQueue ? "Разрешить выбранные" : t("reviewQueue.actions.bulkMobile")}
            </button>
            <button
              className="small-button"
              style={{ background: "var(--danger)", color: "#fff", border: "1px solid var(--danger)" }}
              disabled={
                !canResolve || selectedIds.length === 0 || resolvingId !== null
              }
              onClick={() => resolveSelected("HOME")}
            >
              {resolvingId === -1 && resolvingAction === "HOME" && (
                <Loader2 size={12} className="spinner" style={{ marginRight: "4px" }} />
              )}
              {isViolationsQueue ? "Ограничить выбранные" : t("reviewQueue.actions.bulkHome")}
            </button>
            <button
              className="ghost small-button"
              disabled={
                !canResolve || selectedIds.length === 0 || resolvingId !== null
              }
              onClick={() => resolveSelected("SKIP")}
            >
              {resolvingId === -1 && resolvingAction === "SKIP" && (
                <Loader2 size={12} className="spinner" style={{ marginRight: "4px" }} />
              )}
              {t("reviewQueue.actions.bulkSkip")}
            </button>
          </div>
        </div>
      </div>


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
          {visibleQueueItems.map((item, index) => (
            <article key={item.id} className="queue-card" style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
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
                const softReasons = (() => {
                  const profileReasons = item.usage_profile?.soft_reasons || [];
                  const dbReasons = item.usage_profile_soft_reasons || [];
                  return Array.from(new Set([...profileReasons, ...dbReasons]));
                })();
                const isDeviceLimitExceeded =
                  item.hwid_device_limit !== null &&
                  item.hwid_device_limit !== undefined &&
                  item.hwid_device_count_exact !== null &&
                  item.hwid_device_count_exact !== undefined &&
                  item.hwid_device_count_exact > item.hwid_device_limit;
                const isDeviceViolation = softReasons.includes("device_rotation") || softReasons.includes("device_os_mismatch") || isDeviceLimitExceeded;
                const isTrafficViolation = softReasons.includes("traffic_burst") || (item.review_reason === "traffic_limit_exceeded");
                const hasOngoing = Boolean(item.usage_profile_ongoing_duration_seconds && item.usage_profile_ongoing_duration_seconds > 0);
                return (
                  <>
                    {/* Header: IP + Checkbox */}
                    <div className="queue-card-top" style={{ alignItems: "center", borderBottom: "1px solid var(--line)", paddingBottom: "0.75rem", gap: "0.5rem" }}>
                      <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
                        <label className="inline-check queue-check" style={{ display: "flex", margin: 0 }}>
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
                        <div style={{ display: "flex", flexDirection: "column" }}>
                          <div style={{ display: "flex", alignItems: "center", gap: "0.35rem" }}>
                            <strong style={{ fontSize: "1.1rem", color: "var(--ink)", fontFamily: "var(--font-display)" }}>{primaryIp}</strong>
                            <button
                              className="info-button"
                              style={{ width: "1.25rem", height: "1.25rem", minWidth: "1.25rem", border: 0, background: "none", color: "var(--muted)", cursor: "pointer", padding: 0 }}
                              onClick={() => {
                                navigator.clipboard.writeText(primaryIp);
                                pushToast("success", t("reviewQueue.ipCopiedToast"));
                              }}
                              title={t("reviewQueue.copyIpTooltip")}
                            >
                              <Copy size={12} />
                            </button>
                          </div>
                          <span style={{ fontSize: "0.75rem", color: "var(--muted)" }}>
                            {scopeContext.queueScopeLabel}
                          </span>
                        </div>
                      </div>
                      {item.status !== "OPEN" ? (
                        <span className={`status-badge status-${item.status.toLowerCase()}`}>
                          {item.status}
                        </span>
                      ) : null}
                    </div>

                    {/* Metadata Grid */}
                    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.6rem", fontSize: "0.8rem" }}>
                      <div>
                        <span style={{ color: "var(--muted)", display: "block", fontSize: "0.72rem", textTransform: "uppercase", fontWeight: 600 }}>{t("reviewQueue.identifiers.user")}</span>
                        <strong style={{ color: "var(--ink)" }}>{item.username || item.system_id || "—"}</strong>
                      </div>
                      <div>
                        <span style={{ color: "var(--muted)", display: "block", fontSize: "0.72rem", textTransform: "uppercase", fontWeight: 600 }}>{t("reviewQueue.identifiers.module")}</span>
                        <strong style={{ color: "var(--ink)" }}>{item.module_name || item.module_id}</strong>
                      </div>
                      {scopeContext.scopeType === "ip_device" && (
                        <div style={{ gridColumn: "span 2" }}>
                          <span style={{ color: "var(--muted)", display: "block", fontSize: "0.72rem", textTransform: "uppercase", fontWeight: 600 }}>{t("reviewQueue.identifiers.device")}</span>
                          <strong style={{ color: "var(--ink)" }}>{deviceDisplay}</strong>
                        </div>
                      )}
                      {item.telegram_id ? (
                        <div style={{ gridColumn: "span 2" }}>
                          <span style={{ color: "var(--muted)", display: "block", fontSize: "0.72rem", textTransform: "uppercase", fontWeight: 600 }}>Telegram ID</span>
                          <code style={{ color: "var(--accent)", fontFamily: "var(--font-mono)", fontSize: "0.78rem" }}>{item.telegram_id}</code>
                        </div>
                      ) : null}
                    </div>

                    {isViolationsQueue ? (
                      <div style={{ display: "flex", flexDirection: "column", gap: "0.6rem" }}>
                        {isDeviceViolation && (() => {
                          const profileDevices = item.usage_profile?.devices || [];
                          const limit = item.hwid_device_limit ?? item.usage_profile?.hwid_device_limit ?? 0;
                          const count = item.hwid_device_count_exact ?? item.usage_profile?.hwid_device_count_exact ?? 0;
                          
                          return (
                            <div style={{ background: "rgba(239, 68, 68, 0.08)", border: "1px solid rgba(239, 68, 68, 0.2)", borderRadius: "12px", padding: "0.75rem 1rem", display: "flex", flexDirection: "column", gap: "0.5rem" }}>
                              <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.72rem", color: "var(--muted)", textTransform: "uppercase", fontWeight: 600 }}>
                                <span style={{ color: "var(--danger)" }}>
                                  {isDeviceLimitExceeded 
                                    ? t("reviewQueue.deviceLimitExceeded") 
                                    : softReasons.includes("device_rotation") && softReasons.includes("device_os_mismatch")
                                      ? t("reviewQueue.deviceRotationAndMismatch")
                                      : softReasons.includes("device_rotation")
                                        ? t("reviewQueue.deviceRotationDetected")
                                        : softReasons.includes("device_os_mismatch")
                                          ? t("reviewQueue.deviceOsMismatchDetected")
                                          : t("reviewQueue.deviceViolationGeneric")}
                                </span>
                              </div>
                              
                              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.5rem", borderBottom: "1px solid rgba(239, 68, 68, 0.15)", paddingBottom: "0.5rem" }}>
                                <div>
                                  <span style={{ color: "var(--muted)", display: "block", fontSize: "0.68rem", textTransform: "uppercase", fontWeight: 600 }}>{t("reviewQueue.allowed")}</span>
                                  <span style={{ color: "var(--ink)", fontWeight: 600, fontSize: "0.95rem" }}>{t("reviewQueue.deviceUnit", { count: limit })}</span>
                                </div>
                                <div>
                                  <span style={{ color: "var(--muted)", display: "block", fontSize: "0.68rem", textTransform: "uppercase", fontWeight: 600 }}>{t("reviewQueue.used")}</span>
                                  <span style={{ color: "var(--danger)", fontWeight: 700, fontSize: "0.95rem" }}>{t("reviewQueue.deviceUnit", { count: count })}</span>
                                </div>
                              </div>
                              
                              {profileDevices.length > 0 && (
                                <div style={{ display: "flex", flexDirection: "column", gap: "0.3rem" }}>
                                  <span style={{ color: "var(--muted)", fontSize: "0.68rem", textTransform: "uppercase", fontWeight: 600 }}>{t("reviewQueue.deviceList")}</span>
                                  <div style={{ display: "flex", flexDirection: "column", gap: "0.25rem" }}>
                                    {profileDevices.map((dev: any, idx: number) => {
                                      const devLabel = dev.label || dev.device_id || t("reviewQueue.deviceLabel", { idx: idx + 1 });
                                      const devOs = [dev.os_family, dev.os_version].filter(Boolean).join(" ");
                                      const devApp = [dev.app_name, dev.app_version].filter(Boolean).join(" ");
                                      const devIp = dev.ip || "";
                                      return (
                                        <div key={idx} style={{ fontSize: "0.75rem", color: "var(--ink)", display: "flex", flexDirection: "column", background: "rgba(255, 255, 255, 0.03)", border: "1px solid rgba(255, 255, 255, 0.05)", borderRadius: "6px", padding: "4px 8px" }}>
                                          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                                            <span style={{ fontWeight: 600, color: "var(--ink)" }}>📱 {devLabel}</span>
                                            {devIp ? (
                                              <code style={{ fontSize: "0.7rem", color: "var(--accent)", background: "rgba(59, 130, 246, 0.08)", padding: "1px 4px", borderRadius: "4px" }}>{devIp}</code>
                                            ) : null}
                                          </div>
                                          {devOs || devApp ? (
                                            <div style={{ fontSize: "0.68rem", color: "var(--muted)", marginTop: "2px" }}>
                                              {[devOs, devApp].filter(Boolean).join(" · ")}
                                            </div>
                                          ) : null}
                                        </div>
                                      );
                                    })}
                                  </div>
                                </div>
                              )}
                              
                              <div style={{ display: "flex", flexWrap: "wrap", gap: "0.4rem", marginTop: "0.2rem" }}>
                                {softReasons.includes("device_rotation") && (
                                  <span className="tag" style={{ background: "rgba(239, 68, 68, 0.15)", color: "var(--danger)", fontSize: "0.68rem", padding: "2px 6px" }}>
                                    {t("reviewQueue.deviceRotationTag")}
                                  </span>
                                )}
                                {softReasons.includes("device_os_mismatch") && (
                                  <span className="tag" style={{ background: "rgba(239, 68, 68, 0.15)", color: "var(--danger)", fontSize: "0.68rem", padding: "2px 6px" }}>
                                    {t("reviewQueue.deviceOsMismatchTag")}
                                  </span>
                                )}
                              </div>
                            </div>
                          );
                        })()}
                                         {isTrafficViolation && (() => {
                          const burst = item.usage_profile?.traffic_burst;
                          const minBytes = 10737418240; // 10 GB
                          const eventCount = burst?.event_count || item.repeat_count || 1;
                          const limitVal = burst?.min_bytes || minBytes;
                          const actualVal = (burst?.source === "traffic_bytes" && burst?.bytes) ? burst.bytes : (limitVal + eventCount * 268435456);
                          const limitText = formatBytes(limitVal);
                          const actualText = formatBytes(actualVal);
                          const excessVal = actualVal - limitVal;
                          
                          const calculationText = excessVal > 0 
                            ? t("reviewQueue.exceededBy", { value: formatBytes(excessVal), percent: Math.round((actualVal / limitVal) * 100) })
                            : t("reviewQueue.withinLimit");

                          return (
                            <div style={{ background: "rgba(245, 158, 11, 0.08)", border: "1px solid rgba(245, 158, 11, 0.2)", borderRadius: "12px", padding: "0.75rem 1rem", display: "flex", flexDirection: "column", gap: "0.5rem" }}>
                              <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.72rem", color: "var(--muted)", textTransform: "uppercase", fontWeight: 600 }}>
                                <span style={{ color: "var(--warning)" }}>{t("reviewQueue.trafficBurstTitle")}</span>
                                <span>{t("reviewQueue.trafficWindow", { window: burst?.window_minutes || 30 })}</span>
                              </div>
                              
                              <div style={{ display: "grid", gridTemplateColumns: "1.1fr 1.1fr 1fr", gap: "0.5rem", borderBottom: "1px solid rgba(245, 158, 11, 0.15)", paddingBottom: "0.5rem" }}>
                                <div>
                                  <span style={{ color: "var(--muted)", display: "block", fontSize: "0.68rem", textTransform: "uppercase", fontWeight: 600 }}>{t("reviewQueue.volumeBefore")}</span>
                                  <span style={{ color: "var(--ink)", fontWeight: 600, fontSize: "0.95rem" }}>{limitText}</span>
                                </div>
                                <div>
                                  <span style={{ color: "var(--muted)", display: "block", fontSize: "0.68rem", textTransform: "uppercase", fontWeight: 600 }}>{t("reviewQueue.volumeAfter")}</span>
                                  <span style={{ color: "var(--warning)", fontWeight: 700, fontSize: "0.95rem" }}>{actualText}</span>
                                </div>
                                <div>
                                  <span style={{ color: "var(--muted)", display: "block", fontSize: "0.68rem", textTransform: "uppercase", fontWeight: 600 }}>{t("reviewQueue.difference")}</span>
                                  <span style={{ color: excessVal > 0 ? "var(--danger)" : "var(--success)", fontWeight: 700, fontSize: "0.95rem" }}>
                                    {excessVal > 0 ? `+${formatBytes(excessVal)}` : "0 B"}
                                  </span>
                                </div>
                              </div>
                              
                              <div style={{ fontSize: "0.75rem", color: "var(--ink)", fontWeight: 500 }}>
                                <strong>{t("reviewQueue.calculation")}</strong> {calculationText}
                              </div>
                            </div>
                          );
                        })()}

                        {!isDeviceViolation && !isTrafficViolation && (
                          <div style={{ background: "var(--surface-soft)", border: "1px solid var(--line)", borderRadius: "12px", padding: "0.75rem 1rem", display: "flex", flexDirection: "column", gap: "0.4rem" }}>
                            <div style={{ fontSize: "0.72rem", color: "var(--muted)", textTransform: "uppercase", fontWeight: 600 }}>
                              {t("reviewQueue.limitViolationTitle")}
                            </div>
                            <div style={{ fontSize: "0.82rem", color: "var(--ink)" }}>
                              {item.usage_profile_summary || t("reviewQueue.limitViolationSummaryFallback")}
                            </div>
                          </div>
                        )}
                      </div>
                    ) : (
                      <>
                        {/* Verdict & Score */}
                        <div style={{ display: "flex", gap: "0.5rem", alignItems: "center", flexWrap: "wrap", background: "var(--surface-soft)", padding: "0.6rem 0.85rem", borderRadius: "10px" }}>
                          <span style={{ fontSize: "0.75rem", color: "var(--muted)", fontWeight: 600, textTransform: "uppercase" }}>{t("reviewQueue.card.decision")}:</span>
                          <span className={`status-badge ${item.verdict?.toUpperCase() === "HOME" ? "punitive" : "status-resolved"}`} style={{ fontWeight: 700, padding: "2px 8px", borderRadius: "6px" }}>
                            {item.verdict}
                          </span>
                          <span className={`tag ${item.confidence_band?.startsWith("PROBABLE_") ? "severity-high" : ""}`} style={{ padding: "2px 8px", borderRadius: "6px" }}>{item.confidence_band}</span>
                        </div>

                        {/* Provider & ASN Box */}
                        <div style={{ background: "rgba(255, 255, 255, 0.03)", border: "1px solid var(--line)", borderRadius: "12px", padding: "0.75rem 1rem", display: "flex", flexDirection: "column", gap: "0.2rem" }}>
                          <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.72rem", color: "var(--muted)", textTransform: "uppercase", fontWeight: 600 }}>
                            <span>Провайдер</span>
                            <span>ASN {item.asn ?? "?"}</span>
                          </div>
                          <strong style={{ fontSize: "0.85rem", color: "var(--ink)", wordBreak: "break-all" }}>{providerDisplay}</strong>
                        </div>

                        {/* Limit warning badges if present */}
                        {(isDeviceViolation || isTrafficViolation) && (
                          <div style={{ display: "flex", flexWrap: "wrap", gap: "0.4rem" }}>
                            {isDeviceViolation && (
                              <span className="tag" style={{ background: "rgba(239, 68, 68, 0.1)", color: "var(--danger)", border: "1px solid rgba(239, 68, 68, 0.2)", fontSize: "0.72rem" }}>
                                📱 Устройства: {item.hwid_device_count_exact ?? 0}/{item.hwid_device_limit ?? 0}
                              </span>
                            )}
                            {isTrafficViolation && (
                              <span className="tag" style={{ background: "rgba(245, 158, 11, 0.1)", color: "var(--warning)", border: "1px solid rgba(245, 158, 11, 0.2)", fontSize: "0.72rem" }}>
                                ⚡ Трафик
                              </span>
                            )}
                          </div>
                        )}
                      </>
                    )}

                    {/* Flags */}
                    <div className="queue-card-flags" style={{ gap: "0.4rem" }}>
                      {isViolationsQueue && hasOngoing && (
                        <span className="tag" style={{ background: "rgba(59, 130, 246, 0.15)", color: "var(--accent)", border: "1px solid rgba(59, 130, 246, 0.3)", padding: "4px 8px" }}>
                          🔁 Нарушение продолжается ({item.usage_profile_ongoing_duration_text || "продолжается"})
                        </span>
                      )}
                      {isViolationsQueue && hasOngoing && softReasons.map((reason) => {
                        const desc = describeSoftReason(reason);
                        return (
                          <span key={reason} className="tag" style={{ background: "rgba(59, 130, 246, 0.08)", color: "var(--accent)", border: "1px solid rgba(59, 130, 246, 0.15)", padding: "4px 8px" }} title={desc.description}>
                            {desc.label}
                          </span>
                        );
                      })}
                      {!isTrafficViolation && (
                        <span className="tag" style={{ color: "var(--accent)" }}>
                          Повторов: {item.repeat_count}
                        </span>
                      )}
                      {hardFlagBadges.map((badge) => (
                        <span
                          key={badge.code}
                          className="tag punitive"
                          title={badge.description}
                          style={{ padding: "4px 8px" }}
                        >
                          {badge.label}
                        </span>
                      ))}
                    </div>

                    {/* Inventory History List */}
                    <div className="queue-card-inventory" style={{ gap: "0.4rem" }}>
                      <span className="queue-card-section-label" style={{ fontSize: "0.75rem", textTransform: "uppercase", fontWeight: 600 }}>
                        {scopeContext.historyLabel}
                      </span>
                      <div className="queue-card-chip-list" style={{ gap: "0.35rem" }}>
                        {sameDeviceHistory.slice(0, 3).map((entry) => (
                          <span
                            key={`${entry.ip}-${entry.last_seen_at}`}
                            className="tag queue-inventory-tag"
                            style={{ fontSize: "0.75rem", padding: "4px 8px" }}
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
                            {isTrafficViolation
                              ? (formatObservedDuration(entry.first_seen_at, entry.last_seen_at, "", language)
                                ? `${entry.ip} · ${formatObservedDuration(entry.first_seen_at, entry.last_seen_at, "", language)}`
                                : entry.ip)
                              : formatInventoryChipLabel(
                                  entry.ip,
                                  entry.hit_count,
                                  entry.first_seen_at,
                                  entry.last_seen_at,
                                  language,
                                )}
                          </span>
                        ))}
                        {sameDeviceHistory.length > 3 && (
                          <span className="tag" style={{ fontSize: "0.75rem", background: "none", borderStyle: "dashed" }}>
                            +{sameDeviceHistory.length - 3} ещё
                          </span>
                        )}
                      </div>
                    </div>

                    {/* Quick Resolve & Details Actions */}
                    <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem", marginTop: "auto", paddingTop: "0.5rem" }}>
                      <Link
                        to={`/reviews/${item.id}`}
                        state={{
                          reviewQueueSearch: queueSearch,
                          reviewQueueItemIds: visibleQueueIds,
                          reviewQueueCurrentIndex: index,
                          isViolationsQueue: isViolationsQueue,
                        }}
                        className="button-link ghost small-button"
                        style={{ width: "100%", padding: "0.5rem" }}
                        onMouseEnter={() =>
                          prefetchRouteModule(`/reviews/${item.id}`)
                        }
                        onFocus={() =>
                          prefetchRouteModule(`/reviews/${item.id}`)
                        }
                      >
                        Открыть кейс <ExternalLink size={12} style={{ marginLeft: "4px" }} />
                      </Link>

                      {item.status === "OPEN" && canResolve && (
                        <div style={{ display: "grid", gridTemplateColumns: "1.2fr 1.2fr 1fr", gap: "0.35rem" }}>
                          <button
                            className="small-button"
                            style={{ background: "var(--success-soft)", color: "var(--success)", border: "1px solid var(--success)", padding: "0.5rem" }}
                            disabled={resolvingId === item.id}
                            onClick={(event) =>
                              quickResolve(event, item, "MOBILE")
                            }
                          >
                            {resolvingId === item.id && resolvingAction === "MOBILE" ? (
                              <Loader2 size={12} className="spinner" />
                            ) : isViolationsQueue ? (
                              <Check size={12} />
                            ) : (
                              <Smartphone size={12} />
                            )}{" "}
                            {isViolationsQueue ? "Разрешить" : t("reviewQueue.actions.mobile")}
                          </button>
                          <button
                            className="small-button"
                            style={{ background: "var(--danger-soft)", color: "var(--danger)", border: "1px solid var(--danger)", padding: "0.5rem" }}
                            disabled={resolvingId === item.id}
                            onClick={(event) => quickResolve(event, item, "HOME")}
                          >
                            {resolvingId === item.id && resolvingAction === "HOME" ? (
                              <Loader2 size={12} className="spinner" />
                            ) : isViolationsQueue ? (
                              <ShieldAlert size={12} />
                            ) : (
                              <Home size={12} />
                            )}{" "}
                            {isViolationsQueue ? "Ограничить" : t("reviewQueue.actions.home")}
                          </button>
                          <button
                            className="small-button ghost"
                            style={{ padding: "0.5rem" }}
                            disabled={resolvingId === item.id}
                            onClick={(event) => quickResolve(event, item, "SKIP")}
                          >
                            {resolvingId === item.id && resolvingAction === "SKIP" && (
                              <Loader2 size={12} className="spinner" style={{ marginRight: "4px" }} />
                            )}
                            {t("reviewQueue.actions.skip")}
                          </button>
                        </div>
                      )}
                    </div>

                    <div className="queue-card-bottom" style={{ borderTop: "1px solid var(--line)", paddingTop: "0.6rem", marginTop: "0.25rem", fontSize: "0.72rem" }}>
                      <span>
                        Открыт: {formatDisplayDateTime(
                          item.opened_at,
                          t("common.notAvailable"),
                          language,
                        ).split(" ").slice(0, 2).join(" ")}
                      </span>
                      <span>
                        Активность: {formatDisplayDateTime(
                          item.updated_at,
                          t("common.notAvailable"),
                          language,
                        ).split(" ").slice(0, 2).join(" ")}
                      </span>
                    </div>
                  </>
                );
              })()}
            </article>
          ))}

          {hasMoreQueueItems ? (
            <div className="provider-empty muted" ref={loadMoreQueueItemsRef}>
              <span>{t("common.loading")}</span>
            </div>
          ) : null}
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

      {/* Floating bulk actions bar */}
      {selectedIds.length > 0 && (
        <div className="floating-bulk-bar">
          <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
            <AlertTriangle size={18} style={{ color: "var(--accent)" }} />
            <span>Выбрано кейсов: <strong>{selectedIds.length}</strong></span>
          </div>
          <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
            <button
              onClick={() => resolveSelected("MOBILE")}
              style={{ background: "var(--success, #10b981)", color: "#fff", border: 0, padding: "0.5rem 1rem", fontSize: "0.82rem", fontWeight: 600, borderRadius: "var(--radius-sm)" }}
              disabled={resolvingId !== null}
            >
              <Smartphone size={14} /> Мобильный
            </button>
            <button
              onClick={() => resolveSelected("HOME")}
              style={{ background: "var(--danger, #ef4444)", color: "#fff", border: 0, padding: "0.5rem 1rem", fontSize: "0.82rem", fontWeight: 600, borderRadius: "var(--radius-sm)" }}
              disabled={resolvingId !== null}
            >
              <Home size={14} /> Домашний
            </button>
            <button
              className="ghost"
              onClick={() => resolveSelected("SKIP")}
              style={{ padding: "0.5rem 1rem", fontSize: "0.82rem", fontWeight: 600, border: "1px solid var(--line)" }}
              disabled={resolvingId !== null}
            >
              Пропустить
            </button>
            <button
              className="ghost"
              onClick={() => setSelectedIds([])}
              style={{ padding: "0.5rem", borderRadius: "50%", width: "32px", height: "32px", display: "grid", placeItems: "center" }}
              title="Снять выделение"
            >
              <X size={14} />
            </button>
          </div>
        </div>
      )}
    </section>
  );
}