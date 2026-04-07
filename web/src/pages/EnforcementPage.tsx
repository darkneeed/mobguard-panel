import { useEffect, useState } from "react";

import { api } from "../api/client";

type EnforcementPayload = {
  settings: Record<string, string | number | boolean | string[]>;
};

const BOOLEAN_FIELDS = [
  "warning_only_mode",
  "manual_review_mixed_home_enabled",
  "manual_ban_approval_enabled",
  "dry_run"
];

const NUMBER_FIELDS = [
  "usage_time_threshold",
  "warning_timeout_seconds",
  "warnings_before_ban"
];

const TEXTAREA_FIELDS = [
  "user_warning_only_template",
  "user_warning_template",
  "user_ban_template",
  "admin_warning_only_template",
  "admin_warning_template",
  "admin_ban_template",
  "admin_review_template"
];

export function EnforcementPage() {
  const [data, setData] = useState<EnforcementPayload | null>(null);
  const [draft, setDraft] = useState<Record<string, string>>({});
  const [error, setError] = useState("");
  const [saved, setSaved] = useState("");

  useEffect(() => {
    api
      .getEnforcementSettings()
      .then((payload) => {
        const typed = payload as EnforcementPayload;
        setData(typed);
        setDraft(
          Object.fromEntries(
            Object.entries(typed.settings).map(([key, value]) => [
              key,
              Array.isArray(value) ? value.join("\n") : String(value)
            ])
          )
        );
      })
      .catch((err: Error) => setError(err.message));
  }, []);

  async function save() {
    try {
      const settingsPayload: Record<string, unknown> = {};
      for (const key of NUMBER_FIELDS) {
        const parsed = Number(draft[key]);
        if (!Number.isFinite(parsed)) {
          throw new Error(`${key}: invalid number`);
        }
        settingsPayload[key] = parsed;
      }
      for (const key of BOOLEAN_FIELDS) {
        settingsPayload[key] = draft[key] === "true";
      }
      settingsPayload.report_time = draft.report_time;
      settingsPayload.ban_durations_minutes = draft.ban_durations_minutes
        .split("\n")
        .map((item) => item.trim())
        .filter(Boolean)
        .map((item) => {
          const parsed = Number(item);
          if (!Number.isFinite(parsed)) {
            throw new Error(`ban_durations_minutes: invalid value '${item}'`);
          }
          return parsed;
        });
      for (const key of TEXTAREA_FIELDS) {
        settingsPayload[key] = draft[key];
      }

      const response = (await api.updateEnforcementSettings({
        settings: settingsPayload
      })) as EnforcementPayload;
      setData(response);
      setDraft(
        Object.fromEntries(
          Object.entries(response.settings).map(([key, value]) => [
            key,
            Array.isArray(value) ? value.join("\n") : String(value)
          ])
        )
      );
      setSaved("Enforcement settings saved");
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed");
      setSaved("");
    }
  }

  return (
    <section className="page">
      <div className="page-header">
        <div>
          <span className="eyebrow">Enforcement</span>
          <h1>Warnings, bans, escalation and message templates</h1>
        </div>
        <button onClick={save} disabled={!data}>
          Save enforcement settings
        </button>
      </div>

      {error ? <div className="error-box">{error}</div> : null}
      {saved ? <div className="ok-box">{saved}</div> : null}
      {!data ? <div className="panel">Loading…</div> : null}

      {data ? (
        <>
          <div className="panel">
            <div className="panel-heading">
              <h2>Escalation controls</h2>
              <p className="muted">Canonical enforcement parameters used by core runtime.</p>
            </div>
            <div className="form-grid">
              <div className="rule-field">
                <strong>Usage time threshold</strong>
                <input
                  type="number"
                  value={draft.usage_time_threshold}
                  onChange={(event) => setDraft((prev) => ({ ...prev, usage_time_threshold: event.target.value }))}
                />
              </div>
              <div className="rule-field">
                <strong>Warning timeout (sec)</strong>
                <input
                  type="number"
                  value={draft.warning_timeout_seconds}
                  onChange={(event) => setDraft((prev) => ({ ...prev, warning_timeout_seconds: event.target.value }))}
                />
              </div>
              <div className="rule-field">
                <strong>Warnings before ban</strong>
                <input
                  type="number"
                  value={draft.warnings_before_ban}
                  onChange={(event) => setDraft((prev) => ({ ...prev, warnings_before_ban: event.target.value }))}
                />
              </div>
              <div className="rule-field">
                <strong>Report time</strong>
                <input
                  value={draft.report_time}
                  onChange={(event) => setDraft((prev) => ({ ...prev, report_time: event.target.value }))}
                />
              </div>
              {BOOLEAN_FIELDS.map((key) => (
                <div className="rule-field" key={key}>
                  <strong>{key}</strong>
                  <select
                    value={draft[key]}
                    onChange={(event) => setDraft((prev) => ({ ...prev, [key]: event.target.value }))}
                  >
                    <option value="true">true</option>
                    <option value="false">false</option>
                  </select>
                </div>
              ))}
              <div className="rule-field">
                <strong>Ban durations ladder (minutes)</strong>
                <textarea
                  className="note-box tall"
                  value={draft.ban_durations_minutes}
                  onChange={(event) => setDraft((prev) => ({ ...prev, ban_durations_minutes: event.target.value }))}
                />
              </div>
            </div>
          </div>

          <div className="panel">
            <div className="panel-heading">
              <h2>Message templates</h2>
              <p className="muted">
                Multiline text is preserved. Use placeholders like {`{{username}}`}, {`{{warning_count}}`}, {`{{ban_text}}`}.
              </p>
            </div>
            <div className="detail-grid">
              {TEXTAREA_FIELDS.map((key) => (
                <div className="rule-field" key={key}>
                  <strong>{key}</strong>
                  <textarea
                    className="note-box tall"
                    value={draft[key]}
                    onChange={(event) => setDraft((prev) => ({ ...prev, [key]: event.target.value }))}
                  />
                </div>
              ))}
            </div>
          </div>
        </>
      ) : null}
    </section>
  );
}
