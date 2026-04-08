import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { api } from "../api/client";
import { useI18n } from "../localization";
import { formatDisplayDateTime } from "../utils/datetime";

type DataTab = "users" | "violations" | "overrides" | "cache" | "learning" | "cases";

export function DataPage() {
  const { t, language } = useI18n();
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

  function displayValue(value: unknown): string {
    return value === null || value === undefined || value === "" ? t("common.notAvailable") : String(value);
  }

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
        setError(err instanceof Error ? err.message : t("data.errors.loadTabFailed"));
      }
    }

    load();
  }, [tab, t]);

  async function searchUsers() {
    try {
      const payload = await api.searchUsers(userQuery);
      setUserSearch(payload);
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : t("data.errors.searchUsersFailed"));
    }
  }

  async function loadUser(identifier: string) {
    try {
      const payload = await api.getUserCard(identifier);
      setUserCard(payload);
      setSaved("");
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : t("data.errors.loadUserFailed"));
    }
  }

  async function runUserAction(action: () => Promise<Record<string, unknown>>) {
    try {
      const payload = await action();
      setUserCard(payload);
      setSaved(t("data.saved.userUpdated"));
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : t("data.errors.userActionFailed"));
      setSaved("");
    }
  }

  async function saveExactOverride() {
    try {
      await api.upsertExactOverride(exactOverrideIp, exactOverrideDecision);
      setOverrides(await api.getOverrides());
      setSaved(t("data.saved.exactOverride"));
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : t("data.errors.saveExactOverrideFailed"));
    }
  }

  async function saveUnsureOverride() {
    try {
      await api.upsertUnsureOverride(unsureOverrideIp, unsureOverrideDecision);
      setOverrides(await api.getOverrides());
      setSaved(t("data.saved.unsureOverride"));
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : t("data.errors.saveUnsureOverrideFailed"));
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
      setSaved(t("data.saved.cacheUpdated"));
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : t("data.errors.saveCacheFailed"));
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
              placeholder={t("data.users.searchPlaceholder")}
              value={userQuery}
              onChange={(event) => setUserQuery(event.target.value)}
            />
            <button onClick={searchUsers}>{t("data.users.search")}</button>
          </div>
          {panelMatch ? (
            <div className="tag">
              {t("data.users.panelMatch", {
                value: String(panelMatch.username || panelMatch.uuid || panelMatch.id)
              })}
            </div>
          ) : null}
          <ul className="reason-list">
            {items.map((item) => (
              <li key={String(item.uuid || item.system_id || item.telegram_id)}>
                <button className="ghost" onClick={() => loadUser(String(item.uuid || item.system_id || item.telegram_id))}>
                  {String(item.username || item.uuid || item.system_id)} · {t("data.users.systemLabel", { value: displayValue(item.system_id) })} · {t("data.users.telegramLabel", { value: displayValue(item.telegram_id) })}
                </button>
              </li>
            ))}
          </ul>
        </div>

        {identity ? (
          <div className="detail-grid">
            <div className="panel">
              <h2>{t("data.users.cardTitle")}</h2>
              <dl className="detail-list">
                <div><dt>{t("data.users.fields.username")}</dt><dd>{displayValue(identity.username)}</dd></div>
                <div><dt>{t("data.users.fields.uuid")}</dt><dd>{displayValue(identity.uuid)}</dd></div>
                <div><dt>{t("data.users.fields.systemId")}</dt><dd>{displayValue(identity.system_id)}</dd></div>
                <div><dt>{t("data.users.fields.telegramId")}</dt><dd>{displayValue(identity.telegram_id)}</dd></div>
                <div><dt>{t("data.users.fields.panelStatus")}</dt><dd>{displayValue(panelUser?.status)}</dd></div>
                <div><dt>{t("data.users.fields.exemptSystemId")}</dt><dd>{displayValue(flags?.exempt_system_id)}</dd></div>
                <div><dt>{t("data.users.fields.exemptTelegramId")}</dt><dd>{displayValue(flags?.exempt_telegram_id)}</dd></div>
                <div><dt>{t("data.users.fields.activeBan")}</dt><dd>{displayValue(flags?.active_ban)}</dd></div>
                <div><dt>{t("data.users.fields.activeWarning")}</dt><dd>{displayValue(flags?.active_warning)}</dd></div>
              </dl>
            </div>

            <div className="panel">
              <h2>{t("data.users.actionsTitle")}</h2>
              <div className="form-grid">
                <div className="rule-field">
                  <strong>{t("data.users.actions.banMinutes")}</strong>
                  <input value={banMinutes} onChange={(event) => setBanMinutes(event.target.value)} />
                  <button onClick={() => runUserAction(() => api.banUser(identifier, Number(banMinutes)))}>{t("data.users.actions.startBan")}</button>
                  <button className="ghost" onClick={() => runUserAction(() => api.unbanUser(identifier))}>{t("data.users.actions.unban")}</button>
                </div>
                <div className="rule-field">
                  <strong>{t("data.users.actions.strikes")}</strong>
                  <input value={strikeCount} onChange={(event) => setStrikeCount(event.target.value)} />
                  <div className="action-row">
                    <button className="ghost" onClick={() => runUserAction(() => api.updateUserStrikes(identifier, "add", Number(strikeCount)))}>{t("data.users.actions.add")}</button>
                    <button className="ghost" onClick={() => runUserAction(() => api.updateUserStrikes(identifier, "remove", Number(strikeCount)))}>{t("data.users.actions.remove")}</button>
                    <button onClick={() => runUserAction(() => api.updateUserStrikes(identifier, "set", Number(strikeCount)))}>{t("data.users.actions.set")}</button>
                  </div>
                </div>
                <div className="rule-field">
                  <strong>{t("data.users.actions.warnings")}</strong>
                  <input value={warningCount} onChange={(event) => setWarningCount(event.target.value)} />
                  <div className="action-row">
                    <button onClick={() => runUserAction(() => api.updateUserWarnings(identifier, "set", Number(warningCount)))}>{t("data.users.actions.setWarning")}</button>
                    <button className="ghost" onClick={() => runUserAction(() => api.updateUserWarnings(identifier, "clear", 0))}>{t("data.users.actions.clearWarning")}</button>
                  </div>
                </div>
                <div className="rule-field">
                  <strong>{t("data.users.actions.exemptions")}</strong>
                  <div className="action-row">
                    <button onClick={() => runUserAction(() => api.updateUserExempt(identifier, "system", true))}>{t("data.users.actions.exemptSystem")}</button>
                    <button className="ghost" onClick={() => runUserAction(() => api.updateUserExempt(identifier, "system", false))}>{t("data.users.actions.unexemptSystem")}</button>
                  </div>
                  <div className="action-row">
                    <button onClick={() => runUserAction(() => api.updateUserExempt(identifier, "telegram", true))}>{t("data.users.actions.exemptTelegram")}</button>
                    <button className="ghost" onClick={() => runUserAction(() => api.updateUserExempt(identifier, "telegram", false))}>{t("data.users.actions.unexemptTelegram")}</button>
                  </div>
                </div>
              </div>
            </div>

            <div className="panel">
              <h2>{t("data.users.openCasesTitle")}</h2>
              <ul className="reason-list">
                {reviewCases.length === 0 ? <li><span>{t("data.users.openCasesEmpty")}</span></li> : null}
                {reviewCases.map((item) => (
                  <li key={String(item.id)}>
                    <Link to={`/reviews/${item.id}`}>
                      #{String(item.id)} · {String(item.review_reason)} · {String(item.ip)} · {formatDisplayDateTime(String(item.updated_at ?? ""), t("common.notAvailable"), language)}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>

            <div className="panel">
              <h2>{t("data.users.historyTitle")}</h2>
              <ul className="reason-list">
                {history.length === 0 ? <li><span>{t("data.users.historyEmpty")}</span></li> : null}
                {history.map((item) => (
                  <li key={`${String(item.timestamp)}-${String(item.ip)}`}>
                    <strong>{String(item.ip)}</strong>
                    <span>{String(item.tag)} · {t("data.violations.historyRow", { strike: String(item.strike_number), duration: String(item.punishment_duration) })}</span>
                    <span>{formatDisplayDateTime(String(item.timestamp ?? ""), t("common.notAvailable"), language)}</span>
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
          <h2>{t("data.violations.activeTitle")}</h2>
          <ul className="reason-list">
            {active.map((item) => (
              <li key={String(item.uuid)}>
                <strong>{String(item.uuid)}</strong>
                <span>{t("data.violations.strikes", { value: String(item.strikes) })} · {t("data.violations.warningCount", { value: String(item.warning_count) })}</span>
                <span>{t("data.violations.unban", { value: formatDisplayDateTime(String(item.unban_time ?? ""), t("common.notAvailable"), language) })}</span>
              </li>
            ))}
          </ul>
        </div>
        <div className="panel">
          <h2>{t("data.violations.historyTitle")}</h2>
          <ul className="reason-list">
            {history.map((item) => (
              <li key={String(item.id)}>
                <strong>{String(item.uuid)}</strong>
                <span>{String(item.ip)} · {t("data.violations.historyRow", { strike: String(item.strike_number), duration: String(item.punishment_duration) })}</span>
                <span>{formatDisplayDateTime(String(item.timestamp ?? ""), t("common.notAvailable"), language)}</span>
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
          <h2>{t("data.overrides.exactTitle")}</h2>
          <div className="action-row">
            <input placeholder={t("data.overrides.ipPlaceholder")} value={exactOverrideIp} onChange={(event) => setExactOverrideIp(event.target.value)} />
            <select value={exactOverrideDecision} onChange={(event) => setExactOverrideDecision(event.target.value)}>
              <option value="HOME">HOME</option>
              <option value="MOBILE">MOBILE</option>
              <option value="SKIP">SKIP</option>
            </select>
            <button onClick={saveExactOverride}>{t("data.overrides.save")}</button>
          </div>
          <ul className="reason-list">
            {exactIp.map((item) => (
              <li key={String(item.ip)}>
                <strong>{String(item.ip)}</strong>
                <span>{String(item.decision)} · {t("data.overrides.expires", { value: formatDisplayDateTime(String(item.expires_at ?? ""), t("common.notAvailable"), language) })}</span>
                <button className="ghost" onClick={async () => {
                  await api.deleteExactOverride(String(item.ip));
                  setOverrides(await api.getOverrides());
                }}>{t("data.overrides.delete")}</button>
              </li>
            ))}
          </ul>
        </div>
        <div className="panel">
          <h2>{t("data.overrides.unsureTitle")}</h2>
          <div className="action-row">
            <input placeholder={t("data.overrides.ipPatternPlaceholder")} value={unsureOverrideIp} onChange={(event) => setUnsureOverrideIp(event.target.value)} />
            <select value={unsureOverrideDecision} onChange={(event) => setUnsureOverrideDecision(event.target.value)}>
              <option value="HOME">HOME</option>
              <option value="MOBILE">MOBILE</option>
              <option value="SKIP">SKIP</option>
            </select>
            <button onClick={saveUnsureOverride}>{t("data.overrides.save")}</button>
          </div>
          <ul className="reason-list">
            {unsure.map((item) => (
              <li key={String(item.ip_pattern)}>
                <strong>{String(item.ip_pattern)}</strong>
                <span>{String(item.decision)} · {formatDisplayDateTime(String(item.timestamp ?? ""), t("common.notAvailable"), language)}</span>
                <button className="ghost" onClick={async () => {
                  await api.deleteUnsureOverride(String(item.ip_pattern));
                  setOverrides(await api.getOverrides());
                }}>{t("data.overrides.delete")}</button>
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
          <h2>{t("data.cache.title")}</h2>
          <ul className="reason-list">
            {items.map((item) => (
              <li key={String(item.ip)}>
                <strong>{String(item.ip)}</strong>
                <span>{String(item.status)} / {String(item.confidence)} / ASN {displayValue(item.asn)}</span>
                <div className="action-row">
                  <button className="ghost" onClick={() => {
                    setSelectedCacheIp(String(item.ip));
                    setCacheDraft({
                      status: String(item.status || ""),
                      confidence: String(item.confidence || ""),
                      details: String(item.details || ""),
                      asn: String(item.asn || "")
                    });
                  }}>{t("data.cache.edit")}</button>
                  <button className="ghost" onClick={async () => {
                    await api.deleteCache(String(item.ip));
                    setCache(await api.getCache());
                  }}>{t("data.cache.delete")}</button>
                </div>
              </li>
            ))}
          </ul>
        </div>
        <div className="panel">
          <h2>{t("data.cache.editTitle")}</h2>
          <input placeholder={t("data.cache.selectedIp")} value={selectedCacheIp} onChange={(event) => setSelectedCacheIp(event.target.value)} />
          <input placeholder={t("data.cache.status")} value={cacheDraft.status || ""} onChange={(event) => setCacheDraft((prev) => ({ ...prev, status: event.target.value }))} />
          <input placeholder={t("data.cache.confidence")} value={cacheDraft.confidence || ""} onChange={(event) => setCacheDraft((prev) => ({ ...prev, confidence: event.target.value }))} />
          <textarea className="note-box" placeholder={t("data.cache.details")} value={cacheDraft.details || ""} onChange={(event) => setCacheDraft((prev) => ({ ...prev, details: event.target.value }))} />
          <input placeholder={t("data.cache.asn")} value={cacheDraft.asn || ""} onChange={(event) => setCacheDraft((prev) => ({ ...prev, asn: event.target.value }))} />
          <button onClick={saveCachePatch} disabled={!selectedCacheIp}>{t("data.cache.save")}</button>
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
          <h2>{t("data.learning.promotedActiveTitle")}</h2>
          <ul className="reason-list">
            {promotedActive.map((item) => (
              <li key={`${String(item.pattern_type)}:${String(item.pattern_value)}`}>
                <strong>{String(item.pattern_type)}:{String(item.pattern_value)}</strong>
                <span>{String(item.decision)} · {t("data.learning.support", { value: String(item.support) })} · {t("data.learning.precision", { value: String(item.precision) })}</span>
              </li>
            ))}
          </ul>
        </div>
        <div className="panel">
          <h2>{t("data.learning.promotedStatsTitle")}</h2>
          <ul className="reason-list">
            {promotedStats.map((item) => (
              <li key={`${String(item.pattern_type)}:${String(item.pattern_value)}:${String(item.decision)}`}>
                <strong>{String(item.pattern_type)}:{String(item.pattern_value)}</strong>
                <span>{String(item.decision)} · {t("data.learning.total", { value: String(item.total) })} · {t("data.learning.precision", { value: String(item.precision) })}</span>
              </li>
            ))}
          </ul>
        </div>
        <div className="panel">
          <h2>{t("data.learning.legacyTitle")}</h2>
          <ul className="reason-list">
            {legacy.map((item) => (
              <li key={String(item.id)}>
                <strong>{String(item.pattern_type)}:{String(item.pattern_value)}</strong>
                <span>{String(item.decision)} · {t("data.learning.confidence", { value: String(item.confidence) })}</span>
                <div className="action-row">
                  <button className="ghost" onClick={async () => {
                    await api.patchLegacyLearning(Number(item.id), { confidence: Number(item.confidence) + 1 });
                    setLearning(await api.getLearningAdmin());
                  }}>{t("data.learning.plusOneConfidence")}</button>
                  <button className="ghost" onClick={async () => {
                    await api.deleteLegacyLearning(Number(item.id));
                    setLearning(await api.getLearningAdmin());
                  }}>{t("data.learning.delete")}</button>
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
        <h2>{t("data.cases.title")}</h2>
        <ul className="reason-list">
          {items.map((item) => (
            <li key={String(item.id)}>
              <Link to={`/reviews/${item.id}`}>
                #{String(item.id)} · {String(item.username || item.uuid || t("common.notAvailable"))} · {String(item.ip)} · {String(item.review_reason)}
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
          <span className="eyebrow">{t("data.eyebrow")}</span>
          <h1>{t("data.title")}</h1>
        </div>
      </div>

      <div className="panel tab-row">
        {(["users", "violations", "overrides", "cache", "learning", "cases"] as DataTab[]).map((item) => (
          <button
            key={item}
            className={tab === item ? "" : "ghost"}
            onClick={() => setTab(item)}
          >
            {t(`data.tabs.${item}`)}
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
