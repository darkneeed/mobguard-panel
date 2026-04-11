import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

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

export function ReviewDetailPage() {
  const { t, language } = useI18n();
  const { pushToast } = useToast();
  const { caseId = "" } = useParams();
  const navigate = useNavigate();
  const [data, setData] = useState<ReviewPayload | null>(null);
  const [note, setNote] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [resolving, setResolving] = useState(false);

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
      navigate("/");
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
  const homeSources = Array.from(new Set(reasons.filter((reason) => String(reason.direction).toUpperCase() === "HOME" && Number(reason.weight || 0) < 0).map((reason) => String(reason.source || ""))));
  const mobileSources = Array.from(new Set(reasons.filter((reason) => String(reason.direction).toUpperCase() === "MOBILE" && Number(reason.weight || 0) > 0).map((reason) => String(reason.source || ""))));
  const relatedCases = Array.isArray(data?.related_cases) ? data.related_cases : [];
  const resolutions = Array.isArray(data?.resolutions) ? data.resolutions : [];

  return (
    <section className="page">
      <div className="page-header page-header-stack">
        <div>
          <span className="eyebrow">{t("reviewDetail.eyebrow")}</span>
          <h1>{t("reviewDetail.title", { caseId })}</h1>
          <p className="page-lede">{t("reviewDetail.description")}</p>
        </div>
        <button className="ghost small-button" onClick={() => navigate("/queue")}>
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

            <div className="detail-grid">
              <div className="panel">
                <h2>{t("reviewDetail.sections.reasons")}</h2>
                <ul className="reason-list">
                  {reasons.map((reason, index) => (
                    <li key={`${String(reason.code)}-${index}`}>
                      <strong>{formatValue(reason.code)}</strong>
                      <span>{formatValue(reason.message)}</span>
                      <span>{formatValue(reason.source)} · {formatValue(reason.direction)} · {formatValue(reason.weight)}</span>
                    </li>
                  ))}
                </ul>
              </div>

              <div className="panel">
                <h2>{t("reviewDetail.sections.providerEvidence")}</h2>
                <ul className="reason-list">
                  <li>
                    <strong>{formatValue(providerEvidence.provider_key as string | number | null | undefined)}</strong>
                    <span>{formatValue(providerEvidence.provider_classification as string | number | null | undefined)} · {formatValue(providerEvidence.service_type_hint as string | number | null | undefined)}</span>
                    <span>{Boolean(providerEvidence.service_conflict) ? t("reviewDetail.providerEvidence.conflict") : t("reviewDetail.providerEvidence.clear")}</span>
                    <span>{Boolean(providerEvidence.review_recommended) ? t("reviewDetail.providerEvidence.reviewFirst") : t("reviewDetail.providerEvidence.autoReady")}</span>
                  </li>
                  <li>
                    <strong>{t("reviewDetail.providerEvidence.homeSources")}</strong>
                    <span>{homeSources.length > 0 ? homeSources.join(", ") : t("common.notAvailable")}</span>
                  </li>
                  <li>
                    <strong>{t("reviewDetail.providerEvidence.mobileSources")}</strong>
                    <span>{mobileSources.length > 0 ? mobileSources.join(", ") : t("common.notAvailable")}</span>
                  </li>
                  <li>
                    <strong>{t("reviewDetail.providerEvidence.matchedAliases")}</strong>
                    <span>{Array.isArray(providerEvidence.matched_aliases) && providerEvidence.matched_aliases.length > 0 ? providerEvidence.matched_aliases.join(", ") : t("common.notAvailable")}</span>
                  </li>
                  <li>
                    <strong>{t("reviewDetail.providerEvidence.mobileMarkers")}</strong>
                    <span>{Array.isArray(providerEvidence.provider_mobile_markers) && providerEvidence.provider_mobile_markers.length > 0 ? providerEvidence.provider_mobile_markers.join(", ") : t("common.notAvailable")}</span>
                  </li>
                  <li>
                    <strong>{t("reviewDetail.providerEvidence.homeMarkers")}</strong>
                    <span>{Array.isArray(providerEvidence.provider_home_markers) && providerEvidence.provider_home_markers.length > 0 ? providerEvidence.provider_home_markers.join(", ") : t("common.notAvailable")}</span>
                  </li>
                </ul>
              </div>

              <div className="panel">
                <h2>{t("reviewDetail.sections.log")}</h2>
                <pre className="log-box">{Array.isArray(bundle?.log) ? bundle?.log.join("\n") : ""}</pre>
              </div>

              <div className="panel">
                <h2>{t("reviewDetail.sections.history")}</h2>
                <ul className="reason-list">
                  {resolutions.length === 0 ? <li><span>{t("reviewDetail.history.empty")}</span></li> : null}
                  {resolutions.map((resolution) => (
                    <li key={String(resolution.id)}>
                      <strong>{formatValue(resolution.resolution)}</strong>
                      <span>
                        {formatValue(resolution.actor)} · {formatDisplayDateTime(resolution.created_at, t("common.notAvailable"), language)}
                      </span>
                      <span>{formatValue(resolution.note)}</span>
                    </li>
                  ))}
                </ul>
              </div>

              <div className="panel">
                <h2>{t("reviewDetail.sections.linkedContext")}</h2>
                <ul className="reason-list">
                  {relatedCases.length === 0 ? <li><span>{t("reviewDetail.linkedCases.empty")}</span></li> : null}
                  {relatedCases.map((item) => (
                    <li key={String(item.id)}>
                      <strong>{t("reviewDetail.linkedCases.caseLabel", { id: formatValue(item.id) })}</strong>
                      <span>
                        {formatValue(item.username)} · {formatValue(item.ip)} · {formatValue(item.verdict)} / {formatValue(item.confidence_band)}
                      </span>
                      <span>
                        {formatValue(item.system_id)} · {formatValue(item.telegram_id)} · {formatValue(item.uuid)}
                      </span>
                      <span>{formatDisplayDateTime(item.updated_at, t("common.notAvailable"), language)}</span>
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
