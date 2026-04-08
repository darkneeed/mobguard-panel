import { useEffect, useState } from "react";

import { api } from "../api/client";
import { FieldLabel } from "../components/FieldLabel";
import { useI18n } from "../localization";
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

const ACCESS_FIELDS = RULE_LIST_FIELDS.filter((field) => field.sectionKey === "access");

function listValuesToText(values: Array<string | number> | undefined): string {
  return (values || []).map((item) => String(item)).join("\n");
}

export function AccessPage() {
  const { t } = useI18n();
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
      .catch((err: Error) => setError(err.message || t("access.loadFailed")));
  }, [t]);

  function parseNumberList(text: string): number[] {
    const values: number[] = [];
    for (const raw of text.split("\n").map((item) => item.trim()).filter(Boolean)) {
      const parsed = Number(raw);
      if (!Number.isFinite(parsed)) {
        throw new Error(t("access.invalidNumericValue", { value: raw }));
      }
      values.push(parsed);
    }
    return values;
  }

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
      setSaved(t("access.saved"));
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : t("access.saveFailed"));
      setSaved("");
    }
  }

  return (
    <section className="page">
      <div className="page-header">
        <div>
          <span className="eyebrow">{t("access.eyebrow")}</span>
          <h1>{t("access.title")}</h1>
        </div>
        <button onClick={save} disabled={!data}>
          {t("access.save")}
        </button>
      </div>

      {error ? <div className="error-box">{error}</div> : null}
      {saved ? <div className="ok-box">{saved}</div> : null}
      {!data ? <div className="panel">{t("common.loading")}</div> : null}

      {data ? (
        <>
          <div className="stats-grid">
            <div className="stat-card">
              <span>{t("access.cards.telegramLogin")}</span>
              <strong>{data.auth.telegram_enabled ? t("common.on") : t("common.off")}</strong>
            </div>
            <div className="stat-card">
              <span>{t("access.cards.localFallback")}</span>
              <strong>{data.auth.local_enabled ? t("common.on") : t("common.off")}</strong>
            </div>
          </div>

          <div className="panel">
            <div className="panel-heading">
              <h2>{t("access.authStatusTitle")}</h2>
              <p className="muted">{t("access.authStatusDescription")}</p>
            </div>
            <div className="stats-grid">
              <div className="stat-card">
                <span>{t("access.authCards.telegramPanel")}</span>
                <strong>{data.auth.telegram_enabled ? t("common.configured") : t("common.disabled")}</strong>
              </div>
              <div className="stat-card">
                <span>{t("access.authCards.localFallback")}</span>
                <strong>{data.auth.local_enabled ? t("common.configured") : t("common.disabled")}</strong>
              </div>
            </div>
          </div>

          <div className="panel">
            <div className="panel-heading">
              <h2>{t("access.listsTitle")}</h2>
              <p className="muted">{t("access.listsDescription")}</p>
            </div>
            <div className="detail-grid">
              {ACCESS_FIELDS.map((field) => (
                <div className="rule-field" key={field.key}>
                  <FieldLabel
                    label={t(`rulesMeta.listFields.${field.key}.label`)}
                    description={t(`rulesMeta.listFields.${field.key}.description`)}
                    recommendation={t(`rulesMeta.listFields.${field.key}.recommendation`)}
                  />
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
