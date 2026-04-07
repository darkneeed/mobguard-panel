import { useEffect, useState } from "react";

import { api } from "../api/client";

type EnforcementPayload = {
  settings: Record<string, string | number | boolean | string[]>;
};

type EnforcementField = {
  key: string;
  label: string;
  description: string;
  type: "number" | "boolean";
};

type EnforcementTemplateField = {
  key: string;
  label: string;
  description: string;
};

const BOOLEAN_FIELDS: EnforcementField[] = [
  { key: "warning_only_mode", label: "Only warnings mode", description: "Never escalate to bans automatically.", type: "boolean" },
  { key: "manual_review_mixed_home_enabled", label: "Review mixed HOME cases manually", description: "Send mixed HOME outcomes to manual review before action.", type: "boolean" },
  { key: "manual_ban_approval_enabled", label: "Require admin approval for bans", description: "Pause ban execution until admin approves it.", type: "boolean" },
  { key: "dry_run", label: "Dry run", description: "Analyze and notify without applying remote disable actions.", type: "boolean" }
];

const NUMBER_FIELDS: EnforcementField[] = [
  { key: "usage_time_threshold", label: "Minimum suspicious usage time (sec)", description: "How long a suspicious session must stay active before enforcement starts.", type: "number" },
  { key: "warning_timeout_seconds", label: "Warning cooldown (sec)", description: "Minimum delay before the next warning can be sent.", type: "number" },
  { key: "warnings_before_ban", label: "Warnings before first ban", description: "How many warning events are required before the first ban.", type: "number" }
];

const TEXTAREA_FIELDS: EnforcementTemplateField[] = [
  { key: "user_warning_only_template", label: "User warning-only message", description: "User-facing message when the case is warning-only and does not escalate." },
  { key: "user_warning_template", label: "User warning message", description: "User-facing message for standard warnings before a ban." },
  { key: "user_ban_template", label: "User ban message", description: "User-facing message sent when a ban is applied." },
  { key: "admin_warning_only_template", label: "Admin warning-only message", description: "Admin notification text for warning-only cases." },
  { key: "admin_warning_template", label: "Admin warning message", description: "Admin notification text for warning events." },
  { key: "admin_ban_template", label: "Admin ban message", description: "Admin notification text for ban events." },
  { key: "admin_review_template", label: "Admin review message", description: "Admin notification text for review/manual moderation cases." }
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
      for (const field of NUMBER_FIELDS) {
        const parsed = Number(draft[field.key]);
        if (!Number.isFinite(parsed)) {
          throw new Error(`${field.label}: invalid number`);
        }
        settingsPayload[field.key] = parsed;
      }
      for (const field of BOOLEAN_FIELDS) {
        settingsPayload[field.key] = draft[field.key] === "true";
      }
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
      for (const field of TEXTAREA_FIELDS) {
        settingsPayload[field.key] = draft[field.key];
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
                <strong>{NUMBER_FIELDS[0].label}</strong>
                <span className="muted">{NUMBER_FIELDS[0].description}</span>
                <input
                  type="number"
                  value={draft.usage_time_threshold}
                  onChange={(event) => setDraft((prev) => ({ ...prev, usage_time_threshold: event.target.value }))}
                />
              </div>
              <div className="rule-field">
                <strong>{NUMBER_FIELDS[1].label}</strong>
                <span className="muted">{NUMBER_FIELDS[1].description}</span>
                <input
                  type="number"
                  value={draft.warning_timeout_seconds}
                  onChange={(event) => setDraft((prev) => ({ ...prev, warning_timeout_seconds: event.target.value }))}
                />
              </div>
              <div className="rule-field">
                <strong>{NUMBER_FIELDS[2].label}</strong>
                <span className="muted">{NUMBER_FIELDS[2].description}</span>
                <input
                  type="number"
                  value={draft.warnings_before_ban}
                  onChange={(event) => setDraft((prev) => ({ ...prev, warnings_before_ban: event.target.value }))}
                />
              </div>
              {BOOLEAN_FIELDS.map((field) => (
                <div className="rule-field" key={field.key}>
                  <strong>{field.label}</strong>
                  <span className="muted">{field.description}</span>
                  <select
                    value={draft[field.key]}
                    onChange={(event) => setDraft((prev) => ({ ...prev, [field.key]: event.target.value }))}
                  >
                    <option value="true">true</option>
                    <option value="false">false</option>
                  </select>
                </div>
              ))}
              <div className="rule-field">
                <strong>Ban durations ladder (minutes)</strong>
                <span className="muted">One duration per line: first ban, second ban, third ban, and so on.</span>
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
              {TEXTAREA_FIELDS.map((field) => (
                <div className="rule-field" key={field.key}>
                  <strong>{field.label}</strong>
                  <span className="muted">{field.description}</span>
                  <textarea
                    className="note-box tall"
                    value={draft[field.key]}
                    onChange={(event) => setDraft((prev) => ({ ...prev, [field.key]: event.target.value }))}
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
