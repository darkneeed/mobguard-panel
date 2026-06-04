import { useCallback, useEffect, useState } from "react";

import { api, BedolagaOverviewResponse, BedolagaUser } from "../api/client";
import { useI18n } from "../localization";

function statusColor(status: string): string {
  switch (status?.toLowerCase()) {
    case "active":
      return "var(--green, #22c55e)";
    case "blocked":
      return "var(--red, #ef4444)";
    case "inactive":
    case "expired":
      return "var(--muted)";
    default:
      return "var(--accent)";
  }
}

function statusLabel(status: string): string {
  switch (status?.toLowerCase()) {
    case "active":
      return "Активен";
    case "blocked":
      return "Заблокирован";
    case "inactive":
      return "Неактивен";
    case "expired":
      return "Истёк";
    default:
      return status || "—";
  }
}

function formatDate(iso?: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString("ru-RU", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  });
}

function getUserName(u: BedolagaUser): string {
  if (u.first_name || u.last_name) {
    return [u.first_name, u.last_name].filter(Boolean).join(" ");
  }
  if (u.username) return `@${u.username}`;
  if (u.email) return u.email;
  return `ID ${u.id}`;
}

function getUsers(clients: BedolagaOverviewResponse["clients"]): BedolagaUser[] {
  if (!clients) return [];
  if (Array.isArray(clients)) return clients as BedolagaUser[];
  if ("items" in clients && Array.isArray(clients.items)) return clients.items;
  return [];
}

type MetricCardProps = {
  title: string;
  icon: string;
  data?: Record<string, unknown>;
};

