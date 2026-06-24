import { useState } from "react";
import { Loader2 } from "lucide-react";
import { api } from "../api/client";
import { ModalShell } from "./ModalShell";
import { useToast } from "./ToastProvider";

type ManualBanModalProps = {
  open: boolean;
  username: string;
  onClose: () => void;
  onSuccess?: () => void;
};

export function ManualBanModal({ open, username, onClose, onSuccess }: ManualBanModalProps) {
  const { pushToast } = useToast();
  const [minutes, setMinutes] = useState<number>(1440); // Default 24 hours
  const [reason, setReason] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function handleBan() {
    setLoading(true);
    setError("");
    try {
      await api.manualBanUserInBedolaga(username, minutes, reason);
      pushToast("success", `Пользователь @${username} успешно заблокирован в биллинге.`);
      if (onSuccess) {
        onSuccess();
      }
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось заблокировать пользователя");
    } finally {
      setLoading(false);
    }
  }

  const durationOptions = [
    { label: "3 часа", value: 180 },
    { label: "24 часа", value: 1440 },
    { label: "7 дней", value: 10080 },
    { label: "Навсегда", value: 52560000 },
  ];

  return (
    <ModalShell
      open={open}
      title="Полная блокировка в биллинге"
      description="Вы собираетесь полностью заблокировать пользователя в биллинге Bedolaga."
      closeLabel="Отмена"
      onClose={onClose}
      actions={
        <button
          className="button-home"
          style={{ background: "var(--danger, #ef4444)", color: "#fff", border: 0, padding: "0.4rem 1rem", fontSize: "0.85rem", fontWeight: 600, borderRadius: "var(--radius-sm, 6px)", cursor: "pointer" }}
          disabled={loading || !username}
          onClick={handleBan}
        >
          {loading && <Loader2 size={14} className="spinner" style={{ marginRight: "6px", display: "inline-block" }} />}
          Заблокировать
        </button>
      }
    >
      <div className="modules-modal-stack" style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
        {error && (
          <div className="error-box" style={{ color: "var(--danger, #ef4444)", background: "rgba(239, 68, 68, 0.08)", padding: "0.75rem", borderRadius: "8px", border: "1px solid rgba(239, 68, 68, 0.2)" }}>
            {error}
          </div>
        )}

        <div style={{ display: "flex", flexDirection: "column", gap: "0.25rem" }}>
          <span style={{ fontSize: "0.85rem", color: "var(--muted)", fontWeight: 600 }}>Пользователь</span>
          <strong style={{ fontSize: "1rem" }}>@{username}</strong>
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: "0.25rem" }}>
          <label htmlFor="ban-duration" style={{ fontSize: "0.85rem", color: "var(--muted)", fontWeight: 600 }}>
            Срок блокировки
          </label>
          <select
            id="ban-duration"
            value={minutes}
            onChange={(e) => setMinutes(Number(e.target.value))}
            style={{
              width: "100%",
              padding: "0.5rem",
              borderRadius: "var(--radius-sm, 6px)",
              border: "1px solid var(--line)",
              background: "var(--surface)",
              color: "var(--ink)"
            }}
          >
            {durationOptions.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: "0.25rem" }}>
          <label htmlFor="ban-reason" style={{ fontSize: "0.85rem", color: "var(--muted)", fontWeight: 600 }}>
            Причина блокировки
          </label>
          <textarea
            id="ban-reason"
            placeholder="Введите причину..."
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            style={{
              width: "100%",
              minHeight: "80px",
              padding: "0.5rem",
              borderRadius: "var(--radius-sm, 6px)",
              border: "1px solid var(--line)",
              background: "var(--surface)",
              color: "var(--ink)",
              resize: "vertical"
            }}
          />
        </div>
      </div>
    </ModalShell>
  );
}
