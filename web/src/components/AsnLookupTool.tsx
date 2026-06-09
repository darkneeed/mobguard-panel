import React, { useState } from "react";
import { Search, RotateCcw, AlertCircle, Check, Loader2 } from "lucide-react";
import { settingsApi } from "../features/settings/api/client";
import { AsnLookupResponse } from "../api/client";
import { RulesDraft } from "../rulesMeta";


type AsnLookupToolProps = {
  draft: RulesDraft;
  onAddAsn: (listKey: string, asn: number) => void;
};

export function AsnLookupTool({ draft, onAddAsn }: AsnLookupToolProps) {
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<AsnLookupResponse | null>(null);

  const isAsnInput = (val: string) => {
    const clean = val.trim().toUpperCase();
    return /^\d+$/.test(clean) || /^AS\d+$/.test(clean);
  };

  const parseAsnNumber = (val: string) => {
    const clean = val.trim().toUpperCase();
    if (/^AS\d+$/.test(clean)) {
      return parseInt(clean.substring(2), 10);
    }
    return parseInt(clean, 10);
  };

  const handleLookup = async (force: boolean = false) => {
    const cleanQuery = query.trim();
    if (!cleanQuery) return;

    setError("");
    setLoading(true);

    if (isAsnInput(cleanQuery)) {
      const asnNum = parseAsnNumber(cleanQuery);
      setResult({
        ip: `AS${asnNum}`,
        asn: asnNum,
        isp: "Прямой ввод ASN",
        country: null,
        is_mobile: null,
        network_type: "unknown",
        sources_count: 0,
        in_lists: {
          pure_mobile_asns: (draft.pure_mobile_asns || []).map(Number).includes(asnNum),
          pure_home_asns: (draft.pure_home_asns || []).map(Number).includes(asnNum),
          mixed_asns: (draft.mixed_asns || []).map(Number).includes(asnNum),
          exclude_isp_keywords: false
        },
        cached: false,
        cached_at: null
      });
      setLoading(false);
      return;
    }

    try {
      const response = await settingsApi.asnLookup(cleanQuery, force);
      // Sync list check with the live draft rather than backend config
      if (response.asn) {
        const asnNum = Number(response.asn);
        response.in_lists = {
          pure_mobile_asns: (draft.pure_mobile_asns || []).map(Number).includes(asnNum),
          pure_home_asns: (draft.pure_home_asns || []).map(Number).includes(asnNum),
          mixed_asns: (draft.mixed_asns || []).map(Number).includes(asnNum),
          exclude_isp_keywords: response.in_lists?.exclude_isp_keywords ?? false
        };
      }
      setResult(response);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось выполнить поиск ASN");
      setResult(null);
    } finally {
      setLoading(false);
    }
  };

  const handleAdd = (listKey: string) => {
    if (!result || !result.asn) return;
    onAddAsn(listKey, result.asn);
    
    // Update local results view immediately
    setResult(prev => {
      if (!prev) return null;
      return {
        ...prev,
        in_lists: {
          ...prev.in_lists,
          [listKey]: true
        }
      };
    });
  };

  const getNetworkTypeLabel = (type: "mobile" | "home" | "datacenter" | "unknown") => {
    switch (type) {
      case "mobile":
        return "📱 Mobile";
      case "home":
        return "🏠 Home";
      case "datacenter":
        return "🌐 Datacenter";
      default:
        return "❓ Unknown";
    }
  };

  const activeInLists = result?.in_lists 
    ? Object.keys(result.in_lists).filter(key => result.in_lists[key])
    : [];

  return (
    <div className="asn-lookup-tool" style={{ marginBottom: "1.5rem", borderBottom: "1px solid var(--line)", paddingBottom: "1.5rem" }}>
      <h3 style={{ fontSize: "1rem", marginBottom: "0.5rem" }}>Быстрый поиск ASN</h3>
      <p className="muted" style={{ fontSize: "0.85rem", marginBottom: "1rem" }}>
        Введите IP-адрес для получения данных ASN через консенсус-запрос (5 сервисов) или введите ASN напрямую.
      </p>

      <div style={{ display: "flex", gap: "0.5rem", alignItems: "center", marginBottom: "1rem" }}>
        <div style={{ position: "relative", flex: 1 }}>
          <input
            type="text"
            placeholder="Введите IP-адрес или ASN (например, 8.8.8.8 или AS13335)"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleLookup(false)}
            style={{ width: "100%", paddingLeft: "2.2rem" }}
          />
          <Search size={16} style={{ position: "absolute", left: "0.8rem", top: "50%", transform: "translateY(-50%)", color: "var(--muted)" }} />
        </div>
        <button onClick={() => handleLookup(false)} disabled={loading} style={{ display: "flex", alignItems: "center", gap: "0.3rem" }}>
          {loading ? <Loader2 size={16} className="spinner" /> : <Search size={16} />}
          Найти
        </button>
        <button className="ghost" onClick={() => handleLookup(true)} disabled={loading || isAsnInput(query)} title="Сбросить кеш и обновить">
          <RotateCcw size={16} />
        </button>
      </div>

      {error && (
        <div className="error-box" style={{ display: "flex", alignItems: "center", gap: "0.5rem", padding: "0.75rem", marginBottom: "1rem" }}>
          <AlertCircle size={16} />
          <span>{error}</span>
        </div>
      )}

      {result && (
        <div style={{
          border: "1px solid var(--line)",
          borderRadius: "8px",
          background: "var(--surface-hover, rgba(255,255,255,0.01))",
          padding: "1rem",
          animation: "fadeIn 0.2s ease-out"
        }}>
          {/* Header row */}
          <div style={{ display: "flex", flexWrap: "wrap", justifyContent: "space-between", gap: "1rem", borderBottom: "1px solid var(--line)", paddingBottom: "0.75rem", marginBottom: "0.75rem" }}>
            <div>
              <strong style={{ fontSize: "1.1rem", color: "var(--text)" }}>{result.ip}</strong>
              <div style={{ fontSize: "0.85rem", color: "var(--muted)" }}>
                {result.isp ? `${result.isp}` : "Неизвестный провайдер"} 
                {result.country ? ` · ${result.country}` : ""}
              </div>
            </div>
            {result.asn && (
              <div style={{ textAlign: "right" }}>
                <span className="tag" style={{ fontSize: "0.9rem", fontWeight: "bold" }}>AS{result.asn}</span>
                {result.cached && (
                  <div style={{ fontSize: "0.75rem", color: "var(--muted)", marginTop: "0.2rem" }}>
                    Из кеша
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Details grid */}
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))", gap: "1rem", marginBottom: "1rem" }}>
            <div>
              <span style={{ fontSize: "0.75rem", color: "var(--muted)", display: "block", marginBottom: "0.25rem" }}>Тип сети:</span>
              <strong>{getNetworkTypeLabel(result.network_type)}</strong>
            </div>
            <div>
              <span style={{ fontSize: "0.75rem", color: "var(--muted)", display: "block", marginBottom: "0.25rem" }}>Мобильный флаг:</span>
              <strong>
                {result.is_mobile === true ? "✅ Да" : (result.is_mobile === false ? "❌ Нет" : "❓ Неизвестно")}
              </strong>
            </div>
            <div>
              <span style={{ fontSize: "0.75rem", color: "var(--muted)", display: "block", marginBottom: "0.25rem" }}>Источников:</span>
              <strong>{result.sources_count}/5</strong>
            </div>
            <div>
              <span style={{ fontSize: "0.75rem", color: "var(--muted)", display: "block", marginBottom: "0.25rem" }}>Текущий статус:</span>
              <strong style={{ fontSize: "0.85rem" }}>
                {activeInLists.length > 0 ? (
                  <span style={{ color: "var(--accent)" }}>В списках: {activeInLists.join(", ")}</span>
                ) : (
                  <span style={{ color: "var(--muted)" }}>Не в списках</span>
                )}
              </strong>
            </div>
          </div>

          {/* Add buttons */}
          {result.asn && (
            <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap", borderTop: "1px solid var(--line)", paddingTop: "0.75rem" }}>
              <button
                className="button secondary"
                onClick={() => handleAdd("pure_mobile_asns")}
                disabled={result.in_lists.pure_mobile_asns}
                style={{ display: "inline-flex", alignItems: "center", gap: "0.3rem" }}
              >
                {result.in_lists.pure_mobile_asns ? <Check size={14} /> : "+"} Pure Mobile
              </button>
              <button
                className="button secondary"
                onClick={() => handleAdd("pure_home_asns")}
                disabled={result.in_lists.pure_home_asns}
                style={{ display: "inline-flex", alignItems: "center", gap: "0.3rem" }}
              >
                {result.in_lists.pure_home_asns ? <Check size={14} /> : "+"} Pure Home
              </button>
              <button
                className="button secondary"
                onClick={() => handleAdd("mixed_asns")}
                disabled={result.in_lists.mixed_asns}
                style={{ display: "inline-flex", alignItems: "center", gap: "0.3rem" }}
              >
                {result.in_lists.mixed_asns ? <Check size={14} /> : "+"} Mixed ASNs
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
