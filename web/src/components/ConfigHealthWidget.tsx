import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { CheckCircle2, AlertTriangle, XCircle, ArrowRight, ShieldCheck } from "lucide-react";
import { api, ConfigHealthCheck } from "../api/client";

export function ConfigHealthWidget() {
  const navigate = useNavigate();
  const [checks, setChecks] = useState<ConfigHealthCheck[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    async function load() {
      try {
        const response = await api.getConfigHealth();
        if (active) {
          setChecks(response.checks || []);
          setError("");
        }
      } catch (err) {
        if (active) {
          setError(err instanceof Error ? err.message : "Не удалось загрузить состояние конфигурации");
        }
      } finally {
        if (active) {
          setLoading(false);
        }
      }
    }
    load();
    return () => {
      active = false;
    };
  }, []);

  if (loading) {
    return (
      <div className="panel" style={{ marginBottom: "1.5rem" }}>
        <div className="panel-heading">
          <h2>Состояние конфигурации</h2>
          <p className="muted">Проверка ключевых параметров MobGuard...</p>
        </div>
        <div className="loading-stack" style={{ padding: "1rem 0" }}>
          <span className="skeleton-line long" />
          <span className="skeleton-line medium" />
          <span className="skeleton-line short" />
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="panel" style={{ marginBottom: "1.5rem" }}>
        <div className="panel-heading">
          <h2>Состояние конфигурации</h2>
        </div>
        <div className="error-box" style={{ margin: "1rem 0" }}>{error}</div>
      </div>
    );
  }

  const getStatusIcon = (status: "ok" | "warn" | "error") => {
    switch (status) {
      case "ok":
        return <CheckCircle2 size={18} className="text-success" style={{ color: "var(--success, #10b981)" }} />;
      case "warn":
        return <AlertTriangle size={18} className="text-warning" style={{ color: "var(--warning, #f59e0b)" }} />;
      case "error":
        return <XCircle size={18} className="text-danger" style={{ color: "var(--danger, #ef4444)" }} />;
    }
  };

  const getStatusClass = (status: "ok" | "warn" | "error") => {
    switch (status) {
      case "ok":
        return "health-ok";
      case "warn":
        return "health-warn";
      case "error":
        return "health-error";
    }
  };

  return (
    <div className="panel" style={{ marginBottom: "1.5rem" }}>
      <div className="panel-heading" style={{ display: "flex", flexDirection: "row", alignItems: "center", gap: "0.75rem" }}>
        <ShieldCheck size={20} style={{ color: "var(--accent)", flexShrink: 0 }} />
        <div>
          <h2>Состояние конфигурации</h2>
          <p className="muted">Параметры безопасности, списков и интеграций.</p>
        </div>
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem", marginTop: "1rem" }}>
        {checks.map((check) => (
          <div
            key={check.key}
            onClick={() => navigate(check.link)}
            className={`record-item ${getStatusClass(check.status)}`}
            style={{
              display: "flex",
              flexDirection: "row",
              justifyContent: "space-between",
              alignItems: "center",
              padding: "0.75rem 1rem",
              borderRadius: "6px",
              border: "1px solid var(--line)",
              cursor: "pointer",
              transition: "all 0.2s ease-in-out",
              backgroundColor: "var(--surface-hover, rgba(255,255,255,0.02))"
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.borderColor = "var(--accent)";
              e.currentTarget.style.transform = "translateX(4px)";
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.borderColor = "var(--line)";
              e.currentTarget.style.transform = "none";
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
              {getStatusIcon(check.status)}
              <div>
                <strong style={{ fontSize: "0.9rem", color: "var(--text)" }}>{check.label}</strong>
                <div style={{ fontSize: "0.8rem", color: "var(--muted)" }}>{check.detail}</div>
              </div>
            </div>
            <ArrowRight size={16} style={{ color: "var(--muted)" }} />
          </div>
        ))}
      </div>
    </div>
  );
}
