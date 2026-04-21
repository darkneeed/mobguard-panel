import type { ReactNode } from "react";
import { Link } from "react-router-dom";

import { api, UserCardExportResponse, UserCardResponse, UserSearchResponse } from "../../api/client";
import type { Language } from "../../localization/types";
import { formatDisplayDateTime } from "../../utils/datetime";

type PendingKey = "userSearch" | "userLoad" | "userAction" | "userExport";

type TranslateFn = (key: string, params?: Record<string, string | number>) => string;

type Props = {
  t: TranslateFn;
  language: Language;
  userQuery: string;
  setUserQuery: (value: string) => void;
  userSearch: UserSearchResponse | null;
  userCard: UserCardResponse | null;
  userCardExport: UserCardExportResponse | null;
  banMinutes: string;
  setBanMinutes: (value: string) => void;
  trafficCapGigabytes: string;
  setTrafficCapGigabytes: (value: string) => void;
  strikeCount: string;
  setStrikeCount: (value: string) => void;
  warningCount: string;
  setWarningCount: (value: string) => void;
  searchUsers: () => Promise<void>;
  loadUser: (identifier: string) => Promise<void>;
  runUserAction: (action: () => Promise<UserCardResponse>, successMessage: string) => Promise<void>;
  buildUserExport: (identifier: string) => Promise<void>;
  downloadUserExport: () => void;
  isPending: (...keys: PendingKey[]) => boolean;
  displayValue: (value: unknown) => string;
  formatPanelSquads: (value: unknown) => string;
  formatTrafficBytes: (value: unknown) => string;
  renderProviderEvidence: (providerEvidence: Record<string, unknown> | undefined) => ReactNode;
};

