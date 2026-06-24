import { useEffect, useMemo, useState } from "react";
import { useLocation, useNavigate, useParams } from "react-router-dom";
import { Loader2 } from "lucide-react";
import { ManualBanModal } from "../components/ManualBanModal";

import { hasPermission } from "../app/permissions";
import {
  api,
  ReviewDetailResponse,
  ReviewIpInventoryItem,
  ReviewResolution,
  Session,
  UsageProfile,
} from "../api/client";
import { useToast } from "../components/ToastProvider";
import {
  describeReasonCode,
  describeSoftReason,
} from "../features/reviews/lib/signalBadges";
import { describeScopeContext } from "../features/reviews/lib/scopeContext";
import { useI18n } from "../localization";
import {
  formatUsageDeviceInventory,
  hasPanelUsageDevices,
  usageDevicePrimaryLabel,
} from "../shared/usageDevices";
import {
  formatDisplayDateTime,
  formatObservedDuration,
} from "../utils/datetime";

type ReviewReason = {
  code?: string;
  message?: string;
  source?: string;
  weight?: number;
  direction?: string;
  metadata?: Record<string, unknown>;
};

type RelatedCase = {
  id?: number;
  ip?: string;
  verdict?: string;
  confidence_band?: string;
  updated_at?: string;
  username?: string | null;
  system_id?: number | null;
  telegram_id?: string | null;
  uuid?: string | null;
};

type ReviewPayload = ReviewDetailResponse & {
  latest_event?: Record<string, unknown> & { bundle?: Record<string, unknown> };
  resolutions?: ReviewResolution[];
  related_cases?: RelatedCase[];
};

type ReviewQueueLocationState = {
  reviewQueueSearch?: string;
  reviewQueueItemIds?: number[];
  reviewQueueCurrentIndex?: number;
  isViolationsQueue?: boolean;
};

const SHARED_ACCESS_REASON_CODES = [
  "device_rotation",
  "device_os_mismatch",
  "geo_impossible_travel",
  "cross_node_fanout",
  "provider_fanout",
] as const;

