import { useEffect, useState } from "react";

import { api } from "../api/client";

type TelegramPayload = {
  settings: Record<string, string | number | boolean>;
  capabilities: {
    admin_bot_enabled: boolean;
    user_bot_enabled: boolean;
  };
};

type TelegramField = {
  key: string;
  label: string;
  type: "text" | "number" | "boolean";
  step?: number;
  description: string;
};

const TELEGRAM_FIELDS: TelegramField[] = [
  { key: "tg_admin_chat_id", label: "Admin chat destination", type: "text", description: "Telegram chat id for admin notifications." },
  { key: "tg_topic_id", label: "Admin thread/topic", type: "number", description: "Optional topic/thread id inside the admin chat." },
  { key: "telegram_message_min_interval_seconds", label: "Message interval (sec)", type: "number", step: 0.1, description: "Minimum delay between Telegram sends." },
  { key: "telegram_admin_notifications_enabled", label: "Send admin notifications", type: "boolean", description: "Master switch for all admin bot notifications." },
  { key: "telegram_user_notifications_enabled", label: "Send user notifications", type: "boolean", description: "Master switch for all user-facing bot messages." },
  { key: "telegram_admin_commands_enabled", label: "Enable admin bot commands", type: "boolean", description: "Allows Telegram admin command handlers to run." },
  { key: "telegram_notify_review_enabled", label: "Notify review cases", type: "boolean", description: "Send Telegram messages when review/manual moderation is needed." },
  { key: "telegram_notify_warning_only_enabled", label: "Notify warning-only cases", type: "boolean", description: "Send Telegram messages for non-escalating warning-only events." },
  { key: "telegram_notify_warning_enabled", label: "Notify warnings", type: "boolean", description: "Send Telegram messages when a warning is issued." },
  { key: "telegram_notify_ban_enabled", label: "Notify bans", type: "boolean", description: "Send Telegram messages when a ban is issued." }
];

export function TelegramPage() {
  const [data, setData] = useState<TelegramPayload | null>(null);
  const [settings, setSettings] = useState<Record<string, string>>({});
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
      const response = (await api.updateTelegramSettings({
        settings: settingsPayload
      })) as TelegramPayload;
      setData(response);
      setSettings(
        Object.fromEntries(
          TELEGRAM_FIELDS.map((field) => [field.key, String(response.settings[field.key] ?? "")])
        )
      );
      setSaved("Telegram settings saved");
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
              <h2>Telegram capability status</h2>
              <p className="muted">Bot tokens and usernames are managed only through `.env` on the server.</p>
            </div>
            <div className="stats-grid">
              <div className="stat-card">
                <span>Admin bot token + username</span>
                <strong>{data.capabilities.admin_bot_enabled ? "Configured" : "Disabled"}</strong>
              </div>
              <div className="stat-card">
                <span>User bot token</span>
                <strong>{data.capabilities.user_bot_enabled ? "Configured" : "Disabled"}</strong>
              </div>
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
                    <span className="muted">{field.description}</span>
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
