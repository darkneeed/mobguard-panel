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
    <div className="panel bedolaga-metric-card">
      <div className="bedolaga-metric-card-head">
        <span className="bedolaga-metric-card-icon">{icon}</span>
        <h2 className="bedolaga-metric-card-title">{title}</h2>
      </div>
      <div className="bedolaga-metric-card-grid">
        {items.map(({ label, value }) => (
          <div key={label} className="bedolaga-metric-card-item">
            <span className="bedolaga-metric-card-value">
              {typeof value === "number" ? value.toLocaleString("ru-RU") : String(value)}
            </span>
            <span className="bedolaga-metric-card-label">{label}</span>
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
          <h1>Bedolaga</h1>
          <p className="page-lede">
            Мониторинг Telegram-бота и статистика пользователей
          </p>
        </div>
        <div className="bedolaga-header-controls">
          {data && (
            <span className={`bedolaga-status-pill ${data.enabled ? "status-connected" : "status-disconnected"}`}>
              <span className="status-led" />
              {data.enabled ? "Подключено" : "Не подключено"}
            </span>
          )}
          <button
            className="ghost small-button"
            onClick={() => setRefreshAt(Date.now())}
            disabled={loading}
          >
            <span style={{ display: "inline-block", transform: loading ? "rotate(180deg)" : "none", transition: "transform 0.4s" }}>
              ↻
            </span>{" "}
            Обновить
          </button>
        </div>
      </div>

      {/* Connection info */}
      {data?.base_url && (
        <div className="bedolaga-api-box">
          <span className="muted">API:</span>
          <code>{data.base_url}</code>
        </div>
      )}

      {/* Errors */}
      {data?.errors && data.errors.length > 0 && (
        <div className="bedolaga-errors-box">
          <strong>⚠ Ошибки подключения</strong>
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
          <div className="bedolaga-table-header">
            <h2>Последние пользователи</h2>
            <span className="bedolaga-table-count-badge">{users.length}</span>
          </div>
          <div className="bedolaga-table-container">
            <table className="bedolaga-table">
              <thead>
                <tr>
                  {["Пользователь", "Статус", "Подписка", "Группа", "Баланс", "Зарегистрирован"].map((h) => (
                    <th key={h} className="bedolaga-th">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {users.map((u) => (
                  <tr key={u.id} className="bedolaga-tr">
                    <td className="bedolaga-td">
                      <div className="username-box">{getUserName(u)}</div>
                      {u.telegram_id && (
                        <div className="telegram-box">tg: {u.telegram_id}</div>
                      )}
                    </td>
                    <td className="bedolaga-td">
                      <span
                        className="bedolaga-user-status-pill"
                        style={{ "--status-color": statusColor(u.status) } as React.CSSProperties}
                      >
                        {statusLabel(u.status)}
                      </span>
                    </td>
                    <td className="bedolaga-td" style={{ color: "var(--muted)", fontSize: "0.82rem" }}>
                      {u.subscription?.actual_status
                        ? statusLabel(u.subscription.actual_status)
                        : u.subscription?.status
                          ? statusLabel(u.subscription.status)
                          : "—"}
                    </td>
                    <td className="bedolaga-td" style={{ color: "var(--muted)", fontSize: "0.82rem" }}>
                      {u.promo_group?.name ?? "—"}
                    </td>
                    <td className="bedolaga-td" style={{ fontVariantNumeric: "tabular-nums" }}>
                      {typeof u.balance_rubles === "number"
                        ? `${u.balance_rubles.toFixed(2)} ₽`
                        : "—"}
                    </td>
                    <td className="bedolaga-td" style={{ color: "var(--muted)", fontSize: "0.82rem", whiteSpace: "nowrap" }}>
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
        <div className="panel bedolaga-empty-state">
          <div className="bedolaga-empty-state-icon">🔌</div>
          <h2>Bedolaga не настроен</h2>
          <p className="muted">
            Перейдите в <strong>Настройки → Доступ</strong> и укажите URL и токен Bedolaga API
          </p>
        </div>
      )}
    </div>
  );
}
