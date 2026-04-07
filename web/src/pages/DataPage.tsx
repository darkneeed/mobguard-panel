import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { api } from "../api/client";

type DataTab = "users" | "violations" | "overrides" | "cache" | "learning" | "cases";

export function DataPage() {
  const [tab, setTab] = useState<DataTab>("users");
  const [error, setError] = useState("");
  const [saved, setSaved] = useState("");

  const [userQuery, setUserQuery] = useState("");
  const [userSearch, setUserSearch] = useState<Record<string, unknown> | null>(null);
  const [userCard, setUserCard] = useState<Record<string, unknown> | null>(null);
  const [banMinutes, setBanMinutes] = useState("15");
  const [strikeCount, setStrikeCount] = useState("1");
  const [warningCount, setWarningCount] = useState("1");

  const [violations, setViolations] = useState<Record<string, unknown> | null>(null);
  const [overrides, setOverrides] = useState<Record<string, unknown> | null>(null);
  const [cache, setCache] = useState<Record<string, unknown> | null>(null);
  const [learning, setLearning] = useState<Record<string, unknown> | null>(null);
  const [cases, setCases] = useState<Record<string, unknown> | null>(null);

  const [exactOverrideIp, setExactOverrideIp] = useState("");
  const [exactOverrideDecision, setExactOverrideDecision] = useState("HOME");
  const [unsureOverrideIp, setUnsureOverrideIp] = useState("");
  const [unsureOverrideDecision, setUnsureOverrideDecision] = useState("HOME");
  const [selectedCacheIp, setSelectedCacheIp] = useState("");
  const [cacheDraft, setCacheDraft] = useState<Record<string, string>>({});

  useEffect(() => {
    async function load() {
      try {
        if (tab === "violations") {
          setViolations(await api.getViolations());
        } else if (tab === "overrides") {
          setOverrides(await api.getOverrides());
        } else if (tab === "cache") {
          setCache(await api.getCache());
        } else if (tab === "learning") {
          setLearning(await api.getLearningAdmin());
        } else if (tab === "cases") {
          setCases(await api.listCases({ page: 1, page_size: 50 }));
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load data tab");
      }
    }

    load();
  }, [tab]);

  async function searchUsers() {
    try {
      const payload = await api.searchUsers(userQuery);
      setUserSearch(payload);
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "User search failed");
    }
  }

  async function loadUser(identifier: string) {
    try {
      const payload = await api.getUserCard(identifier);
      setUserCard(payload);
      setSaved("");
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load user card");
    }
  }

  async function runUserAction(action: () => Promise<Record<string, unknown>>) {
    try {
      const payload = await action();
      setUserCard(payload);
      setSaved("User data updated");
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "User action failed");
      setSaved("");
    }
  }

  async function saveExactOverride() {
    try {
      await api.upsertExactOverride(exactOverrideIp, exactOverrideDecision);
      setOverrides(await api.getOverrides());
      setSaved("Exact override saved");
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save exact override");
    }
  }

  async function saveUnsureOverride() {
    try {
      await api.upsertUnsureOverride(unsureOverrideIp, unsureOverrideDecision);
      setOverrides(await api.getOverrides());
      setSaved("Unsure override saved");
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save unsure override");
    }
  }

  async function saveCachePatch() {
    if (!selectedCacheIp) return;
    try {
      await api.patchCache(selectedCacheIp, {
        status: cacheDraft.status,
        confidence: cacheDraft.confidence,
        details: cacheDraft.details,
        asn: cacheDraft.asn ? Number(cacheDraft.asn) : null
      });
      setCache(await api.getCache());
      setSaved("Cache entry updated");
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update cache entry");
    }
  }

  function renderUsersTab() {
    const items = (userSearch?.items as Array<Record<string, unknown>> | undefined) || [];
    const panelMatch = userSearch?.panel_match as Record<string, unknown> | undefined;
    const identity = userCard?.identity as Record<string, unknown> | undefined;
    const flags = userCard?.flags as Record<string, unknown> | undefined;
    const reviewCases = (userCard?.review_cases as Array<Record<string, unknown>> | undefined) || [];
    const history = (userCard?.history as Array<Record<string, unknown>> | undefined) || [];
    const panelUser = userCard?.panel_user as Record<string, unknown> | undefined;
    const identifier = String(identity?.uuid || identity?.system_id || identity?.telegram_id || "");

    return (
      <>
        <div className="panel">
          <div className="action-row">
            <input
              placeholder="Search uuid / system id / telegram id / username"
              value={userQuery}
              onChange={(event) => setUserQuery(event.target.value)}
            />
            <button onClick={searchUsers}>Search</button>
          </div>
          {panelMatch ? (
            <div className="tag">Panel match: {String(panelMatch.username || panelMatch.uuid || panelMatch.id)}</div>
          ) : null}
          <ul className="reason-list">
            {items.map((item) => (
              <li key={String(item.uuid || item.system_id || item.telegram_id)}>
                <button className="ghost" onClick={() => loadUser(String(item.uuid || item.system_id || item.telegram_id))}>
                  {String(item.username || item.uuid || item.system_id)} · sys:{String(item.system_id ?? "N/A")} · tg:{String(item.telegram_id ?? "N/A")}
                </button>
              </li>
            ))}
          </ul>
        </div>

        {identity ? (
          <div className="detail-grid">
            <div className="panel">
              <h2>User card</h2>
              <dl className="detail-list">
                <div><dt>Username</dt><dd>{String(identity.username || "N/A")}</dd></div>
                <div><dt>UUID</dt><dd>{String(identity.uuid || "N/A")}</dd></div>
                <div><dt>System ID</dt><dd>{String(identity.system_id || "N/A")}</dd></div>
                <div><dt>Telegram ID</dt><dd>{String(identity.telegram_id || "N/A")}</dd></div>
                <div><dt>Panel status</dt><dd>{String(panelUser?.status || "unknown")}</dd></div>
                <div><dt>Exempt system ID</dt><dd>{String(flags?.exempt_system_id || false)}</dd></div>
                <div><dt>Exempt Telegram ID</dt><dd>{String(flags?.exempt_telegram_id || false)}</dd></div>
                <div><dt>Active ban</dt><dd>{String(flags?.active_ban || false)}</dd></div>
                <div><dt>Active warning</dt><dd>{String(flags?.active_warning || false)}</dd></div>
              </dl>
            </div>

            <div className="panel">
              <h2>User actions</h2>
              <div className="form-grid">
                <div className="rule-field">
                  <strong>Ban minutes</strong>
                  <input value={banMinutes} onChange={(event) => setBanMinutes(event.target.value)} />
                  <button onClick={() => runUserAction(() => api.banUser(identifier, Number(banMinutes)))}>Start ban</button>
                  <button className="ghost" onClick={() => runUserAction(() => api.unbanUser(identifier))}>Unban</button>
                </div>
                <div className="rule-field">
                  <strong>Strikes</strong>
                  <input value={strikeCount} onChange={(event) => setStrikeCount(event.target.value)} />
                  <div className="action-row">
                    <button className="ghost" onClick={() => runUserAction(() => api.updateUserStrikes(identifier, "add", Number(strikeCount)))}>Add</button>
                    <button className="ghost" onClick={() => runUserAction(() => api.updateUserStrikes(identifier, "remove", Number(strikeCount)))}>Remove</button>
                    <button onClick={() => runUserAction(() => api.updateUserStrikes(identifier, "set", Number(strikeCount)))}>Set</button>
                  </div>
                </div>
                <div className="rule-field">
                  <strong>Warnings</strong>
                  <input value={warningCount} onChange={(event) => setWarningCount(event.target.value)} />
                  <div className="action-row">
                    <button onClick={() => runUserAction(() => api.updateUserWarnings(identifier, "set", Number(warningCount)))}>Set warning</button>
                    <button className="ghost" onClick={() => runUserAction(() => api.updateUserWarnings(identifier, "clear", 0))}>Clear warning</button>
                  </div>
                </div>
                <div className="rule-field">
                  <strong>Exemptions</strong>
                  <div className="action-row">
                    <button onClick={() => runUserAction(() => api.updateUserExempt(identifier, "system", true))}>Exempt system</button>
                    <button className="ghost" onClick={() => runUserAction(() => api.updateUserExempt(identifier, "system", false))}>Unexempt system</button>
                  </div>
                  <div className="action-row">
                    <button onClick={() => runUserAction(() => api.updateUserExempt(identifier, "telegram", true))}>Exempt telegram</button>
                    <button className="ghost" onClick={() => runUserAction(() => api.updateUserExempt(identifier, "telegram", false))}>Unexempt telegram</button>
                  </div>
                </div>
              </div>
            </div>

            <div className="panel">
              <h2>Open / recent review cases</h2>
              <ul className="reason-list">
                {reviewCases.length === 0 ? <li><span>No local review cases</span></li> : null}
                {reviewCases.map((item) => (
                  <li key={String(item.id)}>
                    <Link to={`/reviews/${item.id}`}>
                      #{String(item.id)} · {String(item.review_reason)} · {String(item.ip)} · {String(item.updated_at)}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>

            <div className="panel">
              <h2>Violation history</h2>
              <ul className="reason-list">
                {history.length === 0 ? <li><span>No violation history</span></li> : null}
                {history.map((item) => (
                  <li key={`${String(item.timestamp)}-${String(item.ip)}`}>
                    <strong>{String(item.ip)}</strong>
                    <span>{String(item.tag)} · strike {String(item.strike_number)} · {String(item.punishment_duration)} min</span>
                    <span>{String(item.timestamp)}</span>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        ) : null}
      </>
    );
  }

  function renderViolationsTab() {
    const active = (violations?.active as Array<Record<string, unknown>> | undefined) || [];
    const history = (violations?.history as Array<Record<string, unknown>> | undefined) || [];
    return (
      <div className="detail-grid">
        <div className="panel">
          <h2>Active violations / bans</h2>
          <ul className="reason-list">
            {active.map((item) => (
              <li key={String(item.uuid)}>
                <strong>{String(item.uuid)}</strong>
                <span>strikes {String(item.strikes)} · warning_count {String(item.warning_count)}</span>
                <span>unban {String(item.unban_time || "n/a")}</span>
              </li>
            ))}
          </ul>
        </div>
        <div className="panel">
          <h2>Violation history</h2>
          <ul className="reason-list">
            {history.map((item) => (
              <li key={String(item.id)}>
                <strong>{String(item.uuid)}</strong>
                <span>{String(item.ip)} · strike {String(item.strike_number)} · {String(item.punishment_duration)} min</span>
                <span>{String(item.timestamp)}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>
    );
  }

  function renderOverridesTab() {
    const exactIp = (overrides?.exact_ip as Array<Record<string, unknown>> | undefined) || [];
    const unsure = (overrides?.unsure_patterns as Array<Record<string, unknown>> | undefined) || [];
    return (
      <div className="detail-grid">
        <div className="panel">
          <h2>Exact IP overrides</h2>
          <div className="action-row">
            <input placeholder="IP" value={exactOverrideIp} onChange={(event) => setExactOverrideIp(event.target.value)} />
            <select value={exactOverrideDecision} onChange={(event) => setExactOverrideDecision(event.target.value)}>
              <option value="HOME">HOME</option>
              <option value="MOBILE">MOBILE</option>
              <option value="SKIP">SKIP</option>
            </select>
            <button onClick={saveExactOverride}>Save</button>
          </div>
          <ul className="reason-list">
            {exactIp.map((item) => (
              <li key={String(item.ip)}>
                <strong>{String(item.ip)}</strong>
                <span>{String(item.decision)} · expires {String(item.expires_at || "n/a")}</span>
                <button className="ghost" onClick={async () => {
                  await api.deleteExactOverride(String(item.ip));
                  setOverrides(await api.getOverrides());
                }}>Delete</button>
              </li>
            ))}
          </ul>
        </div>
        <div className="panel">
          <h2>Unsure pattern overrides</h2>
          <div className="action-row">
            <input placeholder="IP pattern" value={unsureOverrideIp} onChange={(event) => setUnsureOverrideIp(event.target.value)} />
            <select value={unsureOverrideDecision} onChange={(event) => setUnsureOverrideDecision(event.target.value)}>
              <option value="HOME">HOME</option>
              <option value="MOBILE">MOBILE</option>
              <option value="SKIP">SKIP</option>
            </select>
            <button onClick={saveUnsureOverride}>Save</button>
          </div>
          <ul className="reason-list">
            {unsure.map((item) => (
              <li key={String(item.ip_pattern)}>
                <strong>{String(item.ip_pattern)}</strong>
                <span>{String(item.decision)} · {String(item.timestamp)}</span>
                <button className="ghost" onClick={async () => {
                  await api.deleteUnsureOverride(String(item.ip_pattern));
                  setOverrides(await api.getOverrides());
                }}>Delete</button>
              </li>
            ))}
          </ul>
        </div>
      </div>
    );
  }

  function renderCacheTab() {
    const items = (cache?.items as Array<Record<string, unknown>> | undefined) || [];
    return (
      <div className="detail-grid">
        <div className="panel">
          <h2>IP cache</h2>
          <ul className="reason-list">
            {items.map((item) => (
              <li key={String(item.ip)}>
                <strong>{String(item.ip)}</strong>
                <span>{String(item.status)} / {String(item.confidence)} / ASN {String(item.asn ?? "N/A")}</span>
                <div className="action-row">
                  <button className="ghost" onClick={() => {
                    setSelectedCacheIp(String(item.ip));
                    setCacheDraft({
                      status: String(item.status || ""),
                      confidence: String(item.confidence || ""),
                      details: String(item.details || ""),
                      asn: String(item.asn || "")
                    });
                  }}>Edit</button>
                  <button className="ghost" onClick={async () => {
                    await api.deleteCache(String(item.ip));
                    setCache(await api.getCache());
                  }}>Delete</button>
                </div>
              </li>
            ))}
          </ul>
        </div>
        <div className="panel">
          <h2>Edit cache entry</h2>
          <input placeholder="Selected IP" value={selectedCacheIp} onChange={(event) => setSelectedCacheIp(event.target.value)} />
          <input placeholder="status" value={cacheDraft.status || ""} onChange={(event) => setCacheDraft((prev) => ({ ...prev, status: event.target.value }))} />
          <input placeholder="confidence" value={cacheDraft.confidence || ""} onChange={(event) => setCacheDraft((prev) => ({ ...prev, confidence: event.target.value }))} />
          <textarea className="note-box" placeholder="details" value={cacheDraft.details || ""} onChange={(event) => setCacheDraft((prev) => ({ ...prev, details: event.target.value }))} />
          <input placeholder="asn" value={cacheDraft.asn || ""} onChange={(event) => setCacheDraft((prev) => ({ ...prev, asn: event.target.value }))} />
          <button onClick={saveCachePatch} disabled={!selectedCacheIp}>Save cache entry</button>
        </div>
      </div>
    );
  }

  function renderLearningTab() {
    const promotedActive = (learning?.promoted_active as Array<Record<string, unknown>> | undefined) || [];
    const promotedStats = (learning?.promoted_stats as Array<Record<string, unknown>> | undefined) || [];
    const legacy = (learning?.legacy as Array<Record<string, unknown>> | undefined) || [];
    return (
      <div className="detail-grid">
        <div className="panel">
          <h2>Promoted active patterns</h2>
          <ul className="reason-list">
            {promotedActive.map((item) => (
              <li key={`${String(item.pattern_type)}:${String(item.pattern_value)}`}>
                <strong>{String(item.pattern_type)}:{String(item.pattern_value)}</strong>
                <span>{String(item.decision)} · support {String(item.support)} · precision {String(item.precision)}</span>
              </li>
            ))}
          </ul>
        </div>
        <div className="panel">
          <h2>Promoted stats</h2>
          <ul className="reason-list">
            {promotedStats.map((item) => (
              <li key={`${String(item.pattern_type)}:${String(item.pattern_value)}:${String(item.decision)}`}>
                <strong>{String(item.pattern_type)}:{String(item.pattern_value)}</strong>
                <span>{String(item.decision)} · total {String(item.total)} · precision {String(item.precision)}</span>
              </li>
            ))}
          </ul>
        </div>
        <div className="panel">
          <h2>Legacy learning</h2>
          <ul className="reason-list">
            {legacy.map((item) => (
              <li key={String(item.id)}>
                <strong>{String(item.pattern_type)}:{String(item.pattern_value)}</strong>
                <span>{String(item.decision)} · confidence {String(item.confidence)}</span>
                <div className="action-row">
                  <button className="ghost" onClick={async () => {
                    await api.patchLegacyLearning(Number(item.id), { confidence: Number(item.confidence) + 1 });
                    setLearning(await api.getLearningAdmin());
                  }}>+1 confidence</button>
                  <button className="ghost" onClick={async () => {
                    await api.deleteLegacyLearning(Number(item.id));
                    setLearning(await api.getLearningAdmin());
                  }}>Delete</button>
                </div>
              </li>
            ))}
          </ul>
        </div>
      </div>
    );
  }

  function renderCasesTab() {
    const items = ((cases?.items as Array<Record<string, unknown>>) || []);
    return (
      <div className="panel">
        <h2>Cases</h2>
        <ul className="reason-list">
          {items.map((item) => (
            <li key={String(item.id)}>
              <Link to={`/reviews/${item.id}`}>
                #{String(item.id)} · {String(item.username || item.uuid || "N/A")} · {String(item.ip)} · {String(item.review_reason)}
              </Link>
            </li>
          ))}
        </ul>
      </div>
    );
  }

  return (
    <section className="page">
      <div className="page-header">
        <div>
          <span className="eyebrow">Data</span>
          <h1>Operational runtime data admin</h1>
        </div>
      </div>

      <div className="panel tab-row">
        {(["users", "violations", "overrides", "cache", "learning", "cases"] as DataTab[]).map((item) => (
          <button
            key={item}
            className={tab === item ? "" : "ghost"}
            onClick={() => setTab(item)}
          >
            {item}
          </button>
        ))}
      </div>

      {error ? <div className="error-box">{error}</div> : null}
      {saved ? <div className="ok-box">{saved}</div> : null}

      {tab === "users" ? renderUsersTab() : null}
      {tab === "violations" ? renderViolationsTab() : null}
      {tab === "overrides" ? renderOverridesTab() : null}
      {tab === "cache" ? renderCacheTab() : null}
      {tab === "learning" ? renderLearningTab() : null}
      {tab === "cases" ? renderCasesTab() : null}
    </section>
  );
}