export function UserDataSection({
  t,
  language,
  userQuery,
  setUserQuery,
  userSearch,
  userCard,
  userCardExport,
  banMinutes,
  setBanMinutes,
  trafficCapGigabytes,
  setTrafficCapGigabytes,
  strikeCount,
  setStrikeCount,
  warningCount,
  setWarningCount,
  searchUsers,
  loadUser,
  runUserAction,
  buildUserExport,
  downloadUserExport,
  isPending,
  displayValue,
  formatPanelSquads,
  formatTrafficBytes,
  renderProviderEvidence,
}: Props) {
  const items = userSearch?.items || [];
  const panelMatch = userSearch?.panel_match || undefined;
  const identity = userCard?.identity;
  const flags = userCard?.flags;
  const reviewCases = userCard?.review_cases || [];
  const history = userCard?.history || [];
  const analysisEvents = userCard?.analysis_events || [];
  const panelUser = userCard?.panel_user || undefined;
  const userTraffic =
    panelUser && typeof panelUser === "object" && "userTraffic" in panelUser
      ? (panelUser.userTraffic as Record<string, unknown> | undefined)
      : undefined;
  const identifier = String(identity?.uuid || identity?.system_id || identity?.telegram_id || "");

  function renderUserExportPreview() {
    if (!userCardExport) return null;
    const exportMeta = userCardExport.export_meta || {};
    const recordCounts = exportMeta.record_counts || {};
    const sections: Array<[string, unknown]> = [
      [t("data.users.exportSections.identity"), userCardExport.identity],
      [t("data.users.exportSections.flags"), userCardExport.flags],
      [t("data.users.exportSections.panel"), userCardExport.panel_user],
      [t("data.users.exportSections.reviewCases"), userCardExport.review_cases],
      [t("data.users.exportSections.analysisEvents"), userCardExport.analysis_events],
      [t("data.users.exportSections.history"), userCardExport.history],
      [t("data.users.exportSections.activeTrackers"), userCardExport.active_trackers],
      [t("data.users.exportSections.ipHistory"), userCardExport.ip_history]
    ];

    return (
      <div className="panel">
        <div className="panel-heading panel-heading-row">
          <div>
            <h2>{t("data.users.exportPreviewTitle")}</h2>
            <p className="muted">
              {t("data.users.exportGeneratedAt", {
                value: formatDisplayDateTime(
                  String(exportMeta.generated_at || ""),
                  t("common.notAvailable"),
                  language
                ),
              })}
            </p>
          </div>
          <button className="ghost" onClick={downloadUserExport} disabled={isPending("userExport")}>
            {t("data.users.downloadExport")}
          </button>
        </div>
        <div className="stats-grid">
          <div className="stat-card"><span>{t("data.users.exportCards.reviewCases")}</span><strong>{displayValue(recordCounts.review_cases)}</strong></div>
          <div className="stat-card"><span>{t("data.users.exportCards.analysisEvents")}</span><strong>{displayValue(recordCounts.analysis_events)}</strong></div>
          <div className="stat-card"><span>{t("data.users.exportCards.history")}</span><strong>{displayValue(recordCounts.history)}</strong></div>
          <div className="stat-card"><span>{t("data.users.exportCards.ipHistory")}</span><strong>{displayValue(recordCounts.ip_history)}</strong></div>
        </div>
        <div className="export-sections">
          {sections.map(([label, value]) => (
            <details className="export-section" key={label} open={label === t("data.users.exportSections.identity")}>
              <summary>{label}</summary>
              <pre className="log-box">{JSON.stringify(value ?? null, null, 2)}</pre>
            </details>
          ))}
        </div>
      </div>
    );
  }

  return (
    <>
      <div className="panel">
        <div className="search-strip compact-search-strip">
          <input
            placeholder={t("data.users.searchPlaceholder")}
            value={userQuery}
            onChange={(event) => setUserQuery(event.target.value)}
          />
          <button onClick={searchUsers} disabled={isPending("userSearch") || !userQuery.trim()}>
            {isPending("userSearch") ? t("data.users.searching") : t("data.users.search")}
          </button>
        </div>
        {panelMatch ? (
          <div className="tag">
            {t("data.users.panelMatch", {
              value: String(
                (panelMatch as Record<string, unknown>).username ||
                  (panelMatch as Record<string, unknown>).uuid ||
                  (panelMatch as Record<string, unknown>).id
              ),
            })}
          </div>
        ) : null}
        <ul className="reason-list">
          {items.map((item) => (
            <li key={String(item.uuid || item.system_id || item.telegram_id)}>
              <button
                className="ghost"
                disabled={isPending("userLoad")}
                onClick={() => loadUser(String(item.uuid || item.system_id || item.telegram_id))}
              >
                {String(item.username || item.uuid || item.system_id)} ·{" "}
                {t("data.users.systemLabel", { value: displayValue(item.system_id) })} ·{" "}
                {t("data.users.telegramLabel", { value: displayValue(item.telegram_id) })}
              </button>
            </li>
          ))}
        </ul>
      </div>

      {identity ? (
        <div className="detail-grid">
          <div className="panel">
            <div className="panel-heading panel-heading-row">
              <div>
                <h2>{t("data.users.cardTitle")}</h2>
                <p className="muted">{t("data.users.exportHint")}</p>
              </div>
              <button onClick={() => buildUserExport(identifier)} disabled={isPending("userExport") || !identifier}>
                {isPending("userExport") ? t("data.users.generatingExport") : t("data.users.buildExport")}
              </button>
            </div>
            <dl className="detail-list">
              <div><dt>{t("data.users.fields.username")}</dt><dd>{displayValue(identity.username)}</dd></div>
              <div><dt>{t("data.users.fields.uuid")}</dt><dd>{displayValue(identity.uuid)}</dd></div>
              <div><dt>{t("data.users.fields.systemId")}</dt><dd>{displayValue(identity.system_id)}</dd></div>
              <div><dt>{t("data.users.fields.telegramId")}</dt><dd>{displayValue(identity.telegram_id)}</dd></div>
              <div><dt>{t("data.users.fields.panelStatus")}</dt><dd>{displayValue((panelUser as Record<string, unknown> | undefined)?.status)}</dd></div>
              <div><dt>{t("data.users.fields.panelSquads")}</dt><dd>{formatPanelSquads((panelUser as Record<string, unknown> | undefined)?.activeInternalSquads)}</dd></div>
              <div><dt>{t("data.users.fields.trafficLimitBytes")}</dt><dd>{formatTrafficBytes((panelUser as Record<string, unknown> | undefined)?.trafficLimitBytes)}</dd></div>
              <div><dt>{t("data.users.fields.trafficLimitStrategy")}</dt><dd>{displayValue((panelUser as Record<string, unknown> | undefined)?.trafficLimitStrategy)}</dd></div>
              <div><dt>{t("data.users.fields.usedTrafficBytes")}</dt><dd>{formatTrafficBytes(userTraffic?.usedTrafficBytes)}</dd></div>
              <div><dt>{t("data.users.fields.lifetimeUsedTrafficBytes")}</dt><dd>{formatTrafficBytes(userTraffic?.lifetimeUsedTrafficBytes)}</dd></div>
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
                <button disabled={isPending("userAction")} onClick={() => runUserAction(() => api.banUser(identifier, Number(banMinutes)), t("data.saved.userUpdated"))}>{t("data.users.actions.startBan")}</button>
                <button className="ghost" disabled={isPending("userAction")} onClick={() => runUserAction(() => api.unbanUser(identifier), t("data.saved.userUpdated"))}>{t("data.users.actions.unban")}</button>
              </div>
              <div className="rule-field">
                <strong>{t("data.users.actions.trafficCapGigabytes")}</strong>
                <input value={trafficCapGigabytes} onChange={(event) => setTrafficCapGigabytes(event.target.value)} />
                <div className="action-row">
                  <button disabled={isPending("userAction")} onClick={() => runUserAction(() => api.applyUserTrafficCap(identifier, Number(trafficCapGigabytes)), t("data.saved.userUpdated"))}>{t("data.users.actions.applyTrafficCap")}</button>
                  <button className="ghost" disabled={isPending("userAction")} onClick={() => runUserAction(() => api.restoreUserTrafficCap(identifier), t("data.saved.userUpdated"))}>{t("data.users.actions.restoreTrafficCap")}</button>
                </div>
              </div>
              <div className="rule-field">
                <strong>{t("data.users.actions.strikes")}</strong>
                <input value={strikeCount} onChange={(event) => setStrikeCount(event.target.value)} />
                <div className="action-row">
                  <button className="ghost" disabled={isPending("userAction")} onClick={() => runUserAction(() => api.updateUserStrikes(identifier, "add", Number(strikeCount)), t("data.saved.userUpdated"))}>{t("data.users.actions.add")}</button>
                  <button className="ghost" disabled={isPending("userAction")} onClick={() => runUserAction(() => api.updateUserStrikes(identifier, "remove", Number(strikeCount)), t("data.saved.userUpdated"))}>{t("data.users.actions.remove")}</button>
                  <button disabled={isPending("userAction")} onClick={() => runUserAction(() => api.updateUserStrikes(identifier, "set", Number(strikeCount)), t("data.saved.userUpdated"))}>{t("data.users.actions.set")}</button>
                </div>
              </div>
              <div className="rule-field">
                <strong>{t("data.users.actions.warnings")}</strong>
                <input value={warningCount} onChange={(event) => setWarningCount(event.target.value)} />
                <div className="action-row">
                  <button disabled={isPending("userAction")} onClick={() => runUserAction(() => api.updateUserWarnings(identifier, "set", Number(warningCount)), t("data.saved.userUpdated"))}>{t("data.users.actions.setWarning")}</button>
                  <button className="ghost" disabled={isPending("userAction")} onClick={() => runUserAction(() => api.updateUserWarnings(identifier, "clear", 0), t("data.saved.userUpdated"))}>{t("data.users.actions.clearWarning")}</button>
                </div>
              </div>
              <div className="rule-field">
                <strong>{t("data.users.actions.exemptions")}</strong>
                <div className="action-row">
                  <button disabled={isPending("userAction")} onClick={() => runUserAction(() => api.updateUserExempt(identifier, "system", true), t("data.saved.userUpdated"))}>{t("data.users.actions.exemptSystem")}</button>
                  <button className="ghost" disabled={isPending("userAction")} onClick={() => runUserAction(() => api.updateUserExempt(identifier, "system", false), t("data.saved.userUpdated"))}>{t("data.users.actions.unexemptSystem")}</button>
                </div>
                <div className="action-row">
                  <button disabled={isPending("userAction")} onClick={() => runUserAction(() => api.updateUserExempt(identifier, "telegram", true), t("data.saved.userUpdated"))}>{t("data.users.actions.exemptTelegram")}</button>
                  <button className="ghost" disabled={isPending("userAction")} onClick={() => runUserAction(() => api.updateUserExempt(identifier, "telegram", false), t("data.saved.userUpdated"))}>{t("data.users.actions.unexemptTelegram")}</button>
                </div>
              </div>
            </div>
          </div>

          <div className="panel">
            <h2>{t("data.users.analysisTitle")}</h2>
            <ul className="reason-list">
              {analysisEvents.length === 0 ? <li><span>{t("data.users.analysisEmpty")}</span></li> : null}
              {analysisEvents.map((item, index) => (
                <li key={String((item as Record<string, unknown>).id || index)}>
                  <strong>{displayValue((item as Record<string, unknown>).ip)} · {displayValue((item as Record<string, unknown>).verdict)} / {displayValue((item as Record<string, unknown>).confidence_band)}</strong>
                  <span>{displayValue((item as Record<string, unknown>).isp)} · AS{displayValue((item as Record<string, unknown>).asn)}</span>
                  {renderProviderEvidence((item as Record<string, unknown>).provider_evidence as Record<string, unknown> | undefined)}
                  <span>{formatDisplayDateTime(String((item as Record<string, unknown>).created_at ?? ""), t("common.notAvailable"), language)}</span>
                </li>
              ))}
            </ul>
          </div>

          <div className="panel">
            <h2>{t("data.users.openCasesTitle")}</h2>
            <ul className="reason-list">
              {reviewCases.length === 0 ? <li><span>{t("data.users.openCasesEmpty")}</span></li> : null}
              {reviewCases.map((item, index) => (
                <li key={String((item as Record<string, unknown>).id || index)}>
                  <Link to={`/reviews/${(item as Record<string, unknown>).id}`}>
                    #{String((item as Record<string, unknown>).id)} · {String((item as Record<string, unknown>).review_reason)} · {String((item as Record<string, unknown>).ip)} · {formatDisplayDateTime(String((item as Record<string, unknown>).updated_at ?? ""), t("common.notAvailable"), language)}
                  </Link>
                </li>
              ))}
            </ul>
          </div>

          <div className="panel">
            <h2>{t("data.users.historyTitle")}</h2>
            <ul className="reason-list">
              {history.length === 0 ? <li><span>{t("data.users.historyEmpty")}</span></li> : null}
              {history.map((item, index) => (
                <li key={`${String((item as Record<string, unknown>).timestamp)}-${String((item as Record<string, unknown>).ip)}-${index}`}>
                  <strong>{String((item as Record<string, unknown>).ip)}</strong>
                  <span>{String((item as Record<string, unknown>).tag)} · {t("data.violations.historyRow", { strike: String((item as Record<string, unknown>).strike_number), duration: String((item as Record<string, unknown>).punishment_duration) })}</span>
                  <span>{formatDisplayDateTime(String((item as Record<string, unknown>).timestamp ?? ""), t("common.notAvailable"), language)}</span>
                </li>
              ))}
            </ul>
          </div>

          {renderUserExportPreview()}
        </div>
      ) : null}
    </>
  );
}
