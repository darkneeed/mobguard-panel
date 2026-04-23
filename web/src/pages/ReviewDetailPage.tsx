import { useEffect, useMemo, useState } from "react";
import { useLocation, useNavigate, useParams } from "react-router-dom";

import { hasPermission } from "../app/permissions";
import {
  api,
  ReviewDetailResponse,
  ReviewIpInventoryItem,
  ReviewResolution,
  Session,
  UsageProfile
} from "../api/client";
import { useToast } from "../components/ToastProvider";
import { describeReasonCode, describeSoftReason } from "../features/reviews/lib/signalBadges";
import { useI18n } from "../localization";
import { formatDisplayDateTime } from "../utils/datetime";

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
};

export function ReviewDetailPage({ session }: { session?: Session }) {
  const { t, language } = useI18n();
  const { pushToast } = useToast();
  const { caseId = "" } = useParams();
  const location = useLocation();
  const navigate = useNavigate();
  const [data, setData] = useState<ReviewPayload | null>(null);
  const [note, setNote] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [resolving, setResolving] = useState(false);
  const queueState = (location.state as ReviewQueueLocationState | null) ?? null;
  const queueReturnPath = useMemo(
    () => (queueState?.reviewQueueSearch ? `/queue?${queueState.reviewQueueSearch}` : "/queue"),
    [queueState?.reviewQueueSearch]
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
    return value === null || value === undefined || value === "" ? t("common.notAvailable") : String(value);
  }

  function formatList(values: unknown): string {
    if (!Array.isArray(values)) return t("common.notAvailable");
    const items = values
      .map((item) => String(item ?? "").trim())
      .filter((item) => item.length > 0);
    return items.length > 0 ? items.join(", ") : t("common.notAvailable");
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
      await api.resolveReview(caseId, resolution, note);
      pushToast("success", t("reviewDetail.resolution.saved"));

      if (!queueState?.reviewQueueSearch) {
        navigate(queueReturnPath, { replace: true });
        return;
      }

      try {
        const nextQueue = await api.listReviews(
          Object.fromEntries(new URLSearchParams(queueState.reviewQueueSearch).entries())
        );
        const nextIds = nextQueue.items.map((item) => item.id);
        const currentIndex =
          typeof queueState.reviewQueueCurrentIndex === "number"
            ? queueState.reviewQueueCurrentIndex
            : queueState.reviewQueueItemIds?.indexOf(Number(caseId)) ?? -1;
        const nextFromCurrentOrder =
          currentIndex >= 0
            ? queueState.reviewQueueItemIds
                ?.slice(currentIndex + 1)
                .find((id) => nextIds.includes(id))
            : undefined;
        const fallbackItem =
          nextQueue.items.length > 0
            ? nextQueue.items[Math.min(Math.max(currentIndex, 0), nextQueue.items.length - 1)]
            : undefined;
        const nextCaseId = nextFromCurrentOrder ?? fallbackItem?.id;

        if (nextCaseId !== undefined) {
          navigate(`/reviews/${nextCaseId}`, {
            replace: true,
            state: {
              reviewQueueSearch: queueState.reviewQueueSearch,
              reviewQueueItemIds: nextIds,
              reviewQueueCurrentIndex: nextIds.indexOf(nextCaseId)
            } satisfies ReviewQueueLocationState
          });
          return;
        }
      } catch {
        // If the follow-up queue refresh fails, keep the successful resolution
        // and fall back to the queue view instead of surfacing a false failure.
      }

      navigate(queueReturnPath, { replace: true });
    } catch (err) {
      const message = err instanceof Error ? err.message : t("reviewDetail.errors.resolveFailed");
      setError(message);
      pushToast("error", message);
    } finally {
      setResolving(false);
    }
  }

  const bundle = data?.latest_event?.bundle;
  const reasons = (Array.isArray(bundle?.reasons) ? bundle?.reasons : []) as ReviewReason[];
  const signalFlags = (bundle?.signal_flags as Record<string, unknown> | undefined) || {};
  const providerEvidence = (signalFlags.provider_evidence as Record<string, unknown> | undefined) || {};
  const homeSources = Array.from(
    new Set(
      reasons
        .filter(
          (reason) =>
            String(reason.direction).toUpperCase() === "HOME" && Number(reason.weight || 0) < 0
        )
        .map((reason) => String(reason.source || "").trim())
        .filter((source) => source.length > 0)
    )
  );
  const mobileSources = Array.from(
    new Set(
      reasons
        .filter(
          (reason) =>
            String(reason.direction).toUpperCase() === "MOBILE" && Number(reason.weight || 0) > 0
        )
        .map((reason) => String(reason.source || "").trim())
        .filter((source) => source.length > 0)
    )
  );
  const relatedCases = (Array.isArray(data?.related_cases) ? data.related_cases : []) as RelatedCase[];
  const resolutions = (Array.isArray(data?.resolutions) ? data.resolutions : []) as ReviewResolution[];
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
              asn: data.asn ?? null
            }
          ]
        : []
  ) as ReviewIpInventoryItem[];
  const usageProfile = (data?.usage_profile || undefined) as UsageProfile | undefined;
  const usageTravel = (usageProfile?.travel_flags || {}) as Record<string, unknown>;
  const usageGeo = (usageProfile?.geo_summary || {}) as Record<string, unknown>;
  const usageTopIps = (Array.isArray(usageProfile?.top_ips) ? usageProfile.top_ips : []) as Array<Record<string, unknown>>;
  const usageTopProviders = (Array.isArray(usageProfile?.top_providers) ? usageProfile.top_providers : []) as Array<Record<string, unknown>>;
  const usageRecentLocations = (Array.isArray(usageGeo.recent_locations) ? usageGeo.recent_locations : []) as Array<Record<string, unknown>>;
  const impossibleTravel = (Array.isArray(usageTravel.impossible_travel) ? usageTravel.impossible_travel : []) as Array<Record<string, unknown>>;
  const queueIndex = typeof queueState?.reviewQueueCurrentIndex === "number" ? queueState.reviewQueueCurrentIndex : -1;
  const queueCount = queueState?.reviewQueueItemIds?.length || 0;
  const sameDeviceHistory = Array.isArray(data?.same_device_ip_history) && data.same_device_ip_history.length > 0
    ? data.same_device_ip_history
    : ipInventory;
  const deviceDisplay = formatValue(data?.device_display as string | undefined);
  const inboundTag = formatValue(((data?.inbound_tag || data?.tag || (sameDeviceHistory[0] as Record<string, unknown> | undefined)?.inbound_tag)) as string | undefined);
  const providerDisplay = formatValue(((data?.isp || data?.provider_key || sameDeviceHistory[0]?.isp)) as string | undefined);
  const primaryIp = formatValue((data?.target_ip || data?.ip) as string | undefined);
  const summaryAsn = formatValue(((data?.asn ?? sameDeviceHistory[0]?.asn) as number | string | undefined));

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if (!data) return;
      const target = event.target as HTMLElement | null;
      const tagName = String(target?.tagName || "").toLowerCase();
      if (tagName === "input" || tagName === "textarea" || tagName === "select") return;
      if (event.key === "[" && queueState?.reviewQueueItemIds && queueIndex > 0) {
        const previousId = queueState.reviewQueueItemIds[queueIndex - 1];
        navigate(`/reviews/${previousId}`, {
          replace: true,
          state: {
            reviewQueueSearch: queueState.reviewQueueSearch,
            reviewQueueItemIds: queueState.reviewQueueItemIds,
            reviewQueueCurrentIndex: queueIndex - 1
          } satisfies ReviewQueueLocationState
        });
      }
      if (event.key === "]" && queueState?.reviewQueueItemIds && queueIndex >= 0 && queueIndex < queueCount - 1) {
        const nextId = queueState.reviewQueueItemIds[queueIndex + 1];
        navigate(`/reviews/${nextId}`, {
          replace: true,
          state: {
            reviewQueueSearch: queueState.reviewQueueSearch,
            reviewQueueItemIds: queueState.reviewQueueItemIds,
            reviewQueueCurrentIndex: queueIndex + 1
          } satisfies ReviewQueueLocationState
        });
      }
      if (!canResolve || resolving) return;
      if (event.key.toLowerCase() === "m") void resolve("MOBILE");
      if (event.key.toLowerCase() === "h") void resolve("HOME");
      if (event.key.toLowerCase() === "s") void resolve("SKIP");
    }

    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [canResolve, data, navigate, queueCount, queueIndex, queueState, resolve, resolving]);

  return (
    <section className="page review-detail-page">
      <div className="page-header page-header-stack">
        <div>
          <span className="eyebrow">{t("reviewDetail.eyebrow")}</span>
          <h1>{t("reviewDetail.title", { caseId })}</h1>
          <p className="page-lede">{t("reviewDetail.description")}</p>
        </div>
        <div className="action-row">
          {queueCount > 0 ? <span className="chip">{t("reviewDetail.queuePosition", { current: queueIndex + 1, total: queueCount })}</span> : null}
          <span className="tag severity-low">{t("reviewDetail.keyboardHint")}</span>
          <button className="ghost small-button" onClick={() => navigate(queueReturnPath)}>
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
            <div className="panel">
              <div className="panel-heading panel-heading-row">
                <div>
                  <h2>{t("reviewDetail.sections.summary")}</h2>
                  <p className="muted">{t("reviewDetail.summaryHint")}</p>
                </div>
                <div className="action-row">
                  <button className="ghost small-button" onClick={() => copyValue(data.ip as string | undefined)}>
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
                <div><dt>{t("reviewDetail.fields.ip")}</dt><dd>{primaryIp}</dd></div>
                <div><dt>{t("reviewDetail.fields.device")}</dt><dd>{deviceDisplay}</dd></div>
                <div><dt>{t("reviewDetail.fields.isp")}</dt><dd>{providerDisplay}</dd></div>
                <div><dt>{t("reviewDetail.fields.asn")}</dt><dd>{summaryAsn}</dd></div>
                <div><dt>{t("reviewDetail.fields.tag")}</dt><dd>{inboundTag}</dd></div>
                <div><dt>{t("reviewDetail.fields.verdict")}</dt><dd>{formatValue(data.verdict as string | undefined)}</dd></div>
                <div><dt>{t("reviewDetail.fields.confidence")}</dt><dd>{formatValue(data.confidence_band as string | undefined)}</dd></div>
                <div><dt>{t("reviewDetail.fields.opened")}</dt><dd>{formatDisplayDateTime(data.opened_at as string | undefined, t("common.notAvailable"), language)}</dd></div>
                <div><dt>{t("reviewDetail.fields.updated")}</dt><dd>{formatDisplayDateTime(data.updated_at as string | undefined, t("common.notAvailable"), language)}</dd></div>
                <div><dt>{t("reviewDetail.fields.username")}</dt><dd>{formatValue(data.username as string | null | undefined)}</dd></div>
                <div><dt>{t("reviewDetail.fields.systemId")}</dt><dd>{formatValue(data.system_id as number | null | undefined)}</dd></div>
                <div><dt>{t("reviewDetail.fields.telegramId")}</dt><dd>{formatValue(data.telegram_id as string | null | undefined)}</dd></div>
                <div><dt>{t("reviewDetail.fields.uuid")}</dt><dd>{formatValue(data.uuid as string | null | undefined)}</dd></div>
                <div><dt>{t("reviewDetail.fields.reviewUrl")}</dt><dd>{formatValue(data.review_url as string | undefined)}</dd></div>
              </dl>
            </div>

            <div className="detail-grid review-detail-grid">
              <div className="panel">
                <h2>{t("reviewDetail.sections.reasons")}</h2>
                <ul className="reason-list review-detail-list">
                  {reasons.length === 0 ? (
                    <li className="review-detail-item review-detail-item-empty">
                      <span className="review-detail-item-meta">{t("common.notAvailable")}</span>
                    </li>
                  ) : null}
                  {reasons.map((reason, index) => (
                    <li className="review-detail-item" key={`${String(reason.code)}-${index}`}>
                      <strong
                        className="review-detail-item-title"
                        title={describeReasonCode(String(reason.code || "")).description}
                      >
                        {describeReasonCode(String(reason.code || "")).label}
                      </strong>
                      <span className="review-detail-item-copy">{formatValue(reason.message)}</span>
                      <span className="review-detail-item-meta">
                        {formatValue(reason.code)} · {formatValue(reason.source)} · {formatValue(reason.direction)} · {formatValue(reason.weight)}
                      </span>
                    </li>
                  ))}
                </ul>
              </div>

              <div className="panel">
                <h2>{t("reviewDetail.sections.providerEvidence")}</h2>
                <ul className="reason-list review-detail-list">
                  <li className="review-detail-item">
                    <strong className="review-detail-item-title">
                      {formatValue(providerEvidence.provider_key as string | number | null | undefined)}
                    </strong>
                    <span className="review-detail-item-copy">
                      {formatValue(providerEvidence.provider_classification as string | number | null | undefined)} · {formatValue(providerEvidence.service_type_hint as string | number | null | undefined)}
                    </span>
                    <span className="review-detail-item-meta">
                      {Boolean(providerEvidence.service_conflict)
                        ? t("reviewDetail.providerEvidence.conflict")
                        : t("reviewDetail.providerEvidence.clear")}
                    </span>
                    <span className="review-detail-item-meta">
                      {Boolean(providerEvidence.review_recommended)
                        ? t("reviewDetail.providerEvidence.reviewFirst")
                        : t("reviewDetail.providerEvidence.autoReady")}
                    </span>
                  </li>
                  <li className="review-detail-item">
                    <strong className="review-detail-item-title">
                      {t("reviewDetail.providerEvidence.homeSources")}
                    </strong>
                    <span className="review-detail-item-copy">
                      {homeSources.length > 0 ? homeSources.join(", ") : t("common.notAvailable")}
                    </span>
                  </li>
                  <li className="review-detail-item">
                    <strong className="review-detail-item-title">
                      {t("reviewDetail.providerEvidence.mobileSources")}
                    </strong>
                    <span className="review-detail-item-copy">
                      {mobileSources.length > 0 ? mobileSources.join(", ") : t("common.notAvailable")}
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
                <h2>{t("reviewDetail.sections.ipInventory")}</h2>
                <ul className="reason-list review-detail-list">
                  {sameDeviceHistory.length === 0 ? (
                    <li className="review-detail-item review-detail-item-empty">
                      <span className="review-detail-item-meta">{t("common.notAvailable")}</span>
                    </li>
                  ) : null}
                  {sameDeviceHistory.map((item) => (
                    <li className="review-detail-item" key={`${item.ip}-${item.last_seen_at}`}>
                      <strong className="review-detail-item-title">{item.ip}</strong>
                      <span className="review-detail-item-copy">
                        {t("reviewDetail.ipInventory.summary", {
                          count: item.hit_count,
                          isp: formatValue(item.isp),
                          asn: item.asn ?? "?"
                        })}
                      </span>
                      <span className="review-detail-item-meta">
                        {formatValue(((item as Record<string, unknown>).module_name || (item as Record<string, unknown>).module_id) as string | number | null | undefined)} · {formatValue((item as Record<string, unknown>).inbound_tag as string | number | null | undefined)}
                      </span>
                      <span className="review-detail-item-meta">
                        {formatValue((item as Record<string, unknown>).city as string | number | null | undefined)} · {formatValue((item as Record<string, unknown>).country as string | number | null | undefined)}
                      </span>
                      <span className="review-detail-item-meta">
                        {t("reviewDetail.ipInventory.firstSeen", {
                          value: formatDisplayDateTime(item.first_seen_at, t("common.notAvailable"), language)
                        })}
                      </span>
                      <span className="review-detail-item-meta">
                        {t("reviewDetail.ipInventory.lastSeen", {
                          value: formatDisplayDateTime(item.last_seen_at, t("common.notAvailable"), language)
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
                      <span className="review-detail-item-meta">{t("reviewDetail.usageProfile.empty")}</span>
                    </li>
                  ) : null}
                  {usageProfile?.usage_profile_summary ? (
                    <li className="review-detail-item">
                      <strong className="review-detail-item-title">{t("reviewDetail.usageProfile.summary")}</strong>
                      <span className="review-detail-item-copy">{usageProfile.usage_profile_summary}</span>
                      <span className="review-detail-item-meta">
                        {t("reviewDetail.usageProfile.ongoing")} · {formatValue(usageProfile.ongoing_duration_text)}
                      </span>
                    </li>
                  ) : null}
                  <li className="review-detail-item">
                    <strong className="review-detail-item-title">{t("reviewDetail.usageProfile.devices")}</strong>
                    <span className="review-detail-item-copy">{formatList(usageProfile?.device_labels)}</span>
                    <span className="review-detail-item-meta">
                      {t("reviewDetail.usageProfile.osFamilies")} · {formatList(usageProfile?.os_families)}
                    </span>
                  </li>
                  <li className="review-detail-item">
                    <strong className="review-detail-item-title">{t("reviewDetail.usageProfile.nodes")}</strong>
                    <span className="review-detail-item-copy">{formatList(usageProfile?.nodes)}</span>
                    <span className="review-detail-item-meta">
                      {t("reviewDetail.usageProfile.softReasons")} · {(usageProfile?.soft_reasons || []).map((code) => describeSoftReason(String(code)).label).join(", ") || t("common.notAvailable")}
                    </span>
                  </li>
                  <li className="review-detail-item">
                    <strong className="review-detail-item-title">{t("reviewDetail.usageProfile.geo")}</strong>
                    <span className="review-detail-item-copy">{formatList(usageGeo.countries)}</span>
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
                    <strong className="review-detail-item-title">{t("reviewDetail.usageProfile.topIps")}</strong>
                    <span className="review-detail-item-copy">
                      {usageTopIps.length > 0
                        ? usageTopIps
                            .map(
                              (item) =>
                                `${formatValue(item.ip as string | undefined)} (${formatValue(item.count as number | undefined)})`
                            )
                            .join(", ")
                        : t("common.notAvailable")}
                    </span>
                  </li>
                  <li className="review-detail-item">
                    <strong className="review-detail-item-title">{t("reviewDetail.usageProfile.topProviders")}</strong>
                    <span className="review-detail-item-copy">
                      {usageTopProviders.length > 0
                        ? usageTopProviders
                            .map(
                              (item) =>
                                `${formatValue(item.provider as string | undefined)} (${formatValue(item.count as number | undefined)})`
                            )
                            .join(", ")
                        : t("common.notAvailable")}
                    </span>
                  </li>
                  {usageRecentLocations.length > 0 ? (
                    <li className="review-detail-item">
                      <strong className="review-detail-item-title">{t("reviewDetail.usageProfile.recentLocations")}</strong>
                      <span className="review-detail-item-copy">
                        {usageRecentLocations
                          .map(
                            (item) =>
                              `${formatValue(item.country as string | undefined)}/${formatValue(item.city as string | undefined)}`
                          )
                          .join(", ")}
                      </span>
                    </li>
                  ) : null}
                  {impossibleTravel.length > 0 ? (
                    <li className="review-detail-item">
                      <strong className="review-detail-item-title">{t("reviewDetail.usageProfile.impossibleTravel")}</strong>
                      <span className="review-detail-item-copy">
                        {impossibleTravel
                          .map(
                            (item) =>
                              `${formatValue(item.from_location as string | undefined)} → ${formatValue(item.to_location as string | undefined)}`
                          )
                          .join(", ")}
                      </span>
                    </li>
                  ) : null}
                  <li className="review-detail-item">
                    <strong className="review-detail-item-title">{t("reviewDetail.usageProfile.lastSeen")}</strong>
                    <span className="review-detail-item-copy">
                      {formatDisplayDateTime(usageProfile?.last_seen || "", t("common.notAvailable"), language)}
                    </span>
                    <span className="review-detail-item-meta">
                      {t("reviewDetail.usageProfile.updatedAt")} ·{" "}
                      {formatDisplayDateTime(usageProfile?.updated_at || "", t("common.notAvailable"), language)}
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
                      <span className="review-detail-item-meta">{t("reviewDetail.history.empty")}</span>
                    </li>
                  ) : null}
                  {resolutions.map((resolution) => (
                    <li className="review-detail-item" key={String(resolution.id)}>
                      <strong className="review-detail-item-title">
                        {formatValue(resolution.resolution)}
                      </strong>
                      <span className="review-detail-item-copy">
                        {formatValue(resolution.actor)} · {formatDisplayDateTime(resolution.created_at, t("common.notAvailable"), language)}
                      </span>
                      <span className="review-detail-item-meta">{formatValue(resolution.note)}</span>
                    </li>
                  ))}
                </ul>
              </div>

              <div className="panel">
                <h2>{t("reviewDetail.sections.linkedContext")}</h2>
                <ul className="reason-list review-detail-list">
                  {relatedCases.length === 0 ? (
                    <li className="review-detail-item review-detail-item-empty">
                      <span className="review-detail-item-meta">{t("reviewDetail.linkedCases.empty")}</span>
                    </li>
                  ) : null}
                  {relatedCases.map((item) => (
                    <li className="review-detail-item" key={String(item.id)}>
                      <strong className="review-detail-item-title">
                        {t("reviewDetail.linkedCases.caseLabel", { id: formatValue(item.id) })}
                      </strong>
                      <span className="review-detail-item-copy">
                        {formatValue(item.username)} · {formatValue(item.ip)} · {formatValue(item.verdict)} / {formatValue(item.confidence_band)}
                      </span>
                      <span className="review-detail-item-meta">
                        {formatValue(item.system_id)} · {formatValue(item.telegram_id)} · {formatValue(item.uuid)}
                      </span>
                      <span className="review-detail-item-meta">
                        {formatDisplayDateTime(item.updated_at, t("common.notAvailable"), language)}
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          </div>

          <aside className="detail-sidebar">
            <div className="panel detail-sticky">
              <h2>{t("reviewDetail.sections.resolution")}</h2>
              <p className="muted">{t("reviewDetail.resolutionHint", { ip: primaryIp })}</p>
              <textarea
                className="note-box"
                placeholder={t("reviewDetail.resolution.placeholder")}
                value={note}
                onChange={(event) => setNote(event.target.value)}
              />
              <div className="action-row action-row-vertical">
                <button disabled={resolving || !canResolve} onClick={() => resolve("MOBILE")}>{t("reviewDetail.resolution.mobile")}</button>
                <button disabled={resolving || !canResolve} onClick={() => resolve("HOME")}>{t("reviewDetail.resolution.home")}</button>
                <button className="ghost" disabled={resolving || !canResolve} onClick={() => resolve("SKIP")}>
                  {t("reviewDetail.resolution.skip")}
                </button>
              </div>
              <div className="detail-sidebar-actions">
                <button className="ghost small-button" onClick={() => copyValue(data.uuid as string | null | undefined)}>
                  {t("reviewDetail.copyUuid")}
                </button>
                <button className="ghost small-button" onClick={() => copyValue(data.telegram_id as string | null | undefined)}>
                  {t("reviewDetail.copyTelegram")}
                </button>
              </div>
            </div>
          </aside>
        </div>
      ) : null}
    </section>
  );
}
