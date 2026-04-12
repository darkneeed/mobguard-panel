import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

function loadDictionary(filePath) {
  const source = fs.readFileSync(filePath, "utf8");
  const match = source.match(/export const \w+Dictionary: TranslationDictionary = (\{[\s\S]*\});\s*$/);
  if (!match) {
    throw new Error(`Failed to parse dictionary: ${filePath}`);
  }
  return Function(`return (${match[1]});`)();
}

function collectKeys(value, prefix = "") {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return [prefix].filter(Boolean);
  }
  return Object.entries(value).flatMap(([key, nested]) =>
    collectKeys(nested, prefix ? `${prefix}.${key}` : key)
  );
}

function walkFiles(targetPath) {
  const stats = fs.statSync(targetPath);
  if (stats.isFile()) {
    return [targetPath];
  }

  return fs.readdirSync(targetPath).flatMap((entry) =>
    walkFiles(path.join(targetPath, entry))
  );
}

function shouldScanFile(filePath) {
  return (
    filePath.endsWith(".tsx") &&
    !filePath.endsWith(".test.tsx") &&
    !filePath.includes(`${path.sep}localization${path.sep}`)
  );
}

const rawTextAllowlist = [
  /^https?:\/\/example\.com\/logo\.png$/,
];

function isAllowedRawText(text) {
  return rawTextAllowlist.some((pattern) => pattern.test(text));
}

function isCodeLikeRawText(text) {
  return /Promise|\.join\(|=>|\)\s*:\s*|^\d+\s*\?|^\?\s|:\s*t\(/.test(text);
}

function collectRawUiTextIssues(filePath) {
  const source = fs.readFileSync(filePath, "utf8");
  const lines = source.split(/\r?\n/);
  const issues = [];
  const jsxTextPattern = />\s*([^<{>=]*[A-Za-zА-Яа-я][^<{>=]*)\s*</g;
  const jsxInterpolatedPattern = />\s*([^<{>=]*[A-Za-zА-Яа-я][^<{>=]*)\{[^}]+\}([^<>=]*)\s*</g;
  const visiblePropPattern = /\b(?:placeholder|title|aria-label)\s*=\s*"([^"]*[A-Za-zА-Яа-я][^"]*)"/g;

  lines.forEach((line, index) => {
    const hasJsxTag = /<[^>]+>.*<\/[A-Za-z]/.test(line);
    const patterns = hasJsxTag
      ? [jsxTextPattern, jsxInterpolatedPattern, visiblePropPattern]
      : [visiblePropPattern];
    for (const pattern of patterns) {
      for (const match of line.matchAll(pattern)) {
        const rawText = match
          .slice(1)
          .filter(Boolean)
          .join("")
          .trim();
        if (!rawText || isAllowedRawText(rawText) || isCodeLikeRawText(rawText)) {
          continue;
        }
        issues.push(`${filePath}:${index + 1}: ${rawText}`);
      }
    }
  });

  return issues;
}

const ru = loadDictionary(path.join(root, "src", "localization", "dictionaries", "ru.ts"));
const en = loadDictionary(path.join(root, "src", "localization", "dictionaries", "en.ts"));

const ruKeys = new Set(collectKeys(ru));
const enKeys = new Set(collectKeys(en));

const onlyRu = [...ruKeys].filter((key) => !enKeys.has(key));
const onlyEn = [...enKeys].filter((key) => !ruKeys.has(key));

if (onlyRu.length || onlyEn.length) {
  if (onlyRu.length) {
    console.error("Missing in en:");
    console.error(onlyRu.join("\n"));
  }
  if (onlyEn.length) {
    console.error("Missing in ru:");
    console.error(onlyEn.join("\n"));
  }
  process.exit(1);
}

const scanTargets = [
  ...walkFiles(path.join(root, "src", "components")),
  ...walkFiles(path.join(root, "src", "pages")),
  path.join(root, "src", "App.tsx"),
  path.join(root, "src", "app", "AppRouter.tsx"),
].filter(shouldScanFile);

const rawUiIssues = scanTargets.flatMap(collectRawUiTextIssues);

if (rawUiIssues.length) {
  console.error("Raw UI text found outside localization:");
  console.error(rawUiIssues.join("\n"));
  process.exit(1);
}

console.log(`i18n parity OK (${ruKeys.size} keys)`);
