import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { api } from "../api/client";
import { useI18n } from "../localization";
import { formatDisplayDateTime } from "../utils/datetime";

type ReviewReason = {
  code?: string;
  message?: string;
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
  const { caseId = "" } = useParams();
  const navigate = useNavigate();
  const [data, setData] = useState<ReviewPayload | null>(null);
  const [note, setNote] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    api
      .getReview(caseId)
      .then((payload) => setData(payload as ReviewPayload))
      .catch((err: Error) => setError(err.message));
  }, [caseId]);

  function formatValue(value: string | number | null | undefined): string {
    return value === null || value === undefined || value === "" ? t("common.notAvailable") : String(value);
  }

  async function resolve(resolution: string) {
    try {
      await api.resolveReview(caseId, resolution, note);
      navigate("/");
    } catch (err) {
      setError(err instanceof Error ? err.message : t("reviewDetail.errors.resolveFailed"));
    }
  }

  const bundle = data?.latest_event?.bundle;
  const reasons = (Array.isArray(bundle?.reasons) ? bundle?.reasons : []) as ReviewReason[];
  const relatedCases = Array.isArray(data?.related_cases) ? data.related_cases : [];
  const resolutions = Array.isArray(data?.resolutions) ? data.resolutions : [];

  return (
    <section className="page">
      <div className="page-header">
        <div>
          <span className="eyebrow">{t("reviewDetail.eyebrow")}</span>
          <h1>{t("reviewDetail.title", { caseId })}</h1>
        </div>
      </div>

      {error ? <div className="error-box">{error}</div> : null}
      {!data ? <div className="panel">{t("reviewDetail.loading")}</div> : null}

      {data ? (
        <div className="detail-grid">
          <div className="panel">
            <h2>{t("reviewDetail.sections.summary")}</h2>
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

          <div className="panel">
            <h2>{t("reviewDetail.sections.reasons")}</h2>
            <ul className="reason-list">
              {reasons.map((reason, index) => (
                <li key={`${String(reason.code)}-${index}`}>
                  <strong>{formatValue(reason.code)}</strong>
                  <span>{formatValue(reason.message)}</span>
                </li>
              ))}
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

          <div className="panel">
            <h2>{t("reviewDetail.sections.resolution")}</h2>
            <textarea
              className="note-box"
              placeholder={t("reviewDetail.resolution.placeholder")}
              value={note}
              onChange={(event) => setNote(event.target.value)}
            />
            <div className="action-row">
              <button onClick={() => resolve("MOBILE")}>{t("reviewDetail.resolution.mobile")}</button>
              <button onClick={() => resolve("HOME")}>{t("reviewDetail.resolution.home")}</button>
              <button className="ghost" onClick={() => resolve("SKIP")}>
                {t("reviewDetail.resolution.skip")}
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </section>
  );
}
