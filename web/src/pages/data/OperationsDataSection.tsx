import type { Dispatch, SetStateAction } from "react";
import { api, CacheAdminResponse, OverridesResponse, ViolationsResponse } from "../../api/client";
import type { Language } from "../../localization/types";
import { formatDisplayDateTime } from "../../utils/datetime";

type TranslateFn = (key: string, params?: Record<string, string | number>) => string;
type Mode = "violations" | "overrides" | "cache";
type PendingKey = "exactOverride" | "unsureOverride" | "cacheSave";

type Props = {
  mode: Mode;
  t: TranslateFn;
  language: Language;
  violations: ViolationsResponse | null;
  overrides: OverridesResponse | null;
  cache: CacheAdminResponse | null;
  exactOverrideIp: string;
  setExactOverrideIp: (value: string) => void;
  exactOverrideDecision: string;
  setExactOverrideDecision: (value: string) => void;
  unsureOverrideIp: string;
  setUnsureOverrideIp: (value: string) => void;
  unsureOverrideDecision: string;
  setUnsureOverrideDecision: (value: string) => void;
  selectedCacheIp: string;
  setSelectedCacheIp: (value: string) => void;
  cacheDraft: Record<string, string>;
  setCacheDraft: Dispatch<SetStateAction<Record<string, string>>>;
  saveExactOverride: () => Promise<void>;
  saveUnsureOverride: () => Promise<void>;
  saveCachePatch: () => Promise<void>;
  setOverrides: (value: OverridesResponse) => void;
  setCache: (value: CacheAdminResponse) => void;
  pushToast: (kind: "success" | "error" | "warning" | "info", message: string) => void;
  withPending: <T>(key: PendingKey, action: () => Promise<T>) => Promise<T>;
  isPending: (...keys: PendingKey[]) => boolean;
  displayValue: (value: unknown) => string;
  formatDecisionLabel: (value: unknown) => string;
};

