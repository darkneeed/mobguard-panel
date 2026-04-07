import { useEffect, useState } from "react";

import { api } from "../api/client";
import { RULE_LIST_FIELDS } from "../rulesMeta";

type AccessPayload = {
  revision: number;
  updated_at: string;
  updated_by: string;
  lists: Record<string, Array<string | number>>;
  auth: {
    telegram_enabled: boolean;
    local_enabled: boolean;
    local_username_hint: string;
  };
};

const ACCESS_FIELDS = RULE_LIST_FIELDS.filter((field) => field.section === "Access");

function listValuesToText(values: Array<string | number> | undefined): string {
  return (values || []).map((item) => String(item)).join("\n");
}

function parseNumberList(text: string): number[] {
  const values: number[] = [];
  for (const raw of text.split("\n").map((item) => item.trim()).filter(Boolean)) {
    const parsed = Number(raw);
    if (!Number.isFinite(parsed)) {
      throw new Error(`Invalid numeric value '${raw}'`);
    }
    values.push(parsed);
  }
  return values;
}

export function AccessPage() {
  const [data, setData] = useState<AccessPayload | null>(null);
  const [lists, setLists] = useState<Record<string, string>>({});
  const [error, setError] = useState("");
  const [saved, setSaved] = useState("");

  useEffect(() => {
    api
      .getAccessSettings()
      .then((payload) => {
        const typed = payload as AccessPayload;
        setData(typed);
        setLists(
          Object.fromEntries(
            ACCESS_FIELDS.map((field) => [field.key, listValuesToText(typed.lists[field.key])])
          )
        );
      })
      .catch((err: Error) => setError(err.message));
  }, []);

  async function save() {
    if (!data) return;
    try {
      const payload = {
        revision: data.revision,
        updated_at: data.updated_at,
        lists: Object.fromEntries(
          ACCESS_FIELDS.map((field) => [field.key, parseNumberList(lists[field.key] || "")])
        )
      };
      const response = (await api.updateAccessSettings(payload)) as AccessPayload;
      setData(response);
      setLists(
        Object.fromEntries(
          ACCESS_FIELDS.map((field) => [field.key, listValuesToText(response.lists[field.key])])
        )
      );
      setSaved("Access settings saved");
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
          <span className="eyebrow">Access</span>
          <h1>Способы входа и списки доступа</h1>
        </div>
        <button onClick={save} disabled={!data}>
          Save access settings
        </button>
      </div>

      {error ? <div className="error-box">{error}</div> : null}
      {saved ? <div className="ok-box">{saved}</div> : null}
      {!data ? <div className="panel">Loading…</div> : null}

      {data ? (
        <>
          <div className="stats-grid">
            <div className="stat-card">
              <span>Telegram login</span>
              <strong>{data.auth.telegram_enabled ? "ON" : "OFF"}</strong>
            </div>
            <div className="stat-card">
              <span>Local fallback login</span>
              <strong>{data.auth.local_enabled ? "ON" : "OFF"}</strong>
            </div>
          </div>

          <div className="panel">
            <div className="panel-heading">
              <h2>Authentication status</h2>
              <p className="muted">Credentials are managed only through `.env` on the server.</p>
            </div>
            <div className="stats-grid">
              <div className="stat-card">
                <span>Telegram panel auth</span>
                <strong>{data.auth.telegram_enabled ? "Configured" : "Disabled"}</strong>
              </div>
              <div className="stat-card">
                <span>Local fallback auth</span>
                <strong>{data.auth.local_enabled ? "Configured" : "Disabled"}</strong>
              </div>
            </div>
          </div>

          <div className="panel">
            <div className="panel-heading">
              <h2>Access lists</h2>
              <p className="muted">Panel admins and runtime exclusions are managed separately.</p>
            </div>
            <div className="detail-grid">
              {ACCESS_FIELDS.map((field) => (
                <div className="rule-field" key={field.key}>
                  <div className="rule-copy">
                    <strong>{field.label}</strong>
                    <p>{field.description}</p>
                    <span className="muted">{field.recommendation}</span>
                  </div>
                  <textarea
                    className="note-box tall"
                    value={lists[field.key] || ""}
                    onChange={(event) =>
                      setLists((prev) => ({ ...prev, [field.key]: event.target.value }))
                    }
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
