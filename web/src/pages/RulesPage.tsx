import { useEffect, useState } from "react";

import { api, RulesState } from "../api/client";
import {
  RULE_LIST_FIELDS,
  RULE_SETTING_FIELDS,
  RuleListFieldMeta,
  RuleSettingFieldMeta,
  RuleSettingValue,
  RulesDraft
} from "../rulesMeta";

const LIST_SECTIONS = Array.from(new Set(RULE_LIST_FIELDS.map((field) => field.section)));
const SETTING_SECTIONS = Array.from(new Set(RULE_SETTING_FIELDS.map((field) => field.section)));

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function normalizeRulesDraft(source: Record<string, unknown>): RulesDraft {
  const draft: RulesDraft = { settings: {} };
  const settings = isRecord(source.settings) ? source.settings : {};

  for (const field of RULE_LIST_FIELDS) {
    const rawValue = source[field.key];
    draft[field.key] = Array.isArray(rawValue) ? rawValue.map((item) => String(item)) : [];
  }

  for (const field of RULE_SETTING_FIELDS) {
    const rawValue = settings[field.key];
    if (
      typeof rawValue === "string" ||
      typeof rawValue === "number" ||
      typeof rawValue === "boolean"
    ) {
      draft.settings![field.key] = rawValue;
    }
  }

  return draft;
}

function listValuesToText(values: Array<string | number> | undefined): string {
  return (values || []).map((item) => String(item)).join("\n");
}

function parseListText(text: string): string[] {
  return text
    .split("\n")
    .map((item) => item.trim())
    .filter(Boolean);
}

function serializeListField(meta: RuleListFieldMeta, values: Array<string | number> | undefined) {
  const rawValues = (values || []).map((item) => String(item).trim()).filter(Boolean);
  if (meta.itemType === "string") {
    return rawValues;
  }

  const serialized: number[] = [];
  for (const item of rawValues) {
    const parsed = Number(item);
    if (!Number.isFinite(parsed)) {
      throw new Error(`${meta.label}: invalid number '${item}'`);
    }
    serialized.push(parsed);
  }
  return serialized;
}

function serializeSettingField(meta: RuleSettingFieldMeta, value: RuleSettingValue) {
  if (meta.inputType === "boolean") {
    return Boolean(value);
  }
  if (meta.inputType === "text") {
    return String(value ?? "").trim();
  }

  const parsed = Number(value);
  if (!Number.isFinite(parsed)) {
    throw new Error(`${meta.label}: invalid number`);
  }
  return parsed;
}

function getSettingInputValue(meta: RuleSettingFieldMeta, value: RuleSettingValue): string {
  if (meta.inputType === "boolean") {
    return value === true ? "true" : "false";
  }
  return value === undefined || value === null ? "" : String(value);
}

export function RulesPage() {
  const [state, setState] = useState<RulesState | null>(null);
  const [draft, setDraft] = useState<RulesDraft | null>(null);
  const [savedDraft, setSavedDraft] = useState<RulesDraft | null>(null);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState("");

  useEffect(() => {
    api
      .getRules()
      .then((payload) => {
        const normalized = normalizeRulesDraft(payload.rules);
        setState(payload);
        setDraft(normalized);
        setSavedDraft(normalized);
      })
      .catch((err: Error) => setError(err.message));
  }, []);

  const dirty = JSON.stringify(draft) !== JSON.stringify(savedDraft);

  async function save() {
    if (!draft || !state) return;
    try {
      const payload: Record<string, unknown> = { settings: {} };

      for (const field of RULE_LIST_FIELDS) {
        payload[field.key] = serializeListField(field, draft[field.key]);
      }

      for (const field of RULE_SETTING_FIELDS) {
        payload.settings = {
          ...(payload.settings as Record<string, unknown>),
          [field.key]: serializeSettingField(field, draft.settings?.[field.key])
        };
      }

      const updated = await api.updateRules({
        rules: payload,
        revision: state.revision,
        updated_at: state.updated_at
      });
      const normalized = normalizeRulesDraft(updated.rules);
      setState(updated);
      setDraft(normalized);
      setSavedDraft(normalized);
      setError("");
      setSaved("Rules updated");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed");
      setSaved("");
    }
  }

  function updateListField(meta: RuleListFieldMeta, text: string) {
    setDraft((prev) => ({
      ...(prev || {}),
      [meta.key]: parseListText(text),
      settings: prev?.settings || {}
    }));
    setSaved("");
  }

  function updateSettingField(meta: RuleSettingFieldMeta, value: string) {
    setDraft((prev) => ({
      ...(prev || {}),
      settings: {
        ...(prev?.settings || {}),
        [meta.key]: meta.inputType === "boolean" ? value === "true" : value
      }
    }));
    setSaved("");
  }

  return (
    <section className="page">
      <div className="page-header">
        <div>
          <span className="eyebrow">Live Rules</span>
          <h1>Понятные live-настройки без редактирования сырых ключей</h1>
        </div>
        <div className="action-row">
          <span className={dirty ? "tag review-only" : "tag severity-low"}>
            {dirty ? "unsaved changes" : "saved"}
          </span>
          <button disabled={!dirty} onClick={save}>
            Save rules
          </button>
        </div>
      </div>
      {error ? <div className="error-box">{error}</div> : null}
      {saved ? <div className="ok-box">{saved}</div> : null}
      {state ? (
        <div className="panel queue-footer">
          <span>Revision {state.revision}</span>
          <span>Updated at {state.updated_at || "n/a"}</span>
          <span>Updated by {state.updated_by || "n/a"}</span>
        </div>
      ) : null}
      {!draft ? <div className="panel">Loading…</div> : null}

      {draft ? (
        <div className="page">
          {LIST_SECTIONS.map((section) => (
            <div className="panel" key={section}>
              <div className="panel-heading">
                <h2>{section}</h2>
                <p className="muted">Editable list-based rules.</p>
              </div>
              <div className="detail-grid">
                {RULE_LIST_FIELDS.filter((field) => field.section === section).map((field) => (
                  <div className="rule-field" key={field.key}>
                    <div className="rule-copy">
                      <strong>{field.label}</strong>
                      <p>{field.description}</p>
                      <span className="muted">{field.recommendation}</span>
                    </div>
                    <textarea
                      className="note-box tall"
                      value={listValuesToText(draft[field.key])}
                      onChange={(event) => updateListField(field, event.target.value)}
                    />
                  </div>
                ))}
              </div>
            </div>
          ))}

          {SETTING_SECTIONS.map((section) => (
            <div className="panel" key={section}>
              <div className="panel-heading">
                <h2>{section}</h2>
                <p className="muted">Canonical editable settings only.</p>
              </div>
              <div className="form-grid">
                {RULE_SETTING_FIELDS.filter((field) => field.section === section).map((field) => (
                  <div className="rule-field" key={field.key}>
                    <div className="rule-copy">
                      <strong>{field.label}</strong>
                      <p>{field.description}</p>
                      <span className="muted">{field.recommendation}</span>
                    </div>
                    {field.inputType === "boolean" ? (
                      <select
                        value={getSettingInputValue(field, draft.settings?.[field.key])}
                        onChange={(event) => updateSettingField(field, event.target.value)}
                      >
                        <option value="true">true</option>
                        <option value="false">false</option>
                      </select>
                    ) : (
                      <input
                        type={field.inputType === "number" ? "number" : "text"}
                        step={field.step}
                        value={getSettingInputValue(field, draft.settings?.[field.key])}
                        onChange={(event) => updateSettingField(field, event.target.value)}
                      />
                    )}
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      ) : null}
    </section>
  );
}