function MetricCard({ title, icon, data }: MetricCardProps) {
  if (!data || Object.keys(data).length === 0) return null;

  const items: Array<{ label: string; value: unknown }> = [];
  const labelMap: Record<string, string> = {
    total: "Всего",
    active: "Активных",
    blocked: "Заблокировано",
    new_today: "Новых сегодня",
    new_this_month: "За месяц",
    trial: "Пробных",
    paid: "Платных",
    expired: "Истекло",
    open: "Открытых",
    closed: "Закрытых",
    total_rubles: "Оборот (руб.)",
    today_rubles: "Сегодня (руб.)",
    this_month_rubles: "За месяц (руб.)",
    successful: "Успешных",
    failed: "Неуспешных",
  };

  for (const [key, val] of Object.entries(data)) {
    if (typeof val === "number" || typeof val === "string") {
      items.push({ label: labelMap[key] ?? key, value: val });
    }
  }

  return (
    <div className="panel" style={{ display: "flex", flexDirection: "column", gap: "0.85rem" }}>
      <div style={{ display: "flex", alignItems: "center", gap: "0.6rem" }}>
        <span style={{ fontSize: "1.4rem" }}>{icon}</span>
        <h2 style={{ margin: 0, fontSize: "1rem", fontFamily: "'Space Grotesk', sans-serif" }}>
          {title}
        </h2>
      </div>
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(110px, 1fr))",
          gap: "0.65rem",
        }}
      >
        {items.map(({ label, value }) => (
          <div
            key={label}
            style={{
              display: "flex",
              flexDirection: "column",
              gap: "0.15rem",
              padding: "0.65rem 0.85rem",
              borderRadius: "14px",
              background: "var(--surface-soft, rgba(0,0,0,0.04))",
              border: "1px solid var(--line)",
            }}
          >
            <span style={{ fontSize: "1.25rem", fontWeight: 700, fontFamily: "'Space Grotesk', sans-serif" }}>
              {typeof value === "number" ? value.toLocaleString("ru-RU") : String(value)}
            </span>
            <span style={{ fontSize: "0.75rem", color: "var(--muted)", lineHeight: 1.3 }}>{label}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

export function BedolagaPage() {
  const { t } = useI18n();
  const [data, setData] = useState<BedolagaOverviewResponse | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [refreshAt, setRefreshAt] = useState(0);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const payload = await api.getBedolagaOverview();
      setData(payload);
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось загрузить данные Bedolaga");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load, refreshAt]);

  const users = data ? getUsers(data.clients) : [];
  const metrics = data?.metrics ?? {};

  const metricSections: Array<{ key: string; title: string; icon: string }> = [
    { key: "users", title: "Пользователи", icon: "👥" },
    { key: "subscriptions", title: "Подписки", icon: "📋" },
    { key: "support", title: "Поддержка", icon: "🎫" },
    { key: "payments", title: "Платежи", icon: "💳" },
  ];

  return (
    <div className="page">
      {/* Header */}
      <div className="page-header">
        <div>
          <h1 style={{ margin: 0, fontFamily: "'Space Grotesk', sans-serif" }}>Bedolaga</h1>
          <p className="page-lede" style={{ marginTop: "0.4rem" }}>
            Мониторинг Telegram-бота и статистика пользователей
          </p>
        </div>
        <div style={{ display: "flex", gap: "0.65rem", alignItems: "center" }}>
          {data && (
            <span
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "0.45rem",
                padding: "0.4rem 0.9rem",
                borderRadius: "999px",
                fontSize: "0.82rem",
                fontWeight: 600,
                background: data.enabled
                  ? "rgba(34,197,94,0.12)"
                  : "rgba(239,68,68,0.12)",
                color: data.enabled ? "#22c55e" : "#ef4444",
                border: `1px solid ${data.enabled ? "rgba(34,197,94,0.3)" : "rgba(239,68,68,0.3)"}`,
              }}
            >
              <span
                style={{
                  width: 7,
                  height: 7,
                  borderRadius: "50%",
                  background: data.enabled ? "#22c55e" : "#ef4444",
                  display: "inline-block",
                }}
              />
              {data.enabled ? "Подключено" : "Не подключено"}
            </span>
          )}
          <button
            className="ghost small-button"
            onClick={() => setRefreshAt(Date.now())}
            disabled={loading}
            style={{ display: "flex", alignItems: "center", gap: "0.4rem" }}
          >
            <span style={{ display: "inline-block", transform: loading ? "rotate(180deg)" : "none", transition: "transform 0.4s" }}>
              ↻
            </span>
            Обновить
          </button>
        </div>
      </div>

      {/* Connection info */}
      {data?.base_url && (
        <div
          style={{
            padding: "0.75rem 1rem",
            borderRadius: "14px",
            border: "1px solid var(--line)",
            background: "var(--surface-soft)",
            display: "flex",
            alignItems: "center",
            gap: "0.65rem",
            fontSize: "0.88rem",
          }}
        >
          <span style={{ color: "var(--muted)" }}>API:</span>
          <code style={{ fontFamily: "monospace", color: "var(--accent)" }}>{data.base_url}</code>
        </div>
      )}

      {/* Errors */}
      {data?.errors && data.errors.length > 0 && (
        <div
          style={{
            padding: "1rem",
            borderRadius: "16px",
            border: "1px solid rgba(239,68,68,0.3)",
            background: "rgba(239,68,68,0.07)",
            display: "flex",
            flexDirection: "column",
            gap: "0.45rem",
          }}
        >
          <strong style={{ color: "#ef4444", fontSize: "0.9rem" }}>⚠ Ошибки подключения</strong>
          {data.errors.map((e, i) => (
            <p key={i} style={{ margin: 0, fontSize: "0.85rem", color: "var(--muted)" }}>{e}</p>
          ))}
        </div>
      )}

      {/* Loading */}
      {loading && !data && (
        <div className="panel" style={{ textAlign: "center", padding: "3rem" }}>
          <p className="muted">{t("common.loading")}</p>
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="panel" style={{ borderColor: "rgba(239,68,68,0.3)" }}>
          <p style={{ color: "#ef4444", margin: 0 }}>{error}</p>
        </div>
      )}

      {/* Metrics grid */}
      {data?.enabled && (
        <div className="dashboard-grid">
          {metricSections.map(({ key, title, icon }) => {
            const sectionData = metrics[key] as Record<string, unknown> | undefined;
            return sectionData && Object.keys(sectionData).length > 0 ? (
              <MetricCard key={key} title={title} icon={icon} data={sectionData} />
            ) : null;
          })}
        </div>
      )}

      {/* Users table */}
      {data?.enabled && users.length > 0 && (
        <div className="panel" style={{ overflow: "hidden" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem" }}>
            <h2 style={{ margin: 0, fontFamily: "'Space Grotesk', sans-serif", fontSize: "1rem" }}>
              Последние пользователи
            </h2>
            <span
              style={{
                padding: "0.25rem 0.65rem",
                borderRadius: "999px",
                background: "var(--accent-soft)",
                color: "var(--accent)",
                fontSize: "0.8rem",
                fontWeight: 600,
              }}
            >
              {users.length}
            </span>
          </div>
          <div style={{ overflowX: "auto" }}>
            <table
              style={{
                width: "100%",
                borderCollapse: "collapse",
                fontSize: "0.875rem",
              }}
            >
              <thead>
                <tr>
                  {["Пользователь", "Статус", "Подписка", "Группа", "Баланс", "Зарегистрирован"].map((h) => (
                    <th
                      key={h}
                      style={{
                        textAlign: "left",
                        padding: "0.6rem 0.85rem",
                        color: "var(--muted)",
                        fontWeight: 500,
                        fontSize: "0.8rem",
                        borderBottom: "1px solid var(--line)",
                        whiteSpace: "nowrap",
                      }}
                    >
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {users.map((u) => (
                  <tr
                    key={u.id}
                    style={{ borderBottom: "1px solid var(--line)" }}
                    onMouseEnter={(e) => {
                      (e.currentTarget as HTMLElement).style.background = "var(--surface-soft)";
                    }}
                    onMouseLeave={(e) => {
                      (e.currentTarget as HTMLElement).style.background = "transparent";
                    }}
                  >
                    <td style={{ padding: "0.65rem 0.85rem" }}>
                      <div style={{ fontWeight: 500 }}>{getUserName(u)}</div>
                      {u.telegram_id && (
                        <div style={{ fontSize: "0.75rem", color: "var(--muted)" }}>
                          tg: {u.telegram_id}
                        </div>
                      )}
                    </td>
                    <td style={{ padding: "0.65rem 0.85rem" }}>
                      <span
                        style={{
                          display: "inline-flex",
                          alignItems: "center",
                          gap: "0.35rem",
                          padding: "0.25rem 0.65rem",
                          borderRadius: "999px",
                          fontSize: "0.78rem",
                          fontWeight: 600,
                          background: `${statusColor(u.status)}18`,
                          color: statusColor(u.status),
                          border: `1px solid ${statusColor(u.status)}40`,
                        }}
                      >
                        {statusLabel(u.status)}
                      </span>
                    </td>
                    <td style={{ padding: "0.65rem 0.85rem", color: "var(--muted)", fontSize: "0.82rem" }}>
                      {u.subscription?.actual_status
                        ? statusLabel(u.subscription.actual_status)
                        : u.subscription?.status
                          ? statusLabel(u.subscription.status)
                          : "—"}
                    </td>
                    <td style={{ padding: "0.65rem 0.85rem", color: "var(--muted)", fontSize: "0.82rem" }}>
                      {u.promo_group?.name ?? "—"}
                    </td>
                    <td style={{ padding: "0.65rem 0.85rem", fontVariantNumeric: "tabular-nums" }}>
                      {typeof u.balance_rubles === "number"
                        ? `${u.balance_rubles.toFixed(2)} ₽`
                        : "—"}
                    </td>
                    <td style={{ padding: "0.65rem 0.85rem", color: "var(--muted)", fontSize: "0.82rem", whiteSpace: "nowrap" }}>
                      {formatDate(u.created_at)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Not configured state */}
      {data && !data.enabled && (
        <div className="panel" style={{ textAlign: "center", padding: "3rem 2rem" }}>
          <div style={{ fontSize: "3rem", marginBottom: "1rem" }}>🔌</div>
          <h2 style={{ margin: "0 0 0.5rem", fontFamily: "'Space Grotesk', sans-serif" }}>
            Bedolaga не настроен
          </h2>
          <p className="muted" style={{ maxWidth: "36rem", margin: "0 auto" }}>
            Перейдите в <strong>Настройки → Доступ</strong> и укажите URL и токен Bedolaga API
          </p>
        </div>
      )}
    </div>
  );
}
