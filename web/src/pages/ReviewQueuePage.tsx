import { MouseEvent, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { api, ReviewItem, ReviewListResponse } from "../api/client";

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

function formatIdentifier(label: string, value: string | number | null | undefined) {
  return `${label}: ${value ?? "N/A"}`;
}

export function ReviewQueuePage() {
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
          setError(err instanceof Error ? err.message : "Failed to load reviews");
        }
      }
    }

    load();
    const timer = window.setInterval(load, 15000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [filters]);

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
      setError(err instanceof Error ? err.message : "Resolve failed");
    }
  }

  return (
    <section className="page">
      <div className="page-header">
        <div>
          <span className="eyebrow">Review Queue</span>
          <h1>Спорные решения и ручная модерация</h1>
        </div>
        <div className="action-row">
          <button className="ghost icon-button" onClick={() => setShowFilters((prev) => !prev)} title="Toggle filters">
            ⚲
          </button>
          <div className="chip">
            {list.count} cases · page {list.page}
          </div>
        </div>
      </div>

      <div className="panel search-strip">
        <input
          placeholder="Быстрый поиск по IP / username / ISP / UUID / IDs"
          value={filters.q}
          onChange={(event) => setFilters((prev) => ({ ...prev, q: event.target.value, page: 1 }))}
        />
      </div>

      {showFilters ? (
        <div className="panel filters">
        <input
          placeholder="Username"
          value={String(filters.username ?? "")}
          onChange={(event) =>
            setFilters((prev) => ({ ...prev, username: event.target.value, page: 1 }))
          }
        />
        <input
          placeholder="System ID"
          value={String(filters.system_id ?? "")}
          onChange={(event) =>
            setFilters((prev) => ({ ...prev, system_id: event.target.value, page: 1 }))
          }
        />
        <input
          placeholder="Telegram ID"
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
          placeholder="Repeat count min"
          value={String(filters.repeat_count_min ?? "")}
          onChange={(event) =>
            setFilters((prev) => ({ ...prev, repeat_count_min: event.target.value, page: 1 }))
          }
        />
        <input
          type="number"
          min={0}
          placeholder="Repeat count max"
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
          <option value="">All confidence</option>
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
          <option value="">All reasons</option>
          <option value="unsure">unsure</option>
          <option value="probable_home">probable_home</option>
          <option value="home_requires_review">home_requires_review</option>
          <option value="manual_review_mixed_home">manual_review_mixed_home</option>
        </select>
        <select
          value={filters.severity}
          onChange={(event) => setFilters((prev) => ({ ...prev, severity: event.target.value, page: 1 }))}
        >
          <option value="">All severity</option>
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
          <option value="">Punitive any</option>
          <option value="true">punitive only</option>
          <option value="false">review-only</option>
        </select>
        <select
          value={filters.sort}
          onChange={(event) => setFilters((prev) => ({ ...prev, sort: event.target.value }))}
        >
          <option value="updated_desc">updated desc</option>
          <option value="score_desc">score desc</option>
          <option value="repeat_desc">repeat desc</option>
          <option value="updated_asc">updated asc</option>
        </select>
        </div>
      ) : null}

      {error ? <div className="error-box">{error}</div> : null}

      <div className="queue-grid">
        {list.items.map((item) => (
          <Link key={item.id} to={`/reviews/${item.id}`} className="queue-card">
            <div className="queue-card-top">
              <strong>{item.username || item.uuid || formatIdentifier("User", item.system_id)}</strong>
              <span className={`status-badge status-${item.status.toLowerCase()}`}>{item.status}</span>
            </div>
            <div className="queue-card-identifiers">
              <span>{formatIdentifier("System", item.system_id)}</span>
              <span>{formatIdentifier("TG", item.telegram_id)}</span>
              <span>{formatIdentifier("UUID", item.uuid)}</span>
            </div>
            <div className="queue-card-stack">
              <div className="queue-card-meta">
                <span>IP</span>
                <strong>{item.ip}</strong>
              </div>
              <div className="queue-card-meta">
                <span>ASN</span>
                <strong>AS{item.asn ?? "?"}</strong>
              </div>
              <div className="queue-card-meta">
                <span>Decision</span>
                <strong>{item.verdict} / {item.confidence_band}</strong>
              </div>
            </div>
            <div className="queue-card-meta">
              <span className={`tag severity-${item.severity}`}>{item.severity}</span>
              <span className={item.punitive_eligible ? "tag punitive" : "tag review-only"}>
                {item.punitive_eligible ? "punitive eligible" : "review only"}
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
                  Mobile
                </button>
                <button className="small-button" onClick={(event) => quickResolve(event, item, "HOME")}>
                  Home
                </button>
                <button className="small-button ghost" onClick={(event) => quickResolve(event, item, "SKIP")}>
                  Skip
                </button>
              </div>
            ) : null}
            <div className="queue-card-bottom">
              <span>repeat x{item.repeat_count}</span>
              <span>opened {item.opened_at || "n/a"}</span>
              <span>{item.updated_at}</span>
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
          Prev
        </button>
        <span>
          Page {list.page} · showing {list.items.length} of {list.count}
        </span>
        <button
          className="ghost"
          disabled={list.page * list.page_size >= list.count}
          onClick={() => setFilters((prev) => ({ ...prev, page: prev.page + 1 }))}
        >
          Next
        </button>
      </div>
    </section>
  );
}
