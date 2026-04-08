import { InfoTooltip } from "./InfoTooltip";
import { useI18n } from "../localization";

type FieldLabelProps = {
  label: string;
  description?: string;
  recommendation?: string;
};

export function FieldLabel({
  label,
  description,
  recommendation
}: FieldLabelProps) {
  const { t } = useI18n();
  const hint = [description, recommendation].filter(Boolean).join("\n\n");

  return (
    <div className="field-heading">
      <strong>{label}</strong>
      {hint ? <InfoTooltip content={hint} label={t("common.fieldHintLabel", { field: label })} /> : null}
    </div>
  );
}
