import { useEffect, useState } from "react";

import { api, EnvFieldState } from "../api/client";

type TelegramPayload = {
  settings: Record<string, string | number | boolean>;
  env: Record<string, EnvFieldState>;
  env_file_path: string;
  env_file_writable: boolean;
  capabilities: {
    admin_bot_enabled: boolean;
    user_bot_enabled: boolean;
  };
};

type EnvDraftState = {
  value: string;
  clear: boolean;
};

type TelegramField = {
  key: string;
  label: string;
  type: "text" | "number" | "boolean";
  step?: number;
};

const TELEGRAM_FIELDS: TelegramField[] = [
  { key: "tg_admin_chat_id", label: "Admin chat id", type: "text" },
  { key: "tg_topic_id", label: "Admin topic id", type: "number" },
  { key: "telegram_message_min_interval_seconds", label: "Message min interval (sec)", type: "number", step: 0.1 },
  { key: "telegram_admin_notifications_enabled", label: "Admin notifications enabled", type: "boolean" },
  { key: "telegram_user_notifications_enabled", label: "User notifications enabled", type: "boolean" },
  { key: "telegram_admin_commands_enabled", label: "Admin bot commands enabled", type: "boolean" },
  { key: "telegram_notify_review_enabled", label: "Review notifications enabled", type: "boolean" },
  { key: "telegram_notify_warning_only_enabled", label: "Warning-only notifications enabled", type: "boolean" },
  { key: "telegram_notify_warning_enabled", label: "Warning notifications enabled", type: "boolean" },
  { key: "telegram_notify_ban_enabled", label: "Ban notifications enabled", type: "boolean" }
];

export function TelegramPage() {
  const [data, setData] = useState<TelegramPayload | null>(null);
  const [settings, setSettings] = useState<Record<string, string>>({});
  const [envDraft, setEnvDraft] = useState<Record<string, EnvDraftState>>({});
  const [error, setError] = useState("");
  const [saved, setSaved] = useState("");

  useEffect(() => {
    api
      .getTelegramSettings()
      .then((payload) => {
        const typed = payload as TelegramPayload;
        setData(typed);
        setSettings(
          Object.fromEntries(
            TELEGRAM_FIELDS.map((field) => [field.key, String(typed.settings[field.key] ?? "")])
          )
        );
        setEnvDraft(
          Object.fromEntries(
            Object.entries(typed.env).map(([key, field]) => [
              key,
              {
                value: field.masked ? "" : field.value,
                clear: false
              }
            ])
          )
        );
      })
      .catch((err: Error) => setError(err.message));
  }, []);

  async function save() {
    if (!data) return;
    try {
      const settingsPayload = Object.fromEntries(
        TELEGRAM_FIELDS.map((field) => {
          if (field.type === "boolean") {
            return [field.key, settings[field.key] === "true"];
          }
          if (field.type === "number") {
            const parsed = Number(settings[field.key]);
            if (!Number.isFinite(parsed)) {
              throw new Error(`${field.label}: invalid number`);
            }
            return [field.key, parsed];
          }
          return [field.key, settings[field.key]];
        })
      );
      const envPayload = Object.fromEntries(
        Object.entries(data.env).flatMap(([key, field]) => {
          const draft = envDraft[key];
          if (!draft) return [];
          if (draft.clear) return [[key, ""]];
          if (field.masked) return draft.value ? [[key, draft.value]] : [];
          return [[key, draft.value]];
        })
      );
      const response = (await api.updateTelegramSettings({
        settings: settingsPayload,
        env: envPayload
      })) as TelegramPayload;
      setData(response);
      setSettings(
        Object.fromEntries(
          TELEGRAM_FIELDS.map((field) => [field.key, String(response.settings[field.key] ?? "")])
        )
      );
      setSaved("Telegram settings saved");
      setError("");
      setEnvDraft(
        Object.fromEntries(
          Object.entries(response.env).map(([key, field]) => [
            key,
            { value: field.masked ? "" : field.value, clear: false }
          ])
        )
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed");
      setSaved("");
    }
  }

  return (
    <section className="page">
      <div className="page-header">
        <div>
          <span className="eyebrow">Telegram</span>
          <h1>Bot runtime settings and secrets</h1>
        </div>
        <button onClick={save} disabled={!data}>
          Save telegram settings
        </button>
      </div>
      {error ? <div className="error-box">{error}</div> : null}
      {saved ? <div className="ok-box">{saved}</div> : null}
      {!data ? <div className="panel">Loading…</div> : null}

      {data ? (
        <>
          <div className="stats-grid">
            <div className="stat-card">
              <span>Admin bot</span>
              <strong>{data.capabilities.admin_bot_enabled ? "ON" : "OFF"}</strong>
            </div>
            <div className="stat-card">
              <span>User bot</span>
              <strong>{data.capabilities.user_bot_enabled ? "ON" : "OFF"}</strong>
            </div>
          </div>

          <div className="panel">
            <div className="panel-heading">
              <h2>Telegram secrets</h2>
              <p className="muted">`.env` backed, restart required after change.</p>
            </div>
            {!data.env_file_writable ? (
              <div className="error-box">
                Runtime env is read-only. Values are detected from the container environment, but saving requires a writable env file at {data.env_file_path}.
              </div>
            ) : null}
            <div className="form-grid">
              {Object.entries(data.env).map(([key, field]) => (
                <div className="rule-field" key={key}>
                  <div className="rule-copy">
                    <strong>{key}</strong>
                    <span className="muted">
                      {field.present ? `Configured (${field.value})` : "Not configured"}
                    </span>
                  </div>
                  <input
                    type={key.includes("TOKEN") ? "password" : "text"}
                    placeholder={field.masked ? "Leave blank to keep current value" : ""}
                    value={envDraft[key]?.value || ""}
                    onChange={(event) =>
                      setEnvDraft((prev) => ({
                        ...prev,
                        [key]: { value: event.target.value, clear: false }
                      }))
                    }
                  />
                  {field.masked ? (
                    <label className="inline-check">
                      <input
                        type="checkbox"
                        checked={envDraft[key]?.clear || false}
                        onChange={(event) =>
                          setEnvDraft((prev) => ({
                            ...prev,
                            [key]: { value: "", clear: event.target.checked }
                          }))
                        }
                      />
                      <span>Clear current value</span>
                    </label>
                  ) : null}
                </div>
              ))}
            </div>
          </div>

          <div className="panel">
            <div className="panel-heading">
              <h2>Runtime behavior</h2>
              <p className="muted">Эти параметры live-редактируемые и не требуют restart.</p>
            </div>
            <div className="form-grid">
              {TELEGRAM_FIELDS.map((field) => (
                <div className="rule-field" key={field.key}>
                  <div className="rule-copy">
                    <strong>{field.label}</strong>
                    <span className="muted">{field.key}</span>
                  </div>
                  {field.type === "boolean" ? (
                    <select
                      value={settings[field.key]}
                      onChange={(event) =>
                        setSettings((prev) => ({ ...prev, [field.key]: event.target.value }))
                      }
                    >
                      <option value="true">true</option>
                      <option value="false">false</option>
                    </select>
                  ) : (
                    <input
                      type={field.type === "number" ? "number" : "text"}
                      step={field.step}
                      value={settings[field.key]}
                      onChange={(event) =>
                        setSettings((prev) => ({ ...prev, [field.key]: event.target.value }))
                      }
                    />
                  )}
                </div>
              ))}
            </div>
          </div>
        </>
      ) : null}
    </section>
  );
}
