import { useEffect, useMemo, useState } from "react";
import { useLocation, useNavigate, useParams } from "react-router-dom";

import { api } from "../api/client";
import { useToast } from "../components/ToastProvider";
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

type ReviewResolution = {
  id?: number;
  resolution?: string;
  actor?: string;
  created_at?: string;
  note?: string;
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

type ReviewPayload = Record<string, unknown> & {
  system_id?: number | null;
  telegram_id?: string | null;
  username?: string | null;
  uuid?: string | null;
  latest_event?: Record<string, unknown> & { bundle?: Record<string, unknown> };
  resolutions?: ReviewResolution[];
  related_cases?: RelatedCase[];
};

type ReviewQueueLocationState = {
  reviewQueueSearch?: string;
  reviewQueueItemIds?: number[];
  reviewQueueCurrentIndex?: number;
};

export function ReviewDetailPage() {
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
  const relatedCases = Array.isArray(data?.related_cases) ? data.related_cases : [];
  const resolutions = Array.isArray(data?.resolutions) ? data.resolutions : [];

  return (
    <section className="page review-detail-page">
      <div className="page-header page-header-stack">
        <div>
          <span className="eyebrow">{t("reviewDetail.eyebrow")}</span>
          <h1>{t("reviewDetail.title", { caseId })}</h1>
          <p className="page-lede">{t("reviewDetail.description")}</p>
        </div>
        <button className="ghost small-button" onClick={() => navigate(queueReturnPath)}>
          {t("reviewDetail.backToQueue")}
        </button>
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
                <div><dt>{t("reviewDetail.fields.username")}</dt><dd>{formatValue(data.username as string | null | undefined)}</dd></div>
                <div><dt>{t("reviewDetail.fields.systemId")}</dt><dd>{formatValue(data.system_id as number | null | undefined)}</dd></div>
                <div><dt>{t("reviewDetail.fields.telegramId")}</dt><dd>{formatValue(data.telegram_id as string | null | undefined)}</dd></div>
                <div><dt>{t("reviewDetail.fields.uuid")}</dt><dd>{formatValue(data.uuid as string | null | undefined)}</dd></div>
                <div><dt>{t("reviewDetail.fields.ip")}</dt><dd>{formatValue(data.ip as string | undefined)}</dd></div>
                <div><dt>{t("reviewDetail.fields.tag")}</dt><dd>{formatValue(data.tag as string | undefined)}</dd></div>
                <div><dt>{t("reviewDetail.fields.verdict")}</dt><dd>{formatValue(data.verdict as string | undefined)}</dd></div>
                <div><dt>{t("reviewDetail.fields.confidence")}</dt><dd>{formatValue(data.confidence_band as string | undefined)}</dd></div>
                <div><dt>{t("reviewDetail.fields.punitive")}</dt><dd>{Number(data.punitive_eligible || 0) ? t("common.yes") : t("common.no")}</dd></div>
                <div><dt>{t("reviewDetail.fields.opened")}</dt><dd>{formatDisplayDateTime(data.opened_at as string | undefined, t("common.notAvailable"), language)}</dd></div>
                <div><dt>{t("reviewDetail.fields.updated")}</dt><dd>{formatDisplayDateTime(data.updated_at as string | undefined, t("common.notAvailable"), language)}</dd></div>
                <div><dt>{t("reviewDetail.fields.isp")}</dt><dd>{formatValue(data.isp as string | undefined)}</dd></div>
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
                      <strong className="review-detail-item-title">{formatValue(reason.code)}</strong>
                      <span className="review-detail-item-copy">{formatValue(reason.message)}</span>
                      <span className="review-detail-item-meta">
                        {formatValue(reason.source)} · {formatValue(reason.direction)} · {formatValue(reason.weight)}
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
              <p className="muted">{t("reviewDetail.resolutionHint")}</p>
              <textarea
                className="note-box"
                placeholder={t("reviewDetail.resolution.placeholder")}
                value={note}
                onChange={(event) => setNote(event.target.value)}
              />
              <div className="action-row action-row-vertical">
                <button disabled={resolving} onClick={() => resolve("MOBILE")}>{t("reviewDetail.resolution.mobile")}</button>
                <button disabled={resolving} onClick={() => resolve("HOME")}>{t("reviewDetail.resolution.home")}</button>
                <button className="ghost" disabled={resolving} onClick={() => resolve("SKIP")}>
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
