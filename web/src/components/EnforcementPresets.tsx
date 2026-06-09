import { Shield, ShieldAlert, ShieldX } from "lucide-react";

type EnforcementPresetsProps = {
  onApply: (values: Record<string, string>) => void;
};

export function EnforcementPresets({ onApply }: EnforcementPresetsProps) {
  const presets = [
    {
      name: "🕊 Мягко",
      icon: <Shield size={16} style={{ color: "var(--success, #10b981)" }} />,
      description: "Только предупреждения (Warning-only), 5 предупреждений перед блокировкой, блокировок нет",
      values: {
        warnings_before_ban: "5",
        warning_timeout_seconds: "900",
        ban_durations_minutes: "",
        warning_only_mode: "true"
      }
    },
    {
      name: "📋 Стандарт",
      icon: <ShieldAlert size={16} style={{ color: "var(--warning, #f59e0b)" }} />,
      description: "Режим блокировок активен, 5 предупреждений, прогрессивный бан (15м, 30м, 1ч, 2ч, 3ч, 24ч)",
      values: {
        warnings_before_ban: "5",
        warning_timeout_seconds: "900",
        ban_durations_minutes: "15\n30\n60\n120\n180\n1440",
        warning_only_mode: "false"
      }
    },
    {
      name: "🔒 Строго",
      icon: <ShieldX size={16} style={{ color: "var(--danger, #ef4444)" }} />,
      description: "Режим блокировок активен, только 3 предупреждения, жесткий бан (30м, 1ч, 2ч, 3ч, 24ч)",
      values: {
        warnings_before_ban: "3",
        warning_timeout_seconds: "900",
        ban_durations_minutes: "30\n60\n120\n180\n1440",
        warning_only_mode: "false"
      }
    }
  ];

  return (
    <div className="enforcement-presets" style={{ marginBottom: "1.5rem" }}>
      <span style={{
        fontSize: "0.75rem",
        fontWeight: 600,
        textTransform: "uppercase",
        letterSpacing: "0.05em",
        color: "var(--muted)",
        display: "block",
        marginBottom: "0.5rem"
      }}>
        Быстрые пресеты режима:
      </span>
      <div style={{ display: "flex", gap: "0.75rem", flexWrap: "wrap" }}>
        {presets.map((preset) => (
          <button
            key={preset.name}
            type="button"
            className="button secondary"
            onClick={() => onApply(preset.values)}
            title={preset.description}
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: "0.5rem",
              padding: "0.5rem 1rem",
              borderRadius: "8px",
              cursor: "pointer",
              transition: "all 0.2s ease"
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.transform = "translateY(-1px)";
              e.currentTarget.style.boxShadow = "0 4px 12px rgba(0,0,0,0.15)";
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.transform = "none";
              e.currentTarget.style.boxShadow = "none";
            }}
          >
            {preset.icon}
            <span>{preset.name}</span>
          </button>
        ))}
      </div>
    </div>
  );
}
