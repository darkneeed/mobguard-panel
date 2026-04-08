import type { Language } from "../localization";

function pad(value: number): string {
  return String(value).padStart(2, "0");
}

export function formatDisplayDateTime(
  value: string | null | undefined,
  emptyFallback = "N/A",
  language: Language = "ru"
): string {
  if (!value) {
    return emptyFallback;
  }

  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }

  const day = pad(parsed.getDate());
  const month = pad(parsed.getMonth() + 1);
  const time = `${pad(parsed.getHours())}:${pad(parsed.getMinutes())}`;

  if (language === "en") {
    return `${day}/${month} ${time}`;
  }

  return `${day}.${month} ${time}`;
}
