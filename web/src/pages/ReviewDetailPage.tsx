import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { api } from "../api/client";

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

function formatValue(value: string | number | null | undefined): string {
  return value === null || value === undefined || value === "" ? "N/A" : String(value);
}

export function ReviewDetailPage() {
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

  async function resolve(resolution: string) {
    try {
      await api.resolveReview(caseId, resolution, note);
      navigate("/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Resolve failed");
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
          <span className="eyebrow">Case Detail</span>
          <h1>Review case #{caseId}</h1>
        </div>
      </div>

      {error ? <div className="error-box">{error}</div> : null}
      {!data ? <div className="panel">Loading…</div> : null}

      {data ? (
        <div className="detail-grid">
          <div className="panel">
            <h2>Summary</h2>
            <dl className="detail-list">
              <div><dt>Username</dt><dd>{formatValue(data.username as string | null | undefined)}</dd></div>
              <div><dt>System ID</dt><dd>{formatValue(data.system_id as number | null | undefined)}</dd></div>
              <div><dt>Telegram ID</dt><dd>{formatValue(data.telegram_id as string | null | undefined)}</dd></div>
              <div><dt>UUID</dt><dd>{formatValue(data.uuid as string | null | undefined)}</dd></div>
              <div><dt>IP</dt><dd>{formatValue(data.ip as string | undefined)}</dd></div>
              <div><dt>Tag</dt><dd>{formatValue(data.tag as string | undefined)}</dd></div>
              <div><dt>Verdict</dt><dd>{formatValue(data.verdict as string | undefined)}</dd></div>
              <div><dt>Confidence</dt><dd>{formatValue(data.confidence_band as string | undefined)}</dd></div>
              <div><dt>Punitive</dt><dd>{Number(data.punitive_eligible || 0) ? "yes" : "no"}</dd></div>
              <div><dt>Opened</dt><dd>{formatValue(data.opened_at as string | undefined)}</dd></div>
              <div><dt>Updated</dt><dd>{formatValue(data.updated_at as string | undefined)}</dd></div>
              <div><dt>ISP</dt><dd>{formatValue(data.isp as string | undefined)}</dd></div>
              <div><dt>Review URL</dt><dd>{formatValue(data.review_url as string | undefined)}</dd></div>
            </dl>
          </div>

          <div className="panel">
            <h2>Reasons</h2>
            <ul className="reason-list">
              {reasons.map((reason, index) => {
                return (
                  <li key={`${String(reason.code)}-${index}`}>
                    <strong>{formatValue(reason.code)}</strong>
                    <span>{formatValue(reason.message)}</span>
                  </li>
                );
              })}
            </ul>
          </div>

          <div className="panel">
            <h2>Log</h2>
            <pre className="log-box">{Array.isArray(bundle?.log) ? bundle?.log.join("\n") : ""}</pre>
          </div>

          <div className="panel">
            <h2>Resolution history</h2>
            <ul className="reason-list">
              {resolutions.length === 0 ? <li><span>No resolutions yet</span></li> : null}
              {resolutions.map((resolution) => (
                <li key={String(resolution.id)}>
                  <strong>{formatValue(resolution.resolution)}</strong>
                  <span>
                    {formatValue(resolution.actor)} · {formatValue(resolution.created_at)}
                  </span>
                  <span>{formatValue(resolution.note)}</span>
                </li>
              ))}
            </ul>
          </div>

          <div className="panel">
            <h2>Linked user/IP context</h2>
            <ul className="reason-list">
              {relatedCases.length === 0 ? <li><span>No related cases found</span></li> : null}
              {relatedCases.map((item) => (
                <li key={String(item.id)}>
                  <strong>Case #{formatValue(item.id)}</strong>
                  <span>
                    {formatValue(item.username)} · {formatValue(item.ip)} · {formatValue(item.verdict)} / {formatValue(item.confidence_band)}
                  </span>
                  <span>
                    {formatValue(item.system_id)} · {formatValue(item.telegram_id)} · {formatValue(item.uuid)}
                  </span>
                  <span>{formatValue(item.updated_at)}</span>
                </li>
              ))}
            </ul>
          </div>

          <div className="panel">
            <h2>Resolution</h2>
            <textarea
              className="note-box"
              placeholder="Комментарий для аудита"
              value={note}
              onChange={(event) => setNote(event.target.value)}
            />
            <div className="action-row">
              <button onClick={() => resolve("MOBILE")}>Mark MOBILE</button>
              <button onClick={() => resolve("HOME")}>Mark HOME</button>
              <button className="ghost" onClick={() => resolve("SKIP")}>
                Skip
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </section>
  );
}