export function OperationsDataSection({
  mode,
  t,
  language,
  violations,
  overrides,
  cache,
  exactOverrideIp,
  setExactOverrideIp,
  exactOverrideDecision,
  setExactOverrideDecision,
  unsureOverrideIp,
  setUnsureOverrideIp,
  unsureOverrideDecision,
  setUnsureOverrideDecision,
  selectedCacheIp,
  setSelectedCacheIp,
  cacheDraft,
  setCacheDraft,
  saveExactOverride,
  saveUnsureOverride,
  saveCachePatch,
  setOverrides,
  setCache,
  pushToast,
  withPending,
  isPending,
  displayValue,
  formatDecisionLabel,
}: Props) {
  if (mode === "violations") {
    const active = (violations?.active as Array<Record<string, unknown>> | undefined) || [];
    const history = (violations?.history as Array<Record<string, unknown>> | undefined) || [];
    return (
      <div className="detail-grid">
        <div className="panel">
          <h2>{t("data.violations.activeTitle")}</h2>
          <div className="record-list">
            {active.map((item) => (
              <div className="record-item" key={String(item.uuid)}>
                <div className="record-main">
                  <span className="record-title">{String(item.uuid)}</span>
                  <span className="tag">{String(item.restriction_mode || t("common.notAvailable"))}</span>
                </div>
                <div className="record-meta">
                  <span>{t("data.violations.strikes", { value: String(item.strikes) })}</span>
                  <span>{t("data.violations.warningCount", { value: String(item.warning_count) })}</span>
                  <span>{t("data.violations.unban", { value: formatDisplayDateTime(String(item.unban_time ?? ""), t("common.notAvailable"), language) })}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
        <div className="panel">
          <h2>{t("data.violations.historyTitle")}</h2>
          <div className="record-list">
            {history.map((item) => (
              <div className="record-item" key={String(item.id)}>
                <div className="record-main">
                  <span className="record-title">{String(item.uuid)}</span>
                  <span>{String(item.ip)}</span>
                </div>
                <div className="record-meta">
                  <span>{t("data.violations.historyRow", { strike: String(item.strike_number), duration: String(item.punishment_duration) })}</span>
                  <span>{formatDisplayDateTime(String(item.timestamp ?? ""), t("common.notAvailable"), language)}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    );
  }

  if (mode === "overrides") {
    const exactIp = (overrides?.exact_ip as Array<Record<string, unknown>> | undefined) || [];
    const unsure = (overrides?.unsure_patterns as Array<Record<string, unknown>> | undefined) || [];
    return (
      <div className="detail-grid">
        <div className="panel">
          <h2>{t("data.overrides.exactTitle")}</h2>
          <div className="action-row">
            <input placeholder={t("data.overrides.ipPlaceholder")} value={exactOverrideIp} onChange={(event) => setExactOverrideIp(event.target.value)} />
            <select value={exactOverrideDecision} onChange={(event) => setExactOverrideDecision(event.target.value)}>
              <option value="HOME">{t("data.decisions.home")}</option>
              <option value="MOBILE">{t("data.decisions.mobile")}</option>
              <option value="SKIP">{t("data.decisions.skip")}</option>
            </select>
            <button disabled={isPending("exactOverride")} onClick={saveExactOverride}>{t("data.overrides.save")}</button>
          </div>
          <div className="record-list">
            {exactIp.map((item) => (
              <div className="record-item" key={String(item.ip)}>
                <div className="record-main">
                  <span className="record-title">{String(item.ip)}</span>
                  <span className="tag">{formatDecisionLabel(item.decision)}</span>
                </div>
                <div className="record-meta">
                  <span>{t("data.overrides.expires", { value: formatDisplayDateTime(String(item.expires_at ?? ""), t("common.notAvailable"), language) })}</span>
                </div>
                <div className="record-actions">
                  <button className="ghost" disabled={isPending("exactOverride")} onClick={async () => {
                    try {
                      await withPending("exactOverride", () => api.deleteExactOverride(String(item.ip)));
                      setOverrides(await api.getOverrides());
                      pushToast("success", t("data.saved.exactOverride"));
                    } catch (err) {
                      pushToast("error", err instanceof Error ? err.message : t("data.errors.saveExactOverrideFailed"));
                    }
                  }}>{t("data.overrides.delete")}</button>
                </div>
              </div>
            ))}
          </div>
        </div>
        <div className="panel">
          <h2>{t("data.overrides.unsureTitle")}</h2>
          <div className="action-row">
            <input placeholder={t("data.overrides.ipPatternPlaceholder")} value={unsureOverrideIp} onChange={(event) => setUnsureOverrideIp(event.target.value)} />
            <select value={unsureOverrideDecision} onChange={(event) => setUnsureOverrideDecision(event.target.value)}>
              <option value="HOME">{t("data.decisions.home")}</option>
              <option value="MOBILE">{t("data.decisions.mobile")}</option>
              <option value="SKIP">{t("data.decisions.skip")}</option>
            </select>
            <button disabled={isPending("unsureOverride")} onClick={saveUnsureOverride}>{t("data.overrides.save")}</button>
          </div>
          <div className="record-list">
            {unsure.map((item) => (
              <div className="record-item" key={String(item.ip_pattern)}>
                <div className="record-main">
                  <span className="record-title">{String(item.ip_pattern)}</span>
                  <span className="tag">{formatDecisionLabel(item.decision)}</span>
                </div>
                <div className="record-meta">
                  <span>{formatDisplayDateTime(String(item.timestamp ?? ""), t("common.notAvailable"), language)}</span>
                </div>
                <div className="record-actions">
                  <button className="ghost" disabled={isPending("unsureOverride")} onClick={async () => {
                    try {
                      await withPending("unsureOverride", () => api.deleteUnsureOverride(String(item.ip_pattern)));
                      setOverrides(await api.getOverrides());
                      pushToast("success", t("data.saved.unsureOverride"));
                    } catch (err) {
                      pushToast("error", err instanceof Error ? err.message : t("data.errors.saveUnsureOverrideFailed"));
                    }
                  }}>{t("data.overrides.delete")}</button>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    );
  }

  const items = (cache?.items as Array<Record<string, unknown>> | undefined) || [];
  return (
    <div className="detail-grid">
      <div className="panel">
        <h2>{t("data.cache.title")}</h2>
        <div className="record-list">
          {items.map((item) => (
            <div className="record-item" key={String(item.ip)}>
              <div className="record-main">
                <span className="record-title">{String(item.ip)}</span>
                <span className="tag">{String(item.status)} / {String(item.confidence)}</span>
              </div>
              <div className="record-meta">
                <span>{t("data.cache.asnValue", { value: displayValue(item.asn) })}</span>
                <span>{String(item.details || t("common.notAvailable"))}</span>
              </div>
              <div className="record-actions">
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
                  try {
                    await api.deleteCache(String(item.ip));
                    setCache(await api.getCache());
                    pushToast("success", t("data.saved.cacheUpdated"));
                  } catch (err) {
                    pushToast("error", err instanceof Error ? err.message : t("data.errors.saveCacheFailed"));
                  }
                }}>{t("data.cache.delete")}</button>
              </div>
            </div>
          ))}
        </div>
      </div>
      <div className="panel">
        <div className="panel-heading">
          <h2>{t("data.cache.editTitle")}</h2>
          <p className="muted">{t("data.sectionDescriptions.cache")}</p>
        </div>
        <div className="form-grid compact-form-grid">
          <div className="rule-field compact-rule-field">
            <strong>{t("data.cache.selectedIp")}</strong>
            <input placeholder={t("data.cache.selectedIp")} value={selectedCacheIp} onChange={(event) => setSelectedCacheIp(event.target.value)} />
          </div>
          <div className="rule-field compact-rule-field">
            <strong>{t("data.cache.status")}</strong>
            <input placeholder={t("data.cache.status")} value={cacheDraft.status || ""} onChange={(event) => setCacheDraft((prev) => ({ ...prev, status: event.target.value }))} />
          </div>
          <div className="rule-field compact-rule-field">
            <strong>{t("data.cache.confidence")}</strong>
            <input placeholder={t("data.cache.confidence")} value={cacheDraft.confidence || ""} onChange={(event) => setCacheDraft((prev) => ({ ...prev, confidence: event.target.value }))} />
          </div>
          <div className="rule-field rule-field-wide compact-rule-field">
            <strong>{t("data.cache.details")}</strong>
            <textarea className="note-box compact-note-box" placeholder={t("data.cache.details")} value={cacheDraft.details || ""} onChange={(event) => setCacheDraft((prev) => ({ ...prev, details: event.target.value }))} />
          </div>
          <div className="rule-field compact-rule-field">
            <strong>{t("data.cache.asn")}</strong>
            <input placeholder={t("data.cache.asn")} value={cacheDraft.asn || ""} onChange={(event) => setCacheDraft((prev) => ({ ...prev, asn: event.target.value }))} />
          </div>
        </div>
        <button onClick={saveCachePatch} disabled={!selectedCacheIp || isPending("cacheSave")}>{t("data.cache.save")}</button>
      </div>
    </div>
  );
}