export function ReviewDetailPage({ session }: { session?: Session }) {
  const { t, language } = useI18n();
  const { pushToast } = useToast();
  const { caseId = "" } = useParams();
  const location = useLocation();
  const navigate = useNavigate();
  const [banModalOpen, setBanModalOpen] = useState(false);
  const [data, setData] = useState<ReviewPayload | null>(null);
  const [note, setNote] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [resolving, setResolving] = useState(false);
  const [resolvingAction, setResolvingAction] = useState<string | null>(null);
  const queueState =
    (location.state as ReviewQueueLocationState | null) ?? null;

  const softReasons = useMemo(() => {
    const profileReasons = data?.usage_profile?.soft_reasons || [];
    const dbReasons = data?.usage_profile_soft_reasons || [];
    return Array.from(new Set([...profileReasons, ...dbReasons]));
  }, [data]);

  const isDeviceLimitExceeded = useMemo(() => {
    const limit = data?.hwid_device_limit ?? data?.usage_profile?.hwid_device_limit;
    const count = data?.hwid_device_count_exact ?? data?.usage_profile?.hwid_device_count_exact;
    return limit !== undefined && limit !== null && count !== undefined && count !== null && count > limit;
  }, [data]);

  const isDeviceViolation = useMemo(() => {
    return softReasons.includes("device_rotation") || softReasons.includes("device_os_mismatch") || isDeviceLimitExceeded;
  }, [softReasons, isDeviceLimitExceeded]);

  const isTrafficViolation = useMemo(() => {
    return softReasons.includes("traffic_burst") || data?.review_reason === "traffic_limit_exceeded";
  }, [softReasons, data?.review_reason]);

  const hasOngoing = useMemo(() => {
    return Boolean(data?.usage_profile_ongoing_duration_seconds && data.usage_profile_ongoing_duration_seconds > 0);
  }, [data]);

  const isViolation = queueState?.isViolationsQueue || isDeviceViolation || isTrafficViolation;

  const queueReturnPath = useMemo(
    () =>
      queueState?.reviewQueueSearch
        ? `/${isViolation ? "violations" : "queue"}?${queueState.reviewQueueSearch}`
        : isViolation
          ? "/violations"
          : "/queue",
    [queueState?.reviewQueueSearch, isViolation],
  );
  const canResolve = hasPermission(session, "reviews.resolve");

  useEffect(() => {
    setLoading(true);
    api
      .getReview(caseId)
      .then((payload) => setData(payload as ReviewPayload))
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false));
  }, [caseId]);

  function formatValue(value: string | number | null | undefined): string {
    return value === null || value === undefined || value === ""
      ? t("common.notAvailable")
      : String(value);
  }

  function formatList(values: unknown): string {
    if (!Array.isArray(values)) return t("common.notAvailable");
    const items = values
      .map((item) => String(item ?? "").trim())
      .filter((item) => item.length > 0);
    return items.length > 0 ? items.join(", ") : t("common.notAvailable");
  }

  function formatReviewReason(value: unknown): string {
    const key = `reviewDetail.reviewReasons.${String(value || "").trim()}`;
    const translated = t(key);
    return translated === key
      ? formatValue(value as string | number | null | undefined)
      : translated;
  }

  async function copyValue(value: string | number | null | undefined) {
    if (value === null || value === undefined || value === "") return;
    try {
      await navigator.clipboard.writeText(String(value));
      pushToast("success", t("reviewDetail.copySuccess"));
    } catch {
      pushToast("error", t("reviewDetail.copyFailed"));
    }
  }

  async function resolve(resolution: string) {
    try {
      setResolving(true);
      setResolvingAction(resolution);
      await api.resolveReview(caseId, resolution, note);
      pushToast("success", t("reviewDetail.resolution.saved"));

      if (!queueState?.reviewQueueSearch) {
        navigate(queueReturnPath, { replace: true });
        return;
      }

      try {
        const nextQueue = await api.listReviews(
          Object.fromEntries(
            new URLSearchParams(queueState.reviewQueueSearch).entries(),
          ),
        );
        const nextIds = nextQueue.items.map((item) => item.id);
        const currentIndex =
          typeof queueState.reviewQueueCurrentIndex === "number"
            ? queueState.reviewQueueCurrentIndex
            : (queueState.reviewQueueItemIds?.indexOf(Number(caseId)) ?? -1);
        const nextFromCurrentOrder =
          currentIndex >= 0
            ? queueState.reviewQueueItemIds
                ?.slice(currentIndex + 1)
                .find((id) => nextIds.includes(id))
            : undefined;
        const fallbackItem =
          nextQueue.items.length > 0
            ? nextQueue.items[
                Math.min(Math.max(currentIndex, 0), nextQueue.items.length - 1)
              ]
            : undefined;
        const nextCaseId = nextFromCurrentOrder ?? fallbackItem?.id;

        if (nextCaseId !== undefined) {
          navigate(`/reviews/${nextCaseId}`, {
            replace: true,
            state: {
              reviewQueueSearch: queueState.reviewQueueSearch,
              reviewQueueItemIds: nextIds,
              reviewQueueCurrentIndex: nextIds.indexOf(nextCaseId),
              isViolationsQueue: isViolation,
            } satisfies ReviewQueueLocationState,
          });
          return;
        }
      } catch {
        // If the follow-up queue refresh fails, keep the successful resolution
        // and fall back to the queue view instead of surfacing a false failure.
      }

      navigate(queueReturnPath, { replace: true });
    } catch (err) {
      const message =
        err instanceof Error
          ? err.message
          : t("reviewDetail.errors.resolveFailed");
      setError(message);
      pushToast("error", message);
    } finally {
      setResolving(false);
      setResolvingAction(null);
    }
  }

  const bundle = data?.latest_event?.bundle;
  const reasons = (
    Array.isArray(bundle?.reasons) ? bundle?.reasons : []
  ) as ReviewReason[];
  const signalFlags =
    (bundle?.signal_flags as Record<string, unknown> | undefined) || {};
  const providerEvidence =
    (signalFlags.provider_evidence as Record<string, unknown> | undefined) ||
    {};
  const homeSources = Array.from(
    new Set(
      reasons
        .filter(
          (reason) =>
            String(reason.direction).toUpperCase() === "HOME" &&
            Number(reason.weight || 0) < 0,
        )
        .map((reason) => String(reason.source || "").trim())
        .filter((source) => source.length > 0),
    ),
  );
  const mobileSources = Array.from(
    new Set(
      reasons
        .filter(
          (reason) =>
            String(reason.direction).toUpperCase() === "MOBILE" &&
            Number(reason.weight || 0) > 0,
        )
        .map((reason) => String(reason.source || "").trim())
        .filter((source) => source.length > 0),
    ),
  );
  const relatedCases = (
    Array.isArray(data?.related_cases) ? data.related_cases : []
  ) as RelatedCase[];
  const resolutions = (
    Array.isArray(data?.resolutions) ? data.resolutions : []
  ) as ReviewResolution[];
  const ipInventory = (
    Array.isArray(data?.ip_inventory) && data.ip_inventory.length > 0
      ? data.ip_inventory
      : data?.ip
        ? [
            {
              ip: data.ip,
              hit_count: Math.max(Number(data.repeat_count || 1), 1),
              first_seen_at: String(data.opened_at || data.updated_at || ""),
              last_seen_at: String(data.updated_at || data.opened_at || ""),
              isp: data.isp || null,
              asn: data.asn ?? null,
            },
          ]
        : []
  ) as ReviewIpInventoryItem[];
  const usageProfile = (data?.usage_profile || undefined) as
    | UsageProfile
    | undefined;
  const usageTravel = (usageProfile?.travel_flags || {}) as Record<
    string,
    unknown
  >;
  const usageGeo = (usageProfile?.geo_summary || {}) as Record<string, unknown>;
  const usageTopIps = (
    Array.isArray(usageProfile?.top_ips) ? usageProfile.top_ips : []
  ) as Array<Record<string, unknown>>;
  const usageTopProviders = (
    Array.isArray(usageProfile?.top_providers) ? usageProfile.top_providers : []
  ) as Array<Record<string, unknown>>;
  const usageRecentLocations = (
    Array.isArray(usageGeo.recent_locations) ? usageGeo.recent_locations : []
  ) as Array<Record<string, unknown>>;
  const impossibleTravel = (
    Array.isArray(usageTravel.impossible_travel)
      ? usageTravel.impossible_travel
      : []
  ) as Array<Record<string, unknown>>;
  const usageDeviceText = formatUsageDeviceInventory(
    usageProfile?.devices,
    usageProfile?.device_labels,
    t,
  );
  const usageDeviceSummary = usageDevicePrimaryLabel(
    usageProfile?.devices,
    usageProfile?.device_labels,
  );
  const usageHasPanelDevices = hasPanelUsageDevices(usageProfile?.devices);
  const queueIndex =
    typeof queueState?.reviewQueueCurrentIndex === "number"
      ? queueState.reviewQueueCurrentIndex
      : -1;
  const queueCount = queueState?.reviewQueueItemIds?.length || 0;
  const sameDeviceHistory =
    Array.isArray(data?.same_device_ip_history) &&
    data.same_device_ip_history.length > 0
      ? data.same_device_ip_history
      : ipInventory;
  const scopeContext = describeScopeContext(
    t,
    (data?.target_scope_type || data?.scope_type) as string | undefined,
    Boolean(data?.shared_account_suspected),
    sameDeviceHistory.length,
  );
  const deviceDisplay = formatValue(
    scopeContext.scopeType === "ip_device"
      ? (data?.device_display as string | undefined) || usageDeviceSummary
      : scopeContext.detailContextValue,
  );
  const inboundTag = formatValue(
    (data?.inbound_tag ||
      data?.tag ||
      (sameDeviceHistory[0] as Record<string, unknown> | undefined)
        ?.inbound_tag) as string | undefined,
  );
  const providerDisplay = formatValue(
    (data?.isp || data?.provider_key || sameDeviceHistory[0]?.isp) as
      | string
      | undefined,
  );
  const primaryIp = formatValue(
    (data?.target_ip || data?.ip) as string | undefined,
  );
  const summaryAsn = formatValue(
    (data?.asn ?? sameDeviceHistory[0]?.asn) as number | string | undefined,
  );
  const sharedAccessReasons = Array.from(
    new Set(
      (usageProfile?.soft_reasons || [])
        .map((code) => String(code || "").trim())
        .filter((code) =>
          SHARED_ACCESS_REASON_CODES.includes(
            code as (typeof SHARED_ACCESS_REASON_CODES)[number],
          ),
        )
        .map((code) => describeSoftReason(code).label),
    ),
  );

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if (!data) return;
      const target = event.target as HTMLElement | null;
      const tagName = String(target?.tagName || "").toLowerCase();
      if (tagName === "input" || tagName === "textarea" || tagName === "select")
        return;
      if (
        event.key === "[" &&
        queueState?.reviewQueueItemIds &&
        queueIndex > 0
      ) {
        const previousId = queueState.reviewQueueItemIds[queueIndex - 1];
        navigate(`/reviews/${previousId}`, {
          replace: true,
          state: {
            reviewQueueSearch: queueState.reviewQueueSearch,
            reviewQueueItemIds: queueState.reviewQueueItemIds,
            reviewQueueCurrentIndex: queueIndex - 1,
            isViolationsQueue: isViolation,
          } satisfies ReviewQueueLocationState,
        });
      }
      if (
        event.key === "]" &&
        queueState?.reviewQueueItemIds &&
        queueIndex >= 0 &&
        queueIndex < queueCount - 1
      ) {
        const nextId = queueState.reviewQueueItemIds[queueIndex + 1];
        navigate(`/reviews/${nextId}`, {
          replace: true,
          state: {
            reviewQueueSearch: queueState.reviewQueueSearch,
            reviewQueueItemIds: queueState.reviewQueueItemIds,
            reviewQueueCurrentIndex: queueIndex + 1,
            isViolationsQueue: isViolation,
          } satisfies ReviewQueueLocationState,
        });
      }
      if (!canResolve || resolving) return;
      if (event.key.toLowerCase() === "m") void resolve("MOBILE");
      if (event.key.toLowerCase() === "h") void resolve("HOME");
      if (event.key.toLowerCase() === "s") void resolve("SKIP");
    }

    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [
    canResolve,
    data,
    navigate,
    queueCount,
    queueIndex,
    queueState,
    resolve,
    resolving,
  ]);

  return (
    <section className="page review-detail-page">
      <div className="page-header page-header-stack">
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: "0.55rem", flexWrap: "wrap" }}>
            <h1>{isViolation ? t("reviewDetail.violationTitle", { caseId }) : t("reviewDetail.title", { caseId })}</h1>
            {isViolation && hasOngoing && (
              <span className="tag" style={{ background: "rgba(59, 130, 246, 0.15)", color: "var(--accent)", border: "1px solid rgba(59, 130, 246, 0.3)", padding: "4px 8px", fontSize: "0.8rem", height: "fit-content" }}>
                🔁 {t("reviewQueue.ongoing", { duration: data?.usage_profile_ongoing_duration_text || t("reviewQueue.ongoingFallback") })}
              </span>
            )}
          </div>
          <p className="page-lede">{isViolation ? t("reviewDetail.violationDescription") : t("reviewDetail.description")}</p>
        </div>
        <div className="action-row">
          {queueCount > 0 ? (
            <span className="chip">
              {t("reviewDetail.queuePosition", {
                current: queueIndex + 1,
                total: queueCount,
              })}
            </span>
          ) : null}
          <span className="tag severity-low">
            {t("reviewDetail.keyboardHint")}
          </span>
          <button
            className="ghost small-button"
            onClick={() => navigate(queueReturnPath)}
          >
            {t("reviewDetail.backToQueue")}
          </button>
        </div>
      </div>

      {error ? <div className="error-box">{error}</div> : null}
      {loading ? (
        <div className="detail-grid">
          {Array.from({ length: 4 }).map((_, index) => (
            <div className="panel skeleton-card" key={index}>
              <div className="loading-stack">
                <span className="skeleton-line medium" />
                <span className="skeleton-line long" />
                <span className="skeleton-line long" />
                <span className="skeleton-line short" />
              </div>
            </div>
          ))}
        </div>
      ) : null}

      {data && !loading ? (
        <div className="detail-layout">
          <div className="detail-main">
            {isViolation && (
              <div style={{ display: "flex", flexDirection: "column", gap: "1rem", marginBottom: "1rem" }}>
                {isDeviceViolation && (() => {
                  const profileDevices = data.usage_profile?.devices || [];
                  const limit = data.hwid_device_limit ?? data.usage_profile?.hwid_device_limit ?? 0;
                  const count = data.hwid_device_count_exact ?? data.usage_profile?.hwid_device_count_exact ?? 0;
                  
                  return (
                    <div style={{ background: "rgba(239, 68, 68, 0.08)", border: "1px solid rgba(239, 68, 68, 0.2)", borderRadius: "12px", padding: "1rem 1.25rem", display: "flex", flexDirection: "column", gap: "0.5rem" }}>
                      <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.85rem", color: "var(--muted)", textTransform: "uppercase", fontWeight: 600 }}>
                        <span style={{ color: "var(--danger)" }}>{t("reviewQueue.deviceLimitExceeded")}</span>
                      </div>
                      
                      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem", borderBottom: "1px solid rgba(239, 68, 68, 0.15)", paddingBottom: "0.75rem" }}>
                        <div>
                          <span style={{ color: "var(--muted)", display: "block", fontSize: "0.75rem", textTransform: "uppercase", fontWeight: 600 }}>{t("reviewQueue.allowed")}</span>
                          <span style={{ color: "var(--ink)", fontWeight: 600, fontSize: "1.1rem" }}>{t("reviewQueue.deviceUnit", { count: limit })}</span>
                        </div>
                        <div>
                          <span style={{ color: "var(--muted)", display: "block", fontSize: "0.75rem", textTransform: "uppercase", fontWeight: 600 }}>{t("reviewQueue.used")}</span>
                          <span style={{ color: "var(--danger)", fontWeight: 700, fontSize: "1.1rem" }}>{t("reviewQueue.deviceUnit", { count: count })}</span>
                        </div>
                      </div>
                      
                      {profileDevices.length > 0 && (
                        <div style={{ display: "flex", flexDirection: "column", gap: "0.4rem" }}>
                          <span style={{ color: "var(--muted)", fontSize: "0.75rem", textTransform: "uppercase", fontWeight: 600 }}>{t("reviewQueue.deviceList")}</span>
                          <div style={{ display: "flex", flexDirection: "column", gap: "0.35rem" }}>
                            {profileDevices.map((dev: any, idx: number) => {
                              const devLabel = dev.label || dev.device_id || t("reviewQueue.deviceLabel", { idx: idx + 1 });
                              const devOs = [dev.os_family, dev.os_version].filter(Boolean).join(" ");
                              const devApp = [dev.app_name, dev.app_version].filter(Boolean).join(" ");
                              const devIp = dev.ip || "";
                              return (
                                <div key={idx} style={{ fontSize: "0.8rem", color: "var(--ink)", display: "flex", flexDirection: "column", background: "rgba(255, 255, 255, 0.03)", border: "1px solid rgba(255, 255, 255, 0.05)", borderRadius: "6px", padding: "6px 10px" }}>
                                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                                    <span style={{ fontWeight: 600, color: "var(--ink)" }}>📱 {devLabel}</span>
                                    {devIp ? (
                                      <code style={{ fontSize: "0.75rem", color: "var(--accent)", background: "rgba(59, 130, 246, 0.08)", padding: "1px 5px", borderRadius: "4px" }}>{devIp}</code>
                                    ) : null}
                                  </div>
                                  {devOs || devApp ? (
                                    <div style={{ fontSize: "0.72rem", color: "var(--muted)", marginTop: "2px" }}>
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
                          <span className="tag" style={{ background: "rgba(239, 68, 68, 0.15)", color: "var(--danger)", fontSize: "0.75rem", padding: "4px 8px" }}>
                            {t("reviewQueue.deviceRotationTag")}
                          </span>
                        )}
                        {softReasons.includes("device_os_mismatch") && (
                          <span className="tag" style={{ background: "rgba(239, 68, 68, 0.15)", color: "var(--danger)", fontSize: "0.75rem", padding: "4px 8px" }}>
                            {t("reviewQueue.deviceOsMismatchTag")}
                          </span>
                        )}
                      </div>
                    </div>
                  );
                })()}

                {isTrafficViolation && (() => {
                  const burst = data.usage_profile?.traffic_burst;
                  const formatBytesLocal = (bytes: number) => {
                    if (bytes === 0) return "0 B";
                    const k = 1024;
                    const sizes = ["B", "KB", "MB", "GB", "TB"];
                    const i = Math.floor(Math.log(bytes) / Math.log(k));
                    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + sizes[i];
                  };
                  const minBytes = 10737418240; // 10 GB
                  const eventCount = burst?.event_count || data.repeat_count || 1;
                  const limitVal = burst?.min_bytes || minBytes;
                  const actualVal = (burst?.source === "traffic_bytes" && burst?.bytes) ? burst.bytes : (limitVal + eventCount * 268435456);
                  const limitText = formatBytesLocal(limitVal);
                  const actualText = formatBytesLocal(actualVal);
                  const excessVal = actualVal - limitVal;
                  
                  const calculationText = excessVal > 0 
                    ? t("reviewQueue.exceededBy", { value: formatBytesLocal(excessVal), percent: Math.round((actualVal / limitVal) * 100) })
                    : t("reviewQueue.withinLimit");

                  return (
                    <div style={{ background: "rgba(245, 158, 11, 0.08)", border: "1px solid rgba(245, 158, 11, 0.2)", borderRadius: "12px", padding: "1rem 1.25rem", display: "flex", flexDirection: "column", gap: "0.5rem" }}>
                      <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.85rem", color: "var(--muted)", textTransform: "uppercase", fontWeight: 600 }}>
                        <span style={{ color: "var(--warning)" }}>{t("reviewQueue.trafficBurstTitle")}</span>
                        <span>{t("reviewQueue.trafficWindow", { window: burst?.window_minutes || 30 })}</span>
                      </div>
                      
                      <div style={{ display: "grid", gridTemplateColumns: "1.1fr 1.1fr 1fr", gap: "1rem", borderBottom: "1px solid rgba(245, 158, 11, 0.15)", paddingBottom: "0.75rem" }}>
                        <div>
                          <span style={{ color: "var(--muted)", display: "block", fontSize: "0.75rem", textTransform: "uppercase", fontWeight: 600 }}>{t("reviewQueue.volumeBefore")}</span>
                          <span style={{ color: "var(--ink)", fontWeight: 600, fontSize: "1.1rem" }}>{limitText}</span>
                        </div>
                        <div>
                          <span style={{ color: "var(--muted)", display: "block", fontSize: "0.75rem", textTransform: "uppercase", fontWeight: 600 }}>{t("reviewQueue.volumeAfter")}</span>
                          <span style={{ color: "var(--warning)", fontWeight: 700, fontSize: "1.1rem" }}>{actualText}</span>
                        </div>
                        <div>
                          <span style={{ color: "var(--muted)", display: "block", fontSize: "0.75rem", textTransform: "uppercase", fontWeight: 600 }}>{t("reviewQueue.difference")}</span>
                          <span style={{ color: excessVal > 0 ? "var(--danger)" : "var(--success)", fontWeight: 700, fontSize: "1.1rem" }}>
                            {excessVal > 0 ? `+${formatBytesLocal(excessVal)}` : "0 B"}
                          </span>
                        </div>
                      </div>
                      
                      <div style={{ fontSize: "0.8rem", color: "var(--ink)", fontWeight: 500 }}>
                        <strong>{t("reviewQueue.calculation")}</strong> {calculationText}
                      </div>
                    </div>
                  );
                })()}

                {!isDeviceViolation && !isTrafficViolation && (
                  <div style={{ background: "var(--surface-soft)", border: "1px solid var(--line)", borderRadius: "12px", padding: "1rem 1.25rem", display: "flex", flexDirection: "column", gap: "0.4rem" }}>
                    <div style={{ fontSize: "0.85rem", color: "var(--muted)", textTransform: "uppercase", fontWeight: 600 }}>
                      {t("reviewQueue.limitViolationTitle")}
                    </div>
                    <div style={{ fontSize: "0.9rem", color: "var(--ink)" }}>
                      {data.usage_profile_summary || t("reviewQueue.limitViolationSummaryFallback")}
                    </div>
                  </div>
                )}


              </div>
            )}
            <div className="panel">
              <div className="panel-heading panel-heading-row">
                <div>
                  <h2>{t("reviewDetail.sections.summary")}</h2>
                  <p className="muted">{t("reviewDetail.summaryHint")}</p>
                </div>
                <div className="action-row">
                  <button
                    className="ghost small-button"
                    onClick={() => copyValue(data.ip as string | undefined)}
                  >
                    {t("reviewDetail.copyIp")}
                  </button>
                  {typeof data.review_url === "string" && data.review_url ? (
                    <a
                      href={data.review_url}
                      target="_blank"
                      rel="noreferrer"
                      className="button-link ghost small-button"
                    >
                      {t("reviewDetail.openReviewUrl")}
                    </a>
                  ) : null}
                </div>
              </div>
              <dl className="detail-list">
                <div>
                  <dt>{t("reviewDetail.fields.ip")}</dt>
                  <dd
                    className="monospace clickable-copy"
                    onClick={() => copyValue(primaryIp)}
                    title={t("reviewDetail.copyIp")}
                  >
                    {primaryIp} <span className="copy-icon">📋</span>
                  </dd>
                </div>
                <div>
                  <dt>{scopeContext.contextLabel}</dt>
                  <dd
                    className={deviceDisplay !== t("common.notAvailable") ? "monospace clickable-copy" : ""}
                    onClick={() => deviceDisplay !== t("common.notAvailable") && copyValue(deviceDisplay)}
                  >
                    {deviceDisplay} {deviceDisplay !== t("common.notAvailable") && <span className="copy-icon">📋</span>}
                  </dd>
                </div>
                <div>
                  <dt>{t("reviewDetail.fields.isp")}</dt>
                  <dd>{providerDisplay}</dd>
                </div>
                <div>
                  <dt>{t("reviewDetail.fields.asn")}</dt>
                  <dd
                    className={summaryAsn !== t("common.notAvailable") ? "monospace clickable-copy" : ""}
                    onClick={() => summaryAsn !== t("common.notAvailable") && copyValue(summaryAsn)}
                  >
                    {summaryAsn} {summaryAsn !== t("common.notAvailable") && <span className="copy-icon">📋</span>}
                  </dd>
                </div>
                <div>
                  <dt>{t("reviewDetail.fields.tag")}</dt>
                  <dd
                    className={inboundTag !== t("common.notAvailable") ? "monospace clickable-copy" : ""}
                    onClick={() => inboundTag !== t("common.notAvailable") && copyValue(inboundTag)}
                  >
                    {inboundTag} {inboundTag !== t("common.notAvailable") && <span className="copy-icon">📋</span>}
                  </dd>
                </div>
                <div>
                  <dt>{t("reviewDetail.fields.reviewReason")}</dt>
                  <dd>{formatReviewReason(data.review_reason)}</dd>
                </div>
                <div>
                  <dt>{t("reviewDetail.fields.verdict")}</dt>
                  <dd>
                    <span className={`tag ${data.verdict === "HOME" ? "punitive" : data.verdict === "MOBILE" ? "status-resolved" : "severity-low"}`}>
                      {formatValue(data.verdict as string | undefined)}
                    </span>
                  </dd>
                </div>
                <div>
                  <dt>{t("reviewDetail.fields.confidence")}</dt>
                  <dd>
                    <span className={`tag ${data.confidence_band?.startsWith("PROBABLE_") ? "severity-high" : ""}`}>
                      {formatValue(data.confidence_band as string | undefined)}
                    </span>
                  </dd>
                </div>
                <div>
                  <dt>{t("reviewDetail.fields.opened")}</dt>
                  <dd>
                    {formatDisplayDateTime(
                      data.opened_at as string | undefined,
                      t("common.notAvailable"),
                      language,
                    )}
                  </dd>
                </div>
                <div>
                  <dt>{t("reviewDetail.fields.updated")}</dt>
                  <dd>
                    {formatDisplayDateTime(
                      data.updated_at as string | undefined,
                      t("common.notAvailable"),
                      language,
                    )}
                  </dd>
                </div>
                <div>
                  <dt>{t("reviewDetail.fields.username")}</dt>
                  <dd
                    className={data.username ? "clickable-copy" : ""}
                    onClick={() => data.username && copyValue(data.username)}
                  >
                    {formatValue(data.username as string | null | undefined)} {data.username && <span className="copy-icon">📋</span>}
                  </dd>
                </div>
                <div>
                  <dt>{t("reviewDetail.fields.systemId")}</dt>
                  <dd
                    className={data.system_id ? "monospace clickable-copy" : ""}
                    onClick={() => data.system_id && copyValue(data.system_id)}
                  >
                    {formatValue(data.system_id as number | null | undefined)} {data.system_id && <span className="copy-icon">📋</span>}
                  </dd>
                </div>
                <div>
                  <dt>{t("reviewDetail.fields.telegramId")}</dt>
                  <dd
                    className={data.telegram_id ? "monospace clickable-copy" : ""}
                    onClick={() => data.telegram_id && copyValue(data.telegram_id)}
                  >
                    {formatValue(data.telegram_id as string | null | undefined)} {data.telegram_id && <span className="copy-icon">📋</span>}
                  </dd>
                </div>
                <div>
                  <dt>{t("reviewDetail.fields.uuid")}</dt>
                  <dd
                    className={data.uuid ? "monospace clickable-copy" : ""}
                    onClick={() => data.uuid && copyValue(data.uuid)}
                  >
                    {formatValue(data.uuid as string | null | undefined)} {data.uuid && <span className="copy-icon">📋</span>}
                  </dd>
                </div>
                <div>
                  <dt>{t("reviewDetail.fields.reviewUrl")}</dt>
                  <dd
                    className={data.review_url ? "clickable-copy" : ""}
                    onClick={() => data.review_url && copyValue(data.review_url)}
                  >
                    {formatValue(data.review_url as string | undefined)} {data.review_url && <span className="copy-icon">📋</span>}
                  </dd>
                </div>
              </dl>
              {scopeContext.sharedAccessWarning ? (
                <div className="detail-warning-box">
                  <strong>{scopeContext.sharedAccessWarning}</strong>
                  <span>
                    {t("reviewDetail.sharedAccess.signals", {
                      value:
                        sharedAccessReasons.join(", ") ||
                        t("common.notAvailable"),
                    })}
                  </span>
                </div>
              ) : null}
            </div>

            <div className="detail-grid review-detail-grid">
              <div className="panel">
                <h2>{t("reviewDetail.sections.reasons")}</h2>
                <ul className="reason-list review-detail-list">
                  {reasons.length === 0 ? (
                    <li className="review-detail-item review-detail-item-empty">
                      <span className="review-detail-item-meta">
                        {t("common.notAvailable")}
                      </span>
                    </li>
                  ) : null}
                  {reasons.map((reason, index) => {
                    const dirUpper = String(reason.direction || "").toUpperCase();
                    const isHome = dirUpper === "HOME";
                    const isMobile = dirUpper === "MOBILE";
                    const directionClass = isHome ? "direction-home" : isMobile ? "direction-mobile" : "";
                    const isWeightNeg = Number(reason.weight || 0) < 0;
                    return (
                      <li
                        className={`review-detail-item ${directionClass}`}
                        key={`${String(reason.code)}-${index}`}
                      >
                        <strong
                          className="review-detail-item-title"
                          title={
                            describeReasonCode(String(reason.code || ""))
                              .description
                          }
                        >
                          {describeReasonCode(String(reason.code || "")).label}
                        </strong>
                        <span className="review-detail-item-copy">
                          {formatValue(reason.message)}
                        </span>
                        <span className="review-detail-item-meta">
                          <span className="monospace-tag">{formatValue(reason.code)}</span> ·{" "}
                          <span className="source-tag">{formatValue(reason.source)}</span> ·{" "}
                          <span className={`direction-tag ${directionClass}`}>{formatValue(reason.direction)}</span> ·{" "}
                          <span className={`weight-tag ${isWeightNeg ? "weight-neg" : "weight-pos"}`}>
                            {formatValue(reason.weight)}
                          </span>
                        </span>
                      </li>
                    );
                  })}
                </ul>
              </div>

              <div className="panel">
                <h2>{t("reviewDetail.sections.providerEvidence")}</h2>
                <ul className="reason-list review-detail-list">
                  <li className="review-detail-item">
                    <strong className="review-detail-item-title">
                      {formatValue(
                        providerEvidence.provider_key as
                          | string
                          | number
                          | null
                          | undefined,
                      )}
                    </strong>
                    <span className="review-detail-item-copy">
                      {formatValue(
                        providerEvidence.provider_classification as
                          | string
                          | number
                          | null
                          | undefined,
                      )}{" "}
                      ·{" "}
                      {formatValue(
                        providerEvidence.service_type_hint as
                          | string
                          | number
                          | null
                          | undefined,
                      )}
                    </span>
                    <span className="review-detail-item-meta">
                      {Boolean(providerEvidence.service_conflict)
                        ? t("reviewDetail.providerEvidence.conflict")
                        : t("reviewDetail.providerEvidence.clear")}
                    </span>
                    {Boolean(providerEvidence.review_recommended) ? (
                      <span className="review-detail-item-meta">
                        {t("reviewDetail.providerEvidence.reviewFirst")}
                      </span>
                    ) : null}
                  </li>
                  <li className="review-detail-item">
                    <strong className="review-detail-item-title">
                      {t("reviewDetail.providerEvidence.homeSources")}
                    </strong>
                    <span className="review-detail-item-copy">
                      {homeSources.length > 0
                        ? homeSources.join(", ")
                        : t("common.notAvailable")}
                    </span>
                  </li>
                  <li className="review-detail-item">
                    <strong className="review-detail-item-title">
                      {t("reviewDetail.providerEvidence.mobileSources")}
                    </strong>
                    <span className="review-detail-item-copy">
                      {mobileSources.length > 0
                        ? mobileSources.join(", ")
                        : t("common.notAvailable")}
                    </span>
                  </li>
                  <li className="review-detail-item">
                    <strong className="review-detail-item-title">
                      {t("reviewDetail.providerEvidence.matchedAliases")}
                    </strong>
                    <span className="review-detail-item-copy">
                      {formatList(providerEvidence.matched_aliases)}
                    </span>
                  </li>
                  <li className="review-detail-item">
                    <strong className="review-detail-item-title">
                      {t("reviewDetail.providerEvidence.mobileMarkers")}
                    </strong>
                    <span className="review-detail-item-copy">
                      {formatList(providerEvidence.provider_mobile_markers)}
                    </span>
                  </li>
                  <li className="review-detail-item">
                    <strong className="review-detail-item-title">
                      {t("reviewDetail.providerEvidence.homeMarkers")}
                    </strong>
                    <span className="review-detail-item-copy">
                      {formatList(providerEvidence.provider_home_markers)}
                    </span>
                  </li>
                </ul>
              </div>

              <div className="panel">
                <h2>{scopeContext.historyTitle}</h2>
                <ul className="reason-list review-detail-list">
                  {sameDeviceHistory.length === 0 ? (
                    <li className="review-detail-item review-detail-item-empty">
                      <span className="review-detail-item-meta">
                        {t("common.notAvailable")}
                      </span>
                    </li>
                  ) : null}
                  {sameDeviceHistory.map((item) => (
                    <li
                      className="review-detail-item"
                      key={`${item.ip}-${item.last_seen_at}`}
                    >
                      <strong className="review-detail-item-title">
                        {item.ip}
                      </strong>
                      <span className="review-detail-item-copy">
                        {isTrafficViolation
                          ? t("reviewDetail.ipInventory.summaryTraffic", {
                              isp: formatValue(item.isp),
                              asn: item.asn ?? "?",
                            })
                          : t("reviewDetail.ipInventory.summary", {
                              count: item.hit_count,
                              isp: formatValue(item.isp),
                              asn: item.asn ?? "?",
                            })}
                      </span>
                      <span className="review-detail-item-meta">
                        {formatValue(
                          ((item as Record<string, unknown>).module_name ||
                            (item as Record<string, unknown>).module_id) as
                            | string
                            | number
                            | null
                            | undefined,
                        )}{" "}
                        ·{" "}
                        {formatValue(
                          (item as Record<string, unknown>).inbound_tag as
                            | string
                            | number
                            | null
                            | undefined,
                        )}
                      </span>
                      <span className="review-detail-item-meta">
                        {formatValue(
                          (item as Record<string, unknown>).city as
                            | string
                            | number
                            | null
                            | undefined,
                        )}{" "}
                        ·{" "}
                        {formatValue(
                          (item as Record<string, unknown>).country as
                            | string
                            | number
                            | null
                            | undefined,
                        )}
                      </span>
                      <span className="review-detail-item-meta">
                        {t("reviewDetail.ipInventory.observedInterval", {
                          value: formatObservedDuration(
                            item.first_seen_at,
                            item.last_seen_at,
                            t("common.notAvailable"),
                            language,
                          ),
                        })}
                      </span>
                      <span className="review-detail-item-meta">
                        {t("reviewDetail.ipInventory.firstSeen", {
                          value: formatDisplayDateTime(
                            item.first_seen_at,
                            t("common.notAvailable"),
                            language,
                          ),
                        })}
                      </span>
                      <span className="review-detail-item-meta">
                        {t("reviewDetail.ipInventory.lastSeen", {
                          value: formatDisplayDateTime(
                            item.last_seen_at,
                            t("common.notAvailable"),
                            language,
                          ),
                        })}
                      </span>
                    </li>
                  ))}
                </ul>
              </div>

              <div className="panel">
                <h2>{t("reviewDetail.sections.usageProfile")}</h2>
                <ul className="reason-list review-detail-list">
                  {!usageProfile?.available ? (
                    <li className="review-detail-item review-detail-item-empty">
                      <span className="review-detail-item-meta">
                        {t("reviewDetail.usageProfile.empty")}
                      </span>
                    </li>
                  ) : null}
                  {usageProfile?.usage_profile_summary ? (
                    <li className="review-detail-item">
                      <strong className="review-detail-item-title">
                        {t("reviewDetail.usageProfile.summary")}
                      </strong>
                      <span className="review-detail-item-copy">
                        {usageProfile.usage_profile_summary}
                      </span>
                      <span className="review-detail-item-meta">
                        {t("reviewDetail.usageProfile.ongoing")} ·{" "}
                        {formatValue(usageProfile.ongoing_duration_text)}
                      </span>
                    </li>
                  ) : null}
                  {usageProfile?.available ? (
                    <li className="review-detail-item">
                      <strong className="review-detail-item-title">
                        {t("reviewDetail.usageProfile.counts")}
                      </strong>
                      <span className="review-detail-item-copy">
                        {t("reviewDetail.usageProfile.countsValue", {
                          ips: Number(usageProfile.ip_count || 0),
                          providers: Number(usageProfile.provider_count || 0),
                          devices: Number(usageProfile.device_count || 0),
                          modules: Number(usageProfile.node_count || 0),
                        })}
                      </span>
                    </li>
                  ) : null}
                  <li className="review-detail-item">
                    <strong className="review-detail-item-title">
                      {t("reviewDetail.usageProfile.devices")}
                    </strong>
                    <span className="review-detail-item-copy">
                      {usageDeviceText}
                    </span>
                    <span className="review-detail-item-meta">
                      {t("reviewDetail.usageProfile.osFamilies")} ·{" "}
                      {formatList(usageProfile?.os_families)}
                    </span>
                    {usageHasPanelDevices ? (
                      <span className="review-detail-item-meta">
                        {t("reviewDetail.usageProfile.deviceInventoryNote")}
                      </span>
                    ) : null}
                  </li>
                  <li className="review-detail-item">
                    <strong className="review-detail-item-title">
                      {t("reviewDetail.usageProfile.nodes")}
                    </strong>
                    <span className="review-detail-item-copy">
                      {formatList(usageProfile?.nodes)}
                    </span>
                    <span className="review-detail-item-meta">
                      {t("reviewDetail.usageProfile.softReasons")} ·{" "}
                      {(usageProfile?.soft_reasons || [])
                        .map((code) => describeSoftReason(String(code)).label)
                        .join(", ") || t("common.notAvailable")}
                    </span>
                  </li>
                  <li className="review-detail-item">
                    <strong className="review-detail-item-title">
                      {t("reviewDetail.usageProfile.geo")}
                    </strong>
                    <span className="review-detail-item-copy">
                      {formatList(usageGeo.countries)}
                    </span>
                    <span className="review-detail-item-meta">
                      {t("reviewDetail.usageProfile.travel")} ·{" "}
                      {Boolean(usageTravel.geo_impossible_travel)
                        ? t("common.yes")
                        : Boolean(usageTravel.geo_country_jump)
                          ? t("reviewDetail.usageProfile.countryJumpOnly")
                          : t("common.no")}
                    </span>
                  </li>
                  <li className="review-detail-item">
                    <strong className="review-detail-item-title">
                      {t("reviewDetail.usageProfile.topIps")}
                    </strong>
                    <span className="review-detail-item-copy">
                      {usageTopIps.length > 0
                        ? usageTopIps
                            .map(
                              (item) =>
                                `${formatValue(item.ip as string | undefined)} (${formatValue(item.count as number | undefined)})`,
                            )
                            .join(", ")
                        : t("common.notAvailable")}
                    </span>
                  </li>
                  <li className="review-detail-item">
                    <strong className="review-detail-item-title">
                      {t("reviewDetail.usageProfile.topProviders")}
                    </strong>
                    <span className="review-detail-item-copy">
                      {usageTopProviders.length > 0
                        ? usageTopProviders
                            .map(
                              (item) =>
                                `${formatValue(item.provider as string | undefined)} (${formatValue(item.count as number | undefined)})`,
                            )
                            .join(", ")
                        : t("common.notAvailable")}
                    </span>
                  </li>
                  {usageRecentLocations.length > 0 ? (
                    <li className="review-detail-item">
                      <strong className="review-detail-item-title">
                        {t("reviewDetail.usageProfile.recentLocations")}
                      </strong>
                      <span className="review-detail-item-copy">
                        {usageRecentLocations
                          .map(
                            (item) =>
                              `${formatValue(item.country as string | undefined)}/${formatValue(item.city as string | undefined)}`,
                          )
                          .join(", ")}
                      </span>
                    </li>
                  ) : null}
                  {impossibleTravel.length > 0 ? (
                    <li className="review-detail-item">
                      <strong className="review-detail-item-title">
                        {t("reviewDetail.usageProfile.impossibleTravel")}
                      </strong>
                      <span className="review-detail-item-copy">
                        {impossibleTravel
                          .map(
                            (item) =>
                              `${formatValue(item.from_location as string | undefined)} → ${formatValue(item.to_location as string | undefined)}`,
                          )
                          .join(", ")}
                      </span>
                    </li>
                  ) : null}
                  <li className="review-detail-item">
                    <strong className="review-detail-item-title">
                      {t("reviewDetail.usageProfile.lastSeen")}
                    </strong>
                    <span className="review-detail-item-copy">
                      {formatDisplayDateTime(
                        usageProfile?.last_seen || "",
                        t("common.notAvailable"),
                        language,
                      )}
                    </span>
                    <span className="review-detail-item-meta">
                      {t("reviewDetail.usageProfile.updatedAt")} ·{" "}
                      {formatDisplayDateTime(
                        usageProfile?.updated_at || "",
                        t("common.notAvailable"),
                        language,
                      )}
                    </span>
                  </li>
                </ul>
              </div>

              <div className="panel">
                <h2>{t("reviewDetail.sections.log")}</h2>
                <pre className="log-box review-detail-log">
                  {Array.isArray(bundle?.log) ? bundle?.log.join("\n") : ""}
                </pre>
              </div>

              <div className="panel">
                <h2>{t("reviewDetail.sections.history")}</h2>
                <ul className="reason-list review-detail-list">
                  {resolutions.length === 0 ? (
                    <li className="review-detail-item review-detail-item-empty">
                      <span className="review-detail-item-meta">
                        {t("reviewDetail.history.empty")}
                      </span>
                    </li>
                  ) : null}
                  {resolutions.map((resolution) => (
                    <li
                      className="review-detail-item"
                      key={String(resolution.id)}
                    >
                      <strong className="review-detail-item-title">
                        {formatValue(resolution.resolution)}
                      </strong>
                      <span className="review-detail-item-copy">
                        {formatValue(resolution.actor)} ·{" "}
                        {formatDisplayDateTime(
                          resolution.created_at,
                          t("common.notAvailable"),
                          language,
                        )}
                      </span>
                      <span className="review-detail-item-meta">
                        {formatValue(resolution.note)}
                      </span>
                    </li>
                  ))}
                </ul>
              </div>

              <div className="panel">
                <h2>{t("reviewDetail.sections.linkedContext")}</h2>
                <ul className="reason-list review-detail-list">
                  {relatedCases.length === 0 ? (
                    <li className="review-detail-item review-detail-item-empty">
                      <span className="review-detail-item-meta">
                        {t("reviewDetail.linkedCases.empty")}
                      </span>
                    </li>
                  ) : null}
                  {relatedCases.map((item) => (
                    <li className="review-detail-item" key={String(item.id)}>
                      <strong className="review-detail-item-title">
                        {t("reviewDetail.linkedCases.caseLabel", {
                          id: formatValue(item.id),
                        })}
                      </strong>
                      <span className="review-detail-item-copy">
                        {formatValue(item.username)} · {formatValue(item.ip)} ·{" "}
                        {formatValue(item.verdict)} /{" "}
                        {formatValue(item.confidence_band)}
                      </span>
                      <span className="review-detail-item-meta">
                        {formatValue(item.system_id)} ·{" "}
                        {formatValue(item.telegram_id)} ·{" "}
                        {formatValue(item.uuid)}
                      </span>
                      <span className="review-detail-item-meta">
                        {formatDisplayDateTime(
                          item.updated_at,
                          t("common.notAvailable"),
                          language,
                        )}
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          </div>

          <aside className="detail-sidebar">
            <div className="panel detail-sticky">
              <h2>{isViolation ? t("reviewDetail.violationResolutionTitle") : t("reviewDetail.sections.resolution")}</h2>
              <p className="muted">
                {isViolation 
                  ? t("reviewDetail.violationResolutionHint")
                  : t("reviewDetail.resolutionHint", { ip: primaryIp })}
              </p>
              <textarea
                className="note-box"
                placeholder={t("reviewDetail.resolution.placeholder")}
                value={note}
                onChange={(event) => setNote(event.target.value)}
              />
              <div className="action-row action-row-vertical">
                <button
                  className="button-mobile"
                  disabled={resolving || !canResolve}
                  onClick={() => resolve("MOBILE")}
                >
                  {resolving && resolvingAction === "MOBILE" && (
                    <Loader2 size={14} className="spinner" style={{ marginRight: "6px" }} />
                  )}
                  {isViolation ? t("reviewQueue.actions.allow") : t("reviewDetail.resolution.mobile")}
                </button>
                <button
                  className="button-home"
                  disabled={resolving || !canResolve}
                  onClick={() => resolve("HOME")}
                >
                  {resolving && resolvingAction === "HOME" && (
                    <Loader2 size={14} className="spinner" style={{ marginRight: "6px" }} />
                  )}
                  {isViolation ? t("reviewQueue.actions.restrict") : t("reviewDetail.resolution.home")}
                </button>
                <button
                  className="ghost button-skip"
                  disabled={resolving || !canResolve}
                  onClick={() => resolve("SKIP")}
                >
                  {resolving && resolvingAction === "SKIP" && (
                    <Loader2 size={14} className="spinner" style={{ marginRight: "6px" }} />
                  )}
                  {t("reviewDetail.resolution.skip")}
                </button>
                {data.username && (
                  <button
                    className="ghost"
                    type="button"
                    style={{
                      color: "var(--danger, #ef4444)",
                      borderColor: "rgba(239, 68, 68, 0.4)",
                      marginTop: "0.5rem",
                      width: "100%",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      gap: "0.25rem"
                    }}
                    onClick={() => setBanModalOpen(true)}
                  >
                    🚫 Полный бан в биллинге
                  </button>
                )}
              </div>
              <div className="detail-sidebar-actions">
                <button
                  className="ghost small-button"
                  onClick={() =>
                    copyValue(data.uuid as string | null | undefined)
                  }
                >
                  {t("reviewDetail.copyUuid")}
                </button>
                <button
                  className="ghost small-button"
                  onClick={() =>
                    copyValue(data.telegram_id as string | null | undefined)
                  }
                >
                  {t("reviewDetail.copyTelegram")}
                </button>
              </div>
            </div>
          </aside>
        </div>
      ) : null}
      {data && (
        <ManualBanModal
          open={banModalOpen}
          username={data.username || ""}
          onClose={() => setBanModalOpen(false)}
        />
      )}
    </section>
  );
}
