import { MouseEvent, ReactNode, useEffect } from "react";
import { createPortal } from "react-dom";

type ModalShellProps = {
  open: boolean;
  title: string;
  description?: string;
  closeLabel: string;
  actions?: ReactNode;
  onClose: () => void;
  children: ReactNode;
};

export function ModalShell({
  open,
  title,
  description,
  closeLabel,
  actions,
  onClose,
  children
}: ModalShellProps) {
  useEffect(() => {
    if (!open) return undefined;

    function handleKeydown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        onClose();
      }
    }

    document.body.classList.add("modal-open");
    window.addEventListener("keydown", handleKeydown);
    return () => {
      document.body.classList.remove("modal-open");
      window.removeEventListener("keydown", handleKeydown);
    };
  }, [open, onClose]);

  if (!open || typeof document === "undefined") {
    return null;
  }

  function handleOverlayClick(event: MouseEvent<HTMLDivElement>) {
    if (event.target === event.currentTarget) {
      onClose();
    }
  }

  return createPortal(
    <div className="modal-overlay" onClick={handleOverlayClick}>
      <div className="modal-shell" role="dialog" aria-modal="true" aria-labelledby="modal-shell-title">
        <div className="modal-shell-header">
          <div className="modal-shell-copy">
            <h2 id="modal-shell-title">{title}</h2>
            {description ? <p className="muted">{description}</p> : null}
          </div>
          <div className="modal-shell-header-actions">
            {actions}
            <button className="ghost modal-close" type="button" aria-label={closeLabel} onClick={onClose}>
              {closeLabel}
            </button>
          </div>
        </div>
        <div className="modal-shell-body">{children}</div>
      </div>
    </div>,
    document.body
  );
}
