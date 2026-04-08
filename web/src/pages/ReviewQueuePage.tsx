import { MouseEvent, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { api, ReviewItem, ReviewListResponse } from "../api/client";
import { useI18n } from "../localization";
import { formatDisplayDateTime } from "../utils/datetime";

type ReviewFilters = {
  status: string;
  confidence_band: string;
  review_reason: string;
  severity: string;
  punitive_eligible: string;
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

export function ReviewQueuePage() {
  const { t, language } = useI18n();
  const [list, setList] = useState<ReviewListResponse>({
    items: [],
    count: 0,
    page: 1,
    page_size: 25
  });
  const [error, setError] = useState("");
  const [showFilters, setShowFilters] = useState(false);
  const [filters, setFilters] = useState<ReviewFilters>({
    status: "OPEN",
    confidence_band: "",
    review_reason: "",
    severity: "",
    punitive_eligible: "",
    q: "",
    username: "",
    system_id: "",
    telegram_id: "",
    opened_from: "",
    opened_to: "",
    repeat_count_min: "",
    repeat_count_max: "",
    page: 1,
    page_size: 25,
    sort: "updated_desc"
  });

  function formatIdentifier(label: string, value: string | number | null | undefined) {
    return `${label}: ${value === null || value === undefined || value === "" ? t("common.notAvailable") : value}`;
  }

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const payload = await api.listReviews(filters);
        if (!cancelled) {
          setList(payload);
          setError("");
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : t("reviewQueue.errors.loadFailed"));
        }
      }
    }

    load();
    const timer = window.setInterval(load, 15000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [filters, t]);

  async function quickResolve(
    event: MouseEvent<HTMLButtonElement>,
    item: ReviewItem,
    resolution: "MOBILE" | "HOME" | "SKIP"
  ) {
    event.preventDefault();
    event.stopPropagation();
    try {
      await api.resolveReview(String(item.id), resolution, "quick action from queue");
      const payload = await api.listReviews(filters);
      setList(payload);
    } catch (err) {
      setError(err instanceof Error ? err.message : t("reviewQueue.errors.resolveFailed"));
    }
  }

  return (
    <section className="page">
      <div className="page-header">
        <div>
          <span className="eyebrow">{t("reviewQueue.eyebrow")}</span>
          <h1>{t("reviewQueue.title")}</h1>
        </div>
        <div className="chip">
          {t("reviewQueue.countSummary", { count: list.count, page: list.page })}
        </div>
      </div>

      <div className="panel search-strip">
        <input
          placeholder={t("reviewQueue.searchPlaceholder")}
          value={filters.q}
          onChange={(event) => setFilters((prev) => ({ ...prev, q: event.target.value, page: 1 }))}
        />
        <button
          className="ghost icon-button"
          onClick={() => setShowFilters((prev) => !prev)}
          title={t("reviewQueue.toggleFiltersTitle")}
        >
          ⚲
        </button>
      </div>

      {showFilters ? (
        <div className="panel filters">
          <input
            placeholder={t("reviewQueue.filters.username")}
            value={String(filters.username ?? "")}
            onChange={(event) =>
              setFilters((prev) => ({ ...prev, username: event.target.value, page: 1 }))
            }
          />
          <input
            placeholder={t("reviewQueue.filters.systemId")}
            value={String(filters.system_id ?? "")}
            onChange={(event) =>
              setFilters((prev) => ({ ...prev, system_id: event.target.value, page: 1 }))
            }
          />
          <input
            placeholder={t("reviewQueue.filters.telegramId")}
            value={String(filters.telegram_id ?? "")}
            onChange={(event) =>
              setFilters((prev) => ({ ...prev, telegram_id: event.target.value, page: 1 }))
            }
          />
          <input
            type="date"
            value={String(filters.opened_from ?? "")}
            onChange={(event) =>
              setFilters((prev) => ({ ...prev, opened_from: event.target.value, page: 1 }))
            }
          />
          <input
            type="date"
            value={String(filters.opened_to ?? "")}
            onChange={(event) =>
              setFilters((prev) => ({ ...prev, opened_to: event.target.value, page: 1 }))
            }
          />
          <input
            type="number"
            min={0}
            placeholder={t("reviewQueue.filters.repeatMin")}
            value={String(filters.repeat_count_min ?? "")}
            onChange={(event) =>
              setFilters((prev) => ({ ...prev, repeat_count_min: event.target.value, page: 1 }))
            }
          />
          <input
            type="number"
            min={0}
            placeholder={t("reviewQueue.filters.repeatMax")}
            value={String(filters.repeat_count_max ?? "")}
            onChange={(event) =>
              setFilters((prev) => ({ ...prev, repeat_count_max: event.target.value, page: 1 }))
            }
          />
          <select
            value={filters.status}
            onChange={(event) => setFilters((prev) => ({ ...prev, status: event.target.value, page: 1 }))}
          >
            <option value="OPEN">OPEN</option>
            <option value="RESOLVED">RESOLVED</option>
            <option value="SKIPPED">SKIPPED</option>
            <option value="">ALL</option>
          </select>
          <select
            value={filters.confidence_band}
            onChange={(event) =>
              setFilters((prev) => ({ ...prev, confidence_band: event.target.value, page: 1 }))
            }
          >
            <option value="">{t("reviewQueue.filters.allConfidence")}</option>
            <option value="UNSURE">UNSURE</option>
            <option value="PROBABLE_HOME">PROBABLE_HOME</option>
            <option value="HIGH_HOME">HIGH_HOME</option>
          </select>
          <select
            value={filters.review_reason}
            onChange={(event) =>
              setFilters((prev) => ({ ...prev, review_reason: event.target.value, page: 1 }))
            }
          >
            <option value="">{t("reviewQueue.filters.allReasons")}</option>
            <option value="unsure">unsure</option>
            <option value="probable_home">probable_home</option>
            <option value="home_requires_review">home_requires_review</option>
            <option value="manual_review_mixed_home">manual_review_mixed_home</option>
          </select>
          <select
            value={filters.severity}
            onChange={(event) => setFilters((prev) => ({ ...prev, severity: event.target.value, page: 1 }))}
          >
            <option value="">{t("reviewQueue.filters.allSeverity")}</option>
            <option value="critical">critical</option>
            <option value="high">high</option>
            <option value="medium">medium</option>
            <option value="low">low</option>
          </select>
          <select
            value={filters.punitive_eligible}
            onChange={(event) =>
              setFilters((prev) => ({ ...prev, punitive_eligible: event.target.value, page: 1 }))
            }
          >
            <option value="">{t("reviewQueue.filters.punitiveAny")}</option>
            <option value="true">{t("reviewQueue.filters.punitiveOnly")}</option>
            <option value="false">{t("reviewQueue.filters.reviewOnly")}</option>
          </select>
          <select
            value={filters.sort}
            onChange={(event) => setFilters((prev) => ({ ...prev, sort: event.target.value }))}
          >
            <option value="updated_desc">{t("reviewQueue.filters.sortUpdatedDesc")}</option>
            <option value="score_desc">{t("reviewQueue.filters.sortScoreDesc")}</option>
            <option value="repeat_desc">{t("reviewQueue.filters.sortRepeatDesc")}</option>
            <option value="updated_asc">{t("reviewQueue.filters.sortUpdatedAsc")}</option>
          </select>
        </div>
      ) : null}

      {error ? <div className="error-box">{error}</div> : null}

      <div className="queue-grid">
        {list.items.map((item) => (
          <Link key={item.id} to={`/reviews/${item.id}`} className="queue-card">
            <div className="queue-card-top">
              <strong>{item.username || item.uuid || formatIdentifier(t("reviewQueue.identifiers.user"), item.system_id)}</strong>
              <span className={`status-badge status-${item.status.toLowerCase()}`}>{item.status}</span>
            </div>
            <div className="queue-card-identifiers">
              <span>{formatIdentifier(t("reviewQueue.identifiers.system"), item.system_id)}</span>
              <span>{formatIdentifier(t("reviewQueue.identifiers.telegram"), item.telegram_id)}</span>
              <span>{formatIdentifier(t("reviewQueue.identifiers.uuid"), item.uuid)}</span>
            </div>
            <div className="queue-card-stack">
              <div className="queue-card-meta">
                <span>{t("reviewQueue.card.ip")}</span>
                <strong>{item.ip}</strong>
              </div>
              <div className="queue-card-meta">
                <span>{t("reviewQueue.card.asn")}</span>
                <strong>AS{item.asn ?? "?"}</strong>
              </div>
              <div className="queue-card-meta">
                <span>{t("reviewQueue.card.decision")}</span>
                <strong>{item.verdict} / {item.confidence_band}</strong>
              </div>
            </div>
            <div className="queue-card-meta">
              <span className={`tag severity-${item.severity}`}>{item.severity}</span>
              <span className={item.punitive_eligible ? "tag punitive" : "tag review-only"}>
                {item.punitive_eligible ? t("reviewQueue.card.punitiveEligible") : t("reviewQueue.card.reviewOnly")}
              </span>
            </div>
            <p>{item.isp}</p>
            <div className="queue-card-tags">
              {item.reason_codes.slice(0, 4).map((code) => (
                <span key={code} className="tag">
                  {code}
                </span>
              ))}
            </div>
            {item.status === "OPEN" ? (
              <div className="action-row">
                <button className="small-button" onClick={(event) => quickResolve(event, item, "MOBILE")}>
                  {t("reviewQueue.actions.mobile")}
                </button>
                <button className="small-button" onClick={(event) => quickResolve(event, item, "HOME")}>
                  {t("reviewQueue.actions.home")}
                </button>
                <button className="small-button ghost" onClick={(event) => quickResolve(event, item, "SKIP")}>
                  {t("reviewQueue.actions.skip")}
                </button>
              </div>
            ) : null}
            <div className="queue-card-bottom">
              <span>{t("reviewQueue.card.repeat", { count: item.repeat_count })}</span>
              <span>{t("reviewQueue.card.opened", { value: formatDisplayDateTime(item.opened_at, t("common.notAvailable"), language) })}</span>
              <span>{formatDisplayDateTime(item.updated_at, t("common.notAvailable"), language)}</span>
            </div>
          </Link>
        ))}
      </div>

      <div className="panel queue-footer">
        <button
          className="ghost"
          disabled={filters.page <= 1}
          onClick={() => setFilters((prev) => ({ ...prev, page: Math.max(prev.page - 1, 1) }))}
        >
          {t("reviewQueue.footer.previous")}
        </button>
        <span>
          {t("reviewQueue.footer.pageSummary", {
            page: list.page,
            shown: list.items.length,
            total: list.count
          })}
        </span>
        <button
          className="ghost"
          disabled={list.page * list.page_size >= list.count}
          onClick={() => setFilters((prev) => ({ ...prev, page: prev.page + 1 }))}
        >
          {t("reviewQueue.footer.next")}
        </button>
      </div>
    </section>
  );
}
