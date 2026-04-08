import { type ReactNode, useId, useState } from "react";

import { useI18n } from "../localization";

type InfoTooltipProps = {
  content: ReactNode;
  label?: string;
};

export function InfoTooltip({
  content,
  label
}: InfoTooltipProps) {
  const { t } = useI18n();
  const tooltipId = useId();
  const [open, setOpen] = useState(false);

  return (
    <span className={`info-tooltip${open ? " is-open" : ""}`}>
      <button
        type="button"
        className="info-button"
        aria-label={label || t("common.showHint")}
        aria-describedby={tooltipId}
        aria-expanded={open}
        onClick={() => setOpen((prev) => !prev)}
        onBlur={() => setOpen(false)}
        onMouseLeave={() => setOpen(false)}
      >
        i
      </button>
      <span id={tooltipId} role="tooltip" className="info-tooltip-bubble">
        {content}
      </span>
    </span>
  );
}
